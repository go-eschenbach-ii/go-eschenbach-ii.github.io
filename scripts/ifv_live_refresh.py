import json, os, re, urllib.request, http.cookiejar, html as html_lib
from fractions import Fraction
from datetime import datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

PATH='data/report.json'
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
    text=str(text or '')
    canonical={str(t).casefold():str(t) for t in teamset}
    date_marks=list(re.finditer(r'\b(\d{2}\.\d{2}\.\d{4})\b',text))
    found={}
    for idx,mark in enumerate(date_marks):
        d=dmy(mark.group(1))
        if not d or d<recent_start or d>today:
            continue
        end=date_marks[idx+1].start() if idx+1<len(date_marks) else len(text)
        segment=text[mark.end():end]
        occurrences=[]
        for team in canonical.values():
            for hit in re.finditer(re.escape(team),segment,re.I):
                occurrences.append((hit.start(),hit.end(),team))
        occurrences.sort(key=lambda x:x[0])
        for i in range(len(occurrences)-1):
            hs,he,home=occurrences[i]
            as_,ae,away=occurrences[i+1]
            if home==away:
                continue
            next_team=occurrences[i+2][0] if i+2<len(occurrences) else len(segment)
            tail=segment[ae:next_team]
            score_tokens=re.findall(r'(?m)^[ \t]*(\d{1,2})[ \t]*    played=max(0,n(row.get('played')) or 0)
    penalty=max(0,n(row.get('penalty_points')) or 0)
    penalty_ratio=Fraction(penalty,played) if played else Fraction(0,1)
    return (
        -(n(row.get('points')) or 0),
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
    # IFV-Regel: bei Punktgleichheit zuerst tieferer Strafpunktquotient,
    # danach Tordifferenz. Rang wird deshalb immer deterministisch neu gebildet.
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
- standings: vollständige aktuelle Rangliste aller Gruppenteams. Strafpunkte sind die Zahl in Klammern. Bei Punktgleichheit zählt zuerst der tiefere Strafpunktquotient (Strafpunkte / ausgetragene Spiele), danach die Tordifferenz.
- Keine andere Liga, Gruppe, Cup- oder Juniorenspiele.

RESULTATE + RANGLISTE:
{result_text[:110000]}

SPIELPLAN:
{schedule_text[:110000]}

JSON:
{{"recent_results":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"...","home_goals":0,"away_goals":0}}],"upcoming_matches":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"..."}}],"standings":[{{"rank":1,"team":"...","played":0,"wins":0,"draws":0,"losses":0,"penalty_points":0,"goals_for":0,"goals_against":0,"goal_difference":0,"points":0}}]}}'''
fresh=call_json(prompt,timeout=180)

# Zweite offizielle IFV-Quelle: Resultate zusätzlich direkt aus dem Spielplan lesen.
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
    print(f'{len(direct_schedule_results)} Resultat(e) deterministisch aus dem IFV-Spielplan gelesen.')

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

facts={k:data.get(k) for k in ('eschenbach','recent_results','standings','upcoming_matches','scorers','own_goals')}
editorial=f'''Schreibe die fünf Lesertexte für die Fan-App FC Eschenbach II neu.
FAKTEN: {json.dumps(facts,ensure_ascii=False)}
Regeln: Nur diese Fakten verwenden; nichts erfinden. Resultate, Rangliste und Spielplan sind verbindlich. Keine erfundenen Spielverläufe, Chancen, Taktik, Verletzungen oder Ursachen. Sichere Einordnung von Serien, Punkteabständen, Tordifferenzen und Bedeutung des nächsten Spiels ist erwünscht. Schweizer Rechtschreibung. lead 50–80 Wörter, review 120–190, current_situation 100–160, outlook 100–160. JSON: {{"title":"...","lead":"...","review":"...","current_situation":"...","outlook":"..."}}'''
try:
    text=call_json(editorial,timeout=120)
    for k in ('title','lead','review','current_situation','outlook'):
        v=' '.join(str(text.get(k,'')).split()).strip()
        if v: data[k]=v
except Exception as exc:
    print('Live-Redaktion übersprungen:',exc)

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
,tail)
            if len(score_tokens)>=2:
                hg,ag=int(score_tokens[0]),int(score_tokens[1])
            else:
                score_match=re.search(r'(?<!\d)(\d{1,2})\s*[:\-]\s*(\d{1,2})(?!\d)',tail)
                if not score_match:
                    continue
                hg,ag=int(score_match.group(1)),int(score_match.group(2))
            prefix=segment[max(0,hs-40):hs]
            times=re.findall(r'\b(?:[01]\d|2[0-3]):[0-5]\d\b',prefix)
            item={'date':d.strftime('%d.%m.%Y'),'time':times[-1] if times else '','home':home,'away':away,'home_goals':hg,'away_goals':ag,'note':''}
            found[mkey(item)]=item
    return list(found.values())


def ranking_key(row):
    played=max(0,n(row.get('played')) or 0)
    penalty=max(0,n(row.get('penalty_points')) or 0)
    penalty_ratio=Fraction(penalty,played) if played else Fraction(0,1)
    return (
        -(n(row.get('points')) or 0),
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
    # IFV-Regel: bei Punktgleichheit zuerst tieferer Strafpunktquotient,
    # danach Tordifferenz. Rang wird deshalb immer deterministisch neu gebildet.
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
schedule_text=to_text(fetch_html(schedule_url,referer=result_url))

prompt=f'''Extrahiere ausschliesslich die Daten der IFV 5. Liga, Gruppe 4, Saison 2026/27 aus den beiden direkt geladenen offiziellen IFV-Seiten.
Heute: {today.strftime('%d.%m.%Y')}
Gruppenteams: {json.dumps(teams,ensure_ascii=False)}

