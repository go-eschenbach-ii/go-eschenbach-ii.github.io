import json, os, re, urllib.request, html as html_lib
from datetime import datetime, timedelta
from urllib.parse import urljoin
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
recent_start=today-timedelta(days=7)
future_end=today+timedelta(days=14)

# Einziger fester Einstiegspunkt. Die konkreten Links von Gruppe 4 werden bei
# jedem Update direkt aus dieser offiziellen IFV-Seite neu ermittelt.
IFV_BASE='https://matchcenter.ifv.ch/default.aspx?oid=7&lng=1&s=2027&ln=13040'


def call_json(prompt, web=False, timeout=180):
    payload={'model':'gpt-5.6-luna','reasoning':{'effort':'medium'},'input':prompt}
    if web:
        payload['tools']=[{'type':'web_search'}]
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
        text=''.join(
            c.get('text','') for item in obj.get('output',[]) if isinstance(item,dict)
            for c in item.get('content',[]) if isinstance(c,dict)
            and c.get('type') in ('output_text','text')
        ).strip()
    if text.startswith('```'):
        text=re.sub(r'^```(?:json)?\s*|\s*```$','',text,flags=re.S).strip()
    return json.loads(text)


def fetch_html(url, timeout=45):
    sep='&' if '?' in url else '?'
    req=urllib.request.Request(
        f'{url}{sep}_goe={int(now.timestamp())}',
        headers={
            'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1',
            'Cache-Control':'no-cache, no-store, max-age=0',
            'Pragma':'no-cache',
            'Accept':'text/html,application/xhtml+xml'
        }
    )
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.read().decode('utf-8','ignore')


def html_to_text(raw):
    raw=re.sub(r'(?is)<script\b.*?</script>',' ',raw)
    raw=re.sub(r'(?is)<style\b.*?</style>',' ',raw)
    raw=re.sub(r'(?s)<[^>]+>','\n',raw)
    raw=html_lib.unescape(raw).replace('\xa0',' ')
    lines=[' '.join(x.split()) for x in raw.splitlines()]
    return '\n'.join(x for x in lines if x)


def discover_group4_urls():
    raw=fetch_html(IFV_BASE)
    matches=[]
    for m in re.finditer(r'href=["\']([^"\']*\ba=mrr\b[^"\']*)["\']',raw,re.I):
        left=max(0,m.start()-500)
        right=min(len(raw),m.end()+500)
        context=html_lib.unescape(re.sub(r'(?s)<[^>]+>',' ',raw[left:right]))
        context=' '.join(context.split())
        if re.search(r'\bGruppe\s*4\b',context,re.I):
            href=html_lib.unescape(m.group(1))
            matches.append(urljoin(IFV_BASE,href))
    if not matches:
        raise RuntimeError('IFV-Link für 5. Liga, Gruppe 4 nicht gefunden.')
    result_url=matches[-1]
    if 'a=mrr' not in result_url:
        raise RuntimeError('Unerwarteter IFV-Gruppenlink.')
    schedule_url=result_url.replace('a=mrr','a=msp',1)
    return result_url,schedule_url


def dmy(v):
    try:return datetime.strptime(str(v).strip(),'%d.%m.%Y').date()
    except:return None


def num(v):
    try:return int(v)
    except:return None


def key(m):
    return (str(m.get('date','')),str(m.get('home','')).casefold(),str(m.get('away','')).casefold())


def clean_result(m, teamset):
    if not isinstance(m,dict):return None
    d=dmy(m.get('date'))
    home=' '.join(str(m.get('home','')).split())
    away=' '.join(str(m.get('away','')).split())
    hg=num(m.get('home_goals')); ag=num(m.get('away_goals'))
    if not d or d<recent_start or d>today:return None
    if home not in teamset or away not in teamset or home==away:return None
    if hg is None or ag is None or hg<0 or ag<0:return None
    return {
        'date':d.strftime('%d.%m.%Y'),
        'time':' '.join(str(m.get('time','')).split()),
        'home':home,'away':away,'home_goals':hg,'away_goals':ag,'note':''
    }


def clean_upcoming(m, teamset):
    if not isinstance(m,dict):return None
    d=dmy(m.get('date'))
    home=' '.join(str(m.get('home','')).split())
    away=' '.join(str(m.get('away','')).split())
    if not d or d<today or d>future_end:return None
    if home not in teamset or away not in teamset or home==away:return None
    return {
        'date':d.strftime('%d.%m.%Y'),
        'time':' '.join(str(m.get('time','')).split()),
        'home':home,'away':away,'note':''
    }


def clean_standing(r, teamset):
    if not isinstance(r,dict):return None
    team=' '.join(str(r.get('team','')).split())
    fields=('rank','played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points')
    vals={x:num(r.get(x)) for x in fields}
    if team not in teamset or any(v is None for v in vals.values()):return None
    if min(vals['played'],vals['wins'],vals['draws'],vals['losses'],vals['penalty_points'],vals['goals_for'],vals['goals_against'],vals['points'])<0:return None
    if vals['played']!=vals['wins']+vals['draws']+vals['losses']:return None
    if vals['goal_difference']!=vals['goals_for']-vals['goals_against']:return None
    return {'team':team,**vals,'is_eschenbach':team=='FC Eschenbach II'}


teams=[r.get('team') for r in data.get('standings',[]) if isinstance(r,dict) and r.get('team')]
teamset=set(teams)

