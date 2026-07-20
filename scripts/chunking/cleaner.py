"""
cleaner.py — One cleaning function per content type.

Each function takes the raw loaded JSON data and returns a cleaned version.
Flagged items (truncated, leaked content, empty) are written to flagged/ folder.
"""

from utils import (
    clean_text,
    is_empty,
    is_truncated,
    is_too_long,
    write_flagged,
)


# ─────────────────────────────────────────────
# INFORMATIONAL TEXT
# ─────────────────────────────────────────────

def clean_informational_text(data: dict, chapter: str, flagged_dir: str) -> dict:
    """
    Cleans informational_text.json data:
    - Removes sections/subsections with empty content
    - Renames duplicate section_ids by appending _a, _b, _c
    - Cleans all title and content fields

    Args:
        data:        raw loaded JSON dict
        chapter:     chapter id string e.g. "iesc101"
        flagged_dir: path to flagged/ output folder

    Returns:
        cleaned dict with same structure
    """
    seen_ids = {}       # tracks section_ids already encountered
    cleaned_sections = []
    empty_items = []

    for section in data.get("sections", []):
        sid = section.get("section_id", "")
        content = clean_text(section.get("content", ""))
        title = clean_text(section.get("title", ""))

        # Deduplicate section_id
        if sid in seen_ids:
            seen_ids[sid] += 1
            suffix = chr(96 + seen_ids[sid])   # a, b, c ...
            sid = f"{sid}_{suffix}"
        else:
            seen_ids[sid] = 1

        # Clean subsections
        cleaned_subsections = []
        for sub in section.get("subsections", []):
            sub_id = sub.get("section_id", "")
            sub_content = clean_text(sub.get("content", ""))
            sub_title = clean_text(sub.get("title", ""))

            if is_empty(sub_content):
                empty_items.append({
                    "section_id": sub_id,
                    "title": sub_title,
                    "reason": "empty content"
                })
                continue    # skip empty subsections

            # Deduplicate subsection id too
            if sub_id in seen_ids:
                seen_ids[sub_id] += 1
                suffix = chr(96 + seen_ids[sub_id])
                sub_id = f"{sub_id}_{suffix}"
            else:
                seen_ids[sub_id] = 1

            cleaned_subsections.append({
                "section_id": sub_id,
                "section_number": sub.get("section_number", ""),
                "title": sub_title,
                "content": sub_content,
            })

        # Build cleaned section — keep even if its own content is empty
        # as long as it has valid subsections
        if is_empty(content) and not cleaned_subsections:
            empty_items.append({
                "section_id": sid,
                "title": title,
                "reason": "empty content and no subsections"
            })
            continue

        cleaned_sections.append({
            "section_id": sid,
            "section_number": section.get("section_number", ""),
            "title": title,
            "content": content,
            "subsections": cleaned_subsections,
        })

    if empty_items:
        write_flagged(flagged_dir, chapter, "informational_text", empty_items,
                      "Empty content — likely image/figure in original PDF")

    return {
        "chapter_id": data.get("chapter_id", chapter),
        "chapter_title": clean_text(data.get("chapter_title", "")),
        "sections": cleaned_sections,
    }


# ─────────────────────────────────────────────
# EXAMPLES
# ─────────────────────────────────────────────

def clean_examples(data: list, chapter: str, flagged_dir: str) -> list:
    """
    Cleans examples.json data:
    - Strips OCR artifacts from problem text and steps
    - Cleans all text fields

    Args:
        data:        raw loaded JSON list
        chapter:     chapter id string
        flagged_dir: path to flagged/ folder

    Returns:
        cleaned list of example dicts
    """
    cleaned = []

    for item in data:
        problem = clean_text(item.get("problem", ""))
        final_answer = clean_text(str(item.get("final_answer", "")))
        formulas = [clean_text(f) for f in item.get("formulas_used", []) if f]

        # Clean each step
        raw_steps = item.get("steps", []) or []
        steps = [clean_text(s) for s in raw_steps if not is_empty(s)]

        if is_empty(problem):
            continue    # skip examples with no problem text

        cleaned.append({
            "example_id": item.get("example_id", ""),
            "chapter":    item.get("chapter", chapter),
            "problem":    problem,
            "given":      item.get("given", {}),
            "steps":      steps,
            "formulas_used": formulas,
            "final_answer":  final_answer,
            "units":         item.get("units", ""),
        })

    return cleaned


# ─────────────────────────────────────────────
# EXERCISES
# ─────────────────────────────────────────────

def clean_exercises(data: dict, chapter: str, flagged_dir: str) -> list:
    """
    Cleans exercises.json data:
    - Joins subparts into the parent question text
    - Cleans all text fields

    Args:
        data:        raw loaded JSON dict (has "chapter" and "exercises" keys)
        chapter:     chapter id string
        flagged_dir: path to flagged/ folder

    Returns:
        flat cleaned list of exercise dicts, each self-contained
    """
    cleaned = []
    flagged = []

    exercises = data if isinstance(data, list) else data.get("exercises", [])

    for item in exercises:
        question = clean_text(item.get("question", ""))

        if is_empty(question):
            continue

        # Join subparts into the question text if they exist
        subparts = item.get("subparts", [])
        if subparts:
            parts_text = "\n".join(
                f"({p.get('label', '')}) {clean_text(p.get('text', ''))}"
                for p in subparts
                if not is_empty(p.get("text", ""))
            )
            full_text = f"{question}\n{parts_text}"
        else:
            full_text = question

        # Flag if suspiciously long (page content leaked in)
        if is_too_long(full_text, max_words=300):
            flagged.append({"id": item.get("id"), "text": full_text[:300] + "..."})
            continue

        cleaned.append({
            "id":       item.get("id"),
            "chapter":  chapter,
            "text":     full_text,
        })

    if flagged:
        write_flagged(flagged_dir, chapter, "exercises", flagged,
                      "Suspiciously long — possible page content leakage")

    return cleaned


