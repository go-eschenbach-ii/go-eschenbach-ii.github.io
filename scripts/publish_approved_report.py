"""Publish only an admin-approved Supabase draft using GitHub Actions' scoped write token."""
import json
import os
import pathlib
import subprocess
import urllib.request
import urllib.error

API = 'https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/report-draft'
REQUEST_ID = os.environ.get('REQUEST_ID', '').strip()
PUBLISH_TOKEN = os.environ.get('APPROVAL_TOKEN', '').strip()
if not REQUEST_ID or not PUBLISH_TOKEN:
    raise SystemExit('Missing approved workflow credentials')

def api(action):
    data=json.dumps({'action':action,'request_id':REQUEST_ID,'approval_token':PUBLISH_TOKEN}).encode('utf-8')
    r=urllib.request.Request(API,data=data,method='POST',
        headers={'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(r,timeout=35) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        raise RuntimeError(f'Approved API action {action} failed with HTTP {err.code}') from err

def run(*args):
    subprocess.run(args,check=True)

def publish():
    draft=api('fetch_approved')
    if not draft.get('approved') or not draft.get('report') or not draft.get('news'):
        raise RuntimeError('Server rejected approved draft')
    report=draft['report']
    news=draft['news']
    if not isinstance(report.get('recent_results'),list) or not isinstance(report.get('standings'),list):
        raise RuntimeError('Invalid report')
    if not isinstance(news.get('items'),list):
        raise RuntimeError('Invalid news')
    run('git','fetch','origin','main')
    baseline=json.loads(subprocess.check_output(['git','show','origin/main:data/report.json'],text=True))
    if str(baseline.get('generated_at'))!=str(draft.get('base_generated_at')):
        raise RuntimeError('Live report changed; approval must be rechecked')
    if draft.get('review_required') is False:
        for field in ('title','lead','review','current_situation','outlook','heart_cycle_key'):
            if report.get(field)!=baseline.get(field):
                raise RuntimeError('Data-only update would change '+field)
    run('git','reset','--hard','origin/main')
    for name,obj in [('report',report),('update-news',news)]:
        path=pathlib.Path('data/report.json' if name=='report' else 'data/update-news.json')
        path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    diff=subprocess.run(['git','diff','--quiet','--','data/report.json','data/update-news.json'])
    if diff.returncode==0:
        print('Approved report already equals live files')
    elif diff.returncode==1:
        run('git','config','user.name','github-actions[bot]')
        run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
        run('git','add','data/report.json','data/update-news.json')
        run('git','commit','-m','Freigegebenes Eschenbach-App-Update veröffentlichen')
        run('git','push','origin','HEAD:main')
    else:
        raise RuntimeError('Git status could not be verified')
    result=api('complete_approved')
    if not result.get('published'):
        raise RuntimeError('Approval callback not confirmed')
    print('Admin-approved update published successfully')

if __name__=='__main__':
    try:
        publish()
    except Exception:
        # An uncommitted or failed publish returns to review; never falsely
        # mark a failed publication successful.
        try:
            api('fail_approved')
        except Exception as error:
            print('Could not reset approval for retry:',str(error))
        raise
