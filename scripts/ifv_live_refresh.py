import json, os, re, urllib.request, http.cookiejar, html as html_lib
from fractions import Fraction
from datetime import datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

PATH='data/report.json'
ALERT_PATH='data/alert.json'
BASELINE=os.environ.get('REPORT_BASELINE','/tmp/report-before-update.json')
API_KEY=os.environ.get('OPENAI_API_KEY','').strip()
IFV_BASE='https://matchcenter.ifv.ch/default.aspx?oid=7&lng=1&s=2027&ln=13040'

if not API_KEY:
    raise SystemExit('OPENAI_API_KEY fehlt.')

with open(PATH,'r',encoding='utf-8') as f:
    data=json.load(f)
try:
    with open(BASELINE,'r',encoding='utf-8') as f:
        baseline=json.load(f)
except Exception:
    baseline={}

now=datetime.now(ZoneInfo('Europe/Zurich'))
today=now.date()
recent_start=today-timedelta(days=7)
future_end=today+timedelta(days=14)

jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def fetch_html(url, referer=None, timeout=45):
    headers={
        'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1',
        'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language':'de-CH,de;q=0.9',
        'Cache-Control':'no-cache',
        'Pragma':'no-cache'
    }
    if referer:
        headers['Referer']=referer
    req=urllib.request.Request(url,headers=headers)
    with opener.open(req,timeout=timeout) as r:
        return r.read().decode('utf-8','ignore')


def to_text(raw):
    raw=re.sub(r'(?is)<script\b.*?</script>|<style\b.*?</style>',' ',raw)
    raw=re.sub(r'(?s)<[^>]+>','\n',raw)
    raw=html_lib.unescape(raw).replace('\xa0',' ')
    return '\n'.join(' '.join(x.split()) for x in raw.splitlines() if x.strip())


def call_json(prompt, timeout=180):
    payload={'model':'gpt-5.6-luna','reasoning':{'effort':'medium'},'input':prompt}
    req=urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization':f'Bearer {API_KEY}','Content-Type':'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req,timeout=timeout) as r:
        obj=json.loads(r.read().decode('utf-8'))
    text=obj.get('output_text','').strip()
    if not text:
        parts=[]
        for item in obj.get('output',[]):
            if not isinstance(item,dict): continue
            for c in item.get('content',[]):
                if isinstance(c,dict) and c.get('type') in ('output_text','text'):
                    parts.append(c.get('text',''))
        text=''.join(parts).strip()
    if text.startswith('```'):
        text=re.sub(r'^```(?:json)?\s*|\s*```$','',text,flags=re.S).strip()
    return json.loads(text)


def dmy(v):
    try:return datetime.strptime(str(v).strip(),'%d.%m.%Y').date()
    except:return None


def n(v):
    try:return int(v)
    except:return None


def mkey(m):
    return (str(m.get('date','')),str(m.get('home','')).strip().casefold(),str(m.get('away','')).strip().casefold())


def parse_ifv_schedule_results(text, teamset):
    """Liest sichtbare Resultate im IFV-Spielplan deterministisch aus."""
    lines=[' '.join(str(x).split()) for x in str(text or '').splitlines() if str(x).strip()]
    canonical={str(t).casefold():str(t) for t in teamset}
    found={}
    current_date=None
    current_time=''
    i=0
    while i<len(lines):
        line=lines[i]
        dm=re.search(r'(\d{2}\.\d{2}\.\d{4})',line)
        if dm:
            current_date=dmy(dm.group(1))
            current_time=''
            i+=1
            continue
        if re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',line):
            current_time=line

        valid_date=bool(current_date and recent_start<=current_date<=today)
        folded=line.casefold()
        hits=[]
        for key,team in canonical.items():
            pos=folded.find(key)
            if pos>=0:
                hits.append((pos,team))
        hits.sort(key=lambda x:x[0])

        if valid_date and len(hits)>=2:
            home=hits[0][1]
            away=hits[1][1]
            away_pos=folded.find(away.casefold(),hits[1][0])
            tail=line[away_pos+len(away):] if away_pos>=0 else ''
            nums=[int(v) for v in re.findall(r'(?<!\d)(\d{1,2})(?!\d)',tail)]
            if len(nums)>=2:
                tm=re.search(r'\b(?:[01]\d|2[0-3]):[0-5]\d\b',line[:hits[0][0]])
                item={'date':current_date.strftime('%d.%m.%Y'),'time':tm.group(0) if tm else current_time,'home':home,'away':away,'home_goals':nums[0],'away_goals':nums[1],'note':''}
                found[mkey(item)]=item

        home=canonical.get(folded)
        if valid_date and home:
            j=i+1
            away=None
            while j<len(lines) and j<=i+4:
                if re.search(r'(\d{2}\.\d{2}\.\d{4})',lines[j]):
                    break
                away=canonical.get(lines[j].casefold())
                if away:
                    break
                j+=1
            if away and away!=home:
                nums=[]
                k=j+1
                while k<len(lines) and k<=j+7:
                    token=lines[k]
                    if re.search(r'(\d{2}\.\d{2}\.\d{4})',token) or canonical.get(token.casefold()):
                        break
                    if token.isdigit() and len(token)<=2:
                        nums.append(int(token))
                        if len(nums)>=2:
                            break
                    k+=1
                if len(nums)>=2:
                    item={'date':current_date.strftime('%d.%m.%Y'),'time':current_time,'home':home,'away':away,'home_goals':nums[0],'away_goals':nums[1],'note':''}
                    found[mkey(item)]=item
        i+=1
    return list(found.values())


