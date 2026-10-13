"""Final editorial pass: cross-check every approved eyewitness comment.

Run only for updates that replace the Rückblick. A failed review must stop
publication so an incomplete match report cannot mark comments processed.
"""
import json
import os
import re
import urllib.request
from pathlib import Path

REPORT = Path("data/report.json")
COMMENTS = Path(os.environ.get("MATCH_COMMENTS_FILE", "/tmp/go-eschenbach-match-comments.json"))
API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()

if not COMMENTS.exists():
    raise RuntimeError("Die Matchkommentar-Datei fehlt.")

items = json.loads(COMMENTS.read_text(encoding="utf-8"))
if not isinstance(items, list):
    raise RuntimeError("Matchkommentare haben ein ungültiges Format.")
if any(not isinstance(item, dict) or not str(item.get("transcript", "")).strip() for item in items):
    raise RuntimeError("Ein Kommentar ist leer oder unlesbar.")
if not items:
    print("Keine neuen Matchkommentare zur Schlusskontrolle vorhanden.")
    raise SystemExit(0)

if not API_KEY:
    raise RuntimeError("Ohne API-Schlüssel keine vollständige Prüfung der Matchkommentare möglich.")

data = json.loads(REPORT.read_text(encoding="utf-8"))
facts = {
    "recent_results": [
        m for m in data.get("recent_results", [])
        if isinstance(m, dict) and "FC Eschenbach II" in (m.get("home"), m.get("away"))
    ],
    "season_summary": data.get("eschenbach", {}),
}
numbered = [
    {
        "index": n,
        "match": item.get("match_label"),
        "match_date": item.get("match_date"),
        "observation": " ".join(str(item.get("transcript", "")).split()),
    }
    for n, item in enumerate(items, 1)
]

prompt = f"""Du bist die unabhängige Schlusskontrolle eines Fussballberichts über FC Eschenbach II.
Prüfe den bestehenden Rückblick gegen JEDEN der nummerierten Matchkommentare.
Überarbeite den Rückblick, sodass JEDE inhaltlich eigenständige, relevante
Beobachtung aus JEDEM Kommentar erkennbar eingearbeitet ist. Mehrfach genannte
Ereignisse darfst du bündeln. Kürze niemals eine einzelne, neue Beobachtung weg.
Unterscheide ausdrücklich zwischen verschiedenen Spielen. Ältere Ereignisse
dürfen nur als Rückblick auf frühere Partien erwähnt werden, nicht als
Teil der letzten Partie ausgegeben werden. Resultate und sichere Fakten haben
Vorrang vor fehlerhafter Spracherkennung. Erfinde nichts.
Wähle so viele natürliche Sätze, wie für Vollständigkeit nötig sind.
Schweizer Rechtschreibung. Keine Gedankenstriche (–, —) als Satzzeichen.
Keine Zitate, keine Nennung von Kommentaren oder Redaktor.
Bewahre alle bereits korrekt beschriebenen wesentlichen Ereignisse.

BESTEHENDER RÜCKBLICK:
{data.get("review", "")}

OFFIZIELLE FAKTEN:
{json.dumps(facts, ensure_ascii=False)}

ALLE KOMMENTARE, fortlaufend nummeriert:
{json.dumps(numbered, ensure_ascii=False)}

Antworte ausschliesslich als JSON:
{{"review":"...", "covered_comment_indices":{json.dumps(list(range(1,len(items)+1)))}}}
Die covered_comment_indices müssen jeden von dir inhaltlich
eingearbeiteten bzw. bei Widerspruch zu sicheren Fakten sorgfältig
geprüften Kommentar enthalten. Eine Nummer darfst du nicht ohne Prüfung
des jeweiligen Inhalts aufführen.
"""

req = urllib.request.Request(
    "https://api.openai.com/v1/responses",
    data=json.dumps({
        "model": "gpt-5.6-luna",
        "reasoning": {"effort": "medium"},
        "input": prompt,
    }).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    method="POST",
)
with urllib.request.urlopen(req, timeout=170) as response:
    result = json.loads(response.read().decode("utf-8"))

text = str(result.get("output_text") or "").strip()
if not text:
    text = "".join(
        str(part.get("text") or "")
        for item in result.get("output", [])
        if isinstance(item, dict)
        for part in item.get("content", [])
        if isinstance(part, dict) and part.get("type") in ("output_text", "text")
    ).strip()
if text.startswith(chr(96) * 3):
    text = re.sub(r"^" + re.escape(chr(96) * 3) + r"(?:json)?\s*|\s*" + re.escape(chr(96) * 3) + r"$", "", text, flags=re.S).strip()
checked = json.loads(text)
covered = checked.get("covered_comment_indices")
review = " ".join(str(checked.get("review") or "").split()).strip()
expected = list(range(1, len(items) + 1))
if not isinstance(covered, list) or sorted(set(covered)) != expected:
    raise RuntimeError(f"Nicht alle Matchkommentare in der Schlusskontrolle berücksichtigt: {covered}")
if not review:
    raise RuntimeError("Kein vollständiger Rückblick aus der Schlusskontrolle.")

data["review"] = review
REPORT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Schlusskontrolle erfolgreich: alle {len(items)} freigegebenen Matchkommentare geprüft.")
