import sys
import json
import re
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

TEXT_DIR = Path(os.environ.get("TEXT_DIR", "."))
JSON_DIR = Path(os.environ.get("JSON_DIR", "."))

pdf_name = os.environ.get("CHAPTER_NAME", "")
chapter_match = re.search(r'iesc1(\d+)', pdf_name, re.IGNORECASE)
CHAPTER = str(int(chapter_match.group(1))) if chapter_match else pdf_name

INPUT_FILE  = TEXT_DIR / "think_and_act.txt"
OUTPUT_FILE = JSON_DIR / "think_and_act.json"

def parse_file(filepath):
    entries = []
    current_content = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.lower().startswith("thinkandact:"):
                if current_content:
                    entries.append(" ".join(current_content).strip())
                    current_content = []
                content = stripped[len("thinkandact:"):].strip()
                if content:
                    current_content.append(content)
            else:
                current_content.append(stripped)

        if current_content:
            entries.append(" ".join(current_content).strip())

    return entries

def build_json(entries):
    structured = []
    for content in entries:
        cleaned_content = re.sub(r'^\s*Think and Act\s*', '', content, flags=re.IGNORECASE).strip()
        structured.append({
            "chapter": CHAPTER,
            "thinkandact": cleaned_content
        })
    return structured

if __name__ == "__main__":
    if not INPUT_FILE.exists():
        print(f"[think_and_act.py] ERROR: Input not found: {INPUT_FILE}")
        exit(1)

    JSON_DIR.mkdir(parents=True, exist_ok=True)
    entries = parse_file(INPUT_FILE)
    result  = build_json(entries)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[think_and_act.py] Parsed {len(result)} entries -> {OUTPUT_FILE}")
