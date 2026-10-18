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
