import json, os, re, urllib.request
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


def parse_date(value):
    try:
        return datetime.strptime(str(value).strip(),'%d.%m.%Y').date()
    except Exception:
        return None


def clean_match(item):
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


def fixture_key(item):
    return (item.get('date',''),item.get('home','').casefold(),item.get('away','').casefold())


teams=[str(r.get('team','')).strip() for r in data.get('standings',[]) if isinstance(r,dict) and r.get('team')]
fixture_prompt=f'''Du bist Datenprüfer. Ermittle AUSSCHLIESSLICH die noch nicht mit einem offiziellen Endresultat versehenen Meisterschaftsspiele der IFV 5. Liga, Gruppe 4, Saison 2026/27 im Zeitraum {start_date.strftime('%d.%m.%Y')} bis {end_date.strftime('%d.%m.%Y')} einschliesslich.

Verwende als Primärquellen zwingend diese offiziellen IFV-Seiten und gleiche beide Ansichten ab:
- kompletter Saisonspielplan: https://matchcenter.ifv.ch/default.aspx?a=msp&ln=13040&lng=1&ls=25897&oid=7&s=2027&sg=70471
- Resultate/Rangliste Gruppe 4: https://matchcenter.ifv.ch/Default.aspx?a=rr&lng=1&oid=7&v=352

Aktuelle Gruppenteams laut Bericht:
{json.dumps(teams,ensure_ascii=False)}

WICHTIG:
- Liste JEDES Gruppenspiel im Zeitraum auf. Keine Auswahl und keine Zusammenfassung.
- Spiele des heutigen Tages bleiben in der Liste, solange auf der offiziellen IFV-Seite noch kein Endresultat steht – auch wenn die Anspielzeit bereits vorbei ist.
- Verschobene Partien nur am aktuell publizierten Datum führen.
- Keine Cup-, Freundschafts-, Senioren- oder Juniorenspiele.
- Keine Spielpaarung erfinden. Bei Unsicherheit lieber nochmals die offizielle Seite prüfen.
- Sortiere nach Datum und Anspielzeit.

Antworte ausschliesslich als valides JSON:
{{"upcoming_matches":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"...","note":""}}]}}
'''

try:
    fixture_audit=call_json(fixture_prompt,timeout=180,use_web=True)
    audited=[]
    seen=set()
    for raw in fixture_audit.get('upcoming_matches',[]):
        item=clean_match(raw)
        if not item:
            continue
        if teams and (item['home'] not in teams or item['away'] not in teams):
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

facts={
    'report_date':data.get('report_date'),
    'eschenbach':data.get('eschenbach',{}),
    'recent_results':data.get('recent_results',[]),
    'standings':data.get('standings',[]),
    'upcoming_matches':data.get('upcoming_matches',[]),
    'scorers':data.get('scorers',[]),
    'own_goals':data.get('own_goals',0),
    'scorer_audit':data.get('scorer_audit',{}),
    'existing_texts':{k:data.get(k,'') for k in ('title','lead','review','current_situation','outlook')}
}

