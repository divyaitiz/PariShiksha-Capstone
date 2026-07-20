import sys
import re
import json
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ── Paths from orchestrator ──────────────────────────────────
TEXT_DIR = Path(os.environ.get("TEXT_DIR", "."))
JSON_DIR = Path(os.environ.get("JSON_DIR", "."))

INPUT_FILE  = TEXT_DIR / "examples.txt"
OUTPUT_FILE = JSON_DIR / "examples.json"


# ── Your original functions (untouched) ──────────────────────

def normalize_text(text):
    text = text.replace("–", "-")
    text = text.replace("×", "*")
    text = text.replace("m s-1", "m/s")
    text = text.replace("m s-1", "m/s")
    text = text.replace("km h-1", "km/h")
    text = text.replace("km h-1", "km/h")
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
    text = re.sub(r'\*\s*\*', '*', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def split_examples(text):
    pattern = r'(Example\s+\d+\.\d+)'
    parts   = re.split(pattern, text)
    examples = []
    for i in range(1, len(parts), 2):
        examples.append((parts[i], parts[i+1]))
    return examples


def extract_problem_and_solution(content):
    parts    = content.split("Solution:")
    problem  = parts[0].strip()
    solution = parts[1].strip() if len(parts) > 1 else ""
    return problem, solution


def extract_given(problem):
    distances = list(set(re.findall(r'\b\d+\s?(?:m|km)\b', problem)))
    times     = list(set(re.findall(r'\b\d+\s?(?:s|h|min|minutes)\b', problem)))
    return {"distances": distances, "times": times}


def extract_steps(solution):
    lines = solution.split("\n")
    steps = []
    for line in lines:
        line = line.strip()
        if "=" in line and len(line) > 5:
            if not re.match(r'^=+$', line):
                steps.append(line)
    return steps


def extract_final_answer(solution):
    lines = solution.split("\n")
    for line in reversed(lines):
        line  = line.strip()
        match = re.search(r'(\d+\.?\d*\s?(m/s|km/h))', line)
        if match:
            val  = match.group(1).replace(" ", "")
            unit = match.group(2)
            return val, unit
    return "", ""


def detect_formulas(text):
    formulas = []
    if "average speed" in text.lower():
        formulas.append("average speed = total distance / total time")
    if "v = u + at" in text:
        formulas.append("v = u + at")
    if "s = ut" in text:
        formulas.append("s = ut + 1/2 at^2")
    return list(set(formulas))


def parse_example(example_id, content):
    data  = {}
    match = re.search(r'Example\s+(\d+)\.(\d+)', example_id)
    if match:
        data["chapter"]    = match.group(1)
        data["example_id"] = f"{match.group(1)}.{match.group(2)}"

    content = normalize_text(content)
    problem, solution = extract_problem_and_solution(content)

    data["problem"]       = problem
    data["given"]         = extract_given(problem)
    data["steps"]         = extract_steps(solution)
    final_answer, unit    = extract_final_answer(solution)
    data["formulas_used"] = detect_formulas(content)
    data["final_answer"]  = final_answer
    data["units"]         = unit

    return data


def process_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    raw_text = normalize_text(raw_text)
    examples = split_examples(raw_text)
    results  = []
    for ex_id, content in examples:
        parsed = parse_example(ex_id, content)
        results.append(parsed)
    return results


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    if not INPUT_FILE.exists():
        print(f"[examples.py] ERROR: Input not found: {INPUT_FILE}")
        exit(1)

    JSON_DIR.mkdir(parents=True, exist_ok=True)
    data = process_file(INPUT_FILE)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[examples.py] Parsed {len(data)} examples -> {OUTPUT_FILE}")
