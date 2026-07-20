import sys
import re
import json
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ── Paths from orchestrator ──────────────────────────────────
TEXT_DIR = Path(os.environ.get("TEXT_DIR", "."))
JSON_DIR = Path(os.environ.get("JSON_DIR", "."))

INPUT_FILE  = TEXT_DIR / "activities.txt"
OUTPUT_FILE = JSON_DIR / "activities.json"


# ── Parsing logic ─────────────────────────────────────────────

def parse_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # Split on Activity headers
    parts = re.split(r'(?=^Activity\s+\d+\.\d+)', raw_text, flags=re.MULTILINE | re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]

    activities = []
    for idx, block in enumerate(parts, start=1):
        lines = block.splitlines()
        header = lines[0].strip()

        # Extract activity number
        m = re.search(r'Activity\s+(\d+)\.(\d+)', header, re.IGNORECASE)
        activity_id = f"{m.group(1)}.{m.group(2)}" if m else str(idx)
        chapter     = m.group(1) if m else ""

        # Rest is content
        content = "\n".join(lines[1:]).strip()

        # Extract steps (lines starting with numbers or bullets)
        steps = []
        for line in content.splitlines():
            line = line.strip()
            if re.match(r'^\d+\.?\s+', line) or re.match(r'^[•\-]\s*', line):
                steps.append(re.sub(r'^[\d•\-\.]+\s*', '', line))

        activities.append({
            "id":          idx,
            "activity_id": activity_id,
            "chapter":     chapter,
            "title":       header,
            "content":     content,
            "steps":       steps if steps else None
        })

    return {"activities": activities}


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    if not INPUT_FILE.exists():
        print(f"[activities.py] ERROR: Input not found: {INPUT_FILE}")
        exit(1)

    JSON_DIR.mkdir(parents=True, exist_ok=True)
    data = parse_file(INPUT_FILE)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[activities.py] Parsed {len(data['activities'])} activities -> {OUTPUT_FILE}")
