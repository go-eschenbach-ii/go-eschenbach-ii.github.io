"""Deterministic FC Eschenbach II goal-scorer totals, keyed by match.

Official IFV scorers override report scorers for the SAME match. A match is
counted only once, irrespective of how often an update is regenerated.

The legacy rollup is a frozen count from before match-based tracking. Historical
matches already covered by that rollup may not be added again. IFV corrections
to such games require a known historical attribution; without one the code
preserves totals and marks them for review, rather than inventing a deduction.
"""
import json
import os
import re
from collections import defaultdict
from pathlib import Path

PATH=Path('data/report.json')
BASE=Path(os.environ.get('REPORT_BASELINE','/tmp/report-before-update.json'))
OFFICIAL=Path('data/ifv-match-scorers.json')
TEAM='FC Eschenbach II'

def nice(x):
    return ' '.join(str(x or '').strip().split())

def match_key(date,opponent):
    return nice(date)+'|'+nice(opponent).casefold()

def names_map(*sources):
    found={}
    for source in sources:
        for item in source or []:
            if isinstance(item,dict):
                name=nice(item.get('name'))
                if name:found[name.casefold()]=name
    return found

def canonical(name,known):
    name=nice(name)
    if not name:return ''
    if name.casefold() in known:return known[name.casefold()]
    # Match common documented variations without creating new people.
    for full in known.values():
        a=name.casefold().split()
        b=full.casefold().split()
        if len(a)>=2 and len(b)>=2 and a[0]==b[0] and b[-1] in a:
            return full
    if len(name.split())==1:
        opts=[full for full in known.values() if full.casefold().split()[-1]==name.casefold()]
        if len(opts)==1:return opts[0]
    return name

def scorer_rows(raw,known):
    if not isinstance(raw,list):return []
    counts=defaultdict(int)
    labels={}
    for item in raw:
        if not isinstance(item,dict):continue
        name=canonical(item.get('name'),known)
        if not name or 'forfait' in name.casefold():continue
        try:goals=int(item.get('goals',0))
        except (ValueError,TypeError):continue
        if goals<=0 or goals>30:continue
        k=name.casefold()
        counts[k]+=goals
        labels[k]=name
    return [{'name':labels[k],'goals':n} for k,n in sorted(counts.items()) if n>0]

def from_checked_text(value,known):
    if isinstance(value,list):
        return scorer_rows(value,known)
    result=[]
    for part in re.split(r'[,;]',nice(value)):
        if not part or re.search(r'(?i)nicht|unbekannt|ungewiss|kein|forfait|eigentor|zuordnung|weiterer',part):continue
        m=re.fullmatch(r'([\wÄÖÜäöüÀ-ÿ\- ]+?)(?:\s*\((\d{1,2})\))?',part.strip())
        if not m:continue
        name=canonical(m.group(1),known)
        if not name:continue
        result.append({'name':name,'goals':int(m.group(2) or 1)})
    return scorer_rows(result,known)

def candidates_from_audit(doc,known):
    audit=doc.get('scorer_audit') or {}
    records={}
    for row in audit.get('checked_matches',[]) if isinstance(audit,dict) else []:
        if not isinstance(row,dict):continue
        date=nice(row.get('date'))
        opp=nice(row.get('opponent'))
        if not date or not opp:continue
        scores=from_checked_text(row.get('scorers'),known)
        if not scores:continue
        records[match_key(date,opp)]={
            'date':date,'opponent':opp,'source':'report','scorers':scores
        }
    return records

def official_records(known):
    if not OFFICIAL.exists():return {}
    data=json.loads(OFFICIAL.read_text(encoding='utf-8'))
    found={}
    for m in data.get('matches',[]):
        if not isinstance(m,dict):continue
        date,opponent=nice(m.get('date')),nice(m.get('opponent'))
        src=nice(m.get('source_url'))
        if not date or not opponent or not src.startswith(('https://matchcenter.ifv.ch/','https://club.football.ch/','https://matchcenter.el-pl.ch/')):
            continue
        names=scorer_rows(m.get('scorers'),known)
        if not names:continue
        found[match_key(date,opponent)]={
            'date':date,'opponent':opponent,'source':'ifv',
            'source_url':src,'scorers':names
        }
    return found

def keyed_results(data):
    present={}
    for m in data.get('recent_results',[]):
        if not isinstance(m,dict):continue
        if m.get('home')==TEAM:
            opp=m.get('away')
            gf=m.get('home_goals')
        elif m.get('away')==TEAM:
            opp=m.get('home')
            gf=m.get('away_goals')
        else:continue
        if gf is not None:
            present[match_key(m.get('date'),opp)]=int(gf)
    return present

