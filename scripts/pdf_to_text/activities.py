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

    def clean_header(match):
        full = match.group(0)
        full = re.sub(r'([0,2-9])\1+', r'\1', full)
        full = re.sub(r'(1)\1{3,}', r'\1\1', full)
        full = re.sub(r'(1)\1(?=\d)', r'\1', full)
        full = re.sub(r'\.{2,}', '.', full)
        m = re.search(r'Activity\s*(\d+)\.(\d+)', full, re.IGNORECASE)
        if m:
            return f"Activity {m.group(1)}.{m.group(2)}"
        return full

    text = re.sub(r'Activity\s*[0-9.]+', clean_header, text, flags=re.IGNORECASE)
    text = re.sub(r'\.{5,}', '.', text)
    text = re.sub(r'\b(?:[A-Za-z]\s){2,}[A-Za-z]\b', lambda m: m.group(0).replace(" ", ""), text)
    text = re.sub(r'\b(m|cm|km)\s+(s|h)[–\-](1|2)\b', r'\1 \2^-\3', text)
    text = re.sub(r'\b(m|cm|km|s|h)[–\-](1|2)\b', r'\1^-\2', text)

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

    text = re.sub(r'\bReprint\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bSCIENCE\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b[0-9]?025-26\b', '', text)
    text = re.sub(r'[•●▪■◦◆►]', '', text)
    text = re.sub(r'_{2,}', '', text)

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
    text = re.sub(r'\(?\b(?:as\s+)?(?:shown|given)\s+in\s+Fig\.?s?\s*\d+(?:\.\d+)?\)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\(?\b(?:as\s+)?(?:shown|given)\s+in\s+Figure\s*\d+(?:\.\d+)?\)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\(?\bFig\.?\s*\d+(\.\d+)?[a-zA-Z]?\)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r',\s*(?:as\s+)?shown\s+in\s*$', '.', text, flags=re.MULTILINE)
    text = re.sub(r'\b(?:as\s+)?shown\s+in\s*$', '.', text, flags=re.MULTILINE)

    return text


def extract_from_pdf(pdf_path):
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            mid_x = page.width / 2
            left  = page.within_bbox((0, 0, mid_x, page.height)).extract_text(x_tolerance=3, y_tolerance=3, layout=True) or ""
            right = page.within_bbox((mid_x, 0, page.width, page.height)).extract_text(x_tolerance=3, y_tolerance=3, layout=True) or ""
            full_text += left + "\n" + right + "\n"
    return full_text


def get_activities(text):
    lines = text.split("\n")
    activities = []
    i = 0

    _STOP = re.compile(
        r'^\s*(Activity|Think\s+and\s+Act|Questions|Q\s*uestions|Example|\d+\.\d+|Exercises|Summary)',
        re.IGNORECASE
    )

    while i < len(lines):
        line = lines[i].strip()

        if re.match(r'^Activity\s*\d+', line, re.IGNORECASE):
            if not re.search(r'\d', line):
                i += 1
                continue

            temp = [line]
            i += 1
            while i < len(lines):
                if re.match(r'^\s*what\s*$', lines[i], re.IGNORECASE):
                    lookahead = " ".join([l.strip() for l in lines[i:i+4]])
                    if re.search(r'what\s+you\s+have\s+learnt', lookahead, re.IGNORECASE):
                        break

                if _STOP.match(lines[i]):
                    break

                if re.match(r'^\s*Q\s*$', lines[i], re.IGNORECASE):
                    if i + 1 < len(lines) and re.match(r'^\s*uestions\s*$', lines[i+1], re.IGNORECASE):
                        break

                if lines[i].strip():
                    temp.append(lines[i])
                i += 1

            activities.append("\n".join(temp).strip())
            continue
        i += 1
    return activities


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(pdf_path):
        print(f"[activities.py] ERROR: PDF not found: {pdf_path}")
        exit(1)

    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    raw_text     = extract_from_pdf(pdf_path)
    cleaned_text = clean_text(raw_text)
    activities   = get_activities(cleaned_text)

    if not activities:
        print(f"[activities.py] SKIP: No activities found in {pdf_path}")
        exit(0)

    output_file = TEXT_DIR / "activities.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(activities))

    print(f"[activities.py] Extracted {len(activities)} activities -> {output_file}")
