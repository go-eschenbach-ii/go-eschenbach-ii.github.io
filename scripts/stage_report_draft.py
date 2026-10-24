"""Stage a generated report in the private review queue. Never publish without admin approval."""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

request_id = os.environ.get('REQUEST_ID', '').strip()
secret = os.environ.get('COMMENTS_TOKEN', '').strip()
if not request_id or not secret:
    raise SystemExit('Missing workflow review credentials')

payload = {
    'action': 'submit',
    'request_id': request_id,
    'comments_token': secret,
    'base_generated_at': json.loads(
        Path('/tmp/report-before-update.json').read_text(encoding='utf-8')
    ).get('generated_at', ''),
    'report': json.loads(Path('data/report.json').read_text(encoding='utf-8')),
    'news': json.loads(Path('data/update-news.json').read_text(encoding='utf-8'))
}
# Verification evidence is collected by the official IFV-backed schedule
# synchroniser. Bind it to this private draft so a delayed public table does not
# invalidate a confirmed result when the administrator later approves it.
ledger_file = Path('data/ifv-verified-results.json')
verified = []
if ledger_file.exists():
    doc = json.loads(ledger_file.read_text(encoding='utf-8'))
    source = str(doc.get('source', ''))
    if source.startswith((
        'https://matchcenter.ifv.ch/',
        'https://www.fcschoetz.ch/de/club/teams/team/spielplan-gruppe/'
    )):
        for m in doc.get('matches', []):
            if isinstance(m, dict) and all(k in m for k in
                ('date', 'home', 'away', 'home_goals', 'away_goals')):
                verified.append({
                    'date': m['date'], 'home': m['home'], 'away': m['away'],
                    'home_goals': int(m['home_goals']),
                    'away_goals': int(m['away_goals']),
                })
payload['report']['official_verified_results'] = verified

req = urllib.request.Request(
    'https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/report-draft',
    data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
    method='POST',
    headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
)
try:
    with urllib.request.urlopen(req, timeout=45) as response:
        result = json.load(response)
except urllib.error.HTTPError as error:
    raise SystemExit(f'Entwurf konnte nicht gespeichert werden: HTTP {error.code}')
if not result.get('staged'):
    raise SystemExit('Entwurf wurde vom Server nicht bestätigt')
print('Berichtsentwurf gespeichert. Keine öffentliche Veröffentlichung vor der Freigabe.')
