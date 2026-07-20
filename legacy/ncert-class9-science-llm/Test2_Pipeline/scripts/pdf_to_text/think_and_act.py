import sys
import pdfplumber
import re
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

pdf_path = os.environ.get("PDF_PATH", "")
TEXT_DIR = Path(os.environ.get("TEXT_DIR", "."))

def clean_text(text):
    text = re.sub(r'(.)\1{2,}', r'\1', text)
    text = re.sub(r'\b(?:[A-Za-z]\s){2,}[A-Za-z]\b', lambda m: m.group(0).replace(" ", ""), text)

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
    text = re.sub(r'[_]+', '', text)
    text = re.sub(r'Reprint\s*\d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b\d{4}-\d{2}\b', '', text)
    text = re.sub(r'\b\d{4}\b', '', text)

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        s = line.strip()
        if re.match(r'^(Fig\.?|Figure)\s*\d+(\.\d+)?', s, re.IGNORECASE):
            continue
        if re.match(r'^\d{1,3}$', s):
            n = int(s)
            if 60 <= n <= 100:
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
            left  = page.within_bbox((0, 0, mid_x, page.height)).extract_text(x_tolerance=3, y_tolerance=3) or ""
            right = page.within_bbox((mid_x, 0, page.width, page.height)).extract_text(x_tolerance=3, y_tolerance=3) or ""
            full_text += left + "\n" + right + "\n"
    return full_text

def get_think_and_act(text):
    lines = text.split("\n")
    think_act = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r'^Think\s+and\s+Act', line, re.IGNORECASE):
            temp = [line]
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if re.match(r'^(Activity|Think\s+and\s+Act|Questions|Example|\d+\.\d+)', next_line, re.IGNORECASE):
                    break
                temp.append(next_line)
                i += 1
            think_act.append("\n".join(temp).strip())
            continue
        i += 1
    return think_act

if __name__ == "__main__":
    if not os.path.exists(pdf_path):
        print(f"[think_and_act.py] ERROR: PDF not found: {pdf_path}")
        exit(1)

    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    raw_text     = extract_from_pdf(pdf_path)
    cleaned_text = clean_text(raw_text)
    think_act    = get_think_and_act(cleaned_text)

    if not think_act:
        print(f"[think_and_act.py] SKIP: No Think and Act sections found in {pdf_path}")
        exit(0)

    output_file = TEXT_DIR / "think_and_act.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(think_act))

    print(f"[think_and_act.py] Extracted {len(think_act)} blocks -> {output_file}")
