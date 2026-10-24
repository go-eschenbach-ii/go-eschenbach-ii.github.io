import json
import os
from pathlib import Path
import re
import urllib.request
import html as html_lib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

REPORT_PATH='data/report.json'
SCHEDULE_URLS=[
    'https://matchcenter.ifv.ch/default.aspx?a=msp&ln=13040&lng=1&ls=25897&oid=7&s=2027&sg=70471',
    'https://club.football.ch/?lng=1&tab=3396&v=376&t=31274&ls=25897&sg=70471&tg=4328790',
    'https://www.fcschoetz.ch/de/club/teams/team/spielplan-gruppe/%26v%3D376%26t%3D31274%26ls%3D25897%26sg%3D70471',
]

with open(REPORT_PATH,'r',encoding='utf-8') as f:
    data=json.load(f)

teams=[
    ' '.join(str(r.get('team','')).split())
    for r in data.get('standings',[])
    if isinstance(r,dict) and r.get('team')
]
teamset=set(teams)
canonical={t.casefold():t for t in teams}

if len(teamset)<8:
    raise SystemExit('Zu wenige Gruppenteams im Bericht; Spielplan wird nicht überschrieben.')

now=datetime.now(ZoneInfo('Europe/Zurich'))
today=now.date()
recent_start=today-timedelta(days=7)
future_end=today+timedelta(days=14)

headers={
    'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1',
    'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language':'de-CH,de;q=0.9',
    'Cache-Control':'no-cache',
    'Pragma':'no-cache'
}
raw=None
used_source=None
failures=[]
for url in SCHEDULE_URLS:
    try:
        req=urllib.request.Request(url,headers=headers)
        with urllib.request.urlopen(req,timeout=22) as response:
            candidate=response.read().decode('utf-8','ignore')
        if any(token in candidate for token in ('FC Eschenbach II','FC Hochdorf III','FC Dagmersellen')):
            raw=candidate
            used_source=url
            break
        failures.append(f'{url}: kein Gruppenspielplan im Inhalt')
    except Exception as exc:
        failures.append(f'{url}: {exc}')

if raw is None:
    # An update without a fresh official schedule must fail BEFORE a private
    # preview is prepared. Do not treat an outdated or AI-inferred list as fresh.
    raise RuntimeError('IFV-Spielplan nicht erreichbar. Quellen: '+' | '.join(failures))

raw=re.sub(r'(?is)<script\b.*?</script>|<style\b.*?</style>',' ',raw)
raw=re.sub(r'(?s)<[^>]+>','\n',raw)
text=html_lib.unescape(raw).replace('\xa0',' ')
lines=[' '.join(x.split()) for x in text.splitlines() if x.strip()]


def dmy(value):
    try:
        return datetime.strptime(str(value).strip(),'%d.%m.%Y').date()
    except Exception:
        return None


def kickoff_could_be_finished(date, time):
    # Keine automatischen Resultate vor Abpfiff; auch IFV-Zeilen koennen
    # zusaetzliche Zahlen enthalten, die faelschlich als Tore erkannt werden.
    if date<today:
        return True
    if date>today:
        return False
    try:
        hh,mm=map(int,str(time).strip().split(':'))
        kickoff=datetime(date.year,date.month,date.day,hh,mm,
                         tzinfo=ZoneInfo('Europe/Zurich'))
        return now>=kickoff+timedelta(minutes=110)
    except (ValueError,TypeError):
        return False


def key(item):
    return (
        str(item.get('date','')),
        str(item.get('home','')).strip().casefold(),
        str(item.get('away','')).strip().casefold()
    )


def teams_in_line(line):
    folded=line.casefold()
    hits=[]
    for low,name in canonical.items():
        pos=folded.find(low)
        if pos>=0:
            hits.append((pos,name))
    hits.sort(key=lambda x:x[0])
    return hits


def time_before(line,pos):
    m=re.search(r'\b(?:[01]\d|2[0-3]):[0-5]\d\b',line[:max(0,pos)])
    return m.group(0) if m else ''


def score_after_away(line,away,away_pos):
    tail=line[away_pos+len(away):] if away_pos>=0 else ''
    tail=re.sub(r'(?i)Spielnummer\s+\d+',' ',tail)
    tail=re.sub(r'\b\d{5,}\b',' ',tail)
    nums=[int(v) for v in re.findall(r'(?<!\d)(\d{1,2})(?!\d)',tail)]
    return nums[:2] if len(nums)>=2 else []


results={}
fixtures={}
current_date=None
current_time=''

