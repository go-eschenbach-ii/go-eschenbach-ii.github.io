"""Create one-time in-app update news by comparing published and new reports."""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASELINE = Path(os.getenv('REPORT_BASELINE', '/tmp/report-before-update.json'))
REPORT = Path('data/report.json')
OUTPUT = Path('data/update-news.json')


def loaded(path):
    return json.loads(path.read_text(encoding='utf-8'))


def team_match(match):
    return any(re.search(r'\bFC\s+Eschenbach\s+II\b', str(match.get(k, '')), re.I) for k in ('home', 'away'))


def match_key(match):
    return tuple(str(match.get(k, '')).strip().casefold() for k in ('date', 'home', 'away'))


def score(match):
    a, b = match.get('home_goals'), match.get('away_goals')
    return (str(a), str(b)) if a is not None and b is not None else None


def match_name(match):
    return f"{match.get('home', '')} {match.get('home_goals')}:{match.get('away_goals')} {match.get('away', '')}".strip()


def upcoming_key(match):
    return tuple(str(match.get(k, '')).strip() for k in ('date', 'time', 'home', 'away'))


def next_match(report):
    matches = [m for m in report.get('upcoming_matches', []) if isinstance(m, dict) and team_match(m)]
    return matches[0] if matches else None


def changes(old, new):
    items = []
    old_results = {match_key(m): m for m in old.get('recent_results', []) if isinstance(m, dict)}
    fresh_results = [m for m in new.get('recent_results', []) if isinstance(m, dict)
                     and score(m) is not None and score(m) != score(old_results.get(match_key(m), {}))]
    team_results = [m for m in fresh_results if team_match(m)]
    for m in team_results[:1]:
        items.append('Neues Resultat: ' + match_name(m))

    prev, curr = old.get('eschenbach') or {}, new.get('eschenbach') or {}
    if any(prev.get(key) != curr.get(key) for key in ('rank', 'points')) and curr.get('rank') is not None:
        items.append(f"Eschenbach II: Rang {curr['rank']} mit {curr.get('points', '–')} Punkten.")
    elif old.get('standings') != new.get('standings'):
        items.append('Die Tabelle wurde aktualisiert.')

    old_scorers = {str(s.get('name', '')).strip().casefold(): s.get('goals')
                   for s in old.get('scorers', []) if isinstance(s, dict)}
    changed = [s for s in new.get('scorers', []) if isinstance(s, dict)
               and old_scorers.get(str(s.get('name', '')).strip().casefold()) != s.get('goals')]
    if changed:
        leading = ', '.join(f"{s.get('name', '')} ({s.get('goals', 0)})" for s in changed[:2])
        items.append('Torschützen aktualisiert: ' + leading + (' …' if len(changed) > 2 else '') + '.')

    old_next, new_next = next_match(old), next_match(new)
    if new_next and (not old_next or upcoming_key(new_next) != upcoming_key(old_next)):
        date_time = f"{new_next.get('date', '')} {new_next.get('time', '')}".strip()
        items.append(f"Nächstes Spiel: {new_next.get('home')} – {new_next.get('away')} ({date_time}).")

    if new.get('review', '').strip() != old.get('review', '').strip():
        items.append('Der Rückblick wurde erneuert.')
    elif new.get('outlook', '').strip() != old.get('outlook', '').strip():
        items.append('Der Ausblick auf die kommenden Spiele wurde erneuert.')

    if not team_results and fresh_results and len(items) < 3:
        items.append('Neue Ligaresultate: ' + match_name(fresh_results[0]) + '.')

    if new.get('title', '').strip() != old.get('title', '').strip() and len(items) < 4:
        items.append('Neuer Bericht: ' + str(new['title']).strip())

    if not items:
        items.append('Der Tagesbericht wurde überprüft und aktualisiert.')
    return items[:4]


def main():
    previous, current = loaded(BASELINE), loaded(REPORT)
    now = datetime.now(timezone.utc)
    news = {
        'id': (os.getenv('REQUEST_ID', '').strip() or str(current.get('generated_at', '')).strip() or now.isoformat())[:180],
        'report_version': str(current.get('generated_at', '')).strip(),
        'created_at': now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'expires_at': (now + timedelta(hours=72)).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'title': 'Das ist neu!',
        'items': changes(previous, current),
    }
    OUTPUT.write_text(json.dumps(news, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Update-Hinweis erstellt:', ' | '.join(news['items']))


if __name__ == '__main__':
    main()