def apply_match_delta(rows_by_team, match, direction):
    home=' '.join(str(match.get('home','')).split())
    away=' '.join(str(match.get('away','')).split())
    hg=n(match.get('home_goals')); ag=n(match.get('away_goals'))
    if home not in rows_by_team or away not in rows_by_team or hg is None or ag is None:
        return False
    for team,gf,ga in ((home,hg,ag),(away,ag,hg)):
        row=rows_by_team[team]
        row['played']=n(row.get('played'))+direction
        row['goals_for']=n(row.get('goals_for'))+direction*gf
        row['goals_against']=n(row.get('goals_against'))+direction*ga
        if gf>ga:
            row['wins']=n(row.get('wins'))+direction
            row['points']=n(row.get('points'))+3*direction
        elif gf==ga:
            row['draws']=n(row.get('draws'))+direction
            row['points']=n(row.get('points'))+direction
        else:
            row['losses']=n(row.get('losses'))+direction
        row['goal_difference']=row['goals_for']-row['goals_against']
    return True

def ranking_key(row):
    played=max(1,n(row.get('played')) or 0)
    points=max(0,n(row.get('points')) or 0)
    penalty=max(0,n(row.get('penalty_points')) or 0)
    # IFV-Zwischenrangliste bei unterschiedlicher Spielzahl:
    # zuerst Punkte pro Spiel, danach tieferer Strafpunktquotient.
    points_ratio=Fraction(points,played)
    penalty_ratio=Fraction(penalty,played)
    return (
        -points_ratio,
        penalty_ratio,
        -(n(row.get('goal_difference')) or 0),
        -(n(row.get('goals_for')) or 0),
        str(row.get('team','')).casefold()
    )


def rerank(rows):
    ranked=sorted((dict(r) for r in rows),key=ranking_key)
    for idx,row in enumerate(ranked,1):
        row['rank']=idx
        row['is_eschenbach']=row.get('team')=='FC Eschenbach II'
    return ranked


def parse_ifv_standings_text(text, teamset):
    """Liest die sichtbare IFV-Rangliste deterministisch aus dem Seitentext."""
    canonical={str(t).casefold():str(t) for t in teamset}
    lines=[' '.join(str(x).split()) for x in str(text).splitlines() if str(x).strip()]
    rows=[]
    seen=set()
    for i,line in enumerate(lines):
        team=canonical.get(line.casefold())
        if not team or team in seen or i==0:
            continue
        rank_match=re.fullmatch(r'(\d+)\.',lines[i-1])
        if not rank_match:
            continue
        raw_vals=[]
        for token in lines[i+1:i+18]:
            if token==':':
                continue
            if re.fullmatch(r'\(\d+\)',token) or re.fullmatch(r'[+-]?\d+',token):
                raw_vals.append(token)
                if len(raw_vals)==9:
                    break
        if len(raw_vals)!=9 or not re.fullmatch(r'\(\d+\)',raw_vals[4]):
            continue
        nums=[int(v.strip('()')) for v in raw_vals]
        row={
            'rank':int(rank_match.group(1)),
            'team':team,
            'played':nums[0],
            'wins':nums[1],
            'draws':nums[2],
            'losses':nums[3],
            'penalty_points':nums[4],
            'goals_for':nums[5],
            'goals_against':nums[6],
            'goal_difference':nums[7],
            'points':nums[8],
            'is_eschenbach':team=='FC Eschenbach II'
        }
        rows.append(row)
        seen.add(team)
    return complete_table({'standings':rows},teamset) if len(rows)==len(teamset) else None


