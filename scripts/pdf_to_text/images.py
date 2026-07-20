"""
scripts/pdf_to_text/images.py
==============================
Extracts figures from a chapter PDF and writes images.txt.

Strategy (confirmed by probing iesc104 + iesc111):
  - Figures are NOT standalone xobjects — they are rendered as page content.
  - We locate figures by finding their captions ("Fig. X.Y: ...") via pdfplumber,
    then clip-render the page area ABOVE each caption using PyMuPDF.
  - Section association: find the nearest section heading (e.g. "11.3") that
    appears ABOVE the figure across all pages; fall back to chapter-level ("11.0")
    if the figure precedes the first heading.

Output (TEXT_DIR/images.txt):
  One JSON object per line, each describing one figure:
  {
    "figure_id":   "11.1",
    "caption":     "Fig. 11.1: Vibrating tuning fork just touching ...",
    "section_id":  "11.1",
    "page_number": 1,
    "image_path":  "extracted/iesc111/images/fig_11_1.png"
  }
  image_path is relative to the pipeline root (same convention as source_file).

Environment variables (set by run_pipeline.py):
  PDF_PATH      path to the chapter PDF
  TEXT_DIR      where to write images.txt
  CHAPTER_NAME  e.g. "iesc111"

Requirements:
  pip install pymupdf pdfplumber
"""

import os
import re
import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

try:
    import fitz          # PyMuPDF
    import pdfplumber
except ImportError:
    print("ERROR: pip install pymupdf pdfplumber")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
PDF_PATH     = Path(os.environ["PDF_PATH"])
TEXT_DIR     = Path(os.environ["TEXT_DIR"])
CHAPTER_NAME = os.environ["CHAPTER_NAME"]          # e.g. "iesc111"

# Rendered DPI for saved figure images (144 = 2× PDF point resolution)
RENDER_DPI = 144

# How many points ABOVE the caption to look for the figure content.
# NCERT figures are typically 120–200 pt tall.
FIGURE_WINDOW_ABOVE = 220   # pt

# Minimum gap from page top so we don't grab page headers
MIN_TOP_MARGIN = 30          # pt

# Caption pattern: "Fig. 11.1:", "Fig.4.1:" — tolerates missing space
CAPTION_RE = re.compile(
    r'(?:^|\b)(Fig\.?\s*(\d+\.\d+(?:\.\d+)?)\s*[:\s-])',
    re.IGNORECASE
)

# Section heading pattern: "11.2" or "4.2.1" at start of a text line
HEADING_RE = re.compile(r'^(\d+\.\d+(?:\.\d+)?)\s+\S')


# ── Infer chapter number from CHAPTER_NAME ────────────────────────────────────

def infer_chapter_number(chapter_name: str) -> str:
    """'iesc111' → '11',  'iesc104' → '4'"""
    m = re.search(r'iesc1(\d+)', chapter_name, re.IGNORECASE)
    return str(int(m.group(1))) if m else chapter_name


# ── Extract all captions with page/position info ──────────────────────────────

def extract_captions(pdf_path: Path) -> list[dict]:
    """
    Returns list of:
      { figure_id, caption_text, page_num (0-indexed), caption_top_y, caption_bottom_y,
        caption_x0, caption_x1 }
    Only includes the STANDALONE caption line (not inline references).
    """
    captions = []
    seen_ids = set()

    with pdfplumber.open(str(pdf_path)) as pdf:
        for pg_idx, page in enumerate(pdf.pages):
            words = page.extract_words()
            if not words:
                continue

            # Group words into text lines (bucket by y within 4pt)
            lines_dict: dict[int, list] = {}
            for w in words:
                y_key = round(float(w["top"]) / 4) * 4
                lines_dict.setdefault(y_key, []).append(w)

            for y_key in sorted(lines_dict.keys()):
                line_words = sorted(lines_dict[y_key], key=lambda x: float(x["x0"]))
                line_text  = " ".join(w["text"] for w in line_words)

                # A standalone caption starts with "Fig." at the beginning of the line
                if not re.match(r'^Fig[.\s]', line_text, re.IGNORECASE):
                    continue

                m = CAPTION_RE.search(line_text)
                if not m:
                    continue

                figure_id = m.group(2)   # e.g. "11.1"
                if figure_id in seen_ids:
                    continue             # skip duplicate occurrences of same fig ref
                seen_ids.add(figure_id)

                top    = min(float(w["top"])    for w in line_words)
                bottom = max(float(w["bottom"]) for w in line_words)
                x0     = min(float(w["x0"])     for w in line_words)
                x1     = max(float(w["x1"])     for w in line_words)

                captions.append({
                    "figure_id":     figure_id,
                    "caption_text":  line_text,
                    "page_num":      pg_idx,        # 0-indexed
                    "caption_top_y": top,
                    "caption_bot_y": bottom,
                    "caption_x0":    x0,
                    "caption_x1":    x1,
                    "page_height":   float(page.height),
                    "page_width":    float(page.width),
                })

    return captions


# ── Extract all section headings with page/position info ──────────────────────

