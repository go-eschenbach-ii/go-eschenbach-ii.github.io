import json, os, urllib.request

REQUEST_ID=os.environ.get('REQUEST_ID','').strip()
COMMENTS_TOKEN=os.environ.get('COMMENTS_TOKEN','').strip()
OUT=os.environ.get('MATCH_COMMENTS_FILE','/tmp/go-eschenbach-match-comments.json')
API='https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/report-update-request'

comments=[]
if REQUEST_ID and COMMENTS_TOKEN:
    payload=json.dumps({
        'action':'comments_for_update',
        'request_id':REQUEST_ID,
        'comments_token':COMMENTS_TOKEN
    }).encode('utf-8')
    req=urllib.request.Request(API,data=payload,headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            data=json.loads(r.read().decode('utf-8'))
            comments=data.get('comments') or []
    except Exception as exc:
        print('Matchkommentare konnten nicht geladen werden:',exc)

with open(OUT,'w',encoding='utf-8') as f:
    json.dump(comments,f,ensure_ascii=False,indent=2)
    f.write('\n')

print(f'Matchkommentare für Rückblick: {len(comments)}')
