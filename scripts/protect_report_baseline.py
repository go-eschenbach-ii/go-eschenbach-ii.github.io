import json, os
from datetime import datetime

PATH='data/report.json'
BASELINE=os.environ.get('REPORT_BASELINE','/tmp/report-before-update.json')

with open(PATH,'r',encoding='utf-8') as f:
    current=json.load(f)
try:
    with open(BASELINE,'r',encoding='utf-8') as f:
        baseline=json.load(f)
except Exception:
    baseline={}


def dmy(v):
    try:
        return datetime.strptime(str(v).strip(),'%d.%m.%Y').date()
    except Exception:
        return None


def result_key(m):
    return (
        str(m.get('date','')),
        str(m.get('home','')).strip().casefold(),
        str(m.get('away','')).strip().casefold(),
    )


def confirmed_results(obj):
    out=[]
    for m in obj.get('recent_results',[]) if isinstance(obj,dict) else []:
        if not isinstance(m,dict):
            continue
        if dmy(m.get('date')) is None:
            continue
        try:
            hg=int(m.get('home_goals'))
            ag=int(m.get('away_goals'))
        except Exception:
            continue
        if hg < 0 or ag < 0 or not m.get('home') or not m.get('away'):
            continue
        out.append(m)
    return out


def complete_standings(obj):
    rows=obj.get('standings',[]) if isinstance(obj,dict) else []
    if not isinstance(rows,list) or len(rows)<8:
        return None
    teams=[]
    total=0
    for r in rows:
        if not isinstance(r,dict) or not r.get('team'):
            return None
        try:
            played=int(r.get('played'))
            wins=int(r.get('wins'))
            draws=int(r.get('draws'))
            losses=int(r.get('losses'))
        except Exception:
            return None
        if played != wins + draws + losses or played < 0:
            return None
        teams.append(str(r.get('team')).strip())
        total += played
    if len(set(teams)) != len(rows):
        return None
    return rows,total


def freshness(obj):
    table=complete_standings(obj)
    played=table[1] if table else -1
    results=confirmed_results(obj)
    latest=max((dmy(m.get('date')).toordinal() for m in results),default=-1)
    return (played,latest,len(results))

base_q=freshness(baseline)
cur_q=freshness(current)

if baseline and base_q > cur_q:
    # Der neue Lauf ist objektiv älter/unvollständiger als der bereits bestätigte Stand.
    # In diesem Fall wird der komplette konsistente Ausgangsstand bewahrt.
    protected=baseline
    print(f'Aelteren Datenstand verworfen: neu={cur_q}, bestaetigt={base_q}')
else:
    protected=current
    # Auch bei einem neueren Stand dürfen bereits bestätigte Resultate nicht verschwinden.
    merged={}
    for source in (confirmed_results(baseline),confirmed_results(current)):
        for m in source:
            merged[result_key(m)]=m
    if merged:
        protected['recent_results']=sorted(
            merged.values(),
            key=lambda m:(dmy(m.get('date')) or datetime.min.date(),str(m.get('time','')),str(m.get('home',''))),
            reverse=True
        )
    print(f'Datenstand akzeptiert: neu={cur_q}, bestaetigt={base_q}')

# Ein erfolgreicher Update-Lauf soll in der App als neuer Lauf erkennbar sein,
# auch wenn wegen einer IFV-Sperre bewusst der letzte bestaetigte Stand erhalten blieb.
protected['generated_at']=datetime.now().strftime('%d.%m.%Y %H:%M:%S')

with open(PATH,'w',encoding='utf-8') as f:
    json.dump(protected,f,ensure_ascii=False,indent=2)
    f.write('\n')

print('Rueckfallsicherung abgeschlossen.')
