import json, os, re, urllib.request, html as html_lib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

API_KEY=os.environ.get('OPENAI_API_KEY','').strip()
if not API_KEY:
    print('OPENAI_API_KEY fehlt – Nachprüfung wird übersprungen.')
    raise SystemExit(0)

REPORT_PATH='data/report.json'
with open(REPORT_PATH,'r',encoding='utf-8') as f:
    data=json.load(f)

today=datetime.now(ZoneInfo('Europe/Zurich'))
start_date=today.date()
recent_start=start_date-timedelta(days=7)
end_date=start_date+timedelta(days=14)
date_display=today.strftime('%d.%m.%Y')


def call_json(prompt_text, timeout=180, use_web=False):
    payload={
        'model':'gpt-5.6-luna',
        'reasoning':{'effort':'medium'},
        'input':prompt_text
    }
    if use_web:
        payload['tools']=[{'type':'web_search'}]
    req=urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization':f'Bearer {API_KEY}','Content-Type':'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        response=json.loads(r.read().decode('utf-8'))

    text=response.get('output_text','').strip()
    if not text:
        chunks=[]
        for item in response.get('output',[]):
            for content in item.get('content',[]) if isinstance(item,dict) else []:
                if isinstance(content,dict) and content.get('type') in ('output_text','text'):
                    chunks.append(content.get('text',''))
        text=''.join(chunks).strip()

    if text.startswith('```'):
        lines=text.splitlines()
        if lines and lines[0].startswith('```'):
            lines=lines[1:]
        if lines and lines[-1].strip()=='```':
            lines=lines[:-1]
        text='\n'.join(lines).strip()
        if text.startswith('json'):
            text=text[4:].lstrip()
    return json.loads(text)


