"""
scripts/pdf_to_text/informational_text.py
────────────────────────────────────────────
NCERT PDF → Informational Text Extractor

Used by:
    run_pipeline.py

INPUT:
    Environment Variables:
        PDF_PATH
        TEXT_DIR
        JSON_DIR
        CHAPTER_NAME

OUTPUT:
    extracted/<chapter>/text/informational_text.txt

EXTRACTS:
    • chapter title
    • introduction
    • sections
    • subsections
    • prose/informational text

EXCLUDES:
    • activities
    • examples
    • exercises
    • questions
    • figure captions
    • tables
    • summaries
    • what you have learnt
    • think and act
"""

import os
import re
import fitz
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

# ─────────────────────────────────────────────
# ENV VARIABLES
# ─────────────────────────────────────────────

PDF_PATH = Path(os.environ["PDF_PATH"])

TEXT_DIR = Path(os.environ["TEXT_DIR"])

CHAPTER_NAME = os.environ["CHAPTER_NAME"]

OUTPUT_FILE = TEXT_DIR / "informational_text.txt"


# ─────────────────────────────────────────────
# EXCLUSION RULES
# ─────────────────────────────────────────────

EXCLUDE_PATTERNS = [

    # activities/examples
    r"^activity",
    r"^activities",
    r"^example",
    r"^examples",

    # questions
    r"^questions?$",
    r"^uestions$",
    r"^q$",

    # pedagogical blocks
    r"^think and act",
    r"^what you have learnt",
    r"^what have you learnt",
    r"^more to know",
    r"^group activity",
    r"^exercise",
    r"^exercises",

    # figures/tables
    r"^fig\.",
    r"^figure",
    r"^table",

    # print noise
    r"^reprint",
    r"^science\s*\d*$",
]

EXCLUDE_REGEX = re.compile(
    "|".join(EXCLUDE_PATTERNS),
    re.IGNORECASE
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def clean_text(text):

    text = text.replace("\u00ad", "")

    text = text.replace("\n", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def is_noise(text):

    text = text.strip()

    if len(text) < 2:
        return True

    # page numbers
    if re.fullmatch(r"\d+", text):
        return True

    return False


def should_exclude(text):

    return bool(
        EXCLUDE_REGEX.match(
            text.lower().strip()
        )
    )


def is_section(line):

    return bool(
        re.match(r"^\d+\.\d+\s+", line)
    )


def is_subsection(line):

    return bool(
        re.match(r"^\d+\.\d+\.\d+\s+", line)
    )


def extract_heading(line):

    match = re.match(
        r"^(\d+(?:\.\d+)+)\s+(.*)",
        line
    )

    if not match:
        return None, line

    return match.group(1), match.group(2).strip()


# ─────────────────────────────────────────────
# MERGE WRAPPED HEADINGS
# ─────────────────────────────────────────────

def merge_wrapped_lines(lines):

    merged = []

    i = 0

    while i < len(lines):

        current = lines[i].strip()

        if i + 1 < len(lines):

            nxt = lines[i + 1].strip()

            # Merge wrapped headings
            if (
                re.match(r"^\d+\.\d+", current)
                and len(current.split()) < 8
                and not re.match(r"^\d+\.\d+", nxt)
            ):

                current += " " + nxt

                i += 1

        merged.append(current)

        i += 1

    return merged


# ─────────────────────────────────────────────
# PDF EXTRACTION
# ─────────────────────────────────────────────

def extract_pdf_lines(pdf_path):

    doc = fitz.open(pdf_path)

    lines = []

    for page in doc:

        blocks = page.get_text("blocks")

        for block in blocks:

            block_text = block[4]

            for raw_line in block_text.split("\n"):

                line = clean_text(raw_line)

                if not line:
                    continue

                if is_noise(line):
                    continue

                lines.append(line)

    return lines


# ─────────────────────────────────────────────
# BUILD STRUCTURED TEXT
# ─────────────────────────────────────────────

def build_output(lines):

    output = []

    first_section_found = False

    skip_mode = False

    chapter_found = False

    chapter_number = None

    for line in lines:

        # ─────────────────────────
        # EXCLUSION BLOCKS
        # ─────────────────────────

        if should_exclude(line):

            skip_mode = True

            continue

        # stop skipping at next heading
        if (
            is_section(line)
            or is_subsection(line)
        ):
            skip_mode = False

        if skip_mode:
            continue

        # ─────────────────────────
        # CHAPTER DETECTION
        # ─────────────────────────

        chapter_match = re.match(
            r"^chapter\s+(\d+)",
            line,
            re.IGNORECASE
        )

        if chapter_match:

            chapter_number = chapter_match.group(1)

            chapter_found = True

            continue

        # probable chapter title
        if chapter_found and not first_section_found:

            if (
                len(line.split()) > 2
                and not is_section(line)
            ):

                output.append(
                    f"CHAPTER: {chapter_number} - {line}\n"
                )

                output.append("\nINTRO:\n")

                chapter_found = False

                continue

        # ─────────────────────────
        # SUBSECTION
        # ─────────────────────────

        if is_subsection(line):

            sid, title = extract_heading(line)

            output.append(
                f"\nSUBSECTION: {sid} {title}\n"
            )

            continue

        # ─────────────────────────
        # SECTION
        # ─────────────────────────

        if is_section(line):

            sid, title = extract_heading(line)

            first_section_found = True

            output.append(
                f"\nSECTION: {sid} {title}\n"
            )

            continue

        # ─────────────────────────
        # REMOVE NUMBERED QUESTIONS
        # ─────────────────────────

        if re.match(r"^\d+\.", line):
            continue

        # ─────────────────────────
        # REMOVE SHORT JUNK
        # ─────────────────────────

        if len(line.split()) < 3:
            continue

        # ─────────────────────────
        # PROSE
        # ─────────────────────────

        output.append(line + "\n")

    return "".join(output)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():

    TEXT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print(f"Processing: {PDF_PATH.name}")

    lines = extract_pdf_lines(PDF_PATH)

    print(f"Raw lines extracted: {len(lines)}")

    lines = merge_wrapped_lines(lines)

    structured_text = build_output(lines)

    OUTPUT_FILE.write_text(
        structured_text,
        encoding="utf-8"
    )

    print(f"Saved: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()