def complete_table(obj, teamset):
    rows=obj.get('standings',[]) if isinstance(obj,dict) else []
    if not isinstance(rows,list) or len(rows)!=len(teamset): return None
    clean=[]
    fields=('rank','played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points')
    for r in rows:
        if not isinstance(r,dict): return None
        team=' '.join(str(r.get('team','')).split())
        vals={k:n(r.get(k)) for k in fields}
        if team not in teamset or any(v is None for v in vals.values()): return None
        if vals['played']!=vals['wins']+vals['draws']+vals['losses']: return None
        if vals['points']!=vals['wins']*3+vals['draws']: return None
        if vals['goal_difference']!=vals['goals_for']-vals['goals_against']: return None
        clean.append({'team':team,**vals,'is_eschenbach':team=='FC Eschenbach II'})
    if {r['team'] for r in clean}!=teamset or {r['rank'] for r in clean}!=set(range(1,len(clean)+1)):
        return None
    # IFV-Zwischenrangliste: bei unterschiedlicher Spielzahl zählt zuerst der
    # Punktequotient (Punkte / Spiele), danach der Strafpunktquotient.
    return rerank(clean)


def table_score(rows):
    return sum(int(r.get('played',0) or 0) for r in rows) if rows else -1

teams=[r.get('team') for r in (baseline.get('standings') or data.get('standings') or []) if isinstance(r,dict) and r.get('team')]
teamset=set(teams)
if len(teamset)<8:
    raise SystemExit('Gruppenteams fehlen.')

# Den vom Benutzer genannten offiziellen Einstieg öffnen und alle 5.-Liga-Gruppenlinks lesen.
base_raw=fetch_html(IFV_BASE)
base_text=to_text(base_raw)
links=[]
for href in re.findall(r'href=["\']([^"\']+)["\']',base_raw,re.I):
    href=html_lib.unescape(href)
    if re.search(r'(?:\?|&)a=mrr(?:&|$)',href,re.I):
        u=urljoin(IFV_BASE,href)
        if u not in links: links.append(u)

# Nicht anhand einer fest codierten Gruppen-ID wählen, sondern anhand der tatsächlichen Mannschaften.
result_url=None
result_text=''
for u in links:
    try:
        txt=to_text(fetch_html(u,referer=IFV_BASE))
    except Exception:
        continue
    hits=sum(1 for t in teamset if t and t.casefold() in txt.casefold())
    if hits>=max(8,len(teamset)-2):
        result_url=u
        result_text=txt
        break

if not result_url:
    raise SystemExit('Aktuelle IFV-Seite der Gruppe 4 konnte nicht eindeutig geladen werden.')

schedule_url=re.sub(r'([?&])a=mrr(?=&|$)',r'\1a=msp',result_url,count=1,flags=re.I)
schedule_raw=fetch_html(schedule_url,referer=result_url)
schedule_text=to_text(schedule_raw)

prompt=f'''Extrahiere ausschliesslich die Daten der IFV 5. Liga, Gruppe 4, Saison 2026/27 aus den beiden direkt geladenen offiziellen IFV-Seiten.
Heute: {today.strftime('%d.%m.%Y')}
Gruppenteams: {json.dumps(teams,ensure_ascii=False)}

Regeln:
- Nichts erfinden oder aus Vorwissen ergänzen.
- recent_results: alle Meisterschaftsresultate vom {recent_start.strftime('%d.%m.%Y')} bis heute, aber nur wenn beide Torzahlen sichtbar sind.
- upcoming_matches: alle noch nicht beendeten Meisterschaftsspiele von heute bis {future_end.strftime('%d.%m.%Y')}.
- standings: vollständige aktuelle Rangliste aller Gruppenteams. Strafpunkte sind die Zahl in Klammern. Für die Zwischenrangliste bei unterschiedlicher Spielzahl zuerst den Punktequotienten (Punkte / Spiele) berücksichtigen; bei gleichem Punktequotienten zählt der tiefere Strafpunktquotient (Strafpunkte / Spiele).
- Keine andere Liga, Gruppe, Cup- oder Juniorenspiele.

RESULTATE + RANGLISTE:
{result_text[:110000]}

SPIELPLAN:
{schedule_text[:110000]}

JSON:
{{"recent_results":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"...","home_goals":0,"away_goals":0}}],"upcoming_matches":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"..."}}],"standings":[{{"rank":1,"team":"...","played":0,"wins":0,"draws":0,"losses":0,"penalty_points":0,"goals_for":0,"goals_against":0,"goal_difference":0,"points":0}}]}}'''
fresh=call_json(prompt,timeout=180)