# ─────────────────────────────────────────────
# ACTIVITIES
# ─────────────────────────────────────────────

def clean_activities(data: dict, chapter: str, flagged_dir: str) -> list:
    """
    Cleans activities.json data:
    - Merges items with duplicate activity_id (continuation splits from extraction)
    - Drops the unreliable steps field entirely
    - Cleans content text

    Args:
        data:        raw loaded JSON dict (has "activities" key)
        chapter:     chapter id string
        flagged_dir: path to flagged/ folder

    Returns:
        flat cleaned list of activity dicts
    """
    raw_activities = data.get("activities", data) if isinstance(data, dict) else data

    # First pass: merge duplicates by activity_id
    merged = {}     # activity_id → merged dict
    order = []      # preserve original order

    for item in raw_activities:
        aid = item.get("activity_id", str(item.get("id", "")))
        content = clean_text(item.get("content", ""))
        title = clean_text(item.get("title", ""))

        if aid not in merged:
            merged[aid] = {
                "activity_id": aid,
                "chapter":     item.get("chapter", chapter),
                "title":       title,
                "content":     content,
            }
            order.append(aid)
        else:
            # Append continuation content
            if content:
                merged[aid]["content"] = merged[aid]["content"] + "\n\n" + content

    # Second pass: clean merged content and skip empties
    cleaned = []
    for aid in order:
        item = merged[aid]
        if is_empty(item["content"]):
            continue
        cleaned.append(item)

    return cleaned


# ─────────────────────────────────────────────
# IN-CHAPTER QUESTIONS
# ─────────────────────────────────────────────

def clean_in_chapter_questions(data: dict, chapter: str, flagged_dir: str) -> list:
    """
    Cleans in_chapter_questions.json data:
    - Flags truncated questions (cut off mid-sentence)
    - Flags questions where page content leaked in (too long)
    - Cleans question text

    Args:
        data:        raw loaded JSON dict (has "sections" key)
        chapter:     chapter id string
        flagged_dir: path to flagged/ folder

    Returns:
        flat cleaned list of question dicts
    """
    cleaned = []
    flagged_truncated = []
    flagged_leaked = []

    for section in data.get("sections", []):
        section_id = section.get("section_key", section.get("section_id", ""))

        for q in section.get("questions", []):
            qid = q.get("qid", str(q.get("id", "")))
            text = clean_text(q.get("question", ""))

            if is_empty(text):
                continue

            if is_too_long(text, max_words=200):
                flagged_leaked.append({"qid": qid, "section": section_id,
                                       "preview": text[:200] + "..."})
                continue

            if is_truncated(text):
                flagged_truncated.append({"qid": qid, "section": section_id,
                                          "text": text})
                continue

            cleaned.append({
                "qid":       qid,
                "section_id": section_id,
                "chapter":   chapter,
                "text":      text,
            })

    if flagged_truncated:
        write_flagged(flagged_dir, chapter, "in_chapter_questions",
                      flagged_truncated, "Truncated mid-sentence — extraction issue")

    if flagged_leaked:
        write_flagged(flagged_dir, chapter, "in_chapter_questions",
                      flagged_leaked, "Suspiciously long — page content leaked in")

    return cleaned


# ─────────────────────────────────────────────
# WHAT YOU HAVE LEARNT
# ─────────────────────────────────────────────

def clean_what_you_have_learnt(data: dict, chapter: str, flagged_dir: str) -> list:
    """
    Cleans what_you_have_learnt.json data:
    - Strips chapter title and page number leakage from point text
    - Skips empty points

    Args:
        data:        raw loaded JSON dict (has "points" key)
        chapter:     chapter id string
        flagged_dir: path to flagged/ folder

    Returns:
        flat cleaned list of point dicts
    """
    cleaned = []

    for point in data.get("points", []):
        text = clean_text(point.get("text", ""))

        if is_empty(text):
            continue

        cleaned.append({
            "id":      point.get("id"),
            "chapter": chapter,
            "text":    text,
        })

    return cleaned


# ─────────────────────────────────────────────
# THINK AND ACT
# ─────────────────────────────────────────────

def clean_think_and_act(data: list, chapter: str, flagged_dir: str) -> list:
    """
    Cleans think_and_act.json data:
    - Simplest cleaner — just clean_text on the thinkandact field
    - Skips empty items

    Args:
        data:        raw loaded JSON list
        chapter:     chapter id string
        flagged_dir: path to flagged/ folder

    Returns:
        cleaned list of dicts
    """
    cleaned = []

    for i, item in enumerate(data):
        text = clean_text(item.get("thinkandact", ""))

        if is_empty(text):
            continue

        cleaned.append({
            "id":      i + 1,
            "chapter": item.get("chapter", chapter),
            "text":    text,
        })

    return cleaned