import json, os, re, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

API_KEY=os.environ.get('OPENAI_API_KEY','').strip()
if not API_KEY:
    print('OPENAI_API_KEY fehlt – bestehender Bericht bleibt unverändert.')
    raise SystemExit(0)

today=datetime.now(ZoneInfo('Europe/Zurich'))
date_display=today.strftime('%d.%m.%Y')

previous_data={}
try:
    with open('data/report.json','r',encoding='utf-8') as f:
        previous_data=json.load(f)
except Exception:
    previous_data={}

match_comments=[]
comments_path=os.environ.get('MATCH_COMMENTS_FILE','').strip()
if comments_path:
    try:
        with open(comments_path,'r',encoding='utf-8') as f:
            raw_comments=json.load(f)
        if isinstance(raw_comments,list):
            for item in raw_comments:
                if not isinstance(item,dict):
                    continue
                transcript=' '.join(str(item.get('transcript','')).split()).strip()
                if not transcript:
                    continue
                match_comments.append({
                    'match_label':str(item.get('match_label','')).strip(),
                    'match_date':str(item.get('match_date','')).strip(),
                    'match_time':str(item.get('match_time','')).strip(),
                    'spoken_at':str(item.get('spoken_at','')).strip(),
                    'transcript':transcript
                })
    except Exception as exc:
        print('Matchkommentare konnten nicht eingelesen werden:',exc)


