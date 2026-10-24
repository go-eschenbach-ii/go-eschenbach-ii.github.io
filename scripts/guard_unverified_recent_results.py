"""Hold newly inferred match scores if the official table does not corroborate them.

The IFV mirror sometimes lags behind official match results. A score explicitly
verified in the official IFV match center has priority over stale standings.
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
# Independently verified match-center results have priority even if the
# separately cached standings page is delayed.
verified_file=Path('data/ifv-verified-results.json')
if verified_file.exists():
    verified_doc=json.loads(verified_file.read_text(encoding='utf-8'))
    official_results={
        key(m):(int(m['home_goals']),int(m['away_goals']))
        for m in verified_doc.get('matches',[]) if isinstance(m,dict)
    }
else:
    official_results={}

results=[]
held=[]
for m in report.get('recent_results',[]):
    if not isinstance(m,dict):
        continue
    k=key(m)
    # Published results are retained, but a newer explicit IFV result
    # supersedes any stale or inferred score for the same fixture.
    official=official_results.get(k)
    if official is not None:
        if (m.get('home_goals'),m.get('away_goals')) != official:
            print('IFV result overrides report estimate:',k,official)
            m={**m,'home_goals':official[0],'away_goals':official[1],
               'verified_by':'ifv_official'}
        results.append(m)
        continue
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
    # The standings alone do not prove an individual score. Only the
    # IFV-backed result list or an explicit finished admin ticker does.
    # In particular, a 3:0 forfait must never be invented from the table.
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
