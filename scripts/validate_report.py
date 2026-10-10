import json

PATH='data/report.json'
with open(PATH,'r',encoding='utf-8') as f:
    data=json.load(f)

changed=False

def as_int(value, default=0):
    try:
        return int(value)
    except (TypeError,ValueError):
        return default

expected=max(0,as_int((data.get('eschenbach') or {}).get('goals_for')))
scorers=data.get('scorers') if isinstance(data.get('scorers'),list) else []
clean_scorers=[]
legacy_forfait=0
for s in scorers:
    if not isinstance(s,dict):
        continue
    name=' '.join(str(s.get('name','')).split()).strip()
    goals=max(0,as_int(s.get('goals')))
    if not name or goals<=0:
        continue
    if 'forfait' in name.casefold():
        legacy_forfait=max(legacy_forfait,goals)
        changed=True
        continue
    clean_scorers.append({'name':name,'goals':goals})

if clean_scorers!=scorers:
    data['scorers']=clean_scorers

player_goals=sum(max(0,as_int(s.get('goals'))) for s in clean_scorers)
own_goals=max(0,as_int(data.get('own_goals')))
audit=data.get('scorer_audit') if isinstance(data.get('scorer_audit'),dict) else {}
forfait_goals=max(
    legacy_forfait,
    max(0,as_int(data.get('forfait_goals'))),
    max(0,as_int(audit.get('forfait_goals')))
)
data['forfait_goals']=forfait_goals
accounted=player_goals+own_goals+forfait_goals

audit['expected_goals']=expected
audit['player_goals']=player_goals
audit['own_goals']=own_goals
audit['forfait_goals']=forfait_goals
audit['accounted_goals']=accounted

if expected and accounted==expected:
    if audit.get('complete') is not True:
        changed=True
    audit['complete']=True
elif expected and accounted<expected:
    # Ein unvollständiger Stand darf bestätigte Torschützen nicht mehr ausblenden.
    audit['complete']=False
    missing=expected-accounted
    data['scorer_note']=f'Bestätigt zugeordnet: {accounted} von {expected} Toren; noch offen: {missing}. Die bestätigten Torschützen bleiben sichtbar.'
    changed=True
elif expected and accounted>expected:
    # Dieser Fall sollte bereits durch protect_scorers.py abgefangen sein.
    # Zur Sicherheit markieren wir den Stand als widersprüchlich, löschen aber keine bestätigten Namen.
    audit['complete']=False
    data['scorer_note']=f'Torschützenstand wird geprüft: {accounted} Zuordnungen bei {expected} Saisontoren.'
    changed=True

data['scorer_audit']=audit

# Ein Spiel mit bestätigtem Resultat darf nie gleichzeitig als kommendes Spiel erscheinen.
def fixture_key(match):
    return (
        str(match.get('date','')).strip(),
        str(match.get('home','')).strip().casefold(),
        str(match.get('away','')).strip().casefold(),
    )

completed_keys=set()
for match in data.get('recent_results',[]) if isinstance(data.get('recent_results'),list) else []:
    if not isinstance(match,dict):
        continue
    if match.get('home_goals') is None or match.get('away_goals') is None:
        continue
    if match.get('date') and match.get('home') and match.get('away'):
        completed_keys.add(fixture_key(match))

upcoming=data.get('upcoming_matches') if isinstance(data.get('upcoming_matches'),list) else []
clean_upcoming=[
    match for match in upcoming
    if isinstance(match,dict) and fixture_key(match) not in completed_keys
]
if clean_upcoming!=upcoming:
    data['upcoming_matches']=clean_upcoming
    changed=True

# Letzte Sicherung für die Tabelle: Rangierung gemäss IFV-Regel.
rows=data.get('standings') if isinstance(data.get('standings'),list) else []
valid_rows=[]
for r in rows:
    if not isinstance(r,dict) or not r.get('team'):
        valid_rows=[]
        break
    try:
        row=dict(r)
        for key in ('played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points'):
            row[key]=int(row.get(key))
    except Exception:
        valid_rows=[]
        break
    if row['played']!=row['wins']+row['draws']+row['losses']:
        valid_rows=[]
        break
    if row['points']!=row['wins']*3+row['draws']:
        valid_rows=[]
        break
    if row['goal_difference']!=row['goals_for']-row['goals_against']:
        valid_rows=[]
        break
    valid_rows.append(row)

if valid_rows and len({r['team'] for r in valid_rows})==len(valid_rows):
    def table_rank_key(row):
        played=max(1,row['played'])
        return (
            -row['points'],
            max(0,row['penalty_points'])/played,
            -row['goal_difference'],
            -row['goals_for'],
            str(row['team']).casefold()
        )
    ranked=sorted(valid_rows,key=table_rank_key)
    for idx,row in enumerate(ranked,1):
        row['rank']=idx
        row['is_eschenbach']=str(row.get('team','')).strip()=='FC Eschenbach II'
    if ranked!=rows:
        data['standings']=ranked
        changed=True
    esch=next((r for r in ranked if r.get('is_eschenbach')),None)
    if esch:
        target=data.setdefault('eschenbach',{})
        for key in ('rank','played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points'):
            if target.get(key)!=esch[key]:
                target[key]=esch[key]
                changed=True

if changed:
    with open(PATH,'w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
        f.write('\n')
    print(f'Bericht validiert: Torschützen bleiben sichtbar ({accounted}/{expected}).')
else:
    print('Bericht validiert: keine Widersprüche gefunden.')
