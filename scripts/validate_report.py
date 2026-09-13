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
player_goals=sum(max(0,as_int(s.get('goals'))) for s in scorers if isinstance(s,dict))
own_goals=max(0,as_int(data.get('own_goals')))
accounted=player_goals+own_goals

audit=data.get('scorer_audit') if isinstance(data.get('scorer_audit'),dict) else {}
audit['expected_goals']=expected
audit['player_goals']=player_goals
audit['own_goals']=own_goals
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

if changed:
    with open(PATH,'w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
        f.write('\n')
    print(f'Bericht validiert: Torschützen bleiben sichtbar ({accounted}/{expected}).')
else:
    print('Bericht validiert: keine Widersprüche gefunden.')