def extract_headings(pdf_path: Path, chapter_number: str) -> list[dict]:
    """
    Returns list of { section_id, page_num (0-indexed), heading_top_y }
    sorted by (page_num, heading_top_y).
    """
    headings = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for pg_idx, page in enumerate(pdf.pages):
            words = page.extract_words()
            if not words:
                continue

            lines_dict: dict[int, list] = {}
            for w in words:
                y_key = round(float(w["top"]) / 3) * 3
                lines_dict.setdefault(y_key, []).append(w)

            for y_key in sorted(lines_dict.keys()):
                line_words = sorted(lines_dict[y_key], key=lambda x: float(x["x0"]))
                line_text  = " ".join(w["text"] for w in line_words)
                top        = min(float(w["top"]) for w in line_words)

                hm = HEADING_RE.match(line_text)
                if not hm:
                    continue

                section_id = hm.group(1)
                parts      = section_id.split(".")
                try:
                    if int(parts[0]) != int(chapter_number):
                        continue
                except ValueError:
                    continue

                headings.append({
                    "section_id": section_id,
                    "page_num":   pg_idx,
                    "top_y":      top,
                })

    return sorted(headings, key=lambda h: (h["page_num"], h["top_y"]))


# ── Map a figure (page, y) to the nearest heading above it ───────────────────

def find_section_for_figure(fig_page: int, fig_top_y: float,
                             headings: list[dict],
                             chapter_number: str) -> str:
    """
    Returns the section_id of the nearest heading that appears ABOVE (or at)
    the figure's position. Falls back to "chapter_number.0" if none found.
    """
    best = None
    for h in headings:
        if h["page_num"] < fig_page:
            best = h
        elif h["page_num"] == fig_page and h["top_y"] <= fig_top_y:
            best = h
        else:
            break   # headings are sorted; no need to continue

    return best["section_id"] if best else f"{chapter_number}.0"


# ── Clip-render a figure region from the PDF page ────────────────────────────

def render_figure_region(doc: fitz.Document,
                          page_num: int,
                          caption_top_pdflb: float,
                          caption_bot_pdflb: float,
                          page_height_pdflb: float,
                          page_height_pm: float) -> fitz.Pixmap:
    """
    Renders the region ABOVE the caption on `page_num`.
    pdfplumber and PyMuPDF share the same coordinate scale but pdfplumber
    reports page.height in its own units — we scale accordingly.
    """
    page = doc[page_num]
    pm_h = page.rect.height

    # Coordinate scaling: pdfplumber → PyMuPDF
    scale = pm_h / page_height_pdflb

    cap_top_pm = caption_top_pdflb * scale
    cap_bot_pm = caption_bot_pdflb * scale

    # Figure occupies the area above the caption
    fig_bottom = cap_top_pm          # bottom of figure = top of caption
    fig_top    = max(MIN_TOP_MARGIN, fig_bottom - FIGURE_WINDOW_ABOVE)

    # Use full page width (figures span both columns or either column)
    clip = fitz.Rect(0, fig_top, page.rect.width, fig_bottom)

    mat = fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72)
    pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
    return pix


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    chapter_number = infer_chapter_number(CHAPTER_NAME)

    # Output paths
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    images_dir = Path("extracted") / CHAPTER_NAME / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    output_txt = TEXT_DIR / "images.txt"

    print(f"Scanning {PDF_PATH.name} (ch{chapter_number}) for figures...")

    captions = extract_captions(PDF_PATH)
    headings = extract_headings(PDF_PATH, chapter_number)

    if not captions:
        print(f"No figure captions found in {PDF_PATH.name}. Skipping.")
        # Write empty file so run_pipeline.py knows we ran cleanly
        output_txt.write_text("", encoding="utf-8")
        return

    print(f"Found {len(captions)} captions, {len(headings)} section headings")

    doc = fitz.open(str(PDF_PATH))
    records = []

    for cap in captions:
        fig_id    = cap["figure_id"]
        fig_label = fig_id.replace(".", "_")
        img_filename = f"fig_{fig_label}.png"
        img_rel_path = str(images_dir / img_filename)  # relative to pipeline root

        # Section association
        section_id = find_section_for_figure(
            cap["page_num"], cap["caption_top_y"], headings, chapter_number
        )

        # Render the figure region
        try:
            pix = render_figure_region(
                doc,
                page_num           = cap["page_num"],
                caption_top_pdflb  = cap["caption_top_y"],
                caption_bot_pdflb  = cap["caption_bot_y"],
                page_height_pdflb  = cap["page_height"],
                page_height_pm     = None,   # computed inside function
            )
            pix.save(str(images_dir / img_filename))
            print(f"  Fig {fig_id} → page {cap['page_num']+1}, section {section_id}, saved {img_filename}")
        except Exception as e:
            print(f"  WARN: Could not render Fig {fig_id}: {e}")
            img_rel_path = ""

        records.append({
            "figure_id":   fig_id,
            "caption":     cap["caption_text"],
            "section_id":  section_id,
            "page_number": cap["page_num"] + 1,    # 1-indexed for humans
            "image_path":  img_rel_path,
        })

    doc.close()

    # Write images.txt — one JSON record per line
    with open(output_txt, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} records to {output_txt}")


if __name__ == "__main__":
    main()