def main():
    data=json.loads(PATH.read_text(encoding='utf-8'))
    baseline=json.loads(BASE.read_text(encoding='utf-8')) if BASE.exists() else {}
    ledger=baseline.get('scorer_match_ledger') or data.get('scorer_match_ledger')
    if not isinstance(ledger,dict):
        # Only one migration of the legacy season sums. This snapshot is never
        # overwritten by a subsequent AI-generated season total.
        legacy=scorer_rows(baseline.get('scorers',data.get('scorers',[])),{})
        checked=(baseline.get('scorer_audit') or {}).get('checked_matches',[])
        covered=[match_key(r.get('date'),r.get('opponent')) for r in checked
                 if isinstance(r,dict) and r.get('date') and r.get('opponent')]
        ledger={
            'schema':1,
            'legacy_scorers':legacy,
            'legacy_own_goals':int(baseline.get('own_goals',data.get('own_goals',0)) or 0),
            'legacy_forfait_goals':int(baseline.get('forfait_goals',data.get('forfait_goals',0)) or 0),
            'legacy_covered_matches':sorted(set(covered)),
            'matches':[]
        }
    known=names_map(ledger.get('legacy_scorers'),data.get('scorers'))
    for entry in ledger.get('matches',[]):
        known.update(names_map(entry.get('scorers')))
    entries={match_key(x['date'],x['opponent']):x for x in ledger.get('matches',[])
             if isinstance(x,dict) and x.get('date') and x.get('opponent')}
    prior=set(ledger.get('legacy_covered_matches',[]))
    result_goals=keyed_results(data)
    proposals=candidates_from_audit(data,known)
    official=official_records(known)
    unresolved=[]
    for k,proposal in proposals.items():
        if k in prior and k not in entries:
            continue
        if k not in result_goals and k not in entries:
            continue
        if k not in entries or entries[k].get('source')!='ifv':
            entries[k]=proposal
    for k,record in official.items():
        if k in prior and k not in entries:
            unresolved.append(k)
            # No verified historical allocation can be subtracted from the
            # legacy rollup without risking double counting.
            continue
        if k not in result_goals and k not in entries:
            continue
        entries[k]=record

    counts=defaultdict(int)
    labels={}
    for x in scorer_rows(ledger.get('legacy_scorers',[]),known):
        k=x['name'].casefold();counts[k]+=x['goals'];labels[k]=x['name']
    missing_match_details=[]
    for k,rec in sorted(entries.items()):
        totals=scorer_rows(rec.get('scorers'),known)
        if k in result_goals and sum(m['goals'] for m in totals)>result_goals[k]:
            # Don't count ambiguous/inconsistent match attributions.
            missing_match_details.append(k)
            continue
        for player in totals:
            key=player['name'].casefold()
            counts[key]+=player['goals'];labels[key]=player['name']
    rows=[{'name':labels[k],'goals':v} for k,v in counts.items() if v>0]
    rows.sort(key=lambda r:(-r['goals'],r['name'].casefold()))
    own=int(ledger.get('legacy_own_goals',0))
    forfait=int(ledger.get('legacy_forfait_goals',0))
    expected=int((data.get('eschenbach') or {}).get('goals_for',0) or 0)
    accounted=sum(r['goals'] for r in rows)+own+forfait
    if expected and accounted>expected:
        # Reject the update, never allow the AI or a duplicate match to
        # silently make season totals larger than the IFV team score.
        raise RuntimeError(f'Torschützen {accounted} über offiziellen {expected} Saisontoren.')
    ledger['matches']=[entries[k] for k in sorted(entries)]
    data['scorer_match_ledger']=ledger
    data['scorers']=rows
    data['own_goals']=own
    data['forfait_goals']=forfait
    audit=data.get('scorer_audit')
    if not isinstance(audit,dict):audit={}
    audit.update({
        'player_goals':sum(x['goals'] for x in rows),
        'own_goals':own,'forfait_goals':forfait,'expected_goals':expected,
        'accounted_goals':accounted,'complete':accounted==expected if expected else False,
        'official_priority':True,'counted_matches':len(entries),
        'unresolved_historical_official_matches':unresolved,
        'inconsistent_match_details':missing_match_details,
    })
    data['scorer_audit']=audit
    gap=max(0,expected-accounted)
    data['scorer_note']=(
        f'{sum(r["goals"] for r in rows)} Spielertore, {own} Eigentore und '
        f'{forfait} Forfait-Tore: {accounted} von {expected} Saisontoren zugeordnet.'
        +(f' Noch {gap} nicht eindeutig zugeordnet.' if gap else '')
    )
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Torschützen pro Spiel zusammengeführt: {accounted}/{expected}; '
          f'{len(entries)} Spiele im Einzelmatch-Ledger; IFV-Vorrang aktiv.')

if __name__=='__main__':
    main()
