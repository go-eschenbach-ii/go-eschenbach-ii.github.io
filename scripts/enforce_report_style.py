"""Final style guard for all user-facing prose in data/report.json.

Run as the last editorial step, also when a prior Rückblick was retained.
Do not modify team names, result data, scorer names or source URLs.
"""
import json
import re
from pathlib import Path

PATH = Path("data/report.json")
FIELDS = ("title", "lead", "review", "current_situation", "outlook")
data = json.loads(PATH.read_text(encoding="utf-8"))
changed = []

for key in FIELDS:
    value = data.get(key)
    if not isinstance(value, str) or not re.search(r"[–—]", value):
        continue
    # For numeric ranges retain a hyphen, which is not a Gedankenstrich.
    value = re.sub(r"(?<=\d)[–—](?=\d)", "-", value)
    # An en/em dash used as punctuation is replaced by a comma. The AI
    # prompts already require full sentences; this is a final safety guard.
    value = re.sub(r"\s*[–—]\s*", ", ", value)
    value = re.sub(r"\s+,", ",", value)
    value = re.sub(r",\s*,+", ",", value).strip()
    data[key] = value
    changed.append(key)

if changed:
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Gedankenstriche aus Lesertexten entfernt:", ", ".join(changed))
else:
    print("Sprachregel geprüft: keine Gedankenstriche in Lesertexten.")
