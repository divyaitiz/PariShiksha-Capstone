"""
scripts/text_to_json/informational_text.py
────────────────────────────────────────────
Convert informational_text.txt → informational_text.json

Used by:
    run_pipeline.py

INPUT:
    extracted/<chapter>/text/informational_text.txt

OUTPUT:
    extracted/<chapter>/json/informational_text.json

JSON SCHEMA:
{
  "chapter_id": "iesc103",
  "chapter_number": "3",
  "chapter_title": "Atoms and Molecules",
  "source_file": "iesc103.pdf",
  "introduction": "...",
  "sections": [
    {
      "section_id": "3.1",
      "section_number": "3.1",
      "title": "...",
      "content": "...",
      "subsections": [
        {
          "section_id": "3.1.1",
          "section_number": "3.1.1",
          "title": "...",
          "content": "..."
        }
      ]
    }
  ]
}
"""

import os
import re
import json
import sys

from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


# ─────────────────────────────────────────────
# ENV VARIABLES
# ─────────────────────────────────────────────

TEXT_DIR = Path(
    os.environ.get(
        "TEXT_DIR",
        "../../extracted/iesc101/text"
    )
)

JSON_DIR = Path(
    os.environ.get(
        "JSON_DIR",
        "../../extracted/iesc101/json"
    )
)

CHAPTER_NAME = os.environ.get(
    "CHAPTER_NAME",
    "iesc101"
)

TEXT_FILE = (
    TEXT_DIR / "informational_text.txt"
)

OUTPUT_FILE = (
    JSON_DIR / "informational_text.json"
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def clean_text(text):

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ─────────────────────────────────────────────
# PARSER
# ─────────────────────────────────────────────

def parse_text_file(text_path, chapter_id):

    lines = text_path.read_text(
        encoding="utf-8"
    ).splitlines()

    data = {
        "chapter_id": chapter_id,
        "chapter_number": "",
        "chapter_title": "",
        "source_file": f"{chapter_id}.pdf",
        "introduction": "",
        "sections": []
    }

    current_section = None

    current_subsection = None

    mode = None

    for raw_line in lines:

        line = raw_line.strip()

        if not line:
            continue

        # ─────────────────────────
        # CHAPTER
        # ─────────────────────────

        chapter_match = re.match(
            r"^CHAPTER:\s*(\d+)\s*-\s*(.*)",
            line,
            re.IGNORECASE
        )

        if chapter_match:

            data["chapter_number"] = (
                chapter_match.group(1)
            )

            data["chapter_title"] = (
                chapter_match.group(2).strip()
            )

            continue

        # ─────────────────────────
        # INTRO
        # ─────────────────────────

        if line.startswith("INTRO:"):

            mode = "intro"

            continue

        # ─────────────────────────
        # SECTION
        # ─────────────────────────

        section_match = re.match(
            r"^SECTION:\s*([0-9.]+)\s+(.*)",
            line
        )

        if section_match:

            sid = section_match.group(1)

            title = section_match.group(2).strip()

            current_section = {
                "section_id": sid,
                "section_number": sid,
                "title": title,
                "content": "",
                "subsections": []
            }

            data["sections"].append(
                current_section
            )

            current_subsection = None

            mode = "section"

            continue

        # ─────────────────────────
        # SUBSECTION
        # ─────────────────────────

        subsection_match = re.match(
            r"^SUBSECTION:\s*([0-9.]+)\s+(.*)",
            line
        )

        if subsection_match:

            sid = subsection_match.group(1)

            title = subsection_match.group(2).strip()

            current_subsection = {
                "section_id": sid,
                "section_number": sid,
                "title": title,
                "content": ""
            }

            if current_section:

                current_section[
                    "subsections"
                ].append(current_subsection)

            mode = "subsection"

            continue

        # ─────────────────────────
        # CONTENT
        # ─────────────────────────

        if mode == "intro":

            data["introduction"] += (
                " " + line
            )

        elif mode == "section":

            if current_section:

                current_section["content"] += (
                    " " + line
                )

        elif mode == "subsection":

            if current_subsection:

                current_subsection["content"] += (
                    " " + line
                )

    # ─────────────────────────
    # CLEANUP
    # ─────────────────────────

    data["introduction"] = clean_text(
        data["introduction"]
    )

    for section in data["sections"]:

        section["content"] = clean_text(
            section["content"]
        )

        for subsection in section["subsections"]:

            subsection["content"] = clean_text(
                subsection["content"]
            )

    return data


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():

    JSON_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if not TEXT_FILE.exists():

        print(
            "informational_text.txt not found"
        )

        return

    data = parse_text_file(
        TEXT_FILE,
        CHAPTER_NAME
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()