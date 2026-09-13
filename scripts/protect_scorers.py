import json, os

PATH='data/report.json'
BASELINE=os.environ.get('REPORT_BASELINE','/tmp/report-before-update.json')

with open(PATH,'r',encoding='utf-8') as f:
    current=json.load(f)
try:
    with open(BASELINE,'r',encoding='utf-8') as f:
        baseline=json.load(f)
except Exception:
    baseline={}


def as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clean_name(value):
    return ' '.join(str(value or '').split()).strip()


def scorer_map(obj):
    result={}
    labels={}
    for item in obj.get('scorers',[]) if isinstance(obj,dict) else []:
        if not isinstance(item,dict):
            continue
        name=clean_name(item.get('name'))
        goals=max(0,as_int(item.get('goals')))
        if not name or goals<=0:
            continue
        key=name.casefold()
        # Saison-Summen werden nicht addiert, sondern der höchste bestätigte Stand bewahrt.
        result[key]=max(result.get(key,0),goals)
        labels.setdefault(key,name)
    return result,labels


def merge_scorers(old_obj,new_obj):
    old,old_labels=scorer_map(old_obj)
    new,new_labels=scorer_map(new_obj)
    merged={}
    labels={**old_labels,**new_labels}
    for key in set(old)|set(new):
        merged[key]=max(old.get(key,0),new.get(key,0))
    rows=[{'name':labels.get(k,k),'goals':v} for k,v in merged.items() if v>0]
    rows.sort(key=lambda x:(-x['goals'],x['name'].casefold()))
    return rows


def checked_match_key(item):
    return (str(item.get('date','')),clean_name(item.get('opponent')).casefold())


def merge_checked_matches(old_obj,new_obj):
    merged={}
    for obj in (old_obj,new_obj):
        audit=obj.get('scorer_audit') if isinstance(obj,dict) and isinstance(obj.get('scorer_audit'),dict) else {}
        for item in audit.get('checked_matches',[]) if isinstance(audit.get('checked_matches'),list) else []:
            if isinstance(item,dict) and item.get('date') and item.get('opponent'):
                merged[checked_match_key(item)]=item
    return sorted(merged.values(),key=lambda x:str(x.get('date','')))

expected=max(0,as_int((current.get('eschenbach') or {}).get('goals_for')))
rows=merge_scorers(baseline,current)
base_own=max(0,as_int(baseline.get('own_goals')))
cur_own=max(0,as_int(current.get('own_goals')))
own_goals=max(base_own,cur_own)
player_goals=sum(as_int(x.get('goals')) for x in rows)
accounted=player_goals+own_goals

# Wenn eine neue Recherche offensichtlich über die offizielle Torzahl hinausschiesst,
# bleibt der letzte bestätigte Stand erhalten statt eine falsche Liste zu publizieren.
if expected and accounted>expected:
    base_rows,_=scorer_map(baseline)
    base_player=sum(base_rows.values())
    base_total=base_player+base_own
    if base_total and base_total<=expected:
        rows=[{'name':name,'goals':base_rows[key]} for key,name in (scorer_map(baseline)[1]).items() if key in base_rows]
        rows.sort(key=lambda x:(-x['goals'],x['name'].casefold()))
        own_goals=base_own
        player_goals=sum(as_int(x.get('goals')) for x in rows)
        accounted=player_goals+own_goals

current['scorers']=rows
current['own_goals']=own_goals
complete=bool(expected and accounted==expected)
audit=current.get('scorer_audit') if isinstance(current.get('scorer_audit'),dict) else {}
audit['complete']=complete
audit['expected_goals']=expected
audit['player_goals']=player_goals
audit['own_goals']=own_goals
audit['accounted_goals']=accounted
audit['checked_matches']=merge_checked_matches(baseline,current)
current['scorer_audit']=audit

if complete:
    own_text=''
    if own_goals==1:
        own_text=' plus 1 Eigentor zugunsten von Eschenbach'
    elif own_goals>1:
        own_text=f' plus {own_goals} Eigentore zugunsten von Eschenbach'
    current['scorer_note']=f'{player_goals} Spielertore{own_text} ergeben {accounted} Saisontore.'
elif rows or own_goals:
    missing=max(0,expected-accounted)
    current['scorer_note']=f'Bestätigt zugeordnet: {accounted} von {expected} Toren; noch offen: {missing}. Die bestätigten Torschützen bleiben sichtbar.'
else:
    current['scorer_note']='Noch keine Torschützen eindeutig zugeordnet.'

with open(PATH,'w',encoding='utf-8') as f:
    json.dump(current,f,ensure_ascii=False,indent=2)
    f.write('\n')

print(f'Torschützen geschützt: {accounted}/{expected} Tore, {len(rows)} Spieler, vollständig={complete}.')
