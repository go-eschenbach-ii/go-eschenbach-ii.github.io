import json, os, re, urllib.request

REPORT_PATH='data/report.json'
COMMENTS_PATH=os.environ.get('MATCH_COMMENTS_FILE','/tmp/go-eschenbach-match-comments.json').strip()
API_KEY=os.environ.get('OPENAI_API_KEY','').strip()

if not API_KEY:
    print('OPENAI_API_KEY fehlt – Schlussredaktion des Rückblicks wird übersprungen.')
    raise SystemExit(0)

try:
    with open(REPORT_PATH,'r',encoding='utf-8') as f:
        data=json.load(f)
except Exception as exc:
    print('Bericht konnte nicht geladen werden:',exc)
    raise SystemExit(0)

comments=[]
try:
    with open(COMMENTS_PATH,'r',encoding='utf-8') as f:
        raw=json.load(f)
    if isinstance(raw,list):
        for item in raw:
            if not isinstance(item,dict):
                continue
            transcript=' '.join(str(item.get('transcript','')).split()).strip()
            if not transcript:
                continue
            comments.append({
                'match_label':' '.join(str(item.get('match_label','')).split()).strip(),
                'match_date':' '.join(str(item.get('match_date','')).split()).strip(),
                'match_time':' '.join(str(item.get('match_time','')).split()).strip(),
                'spoken_at':' '.join(str(item.get('spoken_at','')).split()).strip(),
                'transcript':transcript
            })
except Exception as exc:
    print('Matchkommentare konnten nicht geladen werden:',exc)


def is_eschenbach_match(item):
    if not isinstance(item,dict):
        return False
    return item.get('home')=='FC Eschenbach II' or item.get('away')=='FC Eschenbach II'


# Entscheidend: Für den Rückblick dürfen nur Resultate als Eschenbach-Spiele gelten,
# in denen FC Eschenbach II tatsächlich als Heim- oder Auswärtsteam vorkommt.
eschenbach_results=[r for r in data.get('recent_results',[]) if is_eschenbach_match(r)]

facts={
    'season_summary':data.get('eschenbach',{}),
    'eschenbach_results':eschenbach_results,
    'standings':data.get('standings',[]),
    'match_comments':comments
}

prompt=f'''Du bist Redaktor einer mobilen Fussball-App für FC Eschenbach II. Schreibe NUR den Rückblick neu.

FAKTENPAKET:
{json.dumps(facts,ensure_ascii=False)}

VERBINDLICH – KEINE AUSNAHMEN:
- Ein Gegner darf nur dann als bereits gespielter Gegner von FC Eschenbach II bezeichnet werden, wenn die entsprechende Partie ausdrücklich in eschenbach_results steht.
- Resultate anderer Ligaspiele und die Rangliste dürfen NIEMALS verwendet werden, um frühere Gegner von Eschenbach zu erraten oder abzuleiten.
- Behaupte insbesondere keine Begegnung zwischen Eschenbach und einem Team, nur weil dieses Team in standings oder in einem anderen recent_result vorkommt.
- Der Schwerpunkt liegt auf dem jüngsten Eintrag in eschenbach_results.
- Wenn match_comments zu diesem Spiel vorhanden sind, sind sie direkte Beobachtungen vom Platz und müssen den erzählerischen Rückblick prägen: Spielverlauf, Druckphasen, Chancen, Aluminiumtreffer, auffällige Leistungen und Stimmung nur soweit tatsächlich genannt.
- Gib Matchkommentare nicht als Zitate wieder und erwähne weder den Autor noch das Wort «Kommentar».
- Offizielles Resultat aus eschenbach_results hat Vorrang. Bei Torschützennamen aus der Spracherkennung nur eindeutig verständliche Namen verwenden; bei Unsicherheit den Namen weglassen statt raten.
- Erfinde keine zusätzlichen Chancen, Tore, Torschützen, taktischen Details, Ursachen oder früheren Partien.
- Saisonwerte wie Anzahl Siege, Tore oder Punkte dürfen aus season_summary genannt werden, ohne daraus unbekannte Gegner abzuleiten.
- Schweizer Rechtschreibung, sportlich, natürlich und gut lesbar.
- 6 bis 9 Sätze. Keine Listen und kein Quellen- oder Recherchejargon.

Antworte ausschliesslich als valides JSON:
{{"review":"..."}}
'''

payload={
    'model':'gpt-5.6-luna',
    'reasoning':{'effort':'medium'},
    'input':prompt
}
req=urllib.request.Request(
    'https://api.openai.com/v1/responses',
    data=json.dumps(payload).encode('utf-8'),
    headers={'Authorization':f'Bearer {API_KEY}','Content-Type':'application/json'},
    method='POST'
)

try:
    with urllib.request.urlopen(req,timeout=140) as r:
        response=json.loads(r.read().decode('utf-8'))
    text=response.get('output_text','').strip()
    if not text:
        parts=[]
        for item in response.get('output',[]):
            if not isinstance(item,dict):
                continue
            for c in item.get('content',[]):
                if isinstance(c,dict) and c.get('type') in ('output_text','text'):
                    parts.append(c.get('text',''))
        text=''.join(parts).strip()
    if text.startswith('```'):
        text=re.sub(r'^```(?:json)?\s*|\s*```$','',text,flags=re.S).strip()
    edited=json.loads(text)
    review=' '.join(str(edited.get('review','')).split()).strip()
    if review:
        data['review']=review
        with open(REPORT_PATH,'w',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2)
            f.write('\n')
        print(f'Sicherer Rückblick erstellt: {len(eschenbach_results)} echte Eschenbach-Resultate, {len(comments)} Matchkommentare.')
    else:
        print('Schlussredaktion lieferte keinen Rückblick – bestehender Text bleibt.')
except Exception as exc:
    print('Rückblick-Schlussredaktion übersprungen:',exc)