def call_json(prompt_text, timeout=180, use_web=False):
    payload={
        'model':'gpt-5.6-luna',
        'reasoning':{'effort':'low'},
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


def normalize_scorers(items):
    merged={}
    names={}
    for item in items or []:
        if not isinstance(item,dict):
            continue
        name=' '.join(str(item.get('name','')).split())
        if not name:
            continue
        try:
            goals=int(item.get('goals',0))
        except (TypeError,ValueError):
            continue
        if goals<=0:
            continue
        key=name.casefold()
        merged[key]=merged.get(key,0)+goals
        names.setdefault(key,name)
    result=[{'name':names[k],'goals':v} for k,v in merged.items()]
    result.sort(key=lambda x:(-x['goals'],x['name'].casefold()))
    return result


TABLE_FIELDS=('rank','played','wins','draws','losses','penalty_points','goals_for','goals_against','goal_difference','points')


def complete_standing_rows(rows):
    return sum(
        1 for row in rows or []
        if isinstance(row,dict) and row.get('team') and all(row.get(k) is not None for k in TABLE_FIELDS)
    )


def preserve_last_complete_table(data, previous):
    new_rows=data.get('standings') if isinstance(data.get('standings'),list) else []
    old_rows=previous.get('standings') if isinstance(previous.get('standings'),list) else []
    if complete_standing_rows(old_rows)>=8 and complete_standing_rows(new_rows)<8:
        data['standings']=old_rows
        esch=next((r for r in old_rows if r.get('is_eschenbach') or r.get('team')=='FC Eschenbach II'),None)
        if esch:
            target=data.setdefault('eschenbach',{})
            for key in TABLE_FIELDS:
                if esch.get(key) is not None:
                    target[key]=esch.get(key)
    return data


comment_context=json.dumps(match_comments,ensure_ascii=False) if match_comments else 'Keine eigenen Matchkommentare vorhanden.'

prompt=f'''Du bist Sportredaktor für den Schweizer Amateurfussball. Recherchiere mit Websuche die aktuelle Situation der IFV 5. Liga, Gruppe 4, Saison 2026/27. Fokus klar auf FC Eschenbach II.

Stichtag: {date_display} (Europe/Zurich).

RECHERCHE – VERBINDLICH:
1. Ermittle im offiziellen IFV Matchcenter die aktuelle Gruppenzusammensetzung, vollständige Tabelle, Resultate der letzten 7 Tage und Spiele der kommenden 14 Tage.
2. Übernimm für jedes Team Rang, Spiele, Siege, Unentschieden, Niederlagen, Strafpunkte, Tore erzielt, Tore erhalten, Tordifferenz und Punkte.
3. Prüfe die offiziellen Websites der Gruppenteams auf aktuelle Matchberichte, besonders beim letzten und nächsten Gegner von FC Eschenbach II.
4. Ergänze bei Bedarf seriöse lokale Quellen. Bei Widersprüchen haben IFV-Resultat- und Tabellendaten Vorrang.
5. Nichts erfinden. Torschützen, Spielverläufe oder andere Details nur verwenden, wenn sie eindeutig belegt sind.

EIGENE MATCHKOMMENTARE DES APP-REDAKTORS:
{comment_context}

Diese Kommentare sind persönliche Beobachtungen direkt vom Spiel. Wenn sie zu einem aktuellen Eschenbach-Spiel gehören, nutze sie für den spielerischen Verlauf, Chancen, Druckphasen, Stimmung oder andere beobachtete Eindrücke im Feld review. Resultat, Torschützen und Tabellenfakten müssen trotzdem mit den offiziellen Daten übereinstimmen. Bei einem Widerspruch haben die offiziellen Fakten Vorrang. Erwähne in der App nicht, dass die Informationen aus Sprachkommentaren stammen.

LESERTEXTE – BESONDERS WICHTIG:
Die Felder title, lead, review, current_situation und outlook werden direkt in der App angezeigt. Sie müssen wie ein kurzer, gut geschriebener Sportbericht klingen.
- Schreibe natürlich, knapp und verständlich. Keine bürokratische oder technische Sprache.
- In diesen fünf Feldern NIEMALS über Recherche, Quellen, Datenverfügbarkeit, Verifizierung oder technische Probleme sprechen.
- Dort keine Wörter oder Formulierungen wie IFV, Matchcenter, Quelle, Website, Datensatz, Recherche, Stichtag, verifiziert, geprüft, öffentlich abrufbar, verfügbar, nicht ermittelbar oder Rangliste nicht auslesbar verwenden.
- Wenn eine Information nicht sicher vorliegt, lasse sie einfach weg. Erkläre dem Leser nicht, warum sie fehlt.
- title: prägnant, sportlich, maximal ca. 70 Zeichen.
- lead: 2 kurze Sätze, Kernaussage zu Eschenbach II.
- review: 3–5 flüssige Sätze; bei vorhandenen eigenen Matchkommentaren darf der Rückblick 4–7 Sätze umfassen. Eschenbach II zuerst; nur relevante weitere Gruppenspiele erwähnen.
- current_situation: 3–4 Sätze zur Tabelle/Form, ohne Quellenhinweise.
- outlook: 2–4 Sätze, Schwerpunkt auf dem nächsten Spiel von Eschenbach II.
- Daten in lesefreundlicher Form schreiben, z. B. „am 12. September“ statt unnötig vieler technischer Datumsangaben.
- Quellen und technische Nachvollziehbarkeit gehören ausschliesslich in das Feld sources.

Antworte ausschliesslich als valides JSON in exakt dieser Struktur:
{{
  "report_date":"DD.MM.YYYY",
  "title":"...",
  "lead":"...",
  "review":"...",
  "current_situation":"...",
  "outlook":"...",
  "eschenbach":{{"rank":1,"played":0,"wins":0,"draws":0,"losses":0,"penalty_points":0,"goals_for":0,"goals_against":0,"goal_difference":0,"points":0,"form":"..."}},
  "recent_results":[{{"date":"DD.MM.YYYY","time":"","home":"...","away":"...","home_goals":0,"away_goals":0,"note":"..."}}],
  "standings":[{{"rank":1,"team":"...","played":0,"wins":0,"draws":0,"losses":0,"penalty_points":0,"goals_for":0,"goals_against":0,"goal_difference":0,"points":0,"is_eschenbach":false}}],
  "upcoming_matches":[{{"date":"DD.MM.YYYY","time":"HH:MM","home":"...","away":"...","note":"..."}}],
  "scorers":[],
  "scorer_note":"Die Saison-Torschützen werden separat geprüft.",
  "sources":[{{"title":"...","url":"https://..."}}]
}}
'''

data=call_json(prompt, timeout=180, use_web=True)
data=preserve_last_complete_table(data, previous_data)

expected_goals=int(data.get('eschenbach',{}).get('goals_for') or 0)
scorer_prompt=f'''Du bist Datenprüfer für Schweizer Amateurfussball. Ermittle die vollständige Saison-Torschützenliste von FC Eschenbach II in der IFV 5. Liga, Gruppe 4, Saison 2026/27 bis einschliesslich {date_display}.

VERBINDLICH:
1. Ermittle alle bereits ausgetragenen Meisterschaftsspiele von FC Eschenbach II. Keine Cup-, Test- oder Freundschaftsspiele.
2. Prüfe jedes Spiel einzeln und erfasse alle Eschenbacher Torschützen.
3. Eigentore des Gegners zugunsten von Eschenbach separat als own_goals zählen.
4. Falls nötig, prüfe zusätzlich offizielle Vereinsberichte zum exakt passenden Spiel.
5. Identische Spielernamen zusammenführen und Tore summieren.
6. Kontrollsumme: Spielertore plus own_goals muss exakt {expected_goals} ergeben.
7. Nichts schätzen oder erfinden. Wenn nicht vollständig, complete=false setzen.

Antworte ausschliesslich als valides JSON:
{{
  "complete":true,
  "expected_goals":{expected_goals},
  "own_goals":0,
  "scorers":[{{"name":"...","goals":1}}],
  "checked_matches":[{{"date":"DD.MM.YYYY","opponent":"...","result":"...","scorers":"...","own_goals":0}}],
  "note":"..."
}}
'''

audit=call_json(scorer_prompt, timeout=240, use_web=True)
audit_scorers=normalize_scorers(audit.get('scorers',[]))
try:
    own_goals=max(0,int(audit.get('own_goals',0) or 0))
except (TypeError,ValueError):
    own_goals=0
player_goals=sum(x['goals'] for x in audit_scorers)
accounted=player_goals+own_goals
complete=bool(audit.get('complete')) and accounted==expected_goals

if not complete and expected_goals>0:
    missing=expected_goals-accounted
    retry_prompt=f'''Prüfe die Saison-Torschützen von FC Eschenbach II nochmals vollständig. Die erste Prüfung hat {accounted} von {expected_goals} Meisterschaftstoren zugeordnet; Differenz: {missing}.

Bisheriges Audit:
{json.dumps(audit, ensure_ascii=False)}

Gehe jedes Meisterschaftsspiel erneut einzeln durch. Ergänze fehlende Torschützen oder Eigentore, ohne bereits verifizierte Tore doppelt zu zählen. Die Endsumme muss exakt {expected_goals} ergeben. Nichts erfinden.

Antworte ausschliesslich als valides JSON im selben Format:
{{"complete":true,"expected_goals":{expected_goals},"own_goals":0,"scorers":[{{"name":"...","goals":1}}],"checked_matches":[{{"date":"DD.MM.YYYY","opponent":"...","result":"...","scorers":"...","own_goals":0}}],"note":"..."}}
'''
    retry=call_json(retry_prompt, timeout=240, use_web=True)
    retry_scorers=normalize_scorers(retry.get('scorers',[]))
    try:
        retry_own=max(0,int(retry.get('own_goals',0) or 0))
    except (TypeError,ValueError):
        retry_own=0
    retry_total=sum(x['goals'] for x in retry_scorers)+retry_own
    if retry_total>=accounted:
        audit=retry
        audit_scorers=retry_scorers
        own_goals=retry_own
        player_goals=sum(x['goals'] for x in audit_scorers)
        accounted=retry_total
        complete=bool(retry.get('complete')) and accounted==expected_goals

data['scorers']=audit_scorers
data['own_goals']=own_goals
if complete:
    own_text=''
    if own_goals:
        own_text=f' plus {own_goals} Eigentor' + ('e' if own_goals!=1 else '') + ' zugunsten von Eschenbach'
    data['scorer_note']=f'{player_goals} Spielertore{own_text} ergeben {accounted} Saisontore.'
else:
    missing=max(0,expected_goals-accounted)
    data['scorer_note']=f'Verifiziert zugeordnet: {accounted} von {expected_goals} Toren; noch nicht eindeutig zuordenbar: {missing}.'

data['scorer_audit']={
    'complete':complete,
    'expected_goals':expected_goals,
    'player_goals':player_goals,
    'own_goals':own_goals,
    'accounted_goals':accounted,
    'checked_matches':audit.get('checked_matches',[])
}

draft_texts={k:data.get(k,'') for k in ('title','lead','review','current_situation','outlook')}
editorial_facts={
    'draft_texts':draft_texts,
    'eschenbach':data.get('eschenbach',{}),
    'recent_results':data.get('recent_results',[]),
    'standings':data.get('standings',[]),
    'upcoming_matches':data.get('upcoming_matches',[]),
    'scorer_audit':data.get('scorer_audit',{}),
    'admin_match_comments':match_comments
}
editorial_prompt=f'''Du bist Redaktor einer mobilen Fussball-App für Fans von FC Eschenbach II. Überarbeite ausschliesslich die fünf Lesertexte anhand der gelieferten Fakten.

FAKTENPAKET:
{json.dumps(editorial_facts, ensure_ascii=False)}

REGELN:
- Keine neuen Fakten erfinden.
- Sportlich, natürlich, kurz und angenehm lesbar.
- Kein Recherche- oder Quellenjargon.
- In keinem Feld Wörter/Begriffe wie IFV, Matchcenter, Quelle, Website, Datensatz, Recherche, Stichtag, verifiziert, geprüft, öffentlich abrufbar, verfügbar oder nicht ermittelbar.
- Wenn ein Fakt unsicher oder fehlend ist, nicht erwähnen und keine Erklärung dazu schreiben.
- Wenn admin_match_comments vorhanden sind und zum jüngsten Eschenbach-Spiel passen, bilden sie die wichtigste Grundlage für den erzählerischen Rückblick: Spielverlauf, Druckphasen, Chancen, Stimmung und beobachtete Eindrücke konkret und flüssig einarbeiten.
- Die Matchkommentare sind direkte Beobachtungen des App-Redaktors. Nicht als Zitate oder als „Kommentare“ kennzeichnen und den Autor nicht erwähnen.
- Resultat, Torschützen und Tabellenwerte aus den offiziellen Daten haben bei Widersprüchen Vorrang vor den Matchkommentaren.
- title maximal ca. 70 Zeichen.
- lead genau 2 kurze Sätze.
- review 3–5 Sätze; mit admin_match_comments 4–7 Sätze, Fokus Eschenbach II.
- current_situation 3–4 Sätze.
- outlook 2–4 Sätze, nächstes Eschenbach-Spiel im Zentrum.
- Keine abgebrochenen Sätze und keine Listen in den Textfeldern.

Antworte ausschliesslich als JSON:
{{"title":"...","lead":"...","review":"...","current_situation":"...","outlook":"..."}}
'''

try:
    edited=call_json(editorial_prompt, timeout=120, use_web=False)
    banned=re.compile(r'\b(?:IFV|Matchcenter|Quelle|Website|Datensatz|Recherche|Stichtag|verifiziert|geprüft|öffentlich\s+abrufbar|nicht\s+ermittelbar)\b',re.I)
    for key in ('title','lead','review','current_situation','outlook'):
        value=str(edited.get(key,'')).strip()
        if value and not banned.search(value):
            data[key]=value
except Exception as exc:
    print('Redaktionsschritt übersprungen:', exc)

data['report_date']=date_display
data['generated_at']=today.strftime('%d.%m.%Y %H:%M')

os.makedirs('data',exist_ok=True)
with open('data/report.json','w',encoding='utf-8') as f:
    json.dump(data,f,ensure_ascii=False,indent=2)
    f.write('\n')

print('Bericht aktualisiert:', date_display)
print('Matchkommentare verwendet:',len(match_comments))
print('Torschützen-Audit:', 'vollständig' if complete else 'unvollständig', f'({accounted}/{expected_goals})')
