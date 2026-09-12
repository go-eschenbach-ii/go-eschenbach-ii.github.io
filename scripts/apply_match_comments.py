import json, os, re, urllib.request

REPORT_PATH='data/report.json'
COMMENTS_PATH=os.environ.get('MATCH_COMMENTS_FILE','/tmp/go-eschenbach-match-comments.json').strip()
API_KEY=os.environ.get('OPENAI_API_KEY','').strip()

if not API_KEY:
    print('OPENAI_API_KEY fehlt – Matchkommentare werden nicht nachbearbeitet.')
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
    raise SystemExit(0)

if not comments:
    print('Keine Matchkommentare vorhanden – Rückblick bleibt unverändert.')
    raise SystemExit(0)

facts={
    'existing_review':data.get('review',''),
    'eschenbach':data.get('eschenbach',{}),
    'recent_results':data.get('recent_results',[]),
    'standings':data.get('standings',[]),
    'scorers':data.get('scorers',[]),
    'own_goals':data.get('own_goals',0),
    'match_comments':comments
}

prompt=f'''Du bist Redaktor einer mobilen Fussball-App für FC Eschenbach II. Überarbeite NUR den bestehenden Rückblick und arbeite die direkten Beobachtungen des App-Redaktors aus den Matchkommentaren sinnvoll ein.

FAKTENPAKET:
{json.dumps(facts,ensure_ascii=False)}

VERBINDLICH:
- Nutze nur Matchkommentare, die anhand Datum oder Spielbezeichnung klar zu einem aktuellen Spiel von FC Eschenbach II gehören.
- Die Matchkommentare sind direkte Beobachtungen vom Spiel und sollen im Rückblick erkennbar verarbeitet werden: Spielverlauf, Druckphasen, Chancen, Stimmung und andere tatsächlich genannte Eindrücke.
- Gib die Kommentare nicht als Zitate wieder und erwähne weder den Autor noch das Wort «Kommentar».
- Resultat, Torschützen und Tabellenwerte aus recent_results, scorers und standings haben bei Widersprüchen Vorrang.
- Erfinde keine zusätzlichen Chancen, Tore, Torschützen, taktischen Details oder Ereignisse.
- Falls kein Kommentar eindeutig zu einem aktuellen Eschenbach-Spiel passt, gib den bestehenden Rückblick unverändert zurück.
- Schweizer Rechtschreibung, sportlich, natürlich und gut lesbar.
- 5 bis 8 Sätze. Keine Listen und kein Quellen- oder Recherchejargon.

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
        print(f'Matchkommentare endgültig in Rückblick eingearbeitet: {len(comments)}')
    else:
        print('Nachbearbeitung lieferte keinen Rückblick – bestehender Text bleibt.')
except Exception as exc:
    print('Matchkommentar-Nachbearbeitung übersprungen:',exc)
