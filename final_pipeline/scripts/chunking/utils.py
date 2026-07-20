"""
utils.py — Shared helper functions for the chunking pipeline.
"""

import os
import re
import json


# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

# File types the pipeline knows about, mapped to their JSON filename
CONTENT_TYPES = {
    "informational_text":   "informational_text.json",
    "examples":             "examples.json",
    "exercises":            "exercises.json",
    "activities":           "activities.json",
    "in_chapter_questions": "in_chapter_questions.json",
    "what_you_have_learnt": "what_you_have_learnt.json",
    "think_and_act":        "think_and_act.json",
}

# Words per chunk threshold — informational_text sections longer than
# this will be passed to semantic splitting
WORD_THRESHOLD = 400


# ─────────────────────────────────────────────
# FILE HELPERS
# ─────────────────────────────────────────────

def get_available_jsons(chapter_path: str) -> dict:
    """
    Scans a chapter's json/ subfolder and returns a dict of
    {content_type: full_file_path} for every file that actually exists.
    Missing files are simply not included — no errors raised.

    Args:
        chapter_path: path to a chapter directory e.g. extracted/iesc101

    Returns:
        dict like {"informational_text": "extracted/iesc101/json/informational_text.json", ...}
    """
    json_dir = os.path.join(chapter_path, "json")
    available = {}

    if not os.path.isdir(json_dir):
        print(f"  [WARN] No json/ folder found at: {json_dir}")
        return available

    for content_type, filename in CONTENT_TYPES.items():
        full_path = os.path.join(json_dir, filename)
        if os.path.isfile(full_path):
            available[content_type] = full_path

    return available


def load_json(filepath: str):
    """
    Loads and returns JSON from a file.
    Returns None and prints a warning if the file is empty or malformed.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data:
            print(f"  [WARN] Empty JSON: {filepath}")
            return None
        return data
    except json.JSONDecodeError as e:
        print(f"  [ERROR] Failed to parse JSON: {filepath} — {e}")
        return None


def save_json(data, filepath: str):
    """Saves data to a JSON file, creating parent directories if needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────
# TEXT CLEANING
# ─────────────────────────────────────────────

# Page number patterns like "MATTER IN OUR SURROUNDINGS 13" or "21"
_PAGE_NUM_RE = re.compile(r'\b[A-Z][A-Z\s]{5,}\d+\s*$', re.MULTILINE)

# Standalone page numbers at start or end of string
_STANDALONE_PAGE_RE = re.compile(r'^\s*\d{1,3}\s*$')

# OCR superscript artifact — e.g. 16 m in^2 s  or  v-u (v-u) / a=
_CARET_RE = re.compile(r'\^(\d+|\(.*?\))')

# Excessive whitespace / newlines
_WHITESPACE_RE = re.compile(r'\n{3,}')

# Repeated dashes used as separators
_DASH_RE = re.compile(r'-{3,}')


def clean_text(text: str) -> str:
    """
    Cleans a raw text string:
    - Strips chapter title + page number leakage (e.g. "IS MATTER AROUND US PURE 21")
    - Removes OCR caret artifacts (^2, ^16)
    - Normalises excessive newlines and whitespace
    - Strips leading/trailing whitespace

    Args:
        text: raw string from JSON field

    Returns:
        cleaned string
    """
    if not text or not isinstance(text, str):
        return ""

    # Remove chapter-title-style page leakage: ALL CAPS phrase + number
    text = _PAGE_NUM_RE.sub("", text)

    # Remove OCR caret superscripts — replace ^2 with ² style or just space
    text = _CARET_RE.sub(lambda m: m.group(1), text)

    # Collapse 3+ newlines into 2
    text = _WHITESPACE_RE.sub("\n\n", text)

    # Remove separator dashes
    text = _DASH_RE.sub("", text)

    # Normalise spaces
    text = re.sub(r'[ \t]+', ' ', text)

    return text.strip()


def word_count(text: str) -> int:
    """Returns approximate word count of a string."""
    return len(text.split())


# ─────────────────────────────────────────────
# QUALITY CHECKS
# ─────────────────────────────────────────────

def is_truncated(text: str) -> bool:
    """
    Heuristic: returns True if the text looks like it was cut off mid-sentence.
    Checks if the last non-whitespace character is NOT a sentence-ending punctuation.

    Args:
        text: question or content string

    Returns:
        True if likely truncated, False otherwise
    """
    if not text:
        return True
    stripped = text.strip()
    return bool(stripped) and stripped[-1] not in ".?!:\"'"


def is_empty(text: str) -> bool:
    """Returns True if text is None, empty, or only whitespace."""
    return not text or not text.strip()


def is_too_long(text: str, max_words: int = 800) -> bool:
    """
    Returns True if text exceeds max_words.
    Used to flag questions/activities where page content leaked in.
    """
    return word_count(text) > max_words


# ─────────────────────────────────────────────
# CHUNK ID BUILDER
# ─────────────────────────────────────────────

def build_chunk_id(chapter: str, content_type: str, index: int) -> str:
    """
    Builds a unique, consistent chunk ID.

    Args:
        chapter:      e.g. "iesc101"
        content_type: e.g. "informational_text"
        index:        integer position of this chunk within its content type

    Returns:
        string like "iesc101_informational_text_003"
    """
    return f"{chapter}_{content_type}_{str(index).zfill(3)}"


# ─────────────────────────────────────────────
# FLAGGING
# ─────────────────────────────────────────────

def write_flagged(flagged_dir: str, chapter: str, content_type: str, items: list, reason: str):
    """
    Saves flagged items (bad data, truncated text, leaked content) to
    flagged/<chapter>_<content_type>_flagged.json with a reason field.

    Args:
        flagged_dir:  path to the flagged/ output directory
        chapter:      e.g. "iesc101"
        content_type: e.g. "in_chapter_questions"
        items:        list of dicts that were flagged
        reason:       human-readable reason string
    """
    if not items:
        return

    os.makedirs(flagged_dir, exist_ok=True)
    filename = f"{chapter}_{content_type}_flagged.json"
    filepath = os.path.join(flagged_dir, filename)

    output = {
        "chapter": chapter,
        "content_type": content_type,
        "reason": reason,
        "count": len(items),
        "items": items
    }

    # If file already exists, append to existing items
    if os.path.isfile(filepath):
        existing = load_json(filepath)
        if existing and "items" in existing:
            output["items"] = existing["items"] + items
            output["count"] = len(output["items"])

    save_json(output, filepath)
    print(f"  [FLAGGED] {len(items)} item(s) → {filepath}  Reason: {reason}")