# 1) Kernfakten direkt aus den offiziellen Seiten von Gruppe 4 lesen.
# Kein Suchindex und keine Drittquelle für Resultate, Tabelle oder Spielplan.
try:
    result_url,schedule_url=discover_group4_urls()
    result_text=html_to_text(fetch_html(result_url))
    schedule_text=html_to_text(fetch_html(schedule_url))

    extraction=f'''Extrahiere ausschliesslich Fakten aus den zwei unten eingefügten, direkt abgerufenen offiziellen IFV-Seiten.

Wettbewerb: IFV 5. Liga, Gruppe 4, Saison 2026/27
Heute: {today_s}
Gruppenteams: {json.dumps(teams,ensure_ascii=False)}

VERBINDLICH:
- Keine Websuche und kein Vorwissen verwenden. Nur den gelieferten IFV-Text.
- recent_results: alle Meisterschaftsresultate von {recent_start.strftime('%d.%m.%Y')} bis {today_s}; nur Partien mit eindeutig sichtbarem Endresultat.
- upcoming_matches: alle noch nicht ausgetragenen Meisterschaftsspiele von {today_s} bis {future_end.strftime('%d.%m.%Y')}.
- Ein heutiges Spiel mit Endresultat gehört nur in recent_results, niemals zusätzlich in upcoming_matches.
- standings: die vollständige aktuelle Rangliste von Gruppe 4 mit allen 10 Teams und allen Spalten.
- Strafpunkte sind die Zahl in Klammern.
- Keine Cup-, Test-, Junioren- oder anderen Gruppen übernehmen.
- Nichts ergänzen oder schätzen.

RESULTATE + RANGLISTE ({result_url}):
{result_text[:110000]}

SPIELPLAN ({schedule_url}):
{schedule_text[:110000]}

Antworte ausschliesslich als JSON:
{{
 "recent_results":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"...","home_goals":0,"away_goals":0}}],
 "upcoming_matches":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"..."}}],
 "standings":[{{"rank":1,"team":"...","played":0,"wins":0,"draws":0,"losses":0,"penalty_points":0,"goals_for":0,"goals_against":0,"goal_difference":0,"points":0}}]
}}'''
    fresh=call_json(extraction,web=False,timeout=170)

    results=[]
    seen=set()
    for raw in fresh.get('recent_results',[]) if isinstance(fresh.get('recent_results'),list) else []:
        item=clean_result(raw,teamset)
        if item and key(item) not in seen:
            seen.add(key(item));results.append(item)
    results.sort(key=lambda m:(dmy(m['date']),m.get('time',''),m['home']))

    upcoming=[]
    seen=set()
    result_keys={key(m) for m in results}
    for raw in fresh.get('upcoming_matches',[]) if isinstance(fresh.get('upcoming_matches'),list) else []:
        item=clean_upcoming(raw,teamset)
        if item and key(item) not in seen and key(item) not in result_keys:
            seen.add(key(item));upcoming.append(item)
    upcoming.sort(key=lambda m:(dmy(m['date']),m.get('time',''),m['home']))

    standings=[]
    for raw in fresh.get('standings',[]) if isinstance(fresh.get('standings'),list) else []:
        item=clean_standing(raw,teamset)
        if item:standings.append(item)
    names={r['team'] for r in standings}
    ranks={r['rank'] for r in standings}

    if results:
        data['recent_results']=results
    if upcoming:
        data['upcoming_matches']=upcoming
    if len(standings)==10 and names==teamset and ranks==set(range(1,11)):
        standings.sort(key=lambda r:r['rank'])
        data['standings']=standings
        er=next((r for r in standings if r['team']=='FC Eschenbach II'),None)
        if er:
            data['eschenbach']={**data.get('eschenbach',{}),**{k:er[k] for k in ('rank','played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points')}}
    else:
        print('Direkte IFV-Rangliste unvollständig – bestehende Tabelle bleibt erhalten.')

    sources=[]
    for s in data.get('sources',[]) if isinstance(data.get('sources'),list) else []:
        if isinstance(s,dict) and s.get('url') and s.get('title'):
            sources.append(s)
    for title,url in [
        ('IFV Matchcenter – Einstieg 5. Liga Saison 2026/27',IFV_BASE),
        ('IFV Matchcenter – Gruppe 4 Resultate und Rangliste',result_url),
        ('IFV Matchcenter – Gruppe 4 Spielplan',schedule_url)
    ]:
        if not any(x.get('url')==url for x in sources):
            sources.append({'title':title,'url':url})
    data['sources']=sources
    print('IFV-Gruppe 4 direkt geladen:',result_url)
except Exception as exc:
    print('Direkter IFV-Gruppenabruf fehlgeschlagen:',exc)
    # Keine unsicheren Ersatzdaten einspielen; der vorhandene Bericht bleibt stehen.

# 2) Lesertexte erst NACH dem direkten IFV-Abgleich neu schreiben.
facts={k:data.get(k) for k in ('eschenbach','recent_results','standings','upcoming_matches','scorers','own_goals')}
editorial=f'''Schreibe die fünf Lesertexte für die Fan-App FC Eschenbach II neu.

FAKTEN:
{json.dumps(facts,ensure_ascii=False)}

REGELN:
- Ausschliesslich diese Fakten verwenden. Nichts erfinden.
- Tabelle, Resultate und Spielplan sind verbindlich.
- Keine Spielverläufe, Taktik, Chancen, Verletzungen oder Gründe erfinden.
- Zusätzliche Einordnung nur aus sicher ableitbaren Zahlen: Serien, Punkteabstände, Tordifferenz, Spielezahl, Rangverschiebungen und Bedeutung des nächsten Spiels.
- Schweizer Rechtschreibung, sportlich und informativ.
- Nicht bloss Resultate wiederholen.
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
    json.dump(data,f,ensure_ascii=False,indent=2)
    f.write('\n')

print('Heutige Schlussprüfung abgeschlossen.')
