import sys
import pdfplumber
import re
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ── Paths from orchestrator ──────────────────────────────────
pdf_path = os.environ.get("PDF_PATH", "")
TEXT_DIR = Path(os.environ.get("TEXT_DIR", "."))


# ── Your original functions (untouched) ──────────────────────

def clean_text(text):
    text = re.sub(r'([A-Za-z])\1{2,}', r'\1', text)
    text = re.sub(r'(\d)\1{4,}', '', text)
    text = re.sub(r'(?<=\s)7\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\b(?:[A-Za-z]\s){2,}[A-Za-z]\b', lambda m: m.group(0).replace(" ", ""), text)
    text = re.sub(r'\b(m|cm|km)\s+(s|h)[–\-](1|2)\b', r'\1 \2^-\3', text)
    text = re.sub(r'\b(m|cm|km|s|h)[–\-](1|2)\b', r'\1^-\2', text)
    text = re.sub(r'(\d+)\s*[×x]\s*10(\d+)', r'\1 x 10^\2', text)
    text = re.sub(r'\b10([2-9]|1[0-9])\b', r'10^\1', text)

    lines = text.split("\n")
    fixed = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if (i + 2 < len(lines) and line.isdigit() and
            lines[i+1].strip().lower() in ("c", "ch") and
            re.match(r"hapter", lines[i+2].strip(), re.IGNORECASE)):
            fixed.append(f"Chapter {line}")
            i += 3
            continue
        if (i + 1 < len(lines) and len(line) == 1 and line.isalpha() and lines[i+1].strip().isalpha()):
            fixed.append(line + lines[i+1].strip())
            i += 2
            continue
        fixed.append(line)
        i += 1
    text = "\n".join(fixed)

    lines = text.split("\n")
    fixed = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r'^\d+\.\d+(\.\d+)?', line):
            combined = line
            j = i + 1
            while j < len(lines) and len(combined.split()) < 8:
                nxt = lines[j].strip()
                if re.match(r'^\d+\.\d+', nxt) or nxt == "":
                    break
                combined += " " + nxt
                j += 1
            combined = re.sub(r'([A-Z])\s*[-–]\s*([A-Z])', r'\1\2', combined)
            combined = re.sub(r'\b([A-Z])\s+([A-Z]+)', r'\1\2', combined)
            fixed.append(combined)
            i = j
            continue
        fixed.append(line)
        i += 1
    text = "\n".join(fixed)

    text = re.sub(r'[•●▪■◦◆►]', '', text)
    text = re.sub(r'[_]{2,}', '', text)
    text = re.sub(r'\bReprint\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bSCIENCE\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\s*MOTION\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\b[0-9]?025-26\b', '', text)
    text = re.sub(r'\bnt\b', '', text)
    text = re.sub(r'\b\d{4}\b', '', text)

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        s = line.strip()
        if re.match(r'^(Fig\.?|Figure)\s*\d+(\.\d+)?', s, re.IGNORECASE):
            continue
        if re.match(r'^\d{1,3}$', s):
            n = int(s)
            if n == 7 or n == 20 or (60 <= n <= 100):
                continue
        cleaned_lines.append(s)

    text = "\n".join([l for l in cleaned_lines if l])
    text = re.sub(r'\(?\bFig\.?\s*\d+(\.\d+)?[a-zA-Z]?\)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(in|shown in|given in)\s*\.', '', text)

    return text


def extract_from_pdf(pdf_path):
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            mid_x = page.width / 2
            left  = page.within_bbox((0, 0, mid_x + 10, page.height)).extract_text(x_tolerance=3, y_tolerance=3, layout=True) or ""
            right = page.within_bbox((mid_x - 10, 0, page.width, page.height)).extract_text(x_tolerance=3, y_tolerance=3, layout=True) or ""
            full_text += left + "\n" + right + "\n"
    return full_text


def get_questions(text):
    lines = text.split("\n")
    questions = []
    i = 0

    _KEYWORDS   = re.compile(r'^\s*(Activity|Think\s+and\s+Act|Questions|Q\s*uestions|Example|Exercises|Summary)', re.IGNORECASE)
    _SECTION_NUM = re.compile(r'^\s*\d+(\.\d+)+\s+[A-Z]')

    while i < len(lines):
        line = lines[i].strip()

        is_header = False
        if re.match(r'^Q\s*uestions$', line, re.IGNORECASE):
            is_header = True
        elif line.upper() == 'QUESTIONS':
            is_header = True
        elif i + 1 < len(lines) and line == 'Q' and re.match(r'^uestions$', lines[i+1].strip(), re.IGNORECASE):
            is_header = True
            i += 1

        if is_header:
            temp = ["Questions"]
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue
                if _KEYWORDS.match(next_line) or _SECTION_NUM.match(next_line):
                    break
                if re.match(r'^\d+$', next_line) and i + 1 < len(lines):
                    lookahead = lines[i+1].strip()
                    if lookahead.startswith('.') or lookahead.startswith('?'):
                        next_line = next_line + lookahead
                        i += 1
                temp.append(next_line)
                i += 1
            questions.append("\n".join(temp).strip())
            continue
        i += 1
    return questions


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(pdf_path):
        print(f"[in_chapter_questions.py] ERROR: PDF not found: {pdf_path}")
        exit(1)

    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    raw_text     = extract_from_pdf(pdf_path)
    cleaned_text = clean_text(raw_text)
    questions    = get_questions(cleaned_text)

    if not questions:
        print(f"[in_chapter_questions.py] SKIP: No question sections found in {pdf_path}")
        exit(0)

    output_file = TEXT_DIR / "in_chapter_questions.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(questions))

    print(f"[in_chapter_questions.py] Extracted {len(questions)} question blocks -> {output_file}")