for i,line in enumerate(lines):
    dm=re.search(r'(\d{2}\.\d{2}\.\d{4})',line)
    if dm:
        current_date=dmy(dm.group(1))
        current_time=''
        continue

    if re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',line):
        current_time=line
        continue

    if not current_date or current_date<recent_start or current_date>future_end:
        continue

    hits=teams_in_line(line)

    # Häufigster IFV-Fall: Zeit + Heimteam + Auswärtsteam + Resultat/Spielnummer in einer Zeile.
    if len(hits)>=2:
        home=hits[0][1]
        away=hits[1][1]
        if home==away:
            continue
        tm=time_before(line,hits[0][0]) or current_time
        away_pos=line.casefold().find(away.casefold(),hits[1][0])
        score=score_after_away(line,away,away_pos)
        item={'date':current_date.strftime('%d.%m.%Y'),'time':tm,'home':home,'away':away,'note':''}
        if score and kickoff_could_be_finished(current_date, tm):
            item['home_goals']=score[0]
            item['away_goals']=score[1]
            results[key(item)]=item
            fixtures.pop(key(item),None)
        elif current_date>=today:
            fixtures[key(item)]=item
        continue

    # Alternativer IFV-Fall: Teams stehen auf separaten Zeilen.
    folded=line.casefold()
    home=canonical.get(folded)
    if not home:
        continue

    j=i+1
    away=None
    while j<len(lines) and j<=i+5:
        if re.search(r'(\d{2}\.\d{2}\.\d{4})',lines[j]):
            break
        candidate=canonical.get(lines[j].casefold())
        if candidate and candidate!=home:
            away=candidate
            break
        j+=1

    if not away:
        continue

    score=[]
    k=j+1
    while k<len(lines) and k<=j+8:
        token=lines[k]
        if re.search(r'(\d{2}\.\d{2}\.\d{4})',token):
            break
        if canonical.get(token.casefold()):
            break
        if re.search(r'(?i)Spielnummer',token):
            break
        if re.fullmatch(r'\d{1,2}',token):
            score.append(int(token))
            if len(score)>=2:
                break
        k+=1

    item={'date':current_date.strftime('%d.%m.%Y'),'time':current_time,'home':home,'away':away,'note':''}
    if len(score)>=2 and kickoff_could_be_finished(current_date, current_time):
        item['home_goals']=score[0]
        item['away_goals']=score[1]
        results[key(item)]=item
        fixtures.pop(key(item),None)
    elif current_date>=today:
        fixtures[key(item)]=item

if not fixtures and not results:
    # It is legitimate to have no matches in the recent/next-14-day window
    # during the winter break. Still require a real complete group-fixture
    # page; the ranking page alone cannot count as consultation.
    present=sum(1 for t in teamset if t.casefold() in text.casefold())
    dates=len(re.findall(r'\b\d{2}\.\d{2}\.\d{4}\b', text))
    if present < 8 or dates < 3:
        raise RuntimeError(
            f'IFV-Spielplan konnte nicht eindeutig gelesen werden: '
            f'{present} Teams, {dates} Daten, Quelle {used_source}'
        )

# Nachweis nur aus dem echten IFV-Matchcenter, nicht aus KI-Texten oder
# möglicherweise veralteten Ranglistenspiegeln. Die offizielle Ergebnisliste
# ist die primäre Quelle für abgeschlossene Spiele.
if results and used_source and (
    used_source.startswith('https://matchcenter.ifv.ch/')
    or used_source.startswith('https://www.fcschoetz.ch/de/club/teams/team/spielplan-gruppe/')
):
    # The FC Schötz group fixture page is an official IFV-backed club feed
    # and is reachable by GitHub Actions when matchcenter.ifv.ch blocks
    # automated requests with HTTP 403. Do not infer verification from
    # AI-generated text or stale standings pages.
    ledger_path=Path('data/ifv-verified-results.json')
    ledger=json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {
        'source':used_source,'matches':[]
    }
    by_key={key(m):m for m in ledger.get('matches',[]) if isinstance(m,dict)}
    for item in results.values():
        saved={
            'date':item['date'],'home':item['home'],'away':item['away'],
            'home_goals':int(item['home_goals']),'away_goals':int(item['away_goals'])
        }
        by_key[key(saved)]=saved
    ledger['source']=used_source
    ledger['matches']=list(by_key.values())
    ledger_path.write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Offizielle IFV-Resultate unabhängig von der verzögerten Tabelle bestätigt:',len(results))

# Offizielle Resultate der letzten 7 Tage ergänzen.
merged_results={}
for raw_item in data.get('recent_results',[]) if isinstance(data.get('recent_results'),list) else []:
    if not isinstance(raw_item,dict):
        continue
    d=dmy(raw_item.get('date'))
    if d and recent_start<=d<=today:
        merged_results[key(raw_item)]=raw_item
for k,item in results.items():
    merged_results[k]=item

data['recent_results']=sorted(
    merged_results.values(),
    key=lambda m:(dmy(m.get('date')) or recent_start,m.get('time',''),m.get('home','')),
    reverse=True
)

# Use the official fixture list, not AI suggestions or the former preview:
# those lists may be stale or incomplete. Both teams already belong to the
# verified ten-team IFV group (checked during parsing).
for k in list(fixtures):
    if k in results:
        fixtures.pop(k,None)
data['upcoming_matches']=sorted(
    fixtures.values(),
    key=lambda m:(dmy(m.get('date')) or future_end,m.get('time',''),m.get('home',''))
)

data['schedule_sync_status']='verified'
data['schedule_sync_source']=used_source
data['schedule_sync_verified_results']=len(results)
data['schedule_sync_verified_fixtures']=len(fixtures)
data['schedule_sync_at']=now.isoformat()
with open(REPORT_PATH,'w',encoding='utf-8') as f:
    json.dump(data,f,ensure_ascii=False,indent=2)
    f.write('\n')

print(f'IFV-Spielplan synchronisiert: {len(results)} Resultate, {len(fixtures)} kommende Spiele.')
