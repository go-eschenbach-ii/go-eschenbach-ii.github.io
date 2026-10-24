"""Required fresh IFV source audit for EVERY update (article and data-only).

Refuse to stage a draft if current-run authoritative rankings AND fixtures /
results have not both been fetched and parsed successfully.
"""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

REPORT=Path('data/report.json')
START=Path(os.environ.get('IFV_UPDATE_START_FILE','/tmp/ifv-update-started-at.txt'))
FIELDS=('rank','played','wins','draws','losses','penalty_points',
        'goals_for','goals_against','goal_difference','points')

def dt(value):
    return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)

def source_valid(value,kind):
    url=urlparse(str(value or ''))
    if url.scheme!='https':
        return False
    if url.hostname=='matchcenter.ifv.ch':
        return True
    if url.hostname=='club.football.ch':
        return (kind=='schedule' and 'tab=3396' in url.query)
    if url.hostname=='www.fcschoetz.ch':
        return (('spielplan-gruppe' in url.path) if kind=='schedule'
                else ('resultate-und-rangliste' in url.path
                      or ('tab=3410' in url.query and url.path=='/')))
    return False

def main():
    report=json.loads(REPORT.read_text(encoding='utf-8'))
    if not START.exists():
        raise RuntimeError('IFV-Pflichtprüfung: Startzeit dieses Updates fehlt.')
    start=dt(START.read_text(encoding='utf-8').strip())
    now=datetime.now(timezone.utc)
    if start>now+timedelta(minutes=2) or start<now-timedelta(hours=2):
        raise RuntimeError('IFV-Pflichtprüfung: unplausibler Abfragestart.')

    for key,kind in [('standings','table'),('schedule','schedule')]:
        if report.get(key+'_sync_status')!='verified':
            raise RuntimeError('IFV-Pflichtprüfung: '+key+' wurde nicht frisch bestätigt.')
        src=report.get(key+'_sync_source')
        if not source_valid(src,kind):
            raise RuntimeError('IFV-Pflichtprüfung: unzulässige Quelle für '+key+': '+str(src))
        raw=report.get(key+'_sync_at')
        if not raw:
            raise RuntimeError('IFV-Pflichtprüfung: '+key+' hat keinen Abfragezeitpunkt.')
        fetched=dt(raw)
        if fetched<start-timedelta(seconds=60) or fetched>now+timedelta(minutes=2):
            raise RuntimeError('IFV-Pflichtprüfung: '+key+' stammt nicht aus diesem Update.')
    standings=report.get('standings')
    if not isinstance(standings,list) or len(standings)!=10:
        raise RuntimeError('IFV-Pflichtprüfung: keine vollständige 10er-Tabelle.')
    teams=set()
    for rank,row in enumerate(standings,1):
        if not isinstance(row,dict) or row.get('rank')!=rank:
            raise RuntimeError('IFV-Pflichtprüfung: Original-Rangfolge unvollständig.')
        team=row.get('team')
        if not team or team in teams:
            raise RuntimeError('IFV-Pflichtprüfung: doppelte oder fehlende Mannschaft.')
        teams.add(team)
        try:
            nums={k:int(row[k]) for k in FIELDS}
        except (ValueError,TypeError,KeyError) as exc:
            raise RuntimeError('IFV-Pflichtprüfung: nicht alle Originalspalten vorhanden.') from exc
        if nums['played']!=nums['wins']+nums['draws']+nums['losses']:
            raise RuntimeError('IFV-Pflichtprüfung: gespielte Partien passen nicht zur Tabelle.')
        if nums['goals_for']-nums['goals_against']!=nums['goal_difference']:
            raise RuntimeError('IFV-Pflichtprüfung: Torverhältnis widersprüchlich.')
    if 'FC Eschenbach II' not in teams:
        raise RuntimeError('IFV-Pflichtprüfung: Eschenbach fehlt in der Tabelle.')

    results=report.get('recent_results',[])
    upcoming=report.get('upcoming_matches',[])
    if not isinstance(results,list) or not isinstance(upcoming,list):
        raise RuntimeError('IFV-Pflichtprüfung: Resultate oder Spielplan fehlen.')
    match_keys=set()
    for match in results:
        if not isinstance(match,dict):
            raise RuntimeError('IFV-Pflichtprüfung: ungültiger Resultateintrag.')
        if match.get('home') not in teams or match.get('away') not in teams:
            raise RuntimeError('IFV-Pflichtprüfung: fremde Mannschaft bei den Resultaten.')
        k=(match.get('date'),match.get('home'),match.get('away'))
        if k in match_keys:
            raise RuntimeError('IFV-Pflichtprüfung: doppelte Resultate.')
        match_keys.add(k)
    for match in upcoming:
        if not isinstance(match,dict) or match.get('home') not in teams or match.get('away') not in teams:
            raise RuntimeError('IFV-Pflichtprüfung: fremde oder ungültige Partie im Spielplan.')
        if (match.get('date'),match.get('home'),match.get('away')) in match_keys:
            raise RuntimeError('IFV-Pflichtprüfung: Partie zugleich als gespielt und ausstehend gelistet.')
    print('IFV-Pflichtprüfung bestanden: offizielle 10er-Rangliste und '
          f'Spielplan/Resultate frisch konsultiert. Quellen: '
          f"{report.get('standings_sync_source')} | {report.get('schedule_sync_source')}")

if __name__=='__main__':
    main()
