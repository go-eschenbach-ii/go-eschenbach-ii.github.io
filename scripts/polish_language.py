import json, os, re, urllib.request

REPORT_PATH='data/report.json'
API_KEY=os.environ.get('OPENAI_API_KEY','').strip()

if not API_KEY:
    print('OPENAI_API_KEY fehlt – sprachliche Schlussredaktion wird übersprungen.')
    raise SystemExit(0)

try:
    with open(REPORT_PATH,'r',encoding='utf-8') as f:
        data=json.load(f)
except Exception as exc:
    print('Bericht konnte nicht geladen werden:',exc)
    raise SystemExit(0)

keys=('title','lead','review','current_situation','outlook')
texts={k:' '.join(str(data.get(k,'')).split()).strip() for k in keys}

facts={
    'eschenbach':data.get('eschenbach',{}),
    'recent_results':data.get('recent_results',[]),
    'standings':data.get('standings',[]),
    'upcoming_matches':data.get('upcoming_matches',[]),
    'scorers':data.get('scorers',[]),
    'own_goals':data.get('own_goals',0)
}

prompt=f'''Du bist die sprachliche Schlussredaktion einer Schweizer Fussball-App. Korrigiere AUSSCHLIESSLICH Sprache und Stil der fünf vorhandenen Lesertexte. Inhalt und Fakten dürfen nicht verändert, ergänzt, gestrichen oder neu interpretiert werden.

AKTUELLE TEXTE:
{json.dumps(texts,ensure_ascii=False)}

FAKTEN ZUR KONTROLLE – NICHT ZUM ERWEITERN:
{json.dumps(facts,ensure_ascii=False)}

VERBINDLICHE SPRACHREGELN:
- Schweizer Rechtschreibung.
- Grammatik, Kasus, Kongruenz, Zeichensetzung und Satzbau müssen fehlerfrei sein.
- Jeder Satz muss auch semantisch logisch und idiomatisch klingen. Verb und Objekt müssen natürlich zusammenpassen.
- Vermeide unpassende Bilder und schiefe Formulierungen. Beispiel: Nicht «Zuschauer sahen einen unterhaltsamen Abend», sondern je nach vorhandener Aussage «Zuschauer verfolgten ein unterhaltsames Spiel» oder eine gleichwertig natürliche Formulierung.
- Schreibe wie ein guter lokaler Sportredaktor: klar, flüssig, präzise, ungekünstelt.
- Keine unnötig komplizierten Sätze, keine Wortwiederholungen und keine gestelzten Wendungen.
- Keine neuen Fakten, keine zusätzlichen Namen, keine neuen Wertungen, keine neue Dramatisierung.
- Zahlen, Resultate, Namen, Daten und Aussagen inhaltlich unverändert lassen.
- Die ungefähre Länge und Funktion jedes Feldes beibehalten.
- Der Spielername lautet Gürber, niemals Gerber.

Antworte ausschliesslich als valides JSON:
{{"title":"...","lead":"...","review":"...","current_situation":"...","outlook":"..."}}
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
    changed=[]
    for key in keys:
        value=' '.join(str(edited.get(key,'')).split()).strip()
        if not value:
            continue
        value=re.sub(r'\bGerber\b','Gürber',value)
        if value!=texts[key]:
            data[key]=value
            changed.append(key)
    if changed:
        with open(REPORT_PATH,'w',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2)
            f.write('\n')
        print('Sprachliche Schlussredaktion angewendet:', ', '.join(changed))
    else:
        print('Sprachliche Schlussredaktion: keine Änderungen nötig.')
except Exception as exc:
    print('Sprachliche Schlussredaktion übersprungen:',exc)
