"""
Text → JSON: Exercises
Converted from Chunking_exercises.ipynb
Logic is identical — only file paths now come from environment variables.
"""

import sys
import re
import json
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ── Paths from orchestrator ──────────────────────────────────
TEXT_DIR  = Path(os.environ.get("TEXT_DIR", "./text"))
JSON_DIR  = Path(os.environ.get("JSON_DIR", "./json"))
CHAPTER   = os.environ.get("CHAPTER_NAME", "Chapter")

INPUT_FILE  = TEXT_DIR / "exercises.txt"
OUTPUT_FILE = JSON_DIR / "exercises.json"


# ── Your original logic (untouched) ─────────────────────────

def split_questions(text):
    text = re.sub(r"\r", "", text)
    text = re.sub(r"\n+", "\n", text)
    pattern = r"(?m)^\s*(\d+)\.\s+(?=[A-Z])"
    parts = re.split(pattern, text)

    questions = []
    for i in range(1, len(parts), 2):
        q_id   = int(parts[i])
        q_text = parts[i + 1].strip()
        questions.append((q_id, q_text))

    return questions


def extract_subparts(q_text):
    subparts = []
    matches  = list(re.finditer(r"\(([a-z])\)", q_text))

    if not matches:
        return q_text.strip(), None

    parts        = re.split(r"\(([a-z])\)", q_text)
    main_question = parts[0].strip()

    for i in range(1, len(parts), 2):
        label = parts[i]
        text  = parts[i + 1].strip()
        subparts.append({"label": label, "text": text})

    return main_question, subparts


def parse_exercises(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    split_qs  = split_questions(text)
    exercises = []

    for q_id, q_text in split_qs:
        main_q, subparts = extract_subparts(q_text)
        exercise = {"id": q_id, "question": main_q}
        if subparts:
            exercise["subparts"] = subparts
        exercises.append(exercise)

    return {"chapter": CHAPTER, "exercises": exercises}


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    if not INPUT_FILE.exists():
        print(f"[exercises.py] ❌ Input not found: {INPUT_FILE}")
        exit(1)

    JSON_DIR.mkdir(parents=True, exist_ok=True)

    data = parse_exercises(INPUT_FILE)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[exercises.py] ✅ Parsed {len(data['exercises'])} exercises → {OUTPUT_FILE}")
