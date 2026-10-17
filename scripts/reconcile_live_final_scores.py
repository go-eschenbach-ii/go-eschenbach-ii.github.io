"""Apply admin-confirmed Liveticker end results before a report is published."""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

PATH = Path('data/report.json')
API = 'https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/live-ticker'


def match_key(m):
    return '|'.join(str(m.get(k, '')).strip() for k in ('date', 'time', 'home', 'away'))


def result_key(m):
    return (str(m.get('date', '')), str(m.get('home', '')), str(m.get('away', '')))


def check_match(m, official):
    return (result_key(m) == result_key(official)
            and str(m.get('time', '')) == str(official.get('time', '')))


report = json.loads(PATH.read_text(encoding='utf-8'))
today = datetime.now(ZoneInfo('Europe/Zurich')).date()
candidates = {}
for group in ('recent_results', 'upcoming_matches'):
    for item in report.get(group, []):
        if not isinstance(item, dict) or 'FC Eschenbach II' not in (item.get('home'), item.get('away')):
            continue
        try:
            match_date = datetime.strptime(str(item.get('date', '')), '%d.%m.%Y').date()
        except ValueError:
            continue
        if today - timedelta(days=14) <= match_date <= today + timedelta(days=1):
            candidates[match_key(item)] = item

confirmed = {
    result_key(x): x for x in report.get('confirmed_live_scores', [])
    if isinstance(x, dict) and x.get('status') == 'finished'
}
changes = 0
for key, original in candidates.items():
    url = API + '?' + urllib.parse.urlencode({'match_key': key})
    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as response:
            payload = json.load(response)
    except Exception as exc:
        print('Live-Endstand derzeit nicht abrufbar:', exc)
        continue
    m = payload.get('match') or {}
    if m.get('status') != 'finished':
        continue
    live = {
        'date': str(m.get('match_date', '')).split('-')[::-1],
        'time': str(m.get('match_time', '')),
        'home': str(m.get('home', '')),
        'away': str(m.get('away', '')),
    }
    live['date'] = '.'.join(live['date'])
    if not check_match(original, live):
        continue
    try:
        hg, ag = int(m.get('home_goals')), int(m.get('away_goals'))
        if not 0 <= hg <= 40 or not 0 <= ag <= 40:
            continue
    except (TypeError, ValueError):
        continue
    live.update({'home_goals': hg, 'away_goals': ag, 'status': 'finished', 'verified_by': 'admin_liveticker'})
    confirmed[result_key(live)] = live
    results = report.setdefault('recent_results', [])
    old = next((x for x in results if isinstance(x, dict) and result_key(x) == result_key(live)), None)
    if old is None:
        results.append(dict(original, home_goals=hg, away_goals=ag))
        changes += 1
    elif (old.get('home_goals'), old.get('away_goals')) != (hg, ag):
        print('Falsches Resultat ersetzt:', key, '->', hg, ag)
        old['home_goals'], old['away_goals'] = hg, ag
        changes += 1

if confirmed:
    report['confirmed_live_scores'] = list(confirmed.values())
    known = {result_key(item) for item in report.get('recent_results', []) if isinstance(item, dict)}
    report['upcoming_matches'] = [
        item for item in report.get('upcoming_matches', [])
        if result_key(item) not in known
    ]
    report['recent_results'].sort(
        key=lambda m: (datetime.strptime(m['date'], '%d.%m.%Y'), str(m.get('time', ''))),
        reverse=True,
    )
    PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(confirmed)} bestätigte Liveticker-Endstände, {changes} Resultatkorrekturen.')