Regeln:
- Nichts erfinden oder aus Vorwissen ergänzen.
- recent_results: alle Meisterschaftsresultate vom {recent_start.strftime('%d.%m.%Y')} bis heute, aber nur wenn beide Torzahlen sichtbar sind.
- upcoming_matches: alle noch nicht beendeten Meisterschaftsspiele von heute bis {future_end.strftime('%d.%m.%Y')}.
- standings: vollständige aktuelle Rangliste aller Gruppenteams. Strafpunkte sind die Zahl in Klammern. Bei Punktgleichheit zählt zuerst der tiefere Strafpunktquotient (Strafpunkte / ausgetragene Spiele), danach die Tordifferenz.
- Keine andere Liga, Gruppe, Cup- oder Juniorenspiele.

RESULTATE + RANGLISTE:
{result_text[:110000]}

SPIELPLAN:
{schedule_text[:110000]}

JSON:
{{"recent_results":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"...","home_goals":0,"away_goals":0}}],"upcoming_matches":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"..."}}],"standings":[{{"rank":1,"team":"...","played":0,"wins":0,"draws":0,"losses":0,"penalty_points":0,"goals_for":0,"goals_against":0,"goal_difference":0,"points":0}}]}}'''
fresh=call_json(prompt,timeout=180)

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

facts={k:data.get(k) for k in ('eschenbach','recent_results','standings','upcoming_matches','scorers','own_goals')}
editorial=f'''Schreibe die fünf Lesertexte für die Fan-App FC Eschenbach II neu.
FAKTEN: {json.dumps(facts,ensure_ascii=False)}
Regeln: Nur diese Fakten verwenden; nichts erfinden. Resultate, Rangliste und Spielplan sind verbindlich. Keine erfundenen Spielverläufe, Chancen, Taktik, Verletzungen oder Ursachen. Sichere Einordnung von Serien, Punkteabständen, Tordifferenzen und Bedeutung des nächsten Spiels ist erwünscht. Schweizer Rechtschreibung. lead 50–80 Wörter, review 120–190, current_situation 100–160, outlook 100–160. JSON: {{"title":"...","lead":"...","review":"...","current_situation":"...","outlook":"..."}}'''
try:
    text=call_json(editorial,timeout=120)
    for k in ('title','lead','review','current_situation','outlook'):
        v=' '.join(str(text.get(k,'')).split()).strip()
        if v: data[k]=v
except Exception as exc:
    print('Live-Redaktion übersprungen:',exc)

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