# Zweite offizielle IFV-Quelle: sichtbare Resultate im Spielplan werden
# zusätzlich deterministisch gelesen. Dadurch bleibt ein beendeter Match
# nicht als kommend stehen, wenn die Resultateseite noch verzögert ist.
direct_schedule_results=parse_ifv_schedule_results(schedule_text,teamset)
if direct_schedule_results:
    merged_results={}
    for source in (fresh.get('recent_results',[]),direct_schedule_results):
        if not isinstance(source,list):
            continue
        for m in source:
            if isinstance(m,dict):
                merged_results[mkey(m)]=m
    fresh['recent_results']=list(merged_results.values())
    direct_keys={mkey(m) for m in direct_schedule_results}
    if isinstance(fresh.get('upcoming_matches'),list):
        fresh['upcoming_matches']=[m for m in fresh['upcoming_matches'] if not isinstance(m,dict) or mkey(m) not in direct_keys]
    print(f'{len(direct_schedule_results)} Resultat(e) direkt aus dem IFV-Spielplan gelesen.')

# Die zentrale Liga-Seite ist die bevorzugte Quelle für Rang und Strafpunkte.
# Sie wird ohne Modellinterpretation direkt ausgelesen. Die Gruppen-Unterseite
# dient als zweite offizielle Quelle, falls die zentrale Seite unvollständig ist.
direct_base=parse_ifv_standings_text(base_text,teamset)
direct_result=parse_ifv_standings_text(result_text,teamset)
if direct_base:
    fresh['standings']=direct_base
    print('Rangliste deterministisch aus zentraler IFV-Ligaseite gelesen.')
elif direct_result:
    fresh['standings']=direct_result
    print('Rangliste deterministisch aus IFV-Gruppenseite gelesen.')

# Falls die kombinierte Extraktion bei der Rangliste unvollständig ist, die Tabelle
# separat und mit engerem Auftrag nochmals lesen. So kann ein neues Resultat nicht
# mit einer veralteten Tabelle veröffentlicht werden.
if not complete_table(fresh,teamset):
    table_prompt=f'''Lies ausschliesslich die aktuelle Rangliste der IFV 5. Liga, Gruppe 4, Saison 2026/27 aus dem unten eingefügten offiziellen Seitentext.

Gruppenteams: {json.dumps(teams,ensure_ascii=False)}

Regeln:
- Genau alle Gruppenteams liefern.
- Für jedes Team: Rang, Spiele, Siege, Unentschieden, Niederlagen, Strafpunkte, Tore erzielt, Tore erhalten, Tordifferenz und Punkte.
- Strafpunkte sind die Zahl in Klammern.
- Keine Resultate, keinen Spielplan und keine anderen Gruppen ausgeben.
- Nichts schätzen oder ergänzen.

OFFIZIELLER IFV-TEXT:
{result_text[:110000]}

JSON:
{{"standings":[{{"rank":1,"team":"...","played":0,"wins":0,"draws":0,"losses":0,"penalty_points":0,"goals_for":0,"goals_against":0,"goal_difference":0,"points":0}}]}}'''
    for attempt in range(2):
        try:
            retry=call_json(table_prompt,timeout=140)
            rows=complete_table(retry,teamset)
            if rows:
                fresh['standings']=rows
                print(f'Rangliste im separaten Versuch {attempt+1} vollständig gelesen.')
                break
        except Exception as exc:
            print(f'Separater Ranglistenversuch {attempt+1} fehlgeschlagen:',exc)

# Bestätigte Resultate niemals wieder verlieren. Baseline + bestehender Bericht + Live-Daten zusammenführen.
results={}
for source in (baseline.get('recent_results',[]),data.get('recent_results',[]),fresh.get('recent_results',[])):
    if not isinstance(source,list): continue
    for m in source:
        if not isinstance(m,dict): continue
        d=dmy(m.get('date')); hg=n(m.get('home_goals')); ag=n(m.get('away_goals'))
        home=' '.join(str(m.get('home','')).split()); away=' '.join(str(m.get('away','')).split())
        if not d or d<recent_start or d>today or home not in teamset or away not in teamset: continue
        if hg is None or ag is None or hg<0 or ag<0: continue
        item={'date':d.strftime('%d.%m.%Y'),'time':' '.join(str(m.get('time','')).split()),'home':home,'away':away,'home_goals':hg,'away_goals':ag,'note':str(m.get('note','') or '')}
        results[mkey(item)]=item

