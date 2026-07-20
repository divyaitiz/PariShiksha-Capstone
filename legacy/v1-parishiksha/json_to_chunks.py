"""
json_to_chunks.py
=================
Reads all extracted/<chapter>/json/*.json files and produces
a single chunks/all_chunks.jsonl where every line is one chunk.

Each chunk:
{
  "chunk_id":      "iesc101_informational_text_1.2.1_0",
  "chapter_id":    "iesc101",
  "chapter_number":"1",
  "chapter_title": "Matter in Our Surroundings",
  "source_file":   "iesc101.pdf",
  "section_type":  "informational_text",
  "section_id":    "1.2.1",
  "section_title": "Particles Of Matter Have Space Between Them",
  "parent_id":     "1.2",
  "parent_title":  "Characteristics of Particles of Matter",
  "topic":         "",          ← filled for in_chapter_questions
  "content":       "...",
  "chunk_index":   0            ← >0 when a block is split due to length
}

Chunking strategy per section type:
  informational_text  → one chunk per subsection; one chunk per section
                        if it has no subsections. Long blocks split with
                        overlap. Garbage section IDs filtered.
  exercises           → one chunk per exercise (subparts joined into content)
  activities          → one chunk per activity
  examples            → one chunk per example (problem + steps joined)
  in_chapter_questions→ one chunk per question (topic carried as metadata)
  think_and_act       → one chunk per item
  what_you_have_learnt→ one chunk per point
"""

import sys
import re
import json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ── Config ────────────────────────────────────────────────────────────────────
EXTRACT_DIR = Path("./extracted")
CHUNKS_DIR  = Path("./chunks")

# Split a content block into smaller chunks when it exceeds this many words.
MAX_WORDS    = 200
OVERLAP_WORDS = 30   # words of overlap between consecutive splits

