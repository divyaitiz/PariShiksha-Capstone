import sys
import pdfplumber
import re
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# -- Paths from orchestrator --------------------------------------------------
pdf_path = os.environ.get("PDF_PATH", "")
TEXT_DIR = Path(os.environ.get("TEXT_DIR", "."))


# -- Text extraction (two-column layout) --------------------------------------

def extract_from_pdf(pdf_path):
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            mid_x = page.width / 2
            left  = page.within_bbox((0, 0, mid_x + 10, page.height)).extract_text(
                        x_tolerance=3, y_tolerance=3) or ""
            right = page.within_bbox((mid_x - 10, 0, page.width, page.height)).extract_text(
                        x_tolerance=3, y_tolerance=3) or ""
            full_text += left + "\n" + right + "\n"
    return full_text


# -- Noise filter -------------------------------------------------------------

def is_noise(line):
    s = line.strip()
    lower = s.lower()

    if not s:
        return True
    if re.search(r'\bscience\b', lower) or re.search(r'\breprint\b', lower):
        return True
    if re.fullmatch(r'\d{1,3}', s):
        return True
    if re.match(r'^(Fig\.?|Figure)\s*\d+', s, re.IGNORECASE):
        return True
    if re.match(r'^Activity[\s_\-]*\d+', s, re.IGNORECASE):
        return True
    if re.search(r'_{4,}', s):
        return True
    if re.search(r'(.)\1{6,}', s):
        return True
    # Reprint year artifacts like "nt 2025-26"
    if re.search(r'\bnt\s+\d{4}-\d{2}\b', s):
        return True
    if re.match(r'^\d+\.\d+[\s\.]', s):
        return True
    if re.match(r'^[A-Z\s]{15,}$', s):
        return True
    return False


# -- Clean a single line ------------------------------------------------------

def clean_line(line):
    line = re.sub(r'(.)\1{3,}', r'\1', line)
    line = line.replace('\u2013', '-').replace('\u2014', '-')
    return line.strip()


# -- Check if a line is a Questions header ------------------------------------

def is_questions_header(line):
    """
    Matches all OCR variants seen in iesc PDFs:
      - "Questions"
      - "Q uestions"
      - "uestions"        (Q absorbed into drop-cap image)
      - "uestions 1"      (page 6 of iesc101 — trailing char merged in)
      - "Q" alone         (next line will be checked separately)
    """
    s = line.strip()
    if re.fullmatch(r'Questions', s, re.IGNORECASE):
        return True
    if re.fullmatch(r'Q\s*uestions', s, re.IGNORECASE):
        return True
    # KEY FIX: use re.match (not fullmatch) so "uestions 1" also matches
    if re.match(r'uestions', s, re.IGNORECASE):
        return True
    return False


# -- Find and extract all Questions blocks ------------------------------------

def get_question_blocks(text):
    lines = text.splitlines()
    blocks = []
    i = 0

    END_PATTERN = re.compile(
        r'^\s*('
        r'Activity'
        r'|Think\s+and\s+Act'
        r'|Example'
        r'|Exercises'
        r'|\d+\.\d+\s+[A-Z]'
        r'|Group\s+Activity'
        r'|What\s+you\s+have'
        r'|What\s*$'
        r')',
        re.IGNORECASE
    )

    while i < len(lines):
        line = lines[i].strip()
        detected = False

        # Case 1: line itself is a Questions header
        if is_questions_header(line):
            detected = True

        # Case 2: standalone "Q" with next line being "uestions..."
        elif line == 'Q' and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if re.match(r'uestions', next_line, re.IGNORECASE):
                detected = True
                i += 1  # skip the "uestions" line

        if detected:
            block_lines = []
            i += 1

            while i < len(lines):
                current = lines[i].strip()

                if not current:
                    i += 1
                    continue

                # Stop at section boundaries
                if END_PATTERN.match(current):
                    break

                # Stop at next Questions header
                if is_questions_header(current):
                    break
                if current == 'Q' and i + 1 < len(lines):
                    if re.match(r'uestions', lines[i + 1].strip(), re.IGNORECASE):
                        break

                if is_noise(current):
                    i += 1
                    continue

                # Stop on column-bleed fragment lines
                # These start with a single lowercase letter + space
                # e.g. "p of small particles." (from "u[p of]...")
                if re.match(r'^[a-z] ', current):
                    break

                block_lines.append(clean_line(current))
                i += 1

            if block_lines:
                blocks.append("Questions\n" + "\n".join(block_lines))
            continue

        i += 1

    return blocks


# -- Entry point --------------------------------------------------------------

if __name__ == "__main__":
    if not os.path.exists(pdf_path):
        print(f"[in_chapter_questions.py] ERROR: PDF not found: {pdf_path}")
        exit(1)

    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    raw_text = extract_from_pdf(pdf_path)
    blocks   = get_question_blocks(raw_text)

    if not blocks:
        print(f"[in_chapter_questions.py] SKIP: No question blocks found in {pdf_path}")
        exit(0)

    output_file = TEXT_DIR / "in_chapter_questions.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(blocks))

    print(f"[in_chapter_questions.py] Extracted {len(blocks)} question blocks -> {output_file}")