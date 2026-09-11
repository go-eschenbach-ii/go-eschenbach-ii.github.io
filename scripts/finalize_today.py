import json, os, re, urllib.request
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

PATH='data/report.json'
API_KEY=os.environ.get('OPENAI_API_KEY','').strip()
if not API_KEY:
    raise SystemExit('OPENAI_API_KEY fehlt.')

with open(PATH,'r',encoding='utf-8') as f:
    data=json.load(f)

now=datetime.now(ZoneInfo('Europe/Zurich'))
today=now.date()
today_s=today.strftime('%d.%m.%Y')

def call_json(prompt, web=False, timeout=180):
    payload={'model':'gpt-5.6-luna','reasoning':{'effort':'medium'},'input':prompt}
    if web:
        payload['tools']=[{'type':'web_search'}]
    req=urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(payload).encode(),
        headers={'Authorization':f'Bearer {API_KEY}','Content-Type':'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req,timeout=timeout) as r:
        obj=json.loads(r.read().decode())
    text=obj.get('output_text','').strip()
    if not text:
        text=''.join(
            c.get('text','') for item in obj.get('output',[]) if isinstance(item,dict)
            for c in item.get('content',[]) if isinstance(c,dict)
            and c.get('type') in ('output_text','text')
        ).strip()
    if text.startswith('```'):
        text=re.sub(r'^```(?:json)?\s*|\s*```$','',text,flags=re.S).strip()
    return json.loads(text)

def dmy(v):
    try:return datetime.strptime(str(v),'%d.%m.%Y').date()
    except:return None

def num(v):
    try:return int(v)
    except:return None

def key(m):
    return (str(m.get('date','')),str(m.get('home','')).casefold(),str(m.get('away','')).casefold())

def kickoff_over(m):
    d=dmy(m.get('date'))
    mt=re.match(r'^(\d{1,2}):(\d{2})$',str(m.get('time','')))
    if not d or not mt:return False
    ko=datetime(d.year,d.month,d.day,int(mt.group(1)),int(mt.group(2)),tzinfo=ZoneInfo('Europe/Zurich'))
    return now>=ko+timedelta(minutes=150)

def official_url(url):
    try:
        host=(urlparse(str(url)).hostname or '').lower()
    except Exception:
        return False
    return host.endswith('ifv.ch') or host.endswith('football.ch')

def verify_score(url, home, away, hg, ag):
    if not official_url(url):return False
    try:
        sep='&' if '?' in url else '?'
        req=urllib.request.Request(
            f'{url}{sep}_ts={int(now.timestamp())}',
            headers={'User-Agent':'Mozilla/5.0','Cache-Control':'no-cache','Pragma':'no-cache'}
        )
        with urllib.request.urlopen(req,timeout=35) as r:
            raw=r.read().decode('utf-8','ignore')
        text=re.sub(r'(?is)<script\b.*?</script>|<style\b.*?</style>',' ',raw)
        text=re.sub(r'(?s)<[^>]+>',' ',text)
        text=re.sub(r'\s+',' ',text).casefold()
        h=home.casefold(); a=away.casefold()
        pos=text.find(h)
        while pos!=-1:
            seg=text[pos:pos+1200]
            if a in seg and re.search(rf'\b{hg}\s*[:\-]\s*{ag}\b|\b{hg}\s+{ag}\b',seg):
                return True
            pos=text.find(h,pos+1)
    except Exception:
        return False
    return False

teams=[r.get('team') for r in data.get('standings',[]) if isinstance(r,dict) and r.get('team')]
teamset=set(teams)

prompt=f'''Prüfe den HEUTIGEN Spieltag der IFV 5. Liga, Gruppe 4, Saison 2026/27.
Heute ist {today_s}.

Verwende ausschliesslich offizielle Seiten von ifv.ch, matchcenter.ifv.ch oder football.ch.
Gruppenteams: {json.dumps(teams,ensure_ascii=False)}

WICHTIG:
- Gib ALLE heute angesetzten Gruppenspiele zurück, auch wenn die Anspielzeit vorbei ist.
- Wenn ein offizielles Endresultat sichtbar ist, setze confirmed=true, nenne beide Torzahlen und die exakte offizielle source_url, auf der das Resultat sichtbar ist.
- Wenn kein offizielles Endresultat sichtbar ist, confirmed=false. Niemals raten.
- Gib zusätzlich die aktuellste vollständige Rangliste zurück, aber nur wenn alle 10 Teams und alle Werte sichtbar sind.
- Keine andere Liga oder Mannschaftsstufe verwenden.

JSON:
{{
 "today_matches":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"...","confirmed":false,"home_goals":null,"away_goals":null,"source_url":""}}],
 "standings":[{{"rank":1,"team":"...","played":0,"wins":0,"draws":0,"losses":0,"penalty_points":0,"goals_for":0,"goals_against":0,"goal_difference":0,"points":0,"is_eschenbach":false}}]
}}'''

try:
    fresh=call_json(prompt,web=True,timeout=180)
except Exception as exc:
    print('Heutige Schlussprüfung fehlgeschlagen:',exc)
    fresh={}

results={}
for m in data.get('recent_results',[]) if isinstance(data.get('recent_results'),list) else []:
    results[key(m)]=m

upcoming={}
for m in data.get('upcoming_matches',[]) if isinstance(data.get('upcoming_matches'),list) else []:
    upcoming[key(m)]=m

for raw in fresh.get('today_matches',[]) if isinstance(fresh.get('today_matches'),list) else []:
    if not isinstance(raw,dict):continue
    if dmy(raw.get('date'))!=today:continue
    home=' '.join(str(raw.get('home','')).split())
    away=' '.join(str(raw.get('away','')).split())
    if not home or not away or home not in teamset or away not in teamset:continue
    m={'date':today_s,'time':str(raw.get('time','')).strip(),'home':home,'away':away,'note':''}
    k=key(m)
    hg=num(raw.get('home_goals')); ag=num(raw.get('away_goals'))
    source=str(raw.get('source_url','')).strip()
    confirmed=(raw.get('confirmed') is True and hg is not None and ag is not None and hg>=0 and ag>=0 and verify_score(source,home,away,hg,ag))
    if confirmed:
        results[k]={**m,'home_goals':hg,'away_goals':ag}
        upcoming.pop(k,None)
    elif k not in results:
        if kickoff_over(m):
            m['note']='Resultat noch nicht synchronisiert'
        upcoming[k]=m

for k,m in list(upcoming.items()):
    if dmy(m.get('date'))==today and kickoff_over(m) and k not in results:
        m=dict(m)
        m['note']='Resultat noch nicht synchronisiert'
        upcoming[k]=m

data['recent_results']=sorted(results.values(),key=lambda m:(dmy(m.get('date')) or today,m.get('time',''),m.get('home','')))
data['upcoming_matches']=sorted(upcoming.values(),key=lambda m:(dmy(m.get('date')) or today,m.get('time',''),m.get('home','')))

candidate=[]
for r in fresh.get('standings',[]) if isinstance(fresh.get('standings'),list) else []:
    if not isinstance(r,dict):continue
    vals={x:num(r.get(x)) for x in ('rank','played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points')}
    team=' '.join(str(r.get('team','')).split())
    if team not in teamset or any(v is None for v in vals.values()):continue
    if vals['played']!=vals['wins']+vals['draws']+vals['losses']:continue
    if vals['goal_difference']!=vals['goals_for']-vals['goals_against']:continue
    candidate.append({'team':team,**vals,'is_eschenbach':team=='FC Eschenbach II'})

old=data.get('standings',[]) if isinstance(data.get('standings'),list) else []
if len(candidate)==10 and {r['team'] for r in candidate}==teamset and {r['rank'] for r in candidate}==set(range(1,11)):
    if sum(r['played'] for r in candidate)>=sum(int(r.get('played',0) or 0) for r in old):
        candidate.sort(key=lambda r:r['rank'])
        data['standings']=candidate
        er=next((r for r in candidate if r['team']=='FC Eschenbach II'),None)
        if er:
            data['eschenbach']={**data.get('eschenbach',{}),**{k:er[k] for k in ('rank','played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points')}}

facts={k:data.get(k) for k in ('eschenbach','recent_results','standings','upcoming_matches','scorers','own_goals')}
editorial=f'''Schreibe die fünf Lesertexte für die Fan-App FC Eschenbach II neu.

FAKTEN:
{json.dumps(facts,ensure_ascii=False)}

REGELN:
- Ausschliesslich diese Fakten verwenden. Nichts erfinden.
- Resultate nur nennen, wenn home_goals und away_goals vorhanden sind.
- "Resultat noch nicht synchronisiert" bedeutet: Ausgang unbekannt; keinen Sieger behaupten.
- Tabelle nur gemäss standings beschreiben.
- Keine Spielverläufe, Taktik, Chancen, Verletzungen oder Gründe erfinden.
- Schweizer Rechtschreibung, sportlich und informativ.
- Nicht nur Resultate wiederholen, sondern sichere Zusammenhänge und Abstände einordnen.
- lead 50 bis 80 Wörter; review 120 bis 190 Wörter; current_situation 100 bis 160 Wörter; outlook 100 bis 160 Wörter.
- Faktentreue ist wichtiger als Länge.

JSON:
{{"title":"...","lead":"...","review":"...","current_situation":"...","outlook":"..."}}'''
try:
    text=call_json(editorial,web=False,timeout=120)
    for k in ('title','lead','review','current_situation','outlook'):
        v=' '.join(str(text.get(k,'')).split()).strip()
        if v:data[k]=v
except Exception as exc:
    print('Schlussredaktion übersprungen:',exc)

data['report_date']=today_s
data['generated_at']=now.strftime('%d.%m.%Y %H:%M')
with open(PATH,'w',encoding='utf-8') as f:
    json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')

print('Heutige Schlussprüfung abgeschlossen.')
