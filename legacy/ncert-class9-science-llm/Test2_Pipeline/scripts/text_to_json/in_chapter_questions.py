import sys
import re
import json
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ── Paths from orchestrator ──────────────────────────────────
TEXT_DIR = Path(os.environ.get("TEXT_DIR", "."))
JSON_DIR = Path(os.environ.get("JSON_DIR", "."))

INPUT_FILE  = TEXT_DIR / "in_chapter_questions.txt"
OUTPUT_FILE = JSON_DIR / "in_chapter_questions.json"


# ── Your original functions (untouched) ──────────────────────

def normalize_text(text):
    text = re.sub(r"\r", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def split_sections(text):
    parts = re.split(r"\n?\s*Questions\s*\n", text)
    parts = [p.strip() for p in parts if p.strip()]
    return parts


def split_questions(section_text):
    pattern = r"(?m)^\s*(\d+)\.\s+(?=[A-Z(])"
    parts   = re.split(pattern, section_text)
    questions = []
    for i in range(1, len(parts), 2):
        q_id   = int(parts[i])
        q_text = parts[i + 1].strip()
        questions.append((q_id, q_text))
    return questions


def extract_subparts(q_text):
    matches = list(re.finditer(r"\(([a-z])\)", q_text))
    if not matches:
        return q_text.strip(), None
    parts         = re.split(r"\(([a-z])\)", q_text)
    main_question = parts[0].strip()
    subparts      = []
    for i in range(1, len(parts), 2):
        label = parts[i]
        text  = parts[i + 1].strip()
        subparts.append({"label": label, "text": text})
    return main_question, subparts


def infer_topic(section_text):
    text = section_text.lower()
    if "displacement" in text:
        return "Motion and Displacement"
    elif "velocity" in text or "speed" in text:
        return "Speed and Velocity"
    elif "acceleration" in text:
        return "Acceleration"
    elif "graph" in text:
        return "Graphs of Motion"
    else:
        return None


def parse_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    text         = normalize_text(raw_text)
    sections_raw = split_sections(text)
    sections     = []

    for s_idx, section_text in enumerate(sections_raw, start=1):
        questions_raw = split_questions(section_text)
        questions     = []

        for q_id, q_text in questions_raw:
            main_q, subparts = extract_subparts(q_text)
            q_obj = {
                "id":       q_id,
                "qid":      f"S{s_idx}Q{q_id}",
                "question": main_q
            }
            if subparts:
                q_obj["subparts"] = subparts
            questions.append(q_obj)

        sections.append({
            "section_id":  s_idx,
            "section_key": f"section_{s_idx}",
            "title":       "Questions",
            "topic":       infer_topic(section_text),
            "questions":   questions
        })

    return {"sections": sections}


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    if not INPUT_FILE.exists():
        print(f"[in_chapter_questions.py] ERROR: Input not found: {INPUT_FILE}")
        exit(1)

    JSON_DIR.mkdir(parents=True, exist_ok=True)

    data = parse_file(INPUT_FILE)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    total_q = sum(len(s["questions"]) for s in data["sections"])
    print(f"[in_chapter_questions.py] Parsed {len(data['sections'])} sections, {total_q} questions -> {OUTPUT_FILE}")
