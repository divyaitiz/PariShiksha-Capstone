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

def extract_page_text_two_columns(page):
    mid_x      = page.width / 2
    left_text  = page.within_bbox((0, 0, mid_x, page.height)).extract_text(x_tolerance=3, y_tolerance=3) or ""
    right_text = page.within_bbox((mid_x, 0, page.width, page.height)).extract_text(x_tolerance=3, y_tolerance=3) or ""
    return left_text + "\n" + right_text


def collect_full_text(pdf_path):
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            full_text += extract_page_text_two_columns(page) + "\n"
    return full_text


def fix_formulas(text):
    text = re.sub(r'(?m)^[–-]\s*1\s+[–-]\s*1\s*\nfrom (18 km h) to (36 km h)', r'from \1-1 to \2-1', text)
    text = re.sub(r'(?m)^[–-]\s*2\s*\n(The acceleration of the car is 1 m s) and', r'\1-2 and', text)
    text = re.sub(r'(?m)^1\s*\n(s = u t \+ a t 2)\s*\n2\s*$', r's = u t + (1/2) a t 2', text)
    text = re.sub(r'(?m)^1\s*\n(= 5 m s[–-]1 × 5 s \+ )× (1 m s[–-]2 × \(5 s\)2)\s*\n2\s*$', r'\1(1/2) × \2', text)
    text = re.sub(r'(?m)^1\s*\n(= \(12 m s[–-]1 \) × \(2 s\) \+ )(\(–6 m s[–-]2 \) \(2 s\)2)\s*\n2\s*$', r'\1(1/2) \2', text)
    text = re.sub(r'(?m)^1\s*\n(=\s*)m s[–-]2\s*\n15\s*$', r'\1(1/15) m s-2', text)
    text = re.sub(r'(?m)^1\s*\n(The acceleration of the train is )m s[–-]\s*2\s*\n15\s*$', r'\1(1/15) m s-2', text)
    text = re.sub(r'(?m)^(Total distance\s*travelled)\s*\n(Average speed =)\s*\n(Total\s*time\s*taken|Totaltimetaken)\s*$', r'\2 \1 / \3', text)
    text = re.sub(r'(?m)^(Total distance\s*covered)\s*\n(Average speed =)\s*\n(Total\s*time\s*taken|Totaltimetaken)\s*$', r'\2 \1 / \3', text)
    text = re.sub(r'(?m)^(Displacement)\s*\n(Average velocity =)\s*\n(Total\s*time\s*taken|Totaltimetaken)\s*$', r'\2 \1 / \3', text)
    text = re.sub(r'(?m)^\(v[–-]u\)\s*\n(a\s*=)\s*\n(t)\s*$', r'\1 (v-u) / \2', text)
    text = re.sub(r'(?m)^(v[–-]u)\s*\n(a\s*=)\s*\n(t)\s*$', r'\1 (v-u) / \2', text)
    text = re.sub(r'(?m)^(v2)\s*\n(s =)\s*\n(2a)\s*$', r'\2 \1 / \3', text)
    text = re.sub(r'(?m)^(32 m)\s*\n(=\s*=\s*5\.33 m s[–-]1)\s*\n(6\s*s)\s*$', r'= \1 / \3 = 5.33 m s-1', text)
    text = re.sub(r'(?m)^(6m s[–-]1 [–-]0m s[–-]1)\s*\n(a =)\s*\n(30 s)\s*$', r'\2 (\1) / \3', text)
    text = re.sub(r'(?m)^(4m s[–-]1 [–-]6m s[–-]1)\s*\n(Then, a =)\s*\n(5 s)\s*$', r'\2 (\1) / \3', text)
    text = re.sub(r'(?m)^(20 m s[–-]1 [–-]\s*0ms[–-]1)\s*\n(=)\s*\n(300s)\s*$', r'\2 (\1) / \3', text)
    text = re.sub(r'(?m)^(\(\(20 ms[–-]1\)2\))\s*\n(=)\s*\n(2×\(1/15\)\s*ms[–-]2)\s*$', r'\2 \1 / \3', text)
    text = re.sub(r'(?m)^(\(20 ms[–-]1\)2)\s*\n(=)\s*\n(2×\(1/15\)\s*ms[–-]2)\s*$', r'\2 \1 / \3', text)
    text = re.sub(r'(?m)^(10 m s[–-]1 [–-]\s*5 m s[–-]1)\s*\n(=)\s*\n(5s)\s*$', r'\2 (\1) / \3', text)
    text = re.sub(r'(?m)^(0\s*m)\s*\n(=\s*)\n(60\s*s)\s*$', r'\2 \1 / \3', text)
    text = re.sub(r'(?m)^(v = s = 400 km)\s*\n(av t 8 h)\s*$', r'v_av = s / t = 400 km / 8 h', text)
    text = re.sub(r'(?m)^(km 1000m 1h)\s*\n(= 50 × ×)\s*\n(h 1km 3600s)\s*$', r'= 50 × (1000m / 1km) × (1h / 3600s)', text)
    text = re.sub(r'(?m)^180m 180 m 1min\s*\n= ×\s*\n=\s*\n1min 1min 60s\s*$', r'= (180 m / 1 min) × (1 min / 60 s)', text)
    text = re.sub(r'(?m)^\(\s*\)\s*\n', '', text)
    return text


