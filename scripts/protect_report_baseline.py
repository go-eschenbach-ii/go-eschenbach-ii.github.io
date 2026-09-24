import json, os
from datetime import datetime
from zoneinfo import ZoneInfo

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
    # Strukturierte Tabellen-/Resultatdaten aus dem bestaetigten Stand bewahren,
    # aber redaktionelle Neuerungen des aktuellen Laufs (insbesondere den
    # aus Matchkommentaren erzeugten Rueckblick) niemals zuruecksetzen.
    protected=dict(baseline)
    current_review=str(current.get('review','')).strip()
    if current_review:
        protected['review']=current_review
    print(f'Aeltere Strukturdaten verworfen, aktueller Rueckblick erhalten: neu={cur_q}, bestaetigt={base_q}')
else:
    protected=current
    print(f'Datenstand akzeptiert: neu={cur_q}, bestaetigt={base_q}')

# Bestaetigte Resultate aus Baseline und aktuellem Lauf immer zusammenfuehren.
# Dadurch geht ein neues Resultat auch dann nicht verloren, wenn eine automatisch
# gelesene Rangliste unvollstaendig oder widerspruechlich ist.
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

def as_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def apply_match(rows_by_team, match, direction):
    home=str(match.get('home','')).strip()
    away=str(match.get('away','')).strip()
    hg=as_int(match.get('home_goals'))
    ag=as_int(match.get('away_goals'))
    if home not in rows_by_team or away not in rows_by_team or hg is None or ag is None:
        return False

    for team, gf, ga in ((home,hg,ag),(away,ag,hg)):
        row=rows_by_team[team]
        row['played']=as_int(row.get('played'),0)+direction
        row['goals_for']=as_int(row.get('goals_for'),0)+direction*gf
        row['goals_against']=as_int(row.get('goals_against'),0)+direction*ga
        if gf>ga:
            row['wins']=as_int(row.get('wins'),0)+direction
            row['points']=as_int(row.get('points'),0)+3*direction
        elif gf==ga:
            row['draws']=as_int(row.get('draws'),0)+direction
            row['points']=as_int(row.get('points'),0)+direction
        else:
            row['losses']=as_int(row.get('losses'),0)+direction
        row['goal_difference']=row['goals_for']-row['goals_against']
    return True

# Letzte korrekte Tabelle + seitdem neue/geaenderte Resultate bilden die
# verbindliche Plausibilitaetskontrolle. So kann ein Resultat nie sichtbar sein,
# waehrend Punkte/S-U-N/Tore/Rang noch auf dem alten Stand bleiben.
base_table=complete_standings(baseline)
if base_table and merged:
    base_rows, _ = base_table
    baseline_results={result_key(m):m for m in confirmed_results(baseline)}
    current_results={result_key(m):m for m in protected.get('recent_results',[]) if isinstance(m,dict)}

    changed_keys=set()
    for key in set(baseline_results)|set(current_results):
        old=baseline_results.get(key)
        new=current_results.get(key)
        old_score=None if not old else (as_int(old.get('home_goals')),as_int(old.get('away_goals')))
        new_score=None if not new else (as_int(new.get('home_goals')),as_int(new.get('away_goals')))
        if old_score!=new_score:
            changed_keys.add(key)

    if changed_keys:
        rows_by_team={str(r.get('team','')).strip():dict(r) for r in base_rows}

        # Neuere Strafpunkte duerfen uebernommen werden; die sportlichen Werte
        # werden hingegen deterministisch aus Resultaten fortgeschrieben.
        latest_rows=protected.get('standings',[]) if isinstance(protected.get('standings'),list) else []
        latest_by_team={str(r.get('team','')).strip():r for r in latest_rows if isinstance(r,dict)}
        for team,row in rows_by_team.items():
            newer=latest_by_team.get(team,{})
            pp=as_int(newer.get('penalty_points'))
            if pp is not None and pp>=0:
                row['penalty_points']=pp

        applied=0
        for key in sorted(changed_keys):
            old=baseline_results.get(key)
            new=current_results.get(key)
            if old and apply_match(rows_by_team,old,-1):
                applied+=1
            if new and apply_match(rows_by_team,new,1):
                applied+=1

        valid=True
        for row in rows_by_team.values():
            nums=[as_int(row.get(k)) for k in ('played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points')]
            if any(v is None or v<0 for v in nums):
                valid=False
                break
            if row['played']!=row['wins']+row['draws']+row['losses']:
                valid=False
                break
            if row['points']!=row['wins']*3+row['draws']:
                valid=False
                break
            if row['goal_difference']!=row['goals_for']-row['goals_against']:
                valid=False
                break

        if valid and applied:
            def rank_key(row):
                played=max(1,as_int(row.get('played'),0))
                penalty=max(0,as_int(row.get('penalty_points'),0))
                penalty_ratio=penalty/played
                return (
                    -as_int(row.get('points'),0),
                    penalty_ratio,
                    -as_int(row.get('goal_difference'),0),
                    -as_int(row.get('goals_for'),0),
                    str(row.get('team','')).casefold()
                )

            ranked=sorted(rows_by_team.values(),key=rank_key)
            for idx,row in enumerate(ranked,1):
                row['rank']=idx
                row['is_eschenbach']=str(row.get('team','')).strip()=='FC Eschenbach II'

            protected['standings']=ranked
            esch=next((r for r in ranked if r.get('is_eschenbach')),None)
            if esch:
                target=protected.setdefault('eschenbach',{})
                for key in ('rank','played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points'):
                    target[key]=esch[key]
            print(f'Rangliste aus bestaetigtem Stand und {len(changed_keys)} neuem/geaendertem Resultat(en) abgeglichen.')

# Rangfolge immer abschliessend nach der IFV-Regel normalisieren:
# Punkte -> tieferer Strafpunktquotient -> Tordifferenz -> erzielte Tore.
final_table=complete_standings(protected)
if final_table:
    final_rows,_=final_table
    def final_rank_key(row):
        played=max(1,as_int(row.get('played'),0))
        penalty=max(0,as_int(row.get('penalty_points'),0))
        return (
            -as_int(row.get('points'),0),
            penalty/played,
            -as_int(row.get('goal_difference'),0),
            -as_int(row.get('goals_for'),0),
            str(row.get('team','')).casefold()
        )

    ranked=sorted((dict(r) for r in final_rows),key=final_rank_key)
    for idx,row in enumerate(ranked,1):
        row['rank']=idx
        row['is_eschenbach']=str(row.get('team','')).strip()=='FC Eschenbach II'
    protected['standings']=ranked
    esch=next((r for r in ranked if r.get('is_eschenbach')),None)
    if esch:
        target=protected.setdefault('eschenbach',{})
        for key in ('rank','played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points'):
            target[key]=esch[key]

# Ein erfolgreicher Update-Lauf soll in der App als neuer Lauf erkennbar sein,
# auch wenn wegen einer IFV-Sperre bewusst der letzte bestaetigte Strukturstand erhalten blieb.
protected['generated_at']=datetime.now(ZoneInfo('Europe/Zurich')).strftime('%d.%m.%Y %H:%M:%S')

with open(PATH,'w',encoding='utf-8') as f:
    json.dump(protected,f,ensure_ascii=False,indent=2)
    f.write('\n')

print('Rueckfallsicherung abgeschlossen.')
