"""Hold newly inferred match scores if the official table does not corroborate them.

The IFV mirror often publishes fixtures for a past date before a verified
result. AI guessing e.g. Hochdorf–Nebikon 10:0 must never be published as fact.
Only newly introduced results are checked; already published confirmed results
and manually finished admin live-ticker scores remain untouched.
"""
import json
import os
from datetime import datetime
from pathlib import Path

path=Path('data/report.json')
baseline_path=Path(os.environ.get('REPORT_BASELINE','/tmp/report-before-update.json'))
report=json.loads(path.read_text(encoding='utf-8'))
baseline=json.loads(baseline_path.read_text(encoding='utf-8'))

def key(m):
    return (str(m.get('date','')).strip(),
        str(m.get('home','')).strip().casefold(),
        str(m.get('away','')).strip().casefold())

previous={key(m) for m in baseline.get('recent_results',[])
          if isinstance(m,dict) and m.get('home_goals') is not None
             and m.get('away_goals') is not None}
old_table={str(r.get('team','')).strip():r
           for r in baseline.get('standings',[]) if isinstance(r,dict)}
new_table={str(r.get('team','')).strip():r
           for r in report.get('standings',[]) if isinstance(r,dict)}
confirmed={key(m) for m in report.get('confirmed_live_scores',[])
    if isinstance(m,dict) and m.get('status')=='finished'}
results=[]
held=[]
for m in report.get('recent_results',[]):
    if not isinstance(m,dict):
        continue
    k=key(m)
    if k in previous or k in confirmed or (
        m.get('verified_by')=='admin_liveticker' and m.get('status')=='finished'
    ):
        results.append(m)
        continue
    home,away=str(m.get('home','')).strip(),str(m.get('away','')).strip()
    if home not in old_table or home not in new_table or away not in old_table or away not in new_table:
        results.append(m)
        continue
    try:
        old_h=int(old_table[home]['played']);old_a=int(old_table[away]['played'])
        new_h=int(new_table[home]['played']);new_a=int(new_table[away]['played'])
    except (TypeError,ValueError,KeyError):
        results.append(m)
        continue
    if new_h>old_h and new_a>old_a:
        results.append(m)
        continue
    print('Unbestätigtes neues Resultat zurückgehalten:',
          m.get('date'),home,away,m.get('home_goals'),m.get('away_goals'),
          'Rangliste',old_h,new_h,old_a,new_a)
    held.append(m)
if not held:
    print('Keine unbestätigten neuen Resultate gefunden.')
    raise SystemExit(0)

report['recent_results']=results
fixtures=list(report.get('upcoming_matches',[]))
fixture_keys={key(m) for m in fixtures if isinstance(m,dict)}
for m in held:
    if key(m) not in fixture_keys:
        fixtures.append({'date':m['date'],'time':m.get('time',''),
            'home':m['home'],'away':m['away'],
            'note':'Resultat noch nicht offiziell bestätigt.'})
        fixture_keys.add(key(m))
def sort_key(m):
    try:
        return datetime.strptime(str(m.get('date',''))+' '+str(m.get('time','') or '00:00'),
                                 '%d.%m.%Y %H:%M')
    except Exception:
        return datetime.max
report['upcoming_matches']=sorted(fixtures,key=sort_key)
report['held_unverified_results']=[{
    'date':m.get('date'),'home':m.get('home'),'away':m.get('away')
} for m in held]
path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
