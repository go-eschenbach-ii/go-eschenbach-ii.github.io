import json, os, re, urllib.request, http.cookiejar, html as html_lib
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
        if vals['goal_difference']!=vals['goals_for']-vals['goals_against']: return None
        clean.append({'team':team,**vals,'is_eschenbach':team=='FC Eschenbach II'})
    if {r['team'] for r in clean}!=teamset or {r['rank'] for r in clean}!=set(range(1,len(clean)+1)):
        return None
    return sorted(clean,key=lambda r:r['rank'])


def table_score(rows):
    return sum(int(r.get('played',0) or 0) for r in rows) if rows else -1

teams=[r.get('team') for r in (baseline.get('standings') or data.get('standings') or []) if isinstance(r,dict) and r.get('team')]
teamset=set(teams)
if len(teamset)<8:
    raise SystemExit('Gruppenteams fehlen.')

# Den vom Benutzer genannten offiziellen Einstieg öffnen und alle 5.-Liga-Gruppenlinks lesen.
base_raw=fetch_html(IFV_BASE)
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
- standings: vollständige aktuelle Rangliste aller Gruppenteams. Strafpunkte sind die Zahl in Klammern.
- Keine andere Liga, Gruppe, Cup- oder Juniorenspiele.

RESULTATE + RANGLISTE:
{result_text[:110000]}

SPIELPLAN:
{schedule_text[:110000]}

JSON:
{{"recent_results":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"...","home_goals":0,"away_goals":0}}],"upcoming_matches":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"..."}}],"standings":[{{"rank":1,"team":"...","played":0,"wins":0,"draws":0,"losses":0,"penalty_points":0,"goals_for":0,"goals_against":0,"goal_difference":0,"points":0}}]}}'''
fresh=call_json(prompt,timeout=180)

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
candidates=[]
for obj in (baseline,data,fresh):
    rows=complete_table(obj,teamset)
    if rows: candidates.append(rows)
if candidates:
    best=max(candidates,key=table_score)
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
