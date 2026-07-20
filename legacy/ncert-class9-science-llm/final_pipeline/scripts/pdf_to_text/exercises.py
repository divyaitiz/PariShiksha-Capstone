import pdfplumber
import re
import os
from pathlib import Path

# ── Paths from orchestrator ──────────────────────────────────
pdf_path = os.environ.get("PDF_PATH", "")
TEXT_DIR = Path(os.environ.get("TEXT_DIR", "."))

# ── Extract full text from PDF ───────────────────────────────
full_text = ""
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        extracted = page.extract_text()
        if extracted:
            full_text += extracted + "\n"

lines = full_text.splitlines()
exercises_idx = -1


# -------- Helper: Detect noise --------
def is_noise(line):
    line_strip = line.strip()
    lower = line_strip.lower()

    if "science" in lower or "reprint" in lower:
        return True
    if line_strip.isdigit():
        return True
    if re.fullmatch(r'fig\.?\s*\d+(\.\d+)*', lower):
        return True
    if re.search(r'(.)\1{4,}', line_strip):
        return True
    if len(re.findall(r'\d', line_strip)) > len(line_strip) * 0.6:
        return True

    return False


# -------- Locate "Exercises" heading --------
for i, line in enumerate(lines):
    if line.lower().strip() == "exercises":
        exercises_idx = i
        break


# -------- Extract + clean --------
def clean_line(l):
    l = re.sub(r'(.)\1{3,}', '', l)
    l = re.sub(r'[^\w\s.,:;()\-\u2013\xb0/]', ' ', l)
    return l.strip()


if exercises_idx != -1:
    exercises_lines = lines[exercises_idx:]

    cleaned_exercises = []
    for l in exercises_lines:
        if not is_noise(l):
            cleaned_exercises.append(clean_line(l))

    output_file = TEXT_DIR / "exercises.txt"

    if cleaned_exercises:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(cleaned_exercises).strip())
        print(f"[exercises.py] Extracted exercises -> {output_file}")
    else:
        print("[exercises.py] WARNING: Exercises section found but empty after cleaning")
else:
    print("[exercises.py] ERROR: Could not find 'Exercises' heading in PDF")
    exit(1)
