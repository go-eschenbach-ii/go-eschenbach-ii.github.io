"""Read authoritative group-4 standings from an IFV club mirror.

The direct matchcenter currently denies requests from GitHub Actions. The FC Schötz
site embeds the same official Football.ch result-and-rankings table.
Only a complete, internally consistent 10-team table may replace report data.
"""
import html
import os
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPORT=Path('data/report.json')
URLS=[
    # Both club pages contain the very same IFV/football.ch group table.
    # The direct IFV host frequently returns 403 to GitHub Actions.
    'https://www.fcschoetz.ch/?lng=1&tab=3410&v=376',
    'https://www.fcschoetz.ch/de/club/teams/team/resultate-und-rangliste/%26v%3D376%26t%3D31274',
]


def fetch_text(url):
    req=urllib.request.Request(url,headers={
        'User-Agent':'Mozilla/5.0',
        'Accept-Language':'de-CH,de;q=0.9'
    })
    with urllib.request.urlopen(req,timeout=25) as response:
        raw=response.read().decode('utf-8','ignore')
    raw=re.sub(r'(?is)<script\b.*?</script>|<style\b.*?</style>',' ',raw)
    return [' '.join(t.split()) for t in html.unescape(re.sub(r'(?s)<[^>]+>','\n',raw)).splitlines() if t.strip()]


def parse(lines,teamset):
    for start in range(max(0,len(lines)-11)):
        # The leading team changes every weekend. Never assume that
        # Eschenbach is first, second, or in any particular position.
        if lines[start]!='1.' or lines[start+1] not in teamset:
            continue
        found=[]
        i=start
        for rank in range(1,11):
            if i+11>=len(lines) or lines[i]!=f'{rank}.':
                break
            team=lines[i+1]
            if team not in teamset:
                break
            v=lines[i+2:i+12]
            if len(v)!=10 or v[6]!=':':
                break
            try:
                played,wins,draws,losses=map(int,v[:4])
                penalty=int(re.sub(r'[^0-9]','',v[4]))
                goals_for=int(v[5])
                goals_against=int(v[7])
                difference=int(v[8])
                points=int(v[9])
            except ValueError:
                break
            if any(q<0 for q in (played,wins,draws,losses,penalty,goals_for,goals_against,points)):
                break
            if played!=wins+draws+losses or points!=3*wins+draws or difference!=goals_for-goals_against:
                break
            found.append({
                'rank':rank,'team':team,'played':played,'wins':wins,
                'draws':draws,'losses':losses,'penalty_points':penalty,
                'goals_for':goals_for,'goals_against':goals_against,
                'goal_difference':difference,'points':points,
                'is_eschenbach':team=='FC Eschenbach II'
            })
            i+=12
        if len(found)==10 and {r['team'] for r in found}==teamset:
            return found
    return None


def main():
    report=json.loads(REPORT.read_text(encoding='utf-8'))
    previous=report.get('standings') or []
    teams={x['team'] for x in previous if isinstance(x,dict) and x.get('team')}
    if len(teams)!=10:
        raise RuntimeError('Expected exactly 10 group-4 teams')
    candidates=[]
    failures=[]
    for url in URLS:
        try:
            rows=parse(fetch_text(url),teams)
            if not rows:
                failures.append(f'{url}: no complete, coherent ten-team table')
                continue
            candidates.append((sum(row['played'] for row in rows),rows,url))
        except Exception as e:
            failures.append(f'{url}: {str(e)[:140]}')
    # Prefer the latest match-count snapshot when mirrors refresh at
    # different times. Never replace a newer public IFV table with an older one.
    rows=None
    source=None
    if candidates:
        _,candidate_rows,candidate_source=max(candidates,key=lambda x:x[0])
        old_by_team={r['team']:r for r in previous}
        if all(r['played']>=int(old_by_team[r['team']].get('played',0)) for r in candidate_rows):
            rows,source=candidate_rows,candidate_source
        else:
            failures.append('Official mirror older than current verified standings')
    if rows is None:
        # Fail closed: an AI-calculated table must never replace the IFV.
        baseline_path=Path(os.getenv('REPORT_BASELINE','/tmp/report-before-update.json'))
        if not baseline_path.exists():
            raise RuntimeError('No verified IFV standings and no saved baseline: '+'; '.join(failures))
        baseline=json.loads(baseline_path.read_text(encoding='utf-8'))
        rows=baseline.get('standings',[])
        if (len(rows)!=10 or {r['team'] for r in rows}!=teams
            or baseline.get('standings_sync_status') not in ('verified','last_verified')):
            raise RuntimeError('No trusted IFV standings to preserve: '+'; '.join(failures))
        source=baseline.get('standings_sync_source','official IFV baseline')
        report['standings_sync_status']='last_verified'
        report['standings_sync_note']='Official IFV source currently unavailable or older; last verified table retained.'
        print('IFV momentan nicht frisch abrufbar; letzte offiziell bestätigte Tabelle bleibt erhalten.')
    else:
        report['standings_sync_status']='verified'
        report.pop('standings_sync_note',None)
    report['standings']=rows
    esch=next(r for r in rows if r['is_eschenbach'])
    report.setdefault('eschenbach',{}).update({k:esch[k] for k in (
        'rank','played','wins','draws','losses','penalty_points',
        'goals_for','goals_against','goal_difference','points'
    )})
    report['standings_sync_source']=source
    report['standings_sync_at']=datetime.now(ZoneInfo('Europe/Zurich')).isoformat()
    report['standings_authority']='IFV official source: original positions preserved'
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Verifizierte IFV-Tabelle übernommen: ' + ', '.join(f"{r['rank']}. {r['team']} ({r['points']})" for r in rows))


if __name__=='__main__':
    main()
