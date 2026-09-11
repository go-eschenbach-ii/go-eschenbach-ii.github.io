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

if expected and player_goals+own_goals!=expected:
    audit=data.get('scorer_audit') if isinstance(data.get('scorer_audit'),dict) else {}
    audit['complete']=False
    audit['expected_goals']=expected
    audit['player_goals']=player_goals
    audit['own_goals']=own_goals
    audit['accounted_goals']=player_goals+own_goals
    data['scorer_audit']=audit
    data['scorers']=[]
    data['own_goals']=0
    data['scorer_note']='Torschützen werden erst wieder angezeigt, wenn die Kontrollsumme eindeutig stimmt.'
    changed=True

if changed:
    with open(PATH,'w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
        f.write('\n')
    print('Bericht validiert: widersprüchliche Torschützen-Daten ausgeblendet.')
else:
    print('Bericht validiert: keine Widersprüche gefunden.')