def fetch_live_text(url, timeout=40):
    sep='&' if '?' in url else '?'
    req=urllib.request.Request(
        f'{url}{sep}_ts={int(today.timestamp())}',
        headers={
            'User-Agent':'Mozilla/5.0 (compatible; GO-Eschenbach-II/1.0)',
            'Cache-Control':'no-cache',
            'Pragma':'no-cache'
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw=r.read().decode('utf-8','ignore')
    raw=re.sub(r'(?is)<script\b.*?</script>',' ',raw)
    raw=re.sub(r'(?is)<style\b.*?</style>',' ',raw)
    text=re.sub(r'(?s)<[^>]+>','\n',raw)
    text=html_lib.unescape(text).replace('\xa0',' ')
    lines=[' '.join(line.split()) for line in text.splitlines()]
    text='\n'.join(line for line in lines if line)
    return text[:90000]


def parse_date(value):
    try:
        return datetime.strptime(str(value).strip(),'%d.%m.%Y').date()
    except Exception:
        return None


def int_or_none(value):
    try:
        return int(value)
    except (TypeError,ValueError):
        return None


def clean_upcoming(item):
    if not isinstance(item,dict):
        return None
    d=parse_date(item.get('date'))
    if d is None or d<start_date or d>end_date:
        return None
    home=' '.join(str(item.get('home','')).split()).strip()
    away=' '.join(str(item.get('away','')).split()).strip()
    if not home or not away or home==away:
        return None
    time=' '.join(str(item.get('time','')).split()).strip()
    note=' '.join(str(item.get('note','')).split()).strip()
    return {'date':d.strftime('%d.%m.%Y'),'time':time,'home':home,'away':away,'note':note}


def clean_result(item):
    if not isinstance(item,dict):
        return None
    d=parse_date(item.get('date'))
    if d is None or d<recent_start or d>start_date:
        return None
    home=' '.join(str(item.get('home','')).split()).strip()
    away=' '.join(str(item.get('away','')).split()).strip()
    hg=int_or_none(item.get('home_goals'))
    ag=int_or_none(item.get('away_goals'))
    if not home or not away or home==away or hg is None or ag is None or hg<0 or ag<0:
        return None
    time=' '.join(str(item.get('time','')).split()).strip()
    note=' '.join(str(item.get('note','')).split()).strip()
    return {
        'date':d.strftime('%d.%m.%Y'),'time':time,'home':home,'away':away,
        'home_goals':hg,'away_goals':ag,'note':note
    }


def fixture_key(item):
    return (item.get('date',''),str(item.get('home','')).casefold(),str(item.get('away','')).casefold())


def normalize_text(value):
    return re.sub(r'\s+',' ',str(value or '')).casefold()


def supported_fixture(item, live_text):
    hay=normalize_text(live_text)
    home=normalize_text(item.get('home'))
    away=normalize_text(item.get('away'))
    if not home or not away:
        return False
    start=hay.find(home)
    while start!=-1:
        segment=hay[start:start+700]
        if away in segment:
            return True
        start=hay.find(home,start+1)
    return False


def supported_result(item, live_text):
    if not supported_fixture(item,live_text):
        return False
    hay=normalize_text(live_text)
    home=normalize_text(item.get('home'))
    away=normalize_text(item.get('away'))
    hg=str(item.get('home_goals'))
    ag=str(item.get('away_goals'))
    start=hay.find(home)
    while start!=-1:
        segment=hay[start:start+700]
        if away in segment:
            away_pos=segment.find(away)
            after=segment[away_pos+len(away):away_pos+len(away)+180]
            score_patterns=[
                rf'\b{re.escape(hg)}\s*[:\-]\s*{re.escape(ag)}\b',
                rf'(?:^|\s){re.escape(hg)}\s+{re.escape(ag)}(?:\s|$)'
            ]
            if any(re.search(p,after,re.I) for p in score_patterns):
                return True
        start=hay.find(home,start+1)
    return False


def clean_standing(row):
    if not isinstance(row,dict):
        return None
    team=' '.join(str(row.get('team','')).split()).strip()
    rank=int_or_none(row.get('rank'))
    played=int_or_none(row.get('played'))
    wins=int_or_none(row.get('wins'))
    draws=int_or_none(row.get('draws'))
    losses=int_or_none(row.get('losses'))
    penalty=int_or_none(row.get('penalty_points'))
    gf=int_or_none(row.get('goals_for'))
    ga=int_or_none(row.get('goals_against'))
    gd=int_or_none(row.get('goal_difference'))
    points=int_or_none(row.get('points'))
    vals=(rank,played,wins,draws,losses,penalty,gf,ga,gd,points)
    if not team or any(v is None for v in vals):
        return None
    if min(played,wins,draws,losses,penalty,gf,ga,points)<0:
        return None
    if played!=wins+draws+losses or gd!=gf-ga:
        return None
    return {
        'rank':rank,'team':team,'played':played,'wins':wins,'draws':draws,'losses':losses,
        'penalty_points':penalty,'goals_for':gf,'goals_against':ga,'goal_difference':gd,
        'points':points,'is_eschenbach':team=='FC Eschenbach II'
    }


teams=[str(r.get('team','')).strip() for r in data.get('standings',[]) if isinstance(r,dict) and r.get('team')]
team_set=set(teams)

# 1) Vollständigen Spielplan via Websuche nachprüfen (Fallback/Ergänzung).
fixture_prompt=f'''Du bist Datenprüfer. Ermittle AUSSCHLIESSLICH die noch nicht mit einem offiziellen Endresultat versehenen Meisterschaftsspiele der IFV 5. Liga, Gruppe 4, Saison 2026/27 im Zeitraum {start_date.strftime('%d.%m.%Y')} bis {end_date.strftime('%d.%m.%Y')} einschliesslich.

Verwende als Primärquellen zwingend diese offiziellen IFV-Seiten:
- https://matchcenter.ifv.ch/default.aspx?a=mna&ln=13040&lng=1&ls=25897&oid=7&s=2027&sg=70471
- https://matchcenter.ifv.ch/default.aspx?a=sp&bn=0&cxxlnus=1&lng=1&ls=25897&sg=70471&t=31009&v=357

Aktuelle Gruppenteams:
{json.dumps(teams,ensure_ascii=False)}

WICHTIG:
- Liste JEDES Gruppenspiel im Zeitraum auf. Keine Auswahl.
- Spiele des heutigen Tages bleiben solange kommende Spiele, bis ein offizielles Endresultat vorliegt.
- Verschobene Partien nur am aktuell publizierten Datum führen.
- Keine Cup-, Freundschafts-, Senioren- oder Juniorenspiele.
- Keine Paarung erfinden.
- Sortiere nach Datum und Anspielzeit.

Antworte ausschliesslich als valides JSON:
{{"upcoming_matches":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"...","note":""}}]}}
'''

try:
    fixture_audit=call_json(fixture_prompt,timeout=180,use_web=True)
    audited=[]
    seen=set()
    for raw in fixture_audit.get('upcoming_matches',[]):
        item=clean_upcoming(raw)
        if not item:
            continue
        if team_set and (item['home'] not in team_set or item['away'] not in team_set):
            continue
        key=fixture_key(item)
        if key in seen:
            continue
        seen.add(key)
        audited.append(item)
    audited.sort(key=lambda m:(parse_date(m['date']),m.get('time',''),m['home'],m['away']))
    if audited:
        data['upcoming_matches']=audited
        print(f'Spielplan-Nachprüfung: {len(audited)} kommende Gruppenspiele übernommen.')
    else:
        print('Spielplan-Nachprüfung lieferte keine belastbare Liste – bestehende Liste bleibt erhalten.')
except Exception as exc:
    print('Spielplan-Nachprüfung übersprungen:',exc)

# 2) Offizielle IFV-Seiten direkt und ohne Suchindex-Cache abrufen.
LIVE_URLS=[
    'https://matchcenter.ifv.ch/default.aspx?a=mna&ln=13040&lng=1&ls=25897&oid=7&s=2027&sg=70471',
    'https://matchcenter.ifv.ch/default.aspx?a=sp&bn=0&cxxlnus=1&lng=1&ls=25897&sg=70471&t=31009&v=357',
    'https://matchcenter.ifv.ch/Default.aspx?a=rr&lng=1&oid=7&v=375'
]
live_chunks=[]
for url in LIVE_URLS:
    try:
        text=fetch_live_text(url)
        if text:
            live_chunks.append(f'URL: {url}\n{text}')
    except Exception as exc:
        print('Direkter IFV-Abruf fehlgeschlagen:',url,exc)

live_text='\n\n---\n\n'.join(live_chunks)
if live_text:
    live_prompt=f'''Du liest unten DIREKT abgerufenen Text aus offiziellen IFV-Seiten. Extrahiere ausschliesslich Daten der Meisterschaft 5. Liga, Gruppe 4, Saison 2026/27.

HEUTE: {date_display}
GRUPPENTEAMS:
{json.dumps(teams,ensure_ascii=False)}

REGELN:
- Verwende NUR Angaben, die im gelieferten IFV-Text tatsächlich stehen.
- recent_results: Meisterschaftsresultate der letzten 7 Tage bis heute. Nur Spiele mit eindeutig sichtbarem Endresultat (beide Torzahlen vorhanden).
- upcoming_matches: noch nicht mit Endresultat versehene Gruppenspiele von heute bis {end_date.strftime('%d.%m.%Y')}.
- Heutige Spiele mit Endresultat gehören in recent_results und NICHT mehr in upcoming_matches.
- standings: die aktuell sichtbare vollständige Rangliste der Gruppe 4. Keine Werte ergänzen oder schätzen.
- Keine Cup-, Freundschafts-, Senioren- oder Juniorenspiele.
- Teamnamen exakt übernehmen.

OFFIZIELLER LIVE-TEXT:
{live_text}

Antworte ausschliesslich als valides JSON:
{{
  "recent_results":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"...","home_goals":0,"away_goals":0,"note":""}}],
  "upcoming_matches":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"...","note":""}}],
  "standings":[{{"rank":1,"team":"...","played":0,"wins":0,"draws":0,"losses":0,"penalty_points":0,"goals_for":0,"goals_against":0,"goal_difference":0,"points":0,"is_eschenbach":false}}]
}}
'''
    try:
        live=call_json(live_prompt,timeout=160,use_web=False)

        live_results=[]
        for raw in live.get('recent_results',[]):
            item=clean_result(raw)
            if not item:
                continue
            if team_set and (item['home'] not in team_set or item['away'] not in team_set):
                continue
            if supported_result(item,live_text):
                live_results.append(item)

        result_map={}
        for raw in data.get('recent_results',[]):
            item=clean_result(raw)
            if item:
                result_map[fixture_key(item)]=item
        for item in live_results:
            result_map[fixture_key(item)]=item
        data['recent_results']=sorted(
            result_map.values(),
            key=lambda m:(parse_date(m['date']),m.get('time',''),m['home'],m['away'])
        )

        upcoming_map={}
        for raw in data.get('upcoming_matches',[]):
            item=clean_upcoming(raw)
            if item:
                upcoming_map[fixture_key(item)]=item
        for raw in live.get('upcoming_matches',[]):
            item=clean_upcoming(raw)
            if not item:
                continue
            if team_set and (item['home'] not in team_set or item['away'] not in team_set):
                continue
            if supported_fixture(item,live_text):
                upcoming_map[fixture_key(item)]=item

        for key in result_map:
            upcoming_map.pop(key,None)
        data['upcoming_matches']=sorted(
            upcoming_map.values(),
            key=lambda m:(parse_date(m['date']),m.get('time',''),m['home'],m['away'])
        )

        live_standings=[]
        for raw in live.get('standings',[]):
            row=clean_standing(raw)
            if not row:
                continue
            if team_set and row['team'] not in team_set:
                continue
            live_standings.append(row)
        names={r['team'] for r in live_standings}
        if len(live_standings)==10 and (not team_set or names==team_set):
            live_standings.sort(key=lambda r:r['rank'])
            data['standings']=live_standings
            esch=next((r for r in live_standings if r['team']=='FC Eschenbach II'),None)
            if esch:
                target=data.setdefault('eschenbach',{})
                for key in ('rank','played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points'):
                    target[key]=esch[key]
            print('Live-Rangliste direkt vom IFV übernommen.')

        if live_results:
            print(f'Live-Resultate direkt vom IFV übernommen: {len(live_results)}.')
    except Exception as exc:
        print('Direkte IFV-Auswertung übersprungen:',exc)

# 3) Inkonsistente Torschützen-Daten nicht als sichere Fakten weiterverwenden.
expected_goals=max(0,int_or_none(data.get('eschenbach',{}).get('goals_for')) or 0)
scorers=data.get('scorers',[]) if isinstance(data.get('scorers'),list) else []
player_goals=sum(max(0,int_or_none(s.get('goals')) or 0) for s in scorers if isinstance(s,dict))
own_goals=max(0,int_or_none(data.get('own_goals')) or 0)
scorer_consistent=(expected_goals==0 or player_goals+own_goals==expected_goals)
if not scorer_consistent:
    data['scorer_audit']=dict(data.get('scorer_audit') or {},complete=False)
    data['scorer_note']='Die Torschützenliste wird erst wieder angezeigt, wenn die Kontrollsumme mit den offiziellen Saisontoren übereinstimmt.'

# 4) Objektive Kennzahlen für gehaltvollere, aber faktentreue Texte.
e=data.get('eschenbach',{}) if isinstance(data.get('eschenbach'),dict) else {}
played=max(0,int_or_none(e.get('played')) or 0)
points=max(0,int_or_none(e.get('points')) or 0)
gf=max(0,int_or_none(e.get('goals_for')) or 0)
ga=max(0,int_or_none(e.get('goals_against')) or 0)
recent_esch=[]
for r in data.get('recent_results',[]):
    if not isinstance(r,dict):
        continue
    if r.get('home')=='FC Eschenbach II' or r.get('away')=='FC Eschenbach II':
        recent_esch.append(r)
clean_sheets=0
for r in recent_esch:
    if r.get('home')=='FC Eschenbach II' and int_or_none(r.get('away_goals'))==0:
        clean_sheets+=1
    elif r.get('away')=='FC Eschenbach II' and int_or_none(r.get('home_goals'))==0:
        clean_sheets+=1

standing_rows=data.get('standings',[]) if isinstance(data.get('standings'),list) else []
second=next((r for r in standing_rows if int_or_none(r.get('rank'))==2),None)
derived={
    'points_per_game':round(points/played,2) if played else None,
    'goals_for_per_game':round(gf/played,2) if played else None,
    'goals_against_per_game':round(ga/played,2) if played else None,
    'goal_difference':gf-ga,
    'recent_eschenbach_clean_sheets':clean_sheets,
    'different_scorers':len(scorers) if scorer_consistent else None,
    'top_scorer':max(scorers,key=lambda s:int_or_none(s.get('goals')) or 0) if scorers and scorer_consistent else None,
    'gap_to_second':points-(int_or_none(second.get('points')) or 0) if second else None,
    'second_place_team':second.get('team') if second else None
}

facts={
    'report_date':data.get('report_date'),
    'eschenbach':data.get('eschenbach',{}),
    'recent_results':data.get('recent_results',[]),
    'standings':data.get('standings',[]),
    'upcoming_matches':data.get('upcoming_matches',[]),
    'scorers':data.get('scorers',[]) if scorer_consistent else [],
    'own_goals':data.get('own_goals',0) if scorer_consistent else 0,
    'derived_metrics':derived
}

editorial_prompt=f'''Du bist Sportredaktor einer mobilen Fan-App für FC Eschenbach II. Schreibe die fünf Lesertexte neu. Sie sollen etwas ausführlicher, gehaltvoll und angenehm lesbar sein – ohne Fülltext und ohne erfundene Informationen.

STICHTAG: {date_display}
VERBINDLICHES FAKTENPAKET:
{json.dumps(facts,ensure_ascii=False)}

ABSOLUTE FAKTENTREUE:
- Verwende ausschliesslich Fakten aus diesem Paket.
- Erfinde keine Spielverläufe, Chancen, Verletzungen, taktischen Ursachen, Serien oder Gegnerinformationen.
- Resultate dürfen nur aus recent_results stammen.
- Tabellenbehauptungen müssen direkt aus standings ableitbar sein.
- Angaben zu Torschützen nur verwenden, wenn im Paket scorers vorhanden sind.
- Einfache Berechnungen und Vergleiche aus den gelieferten Zahlen sind erlaubt; derived_metrics sind dafür bereits vorbereitet.
- Wenn zusätzliche Information fehlt, analysiere die vorhandenen Zahlen sinnvoll statt eine Geschichte zu erfinden.
- Kein Resultat mehrfach erzählen und nicht bloss die Tabelle Satz für Satz abschreiben.

SCHREIBWEISE:
- Schweizer Rechtschreibung, sportlich, natürlich, informativ.
- Kein Recherche- oder Quellenjargon in den Lesertexten.
- title: prägnant, maximal ca. 70 Zeichen.
- lead: 2–4 Sätze, ungefähr 50–80 Wörter.
- review: 6–9 Sätze, ungefähr 110–180 Wörter. Entwicklung und belegte Auffälligkeiten einordnen.
- current_situation: 5–7 Sätze, ungefähr 90–150 Wörter. Tabellenlage, Abstände, Spielezahl und Kennzahlen sinnvoll vergleichen.
- outlook: 5–7 Sätze, ungefähr 90–150 Wörter. Nächstes Eschenbach-Spiel und seine tabellarische Bedeutung einordnen; keine ungesicherten Gegnerdetails.
- Die Wortangaben sind Zielgrössen. Faktentreue geht immer vor Länge.

Antworte ausschliesslich als valides JSON:
{{"title":"...","lead":"...","review":"...","current_situation":"...","outlook":"..."}}
'''

banned=re.compile(r'\b(?:IFV|Matchcenter|Quelle|Website|Datensatz|Recherche|Stichtag|verifiziert|geprüft|öffentlich\s+abrufbar|nicht\s+ermittelbar)\b',re.I)
try:
    edited=call_json(editorial_prompt,timeout=180,use_web=False)
    for key in ('title','lead','review','current_situation','outlook'):
        value=' '.join(str(edited.get(key,'')).split()).strip()
        if value and not banned.search(value):
            data[key]=value
except Exception as exc:
    print('Vertiefter Redaktionsschritt übersprungen:',exc)

data['report_date']=date_display
data['generated_at']=today.strftime('%d.%m.%Y %H:%M')
with open(REPORT_PATH,'w',encoding='utf-8') as f:
    json.dump(data,f,ensure_ascii=False,indent=2)
    f.write('\n')
