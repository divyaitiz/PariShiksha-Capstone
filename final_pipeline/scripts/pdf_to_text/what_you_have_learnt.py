import sys
import re
import os
import pdfplumber
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

pdf_path = os.environ.get("PDF_PATH", "")
TEXT_DIR = Path(os.environ.get("TEXT_DIR", "."))

def _is_noise(line: str) -> bool:
    s = line.strip()
    lower = s.lower()
    if not s:
        return False
    if "science" in lower or "reprint" in lower:
        return True
    if s.isdigit():
        return True
    if re.fullmatch(r'fig\.?\s*\d+(\.\d+)*', lower):
        return True
    if re.search(r'(.)\1{4,}', s):
        return True
    if s and len(re.findall(r'\d', s)) > len(s) * 0.6:
        return True
    return False

def _clean_line(line: str) -> str:
    line = re.sub(r'(.)\1{3,}', '', line)
    line = re.sub(r'[^\w\s.,:;()\-\u2013\u00b0/=+]', ' ', line)
    return line.strip()

def _read_pdf_lines(pdf_path: str) -> list:
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                full_text += extracted + "\n"
    return full_text.splitlines()

def extract_what_you_have_learnt(pdf_path: str) -> str:
    lines = _read_pdf_lines(pdf_path)
    start_idx = -1

    for i, line in enumerate(lines):
        lower = line.lower().strip()

        if re.search(r'what\s+you\s+have\s+learnt', lower):
            start_idx = i
            break

        if lower == "what" and i + 2 < len(lines):
            next1 = lines[i+1].lower().strip()
            next2 = lines[i+2].lower().strip()
            if "you have" in next1 and "learnt" in next2:
                start_idx = i
                break

        if lower == "learnt" and i >= 2:
            prev1 = lines[i-1].lower().strip()
            prev2 = lines[i-2].lower().strip()
            if "you have" in prev1 and "what" in prev2:
                start_idx = i - 2
                break

    if start_idx == -1:
        return ""

    section_lines = []
    for line in lines[start_idx:]:
        if line.strip().lower() == "exercises":
            break
        section_lines.append(line)

    cleaned = []
    for l in section_lines:
        if not _is_noise(l):
            cleaned.append(_clean_line(l))

    return "\n".join(cleaned).strip()

if __name__ == "__main__":
    if not os.path.exists(pdf_path):
        print(f"[what_you_have_learnt.py] ERROR: PDF not found: {pdf_path}")
        exit(1)

    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    result = extract_what_you_have_learnt(pdf_path)

    if not result:
        print(f"[what_you_have_learnt.py] SKIP: Section not found in {pdf_path}")
        exit(0)

    output_file = TEXT_DIR / "what_you_have_learnt.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result + "\n")

    print(f"[what_you_have_learnt.py] Extracted {len(result.splitlines())} lines -> {output_file}")
