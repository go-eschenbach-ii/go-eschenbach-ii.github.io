"""Make the five reader-facing report sections consistent with official match facts.

Runs AFTER official IFV standings and completed results have been locked, and
BEFORE a draft is staged. Does not invent match events or player attribution.
Never touches review_cycle / hearts or the published article.
"""
import json
import re
from datetime import datetime
from pathlib import Path

PATH=Path('data/report.json')
TEAM='FC Eschenbach II'

def date_of(match):
    try:
        return datetime.strptime(str(match.get('date',''))+' '+str(match.get('time','00:00') or '00:00'),'%d.%m.%Y %H:%M')
    except (ValueError,TypeError):
        return datetime.min

def fact_title(match):
    home=match['home']==TEAM
    gf=int(match['home_goals'] if home else match['away_goals'])
    ga=int(match['away_goals'] if home else match['home_goals'])
    other=match['away'] if home else match['home']
    at='gegen' if home else 'bei'
    if gf>ga:
        return f'Eschenbach II gewinnt {gf}:{ga} {at} {other}'
    if gf<ga:
        return f'Eschenbach II verliert {gf}:{ga} {at} {other}'
    return f'Eschenbach II spielt {gf}:{ga} {at} {other}'

def sentence_score(match):
    home=match['home']==TEAM
    gf=int(match['home_goals'] if home else match['away_goals'])
    ga=int(match['away_goals'] if home else match['home_goals'])
    other=match['away'] if home else match['home']
    place='Heimspiel gegen' if home else 'Auswärtsspiel bei'
    verb='gewinnt' if gf>ga else ('verliert' if gf<ga else 'spielt remis')
    return f'Eschenbach II {verb} das {place} {other} mit {gf}:{ga}.'