data['recent_results']=sorted(results.values(),key=lambda m:(dmy(m['date']),m.get('time',''),m['home']),reverse=True)
result_keys=set(results)

upcoming={}
for m in fresh.get('upcoming_matches',[]) if isinstance(fresh.get('upcoming_matches'),list) else []:
    if not isinstance(m,dict): continue
    d=dmy(m.get('date')); home=' '.join(str(m.get('home','')).split()); away=' '.join(str(m.get('away','')).split())
    if not d or d<today or d>future_end or home not in teamset or away not in teamset: continue
    item={'date':d.strftime('%d.%m.%Y'),'time':' '.join(str(m.get('time','')).split()),'home':home,'away':away,'note':''}
    if mkey(item) not in result_keys: upcoming[mkey(item)]=item
if upcoming:
    data['upcoming_matches']=sorted(upcoming.values(),key=lambda m:(dmy(m['date']),m.get('time',''),m['home']))

# Manuelle Dringlichkeitsmeldung (z.B. Spielabsage) hat Vorrang vor dem
# automatischen IFV-Spielplan, bis sie abläuft.
active_alert=None
try:
    with open(ALERT_PATH,'r',encoding='utf-8') as f:
        candidate=json.load(f)
    if isinstance(candidate,dict) and candidate.get('active') is True:
        until_raw=str(candidate.get('active_until','')).strip()
        from_raw=str(candidate.get('active_from','')).strip()
        until=datetime.fromisoformat(until_raw) if until_raw else None
        starts=datetime.fromisoformat(from_raw) if from_raw else None
        now_aware=now
        if (starts is None or now_aware>=starts.astimezone(now.tzinfo)) and (until is None or now_aware<=until.astimezone(now.tzinfo)):
            active_alert=candidate
except Exception as exc:
    print('Dringlichkeitsmeldung konnte nicht gelesen werden:',exc)

if active_alert and isinstance(active_alert.get('match'),dict):
    cm=active_alert['match']
    cancelled_key=(str(cm.get('date','')),str(cm.get('home','')).strip().casefold(),str(cm.get('away','')).strip().casefold())
    data['upcoming_matches']=[
        m for m in data.get('upcoming_matches',[])
        if mkey(m)!=cancelled_key
    ]

# Von vollständigen Tabellen immer den fortgeschrittensten Stand behalten.
# Bei gleicher Anzahl absolvierter Spiele gewinnt der frischere Kandidat.
candidates=[]
for priority,obj in enumerate((baseline,data,fresh)):
    rows=complete_table(obj,teamset)
    if rows: candidates.append((table_score(rows),priority,rows))
if candidates:
    _,_,best=max(candidates,key=lambda item:(item[0],item[1]))
    data['standings']=best
    er=next((r for r in best if r['team']=='FC Eschenbach II'),None)
    if er:
        data['eschenbach']={**data.get('eschenbach',{}),**{k:er[k] for k in ('rank','played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points')}}