SECTION_TYPES = [
    "informational_text",
    "exercises",
    "activities",
    "examples",
    "in_chapter_questions",
    "think_and_act",
    "what_you_have_learnt",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def infer_chapter_number(chapter_id: str) -> str:
    """'iesc103' → '3',  'iesc112' → '12',  'iesc107' → '7'"""
    m = re.search(r'iesc1(\d+)', chapter_id, re.IGNORECASE)
    return str(int(m.group(1))) if m else chapter_id


def is_garbage_section_id(sec_id: str, chapter_number: str) -> bool:
    """
    True for section IDs that are clearly not real content:
      - chapter part doesn't match actual chapter  (e.g. 15.0 in chapter 7)
      - chapter part is 0                          (e.g. 0.8, 0.1)
      - section part > 30
    """
    parts = sec_id.split(".")
    try:
        ch  = int(parts[0])
        sec = int(parts[1])
    except (IndexError, ValueError):
        return True
    if ch == 0:
        return True
    try:
        expected = int(chapter_number)
        if ch != expected:
            return True
    except ValueError:
        pass
    if sec > 30:
        return True
    return False


def split_text(text: str, max_words: int, overlap: int) -> list[str]:
    """Split text into word-capped segments with overlap."""
    words = text.split()
    if len(words) <= max_words:
        return [text]
    chunks = []
    start  = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks


def make_chunk(
    chapter_id: str,
    chapter_number: str,
    chapter_title: str,
    source_file: str,
    section_type: str,
    section_id: str,
    section_title: str,
    content: str,
    chunk_index: int,
    parent_id: str = "",
    parent_title: str = "",
    topic: str = "",
) -> dict:
    cid = f"{chapter_id}_{section_type}_{section_id}_{chunk_index}"
    return {
        "chunk_id":      cid,
        "chapter_id":    chapter_id,
        "chapter_number":chapter_number,
        "chapter_title": chapter_title,
        "source_file":   source_file,
        "section_type":  section_type,
        "section_id":    section_id,
        "section_title": section_title,
        "parent_id":     parent_id,
        "parent_title":  parent_title,
        "topic":         topic,
        "content":       content.strip(),
        "chunk_index":   chunk_index,
    }


def emit_chunks(
    content: str,
    chapter_id: str,
    chapter_number: str,
    chapter_title: str,
    source_file: str,
    section_type: str,
    section_id: str,
    section_title: str,
    parent_id: str = "",
    parent_title: str = "",
    topic: str = "",
) -> list[dict]:
    """Split content if needed and return list of chunk dicts."""
    parts = split_text(content, MAX_WORDS, OVERLAP_WORDS)
    return [
        make_chunk(
            chapter_id, chapter_number, chapter_title, source_file,
            section_type, section_id, section_title,
            part, idx, parent_id, parent_title, topic
        )
        for idx, part in enumerate(parts)
        if part.strip()
    ]


# ── Per-type chunkers ─────────────────────────────────────────────────────────

def chunk_informational_text(data: dict, chapter_id: str,
                             chapter_number: str) -> list[dict]:
    chunks      = []
    chapter_title = data.get("chapter_title", "")
    source_file   = data.get("source_file", f"{chapter_id}.pdf")

    # Introduction as its own chunk
    intro = data.get("introduction", "").strip()
    if intro:
        chunks += emit_chunks(
            intro, chapter_id, chapter_number, chapter_title, source_file,
            "informational_text", "intro", "Introduction",
        )

    for sec in data.get("sections", []):
        sec_id    = sec.get("section_id", "")
        sec_title = sec.get("title", "").strip()
        sec_content = sec.get("content", "").strip()
        subsections = sec.get("subsections", [])

        # Skip garbage sections
        if is_garbage_section_id(sec_id, chapter_number):
            continue

        # Section-level prose (before subsections)
        if sec_content:
            chunks += emit_chunks(
                sec_content, chapter_id, chapter_number, chapter_title,
                source_file, "informational_text", sec_id, sec_title,
            )

        # Subsections
        for sub in subsections:
            sub_id    = sub.get("section_id", "")
            sub_title = sub.get("title", "").strip()
            sub_content = sub.get("content", "").strip()

            if is_garbage_section_id(sub_id, chapter_number):
                continue

            if sub_content:
                chunks += emit_chunks(
                    sub_content, chapter_id, chapter_number, chapter_title,
                    source_file, "informational_text", sub_id, sub_title,
                    parent_id=sec_id, parent_title=sec_title,
                )
            else:
                # Keep empty subsections as a marker chunk so nothing is lost
                chunks.append(make_chunk(
                    chapter_id, chapter_number, chapter_title, source_file,
                    "informational_text", sub_id, sub_title, "",
                    0, sec_id, sec_title,
                ))

    return chunks


def chunk_exercises(data: dict, chapter_id: str,
                    chapter_number: str) -> list[dict]:
    chunks      = []
    chapter_title = ""
    source_file   = f"{chapter_id}.pdf"

    for ex in data.get("exercises", []):
        ex_id    = str(ex.get("id", ""))
        question = ex.get("question", "").replace("\n", " ").strip()

        # Append subparts into the content
        subparts = ex.get("subparts", []) or []
        for sp in subparts:
            label = sp.get("label", "")
            text  = sp.get("text",  "").replace("\n", " ").strip()
            question += f"\n({label}) {text}"

        chunks += emit_chunks(
            question, chapter_id, chapter_number, chapter_title, source_file,
            "exercises", ex_id, f"Exercise {ex_id}",
        )
    return chunks


def chunk_activities(data: dict, chapter_id: str,
                     chapter_number: str) -> list[dict]:
    chunks      = []
    chapter_title = ""
    source_file   = f"{chapter_id}.pdf"

    for act in data.get("activities", []):
        act_id  = act.get("activity_id", str(act.get("id", "")))
        title   = act.get("title", f"Activity {act_id}")
        content = act.get("content", "").replace("\n", " ").strip()

        steps = act.get("steps") or []
        if steps:
            content += "\n" + " ".join(steps)

        chunks += emit_chunks(
            content, chapter_id, chapter_number, chapter_title, source_file,
            "activities", act_id, title,
        )
    return chunks


def chunk_examples(data: list, chapter_id: str,
                   chapter_number: str) -> list[dict]:
    chunks      = []
    chapter_title = ""
    source_file   = f"{chapter_id}.pdf"

    items = data if isinstance(data, list) else data.get("examples", [])

    for ex in items:
        ex_id   = ex.get("example_id", "")
        problem = ex.get("problem", "").replace("\n", " ").strip()
        steps   = ex.get("steps", []) or []
        answer  = ex.get("final_answer", "")

        content = problem
        if steps:
            content += "\nSolution: " + " ".join(
                s.replace("\n", " ") for s in steps
            )
        if answer:
            content += f"\nAnswer: {answer}"

        chunks += emit_chunks(
            content, chapter_id, chapter_number, chapter_title, source_file,
            "examples", ex_id, f"Example {ex_id}",
        )
    return chunks


def chunk_in_chapter_questions(data: dict, chapter_id: str,
                                chapter_number: str) -> list[dict]:
    chunks      = []
    chapter_title = ""
    source_file   = f"{chapter_id}.pdf"

    for sec in data.get("sections", []):
        topic = sec.get("topic", "")
        for q in sec.get("questions", []):
            qid      = q.get("qid", str(q.get("id", "")))
            question = q.get("question", "").replace("\n", " ").strip()

            subparts = q.get("subparts", []) or []
            for sp in subparts:
                label = sp.get("label", "")
                text  = sp.get("text", "").replace("\n", " ").strip()
                # Filter out body-text bleed (long subpart text with no label)
                if len(text) < 300:
                    question += f"\n({label}) {text}"

            chunks += emit_chunks(
                question, chapter_id, chapter_number, chapter_title,
                source_file, "in_chapter_questions", qid,
                f"Question {qid}", topic=topic,
            )
    return chunks


def chunk_think_and_act(data: list, chapter_id: str,
                         chapter_number: str) -> list[dict]:
    chunks      = []
    chapter_title = ""
    source_file   = f"{chapter_id}.pdf"

    items = data if isinstance(data, list) else [data]
    for idx, item in enumerate(items):
        content = item.get("thinkandact", "").replace("\n", " ").strip()
        sec_id  = f"TA{idx+1}"
        chunks += emit_chunks(
            content, chapter_id, chapter_number, chapter_title, source_file,
            "think_and_act", sec_id, "Think and Act",
        )
    return chunks


def chunk_what_you_have_learnt(data: dict, chapter_id: str,
                                chapter_number: str) -> list[dict]:
    chunks      = []
    chapter_title = ""
    source_file   = f"{chapter_id}.pdf"

    for pt in data.get("points", []):
        pt_id   = str(pt.get("id", ""))
        content = pt.get("text", "").replace("\n", " ").strip()
        chunks += emit_chunks(
            content, chapter_id, chapter_number, chapter_title, source_file,
            "what_you_have_learnt", pt_id, f"Point {pt_id}",
        )
    return chunks


# ── Dispatch table ────────────────────────────────────────────────────────────

CHUNKERS = {
    "informational_text":   chunk_informational_text,
    "exercises":            chunk_exercises,
    "activities":           chunk_activities,
    "examples":             chunk_examples,
    "in_chapter_questions": chunk_in_chapter_questions,
    "think_and_act":        chunk_think_and_act,
    "what_you_have_learnt": chunk_what_you_have_learnt,
}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    CHUNKS_DIR.mkdir(exist_ok=True)
    out_path = CHUNKS_DIR / "all_chunks.jsonl"

    total_chunks   = 0
    chapter_counts = {}

    with open(out_path, "w", encoding="utf-8") as out_f:
        chapter_dirs = sorted(EXTRACT_DIR.glob("*/"))

        for ch_dir in chapter_dirs:
            json_dir   = ch_dir / "json"
            chapter_id = ch_dir.name
            if not json_dir.is_dir():
                continue

            chapter_number = infer_chapter_number(chapter_id)
            chapter_chunks = 0

            for section_type in SECTION_TYPES:
                json_path = json_dir / f"{section_type}.json"
                if not json_path.exists():
                    continue

                raw  = json_path.read_text(encoding="utf-8")
                data = json.loads(raw)

                chunker = CHUNKERS.get(section_type)
                if not chunker:
                    continue

                chunks = chunker(data, chapter_id, chapter_number)

                for chunk in chunks:
                    out_f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

                chapter_chunks += len(chunks)
                print(f"  {chapter_id}/{section_type}: {len(chunks)} chunks")

            chapter_counts[chapter_id] = chapter_chunks
            total_chunks += chapter_chunks

    print(f"\n{'─'*50}")
    print(f"Total chunks : {total_chunks}")
    print(f"Output       : {out_path}")
    for ch, n in chapter_counts.items():
        print(f"  {ch}: {n} chunks")


if __name__ == "__main__":
    main()