editorial_prompt=f'''Du bist Sportredaktor einer mobilen Fan-App für FC Eschenbach II. Recherchiere gezielt zusätzlichen, belastbaren Kontext und schreibe die fünf Lesertexte neu. Die Texte sollen SUBSTANZ haben und nicht bei jedem Update immer kürzer werden.

STICHTAG: {date_display}
FAKTEN AUS DEM AKTUELLEN BERICHT (für Resultate, Tabelle und Torschützen massgebend):
{json.dumps(facts,ensure_ascii=False)}

RECHERCHE:
1. Nutze für Spielplan, Resultate und Rangliste die offiziellen IFV-Daten.
2. Suche auf offiziellen Vereinsseiten der exakt betroffenen Mannschaften sowie bei seriösen lokalen Sportquellen nach zusätzlichen aktuellen Informationen: Spielberichte, bestätigte Spielverläufe, personelle Hinweise, Formhinweise oder besondere Umstände.
3. Mannschaften exakt unterscheiden. Informationen zu FC Knutwil I dürfen NICHT für FC Knutwil II verwendet werden. Dasselbe gilt für andere erste/zweite/dritte Mannschaften.
4. Eine Information aus einem Vereinsbericht darf nur verwendet werden, wenn der Bericht eindeutig die richtige Mannschaft und das passende Spiel betrifft.
5. Keine Gerüchte, Vermutungen oder erfundenen Details.

SCHREIBWEISE:
- Nicht bloss Resultate und Tabellenwerte in ganzen Sätzen wiederholen. Ordne die Fakten ein: Serien, Entwicklung, Torverteilung, defensive/offensive Tendenzen, Tabellenabstände, Spiele in Reserve, Bedeutung der nächsten Paarung oder bestätigte Besonderheiten aus Spielberichten.
- Einfache, eindeutig aus den gelieferten Zahlen ableitbare Aussagen sind erlaubt. Keine spekulativen Ursachen.
- Wenn die Recherche keinen zusätzlichen belegten Kontext liefert, nutze lieber eine sachliche Einordnung der vorhandenen Fakten als Fülltext zu erfinden.
- Schweizer Rechtschreibung. Sportlich, natürlich, informativ.
- Kein Recherche- oder Quellenjargon in den Lesertexten.
- title: prägnant, maximal ca. 70 Zeichen.
- lead: 2–3 Sätze, ungefähr 35–60 Wörter.
- review: 5–8 Sätze, ungefähr 80–140 Wörter. Eschenbach im Zentrum; Resultat nicht mehrfach wiederholen.
- current_situation: 4–6 Sätze, ungefähr 65–110 Wörter. Tabelle und Form einordnen, nicht nur abschreiben.
- outlook: 4–6 Sätze, ungefähr 65–110 Wörter. Nächstes Eschenbach-Spiel einordnen; nur belegte Gegnerinformationen verwenden.
- Die Wortangaben sind Zielgrössen, kein Grund zum Erfinden. Faktentreue geht immer vor Länge.

QUELLEN:
- Gib nur Quellen zurück, die du tatsächlich für zusätzliche Fakten verwendet hast.
- URLs niemals erfinden; nur tatsächlich gefundene Seiten aus der Websuche verwenden.

Antworte ausschliesslich als valides JSON:
{{
  "title":"...",
  "lead":"...",
  "review":"...",
  "current_situation":"...",
  "outlook":"...",
  "sources":[{{"title":"...","url":"https://..."}}]
}}
'''

banned=re.compile(r'\b(?:IFV|Matchcenter|Quelle|Website|Datensatz|Recherche|Stichtag|verifiziert|geprüft|öffentlich\s+abrufbar|nicht\s+ermittelbar)\b',re.I)
try:
    edited=call_json(editorial_prompt,timeout=220,use_web=True)
    for key in ('title','lead','review','current_situation','outlook'):
        value=' '.join(str(edited.get(key,'')).split()).strip()
        if value and not banned.search(value):
            data[key]=value

    existing=[]
    seen_urls=set()
    for source in list(data.get('sources',[]))+list(edited.get('sources',[])):
        if not isinstance(source,dict):
            continue
        title=' '.join(str(source.get('title','')).split()).strip()
        url=str(source.get('url','')).strip()
        if not title or not url.startswith('http') or url in seen_urls:
            continue
        seen_urls.add(url)
        existing.append({'title':title,'url':url})
    if existing:
        data['sources']=existing
except Exception as exc:
    print('Vertiefter Redaktionsschritt übersprungen:',exc)

data['generated_at']=today.strftime('%d.%m.%Y %H:%M')
with open(REPORT_PATH,'w',encoding='utf-8') as f:
    json.dump(data,f,ensure_ascii=False,indent=2)
    f.write('\n')
