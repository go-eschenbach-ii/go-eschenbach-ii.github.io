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
    """Only report specific, verifiable differences, never generic update status."""
    items = []

    old_results = {
        match_key(m): m for m in old.get('recent_results', [])
        if isinstance(m, dict)
    }
    fresh_results = [
        m for m in new.get('recent_results', []) if isinstance(m, dict)
        and score(m) is not None
        and score(m) != score(old_results.get(match_key(m), {}))
    ]
    # Prefer Eschenbach matches, then the newest other group results.
    fresh_results.sort(
        key=lambda m: (
            team_match(m),
            str(m.get('date', '')).split('.')[::-1],
            str(m.get('time', ''))
        ),
        reverse=True,
    )
    for m in fresh_results[:2]:
        items.append(
            f"{m.get('home', '')} – {m.get('away', '')}: "
            f"{m.get('home_goals')}:{m.get('away_goals')}."
        )

    old_table = {
        str(r.get('team', '')).strip(): r
        for r in old.get('standings', []) if isinstance(r, dict)
    }
    new_table = [
        r for r in new.get('standings', []) if isinstance(r, dict)
    ]
    # The local team's change of rank is always important, including
    # updates without a newly written match report. Put it first so it
    # cannot be cut by the four-item limit of the Neuigkeiten banner.
    def rank_of_eschenbach(report):
        team = next(
            (r for r in report.get('standings', [])
             if isinstance(r, dict)
             and (r.get('is_eschenbach') is True
                  or str(r.get('team', '')).strip().casefold() == 'fc eschenbach ii')),
            None,
        )
        raw = (team or {}).get('rank')
        if raw is None:
            raw = (report.get('eschenbach') or {}).get('rank')
        try:
            rank = int(raw)
            return rank if rank > 0 else None
        except (ValueError, TypeError):
            return None

    previous_rank = rank_of_eschenbach(old)
    current_rank = rank_of_eschenbach(new)
    eschenbach_rank_changed = (
        previous_rank is not None and current_rank is not None
        and previous_rank != current_rank
    )
    if eschenbach_rank_changed:
        direction = 'vorgerückt' if current_rank < previous_rank else 'zurückgefallen'
        items.insert(
            0,
            f"Eschenbach II ist in der Rangliste von Rang {previous_rank} "
            f"auf Rang {current_rank} {direction}.",
        )

    moved = [
        r for r in new_table
        if r.get('team') in old_table
        and str(r.get('team', '')).strip().casefold() != 'fc eschenbach ii'
        and r.get('rank') is not None
        and old_table[r['team']].get('rank') is not None
        and old_table[r['team']].get('rank') != r.get('rank')
    ]
    moved.sort(
        key=lambda r: abs(int(old_table[r['team']]['rank']) - int(r['rank'])),
        reverse=True,
    )
    if moved:
        snippets = [f"{r['team']} neu Rang {r['rank']}" for r in moved[:2]]
        items.append('Rangliste: ' + ', '.join(snippets) + '.')
    elif not eschenbach_rank_changed:
        prev, curr = old.get('eschenbach') or {}, new.get('eschenbach') or {}
        if (
            prev.get('points') is not None
            and curr.get('points') is not None
            and prev.get('points') != curr.get('points')
        ):
            items.append(f"Eschenbach II hat neu {curr['points']} Punkte.")

    old_scorers = {
        str(s.get('name', '')).strip().casefold(): s.get('goals')
        for s in old.get('scorers', []) if isinstance(s, dict)
    }
    changed_scorers = [
        s for s in new.get('scorers', []) if isinstance(s, dict)
        and old_scorers.get(str(s.get('name', '')).strip().casefold()) != s.get('goals')
    ]
    if changed_scorers:
        snippets = [
            f"{s.get('name', '')}: {s.get('goals', 0)} Tore"
            for s in changed_scorers[:2]
        ]
        items.append('Torschützen: ' + ', '.join(snippets) + '.')

    old_next, new_next = next_match(old), next_match(new)
    if new_next and (not old_next or upcoming_key(new_next) != upcoming_key(old_next)):
        date_time = f"{new_next.get('date', '')} {new_next.get('time', '')}".strip()
        items.append(
            f"Nächstes Eschenbach-Spiel: "
            f"{new_next.get('home')} – {new_next.get('away')} ({date_time})."
        )
    else:
        old_fixtures = {
            match_key(m) for m in old.get('upcoming_matches', [])
            if isinstance(m, dict)
        }
        additions = [
            m for m in new.get('upcoming_matches', [])
            if isinstance(m, dict) and match_key(m) not in old_fixtures
        ]
        if additions:
            m = additions[0]
            date_time = f"{m.get('date', '')} {m.get('time', '')}".strip()
            items.append(
                f"Neues Spiel: {m.get('home', '')} – {m.get('away', '')} "
                f"({date_time})."
            )

    # No news banner if the report contains only wording changes,
    # verifications, timestamps or another update without concrete news.
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
