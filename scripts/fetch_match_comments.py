"""Load the entire approved match-comment batch for a report update.

A failed or incomplete download must fail the workflow, not produce an
apparently successful report with missing eyewitness notes.
"""
import json
import os
import urllib.request

REQUEST_ID = os.environ.get("REQUEST_ID", "").strip()
COMMENTS_TOKEN = os.environ.get("COMMENTS_TOKEN", "").strip()
OUT = os.environ.get("MATCH_COMMENTS_FILE", "/tmp/go-eschenbach-match-comments.json")
API = "https://kfpxheegmeupnuzqjqqt.supabase.co/functions/v1/report-update-request-v2"

comments = []
if REQUEST_ID and COMMENTS_TOKEN:
    payload = json.dumps({
        "action": "comments_for_update",
        "request_id": REQUEST_ID,
        "comments_token": COMMENTS_TOKEN,
    }).encode("utf-8")
    req = urllib.request.Request(
        API, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    # Deliberately let HTTP and parsing failures fail the workflow. Comments
    # remain unprocessed in Supabase and can be used on the next update.
    with urllib.request.urlopen(req, timeout=45) as response:
        result = json.loads(response.read().decode("utf-8"))

    if result.get("ok") is not True or not isinstance(result.get("comments"), list):
        raise RuntimeError("Unvollständige Antwort beim Laden der Matchkommentare")
    comments = result["comments"]
    expected = int(result.get("expected_count", -1))
    if expected != len(comments):
        raise RuntimeError(f"Matchkommentare fehlen: erwartet {expected}, erhalten {len(comments)}")
    if any(not isinstance(c, dict) or not str(c.get("transcript") or "").strip() for c in comments):
        raise RuntimeError("Ein Matchkommentar ist leer oder unlesbar")
elif COMMENTS_TOKEN and not REQUEST_ID:
    raise RuntimeError("Matchkommentare ohne Update-ID können nicht zugeordnet werden")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(comments, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"Vollständig geladene Matchkommentare für Rückblick: {len(comments)}")
