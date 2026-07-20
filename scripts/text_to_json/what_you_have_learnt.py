import sys
import re
import json
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

TEXT_DIR = Path(os.environ.get("TEXT_DIR", "."))
JSON_DIR = Path(os.environ.get("JSON_DIR", "."))

INPUT_FILE  = TEXT_DIR / "what_you_have_learnt.txt"
OUTPUT_FILE = JSON_DIR / "what_you_have_learnt.json"

def is_noise(line):
    if not line.strip():
        return True
    if re.match(r'^(Quantity|Temperature|Length|Mass|Weight|Volume|Density|Pressure|Unit|Symbol)', line):
        return True
    if re.match(r'^[A-Z\s]{10,}$', line):
        return True
    return False

def parse_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    heading_words = {"what", "you have", "learnt"}
    content_lines = []
    heading_done = False
    for line in lines:
        if not heading_done:
            if line.lower().strip() in heading_words:
                continue
            heading_done = True
        if not is_noise(line):
            content_lines.append(line.strip())

    points_raw = []
    current = []

    for line in content_lines:
        if not line:
            continue
        if (current and
            re.match(r'^[A-Z]', line) and
            current[-1].endswith('.')):
            points_raw.append(" ".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        points_raw.append(" ".join(current))

    points = []
    for idx, text in enumerate(points_raw, start=1):
        text = text.strip()
        if not text:
            continue
        formulas = re.findall(r"[a-zA-Z]+\s*=\s*[^,\n]+", text)
        point = {"id": idx, "text": text}
        if formulas:
            point["formulas"] = formulas
        points.append(point)

    return {
        "section": "What you have learnt",
        "total_points": len(points),
        "points": points
    }

if __name__ == "__main__":
    if not INPUT_FILE.exists():
        print(f"[what_you_have_learnt.py] ERROR: Input not found: {INPUT_FILE}")
        exit(1)

    JSON_DIR.mkdir(parents=True, exist_ok=True)
    data = parse_file(INPUT_FILE)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[what_you_have_learnt.py] Parsed {len(data['points'])} points -> {OUTPUT_FILE}")