def main():
    d=json.loads(PATH.read_text(encoding='utf-8'))
    standings=d.get('standings') or []
    latest=[m for m in d.get('recent_results',[])
            if isinstance(m,dict) and TEAM in (m.get('home'),m.get('away'))
            and m.get('home_goals') is not None and m.get('away_goals') is not None]
    if not latest:
        raise RuntimeError('Kein bestätigtes Eschenbach-Ergebnis: Bericht nicht freigeben.')
    match=max(latest,key=date_of)
    row=next((x for x in standings if x.get('team')==TEAM),None)
    if (not row or len(standings)!=10 or sorted(int(x.get('rank',0)) for x in standings)!=list(range(1,11))):
        raise RuntimeError('Unvollständige offizielle Tabelle: Bericht nicht freigeben.')
    try:
        row={**row,**{k:int(row[k]) for k in (
            'rank','played','wins','draws','losses','points','goals_for','goals_against','goal_difference'
        )}}
        gf=int(match['home_goals'] if match['home']==TEAM else match['away_goals'])
        ga=int(match['away_goals'] if match['home']==TEAM else match['home_goals'])
    except (ValueError,TypeError,KeyError) as e:
        raise RuntimeError('Ungültiger IFV-Spielstand oder Tabellenwert') from e
    if row['played']!=row['wins']+row['draws']+row['losses']:
        raise RuntimeError('IFV-Tabelle ist widersprüchlich')
    # An IFV table may temporarily be behind an already finished game.
    # Never rewrite text against a stale table.
    table_is_current=(row['played']>=1 and
        date_of(match).date()<=datetime.now().date())
    if not table_is_current:
        raise RuntimeError('IFV-Tabelle oder Matchdatum für Bericht nicht plausibel')

    d['title']=fact_title(match)
    lead=(f"{sentence_score(match)} Nach {row['played']} Spielen belegt die Mannschaft "
          f"mit {row['points']} Punkten und {row['goals_for']}:{row['goals_against']} Toren "
          f"Rang {row['rank']}.")
    d['lead']=lead

    rivals=[x for x in sorted(standings,key=lambda x:int(x['rank'])) if x['team']!=TEAM][:2]
    rivals_note=' '.join(
        f"{x['team']} folgt auf Rang {x['rank']} mit {x['points']} Punkten aus {x['played']} Spielen."
        for x in rivals
    )
    record=(f"{row['wins']} Siege, {row['draws']} Unentschieden und "
            f"{row['losses']} Niederlagen")
    d['current_situation']=(
        f"Eschenbach II steht mit {row['points']} Punkten aus {row['played']} Spielen "
        f"auf Rang {row['rank']}. Die Bilanz: {record} bei "
        f"{row['goals_for']}:{row['goals_against']} Toren "
        f"(Tordifferenz {row['goal_difference']:+d}). {rivals_note}"
    )

    # Next team fixture, not the next group fixture; a past match is excluded.
    upcoming=sorted((x for x in d.get('upcoming_matches',[])
                     if isinstance(x,dict) and TEAM in (x.get('home'),x.get('away'))
                     and date_of(x)>date_of(match)),key=date_of)
    if upcoming:
        next_match=upcoming[0]
        day=next_match.get('date')
        hour=next_match.get('time')
        opposition=next_match['away'] if next_match['home']==TEAM else next_match['home']
        venue='zu Hause gegen' if next_match['home']==TEAM else 'auswärts bei'
        d['outlook']=(f"Nach dem {gf}:{ga} gegen {match['away'] if match['home']==TEAM else match['home']} "
            f"bereitet sich Eschenbach II auf das nächste Meisterschaftsspiel vor. "
            f"Am {day}" + (f" um {hour} Uhr" if hour else "") +
            f" trifft die Mannschaft {venue} {opposition} an.")
    else:
        d['outlook']=(
            "Mit diesem Spiel hat Eschenbach II seinen letzten aktuell erfassten "
            "Meisterschaftsauftritt absolviert. Der Blick richtet sich nun auf "
            "die nächsten Aufgaben. Mit "
            f"{row['points']} Punkten auf Rang {row['rank']} "
            "nimmt die Mannschaft viel Selbstvertrauen mit."
        )

    review=str(d.get('review','')).strip()
    if not review:
        raise RuntimeError('Rückblick fehlt; kein Entwurf ohne Text')
    score=f'{gf}:{ga}'
    # If the review does not discuss the latest match at all, block staging.
    other=match['away'] if match['home']==TEAM else match['home']
    if other.casefold() not in review.casefold() or score not in review:
        raise RuntimeError('Rückblick behandelt nicht das neueste Eschenbach-Spiel.')

    # Replace trailing legacy table recap, without altering match observations.
    # Old copy from the previous game often survives when the review itself
    # was edited from eyewitness notes after the original draft was produced.
    stale_tail=re.compile(
        r'(?:(?:Eschenbach|Die Mannschaft|Das Team)\s+'
        r'(?:beendet|steht|bleibt|liegt|führt)[^.]*'
        r'(?:\b(?:Punkten|Spielen|Siegen|Niederlagen|Tabellenspitze|Rang)\b)[^.]*\.)'
        r'\s*$',re.IGNORECASE
    )
    review=stale_tail.sub('',review).strip()
    closing=(f"Nach {row['played']} Spielen weist Eschenbach II "
             f"{record} auf und steht mit {row['points']} Punkten "
             f"und {row['goals_for']}:{row['goals_against']} Toren "
             f"auf Rang {row['rank']}.")
    if closing not in review:
        review=review.rstrip()+(' ' if review else '')+closing
    d['review']=review
    d['editorial_fact_check']={
        'date':match.get('date'),'home':match['home'],'away':match['away'],
        'home_goals':int(match['home_goals']),'away_goals':int(match['away_goals']),
        'rank':row['rank'],'played':row['played'],'points':row['points'],
        'table_source':d.get('standings_sync_source'),
        'status':'match_and_table_aligned'
    }
    PATH.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"Berichtslogik geprüft: {match['home']} {match['home_goals']}:{match['away_goals']} {match['away']}; Rang {row['rank']}; {row['points']} Punkte")

if __name__=='__main__':
    main()