def normalize_powers(text):
    text = re.sub(r'(?<!\d)([a-zA-Z\)\]])\s+(\d+)', r'\1^\2', text)
    text = re.sub(r'(\([^\)]+\))\s*(\d+)', r'\1^\2', text)
    return text


def clean_text(text):
    text = re.sub(
        r'(\d+\.\d+)\s*\n\s*[Ee]{2,}[Xx]{2,}[Aa]{2,}[Mm]{2,}[Pp]{2,}[Ll]{2,}[Ee]{2,}\s*',
        r'Example \1 ',
        text
    )
    text = re.sub(r'(.)\1{3,}', lambda m: m.group(0)[0], text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = fix_formulas(text)
    text = normalize_powers(text)
    return text.strip()


END_MARKERS = re.compile(
    r'^\s*('
    r'Q\s*$'
    r'|u\s*estions'
    r'|Activity'
    r'|\d+\.\d+\s+[A-Z][a-z]'
    r'|What\s+you\s+have'
    r'|Exercises'
    r'|Table\s+\d'
    r'|\d+\.\d+\.\d+\s'
    r')',
    re.IGNORECASE | re.MULTILINE
)

EXAMPLE_START = re.compile(r'^Example\s+\d+\.\d+', re.IGNORECASE)


def is_skip_line(line):
    stripped = line.strip()
    if re.match(r'^(MOTION|SCIENCE|Reprint|\d{3,4}-\d{2,4})$', stripped, re.IGNORECASE):
        return True
    if re.match(r'^\d{2}$', stripped):
        num = int(stripped)
        if 70 <= num <= 90:
            return True
    return False


def extract_example_blocks(full_text):
    lines   = full_text.splitlines()
    blocks  = []
    current = []
    inside  = False

    for line in lines:
        stripped = line.strip()

        if is_skip_line(stripped):
            continue

        if EXAMPLE_START.match(stripped):
            if current:
                blocks.append("\n".join(current).strip())
            current = [line]
            inside  = True
            continue

        if not inside:
            continue

        if END_MARKERS.match(line):
            blocks.append("\n".join(current).strip())
            current = []
            inside  = False
            continue

        current.append(line)

    if current:
        blocks.append("\n".join(current).strip())

    blocks = [b for b in blocks if 'Solution' in b and len(b) > 80]
    return blocks


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(pdf_path):
        print(f"[examples.py] ERROR: PDF not found: {pdf_path}")
        exit(1)

    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    raw    = collect_full_text(pdf_path)
    text   = clean_text(raw)
    blocks = extract_example_blocks(text)

    if not blocks:
        print(f"[examples.py] SKIP: No examples found in {pdf_path}")
        exit(0)

    output_file = TEXT_DIR / "examples.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(blocks))

    print(f"[examples.py] Extracted {len(blocks)} examples -> {output_file}")