# Falls der Spielplan bereits ein neues Resultat zeigt, die offizielle Rangliste
# aber noch nicht nachgeführt ist, wird die letzte bestätigte Tabelle vor der
# Textredaktion deterministisch um genau diese Resultatänderungen fortgeschrieben.
base_rows=complete_table(baseline,teamset)
if base_rows:
    baseline_results={}
    for m in baseline.get('recent_results',[]) if isinstance(baseline.get('recent_results'),list) else []:
        md=dmy(m.get('date')) if isinstance(m,dict) else None
        if isinstance(m,dict) and md and recent_start<=md<=today and n(m.get('home_goals')) is not None and n(m.get('away_goals')) is not None:
            baseline_results[mkey(m)]=m
    current_results={mkey(m):m for m in data.get('recent_results',[]) if isinstance(m,dict)}
    changed=[]
    for key in set(baseline_results)|set(current_results):
        old=baseline_results.get(key); new=current_results.get(key)
        old_score=None if not old else (n(old.get('home_goals')),n(old.get('away_goals')))
        new_score=None if not new else (n(new.get('home_goals')),n(new.get('away_goals')))
        if old_score!=new_score:
            changed.append(key)
    if changed:
        rows_by_team={r['team']:dict(r) for r in base_rows}
        latest_by_team={r['team']:r for r in data.get('standings',[]) if isinstance(r,dict) and r.get('team')}
        for team,row in rows_by_team.items():
            newer=latest_by_team.get(team,{})
            pp=n(newer.get('penalty_points'))
            if pp is not None and pp>=0:
                row['penalty_points']=pp
        applied=False
        for key in changed:
            old=baseline_results.get(key); new=current_results.get(key)
            if old:
                applied=apply_match_delta(rows_by_team,old,-1) or applied
            if new:
                applied=apply_match_delta(rows_by_team,new,1) or applied
        if applied:
            reconciled=rerank(rows_by_team.values())
            checked=complete_table({'standings':reconciled},teamset)
            if checked:
                data['standings']=checked
                er=next((r for r in checked if r['team']=='FC Eschenbach II'),None)
                if er:
                    data['eschenbach']={**data.get('eschenbach',{}),**{k:er[k] for k in ('rank','played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points')}}
                print(f'Rangliste vor der Textredaktion mit {len(changed)} Resultatänderung(en) abgeglichen.')

facts={k:data.get(k) for k in ('eschenbach','recent_results','standings','upcoming_matches','scorers','own_goals')}
if active_alert:
    facts['active_alert']={k:active_alert.get(k) for k in ('type','title','message','meta','match')}
editorial=f'''Schreibe die fünf Lesertexte für die Fan-App FC Eschenbach II neu.
FAKTEN: {json.dumps(facts,ensure_ascii=False)}
Regeln: Nur diese Fakten verwenden; nichts erfinden. Resultate, Rangliste und Spielplan sind verbindlich. Eine active_alert-Meldung hat Vorrang vor dem Spielplan; ein abgesagtes Spiel darf nicht als kommend beschrieben werden. Keine erfundenen Spielverläufe, Chancen, Taktik, Verletzungen oder Ursachen. Sichere Einordnung von Serien, Punkteabständen, Tordifferenzen und Bedeutung des nächsten Spiels ist erwünscht. Schweizer Rechtschreibung. lead 50–80 Wörter, review 120–190, current_situation 100–160, outlook 100–160. JSON: {{"title":"...","lead":"...","review":"...","current_situation":"...","outlook":"..."}}'''
try:
    text=call_json(editorial,timeout=120)
    for k in ('title','lead','review','current_situation','outlook'):
        v=' '.join(str(text.get(k,'')).split()).strip()
        if v: data[k]=v
except Exception as exc:
    print('Live-Redaktion übersprungen:',exc)

if active_alert and active_alert.get('type')=='match_cancelled':
    cm=active_alert.get('match') or {}
    home=str(cm.get('home','')).strip()
    away=str(cm.get('away','')).strip()
    time_text=str(cm.get('time','')).strip()
    next_esch=next((m for m in data.get('upcoming_matches',[]) if isinstance(m,dict) and 'FC Eschenbach II' in (m.get('home'),m.get('away'))),None)
    first=f"Das heutige Spiel {home} – {away}" + (f" um {time_text} Uhr" if time_text else '') + " ist abgesagt."
    if next_esch:
        data['outlook']=first + f" Der nächste aktuell im Spielplan geführte Eschenbach-Match ist am {next_esch.get('date','')} um {next_esch.get('time','')} Uhr: {next_esch.get('home','')} – {next_esch.get('away','')}."
    else:
        data['outlook']=first + " Sobald ein neuer Termin feststeht, wird er in der App nachgeführt."

# Offizielle, tatsächlich geladene Links dokumentieren.
sources=[s for s in data.get('sources',[]) if isinstance(s,dict) and s.get('url') and s.get('title')]
for title,url in [('IFV Matchcenter – Einstieg 5. Liga 2026/27',IFV_BASE),('IFV Matchcenter – Gruppe 4 Resultate und Rangliste',result_url),('IFV Matchcenter – Gruppe 4 Spielplan',schedule_url)]:
    if not any(s.get('url')==url for s in sources): sources.append({'title':title,'url':url})
data['sources']=sources
data['report_date']=today.strftime('%d.%m.%Y')
data['generated_at']=now.strftime('%d.%m.%Y %H:%M')

with open(PATH,'w',encoding='utf-8') as f:
    json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
print('IFV-Liveabgleich abgeschlossen:',result_url)
