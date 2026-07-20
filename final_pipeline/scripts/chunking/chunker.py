"""
chunker.py — One chunking function per content type.

Takes cleaned JSON data, returns a list of chunk dicts ready for embedding.
Informational text uses BGE-based semantic splitting for long sections.
All other types are rule-based (one item = one chunk).

Every chunk produced has this structure:
{
    "chunk_id":      "iesc101_informational_text_003",
    "chapter":       "iesc101",
    "content_type":  "informational_text",
    "heading":       "States of Matter",
    "text":          "...actual text...",
    "chunk_index":   3
}
"""

from utils import build_chunk_id, word_count, WORD_THRESHOLD


# ─────────────────────────────────────────────
# SEMANTIC SPLITTER (BGE-powered)
# ─────────────────────────────────────────────

def _get_semantic_splitter():
    """
    Lazy-loads the SemanticChunker with BGE embeddings.
    Only imported and initialised when actually needed (informational_text only).
    Raises a clear error if dependencies are not installed.
    """
    try:
        from langchain_experimental.text_splitter import SemanticChunker
        from langchain_community.embeddings import HuggingFaceEmbeddings
    except ImportError:
        raise ImportError(
            "Missing dependencies for semantic chunking.\n"
            "Run: pip install langchain langchain-community "
            "langchain-experimental sentence-transformers"
        )

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-base-en-v1.5",
        encode_kwargs={"normalize_embeddings": True},
    )

    splitter = SemanticChunker(
        embeddings,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=90,
    )

    return splitter


_splitter = None   # module-level cache so BGE loads only once


def _semantic_split(text: str) -> list:
    """
    Splits a long text into semantically coherent sub-chunks using BGE.
    Falls back to the full text as a single chunk if splitting fails.

    Args:
        text: long content string

    Returns:
        list of strings (sub-chunks)
    """
    global _splitter

    if _splitter is None:
        print("  [BGE] Loading BAAI/bge-base-en-v1.5 for semantic splitting...")
        _splitter = _get_semantic_splitter()

    try:
        chunks = _splitter.split_text(text)
        return [c.strip() for c in chunks if c.strip()]
    except Exception as e:
        print(f"  [WARN] Semantic split failed, keeping as single chunk: {e}")
        return [text]


# ─────────────────────────────────────────────
# INFORMATIONAL TEXT
# ─────────────────────────────────────────────

def chunk_informational_text(data: dict, chapter: str) -> list:
    """
    Chunks cleaned informational_text data.

    Strategy:
    - Each subsection with content → candidate chunk
    - If a section has content but no subsections → it's a chunk itself
    - If candidate chunk exceeds WORD_THRESHOLD → semantic split into sub-chunks
    - Empty content was already removed by cleaner

    Args:
        data:    cleaned informational_text dict
        chapter: chapter id e.g. "iesc101"

    Returns:
        list of chunk dicts
    """
    chunks = []
    idx = 0

    for section in data.get("sections", []):
        section_title = section.get("title", "")
        section_content = section.get("content", "")
        subsections = section.get("subsections", [])

        # If section has its own content and no subsections, treat it as a chunk
        if section_content and not subsections:
            candidates = [(section_title, section_content)]
        elif section_content and subsections:
            # Section has both — treat section content as its own chunk first
            candidates = [(section_title, section_content)]
        else:
            candidates = []

        # Add each subsection as a candidate
        for sub in subsections:
            heading = sub.get("title") or section_title
            content = sub.get("content", "")
            if content:
                candidates.append((heading, content))

        # Now chunk each candidate
        for heading, content in candidates:
            if word_count(content) > WORD_THRESHOLD:
                # Long section — apply BGE semantic splitting
                sub_texts = _semantic_split(content)
                for sub_text in sub_texts:
                    chunks.append({
                        "chunk_id":     build_chunk_id(chapter, "informational_text", idx),
                        "chapter":      chapter,
                        "content_type": "informational_text",
                        "heading":      heading,
                        "text":         sub_text,
                        "chunk_index":  idx,
                    })
                    idx += 1
            else:
                chunks.append({
                    "chunk_id":     build_chunk_id(chapter, "informational_text", idx),
                    "chapter":      chapter,
                    "content_type": "informational_text",
                    "heading":      heading,
                    "text":         content,
                    "chunk_index":  idx,
                })
                idx += 1

    return chunks


# ─────────────────────────────────────────────
# EXAMPLES
# ─────────────────────────────────────────────

def chunk_examples(data: list, chapter: str) -> list:
    """
    Chunks cleaned examples data.

    Strategy: one chunk per example.
    Text is assembled from: problem + steps joined + final answer.
    Never split — an example must stay together to be meaningful.

    Args:
        data:    cleaned list of example dicts
        chapter: chapter id

    Returns:
        list of chunk dicts
    """
    chunks = []

    for idx, item in enumerate(data):
        problem = item.get("problem", "")
        steps = item.get("steps", [])
        final_answer = item.get("final_answer", "")
        formulas = item.get("formulas_used", [])

        # Assemble full text
        parts = [f"Problem: {problem}"]

        if formulas:
            parts.append("Formulas: " + "; ".join(formulas))

        if steps:
            parts.append("Solution:\n" + "\n".join(steps))

        if final_answer:
            parts.append(f"Answer: {final_answer} {item.get('units', '')}".strip())

        full_text = "\n".join(parts)

        chunks.append({
            "chunk_id":     build_chunk_id(chapter, "examples", idx),
            "chapter":      chapter,
            "content_type": "examples",
            "heading":      f"Example {item.get('example_id', idx + 1)}",
            "text":         full_text,
            "chunk_index":  idx,
        })

    return chunks


# ─────────────────────────────────────────────
# EXERCISES
# ─────────────────────────────────────────────

def chunk_exercises(data: list, chapter: str) -> list:
    """
    Chunks cleaned exercises data.

    Strategy: one chunk per exercise.
    Subparts were already joined into the text by cleaner.

    Args:
        data:    cleaned list of exercise dicts
        chapter: chapter id

    Returns:
        list of chunk dicts
    """
    chunks = []

    for idx, item in enumerate(data):
        text = item.get("text", "")
        if not text:
            continue

        chunks.append({
            "chunk_id":     build_chunk_id(chapter, "exercises", idx),
            "chapter":      chapter,
            "content_type": "exercises",
            "heading":      f"Exercise {item.get('id', idx + 1)}",
            "text":         text,
            "chunk_index":  idx,
        })

    return chunks


# ─────────────────────────────────────────────
# ACTIVITIES
# ─────────────────────────────────────────────

def chunk_activities(data: list, chapter: str) -> list:
    """
    Chunks cleaned activities data.

    Strategy: one chunk per activity.
    Duplicates were already merged by cleaner.

    Args:
        data:    cleaned list of activity dicts
        chapter: chapter id

    Returns:
        list of chunk dicts
    """
    chunks = []

    for idx, item in enumerate(data):
        text = item.get("content", "")
        if not text:
            continue

        chunks.append({
            "chunk_id":     build_chunk_id(chapter, "activities", idx),
            "chapter":      chapter,
            "content_type": "activities",
            "heading":      item.get("title", f"Activity {item.get('activity_id', idx + 1)}"),
            "text":         text,
            "chunk_index":  idx,
        })

    return chunks


# ─────────────────────────────────────────────
# IN-CHAPTER QUESTIONS
# ─────────────────────────────────────────────

def chunk_in_chapter_questions(data: list, chapter: str) -> list:
    """
    Chunks cleaned in_chapter_questions data.

    Strategy: one chunk per question.
    Truncated and leaked questions were already removed by cleaner.

    Args:
        data:    cleaned flat list of question dicts
        chapter: chapter id

    Returns:
        list of chunk dicts
    """
    chunks = []

    for idx, item in enumerate(data):
        text = item.get("text", "")
        if not text:
            continue

        chunks.append({
            "chunk_id":     build_chunk_id(chapter, "in_chapter_questions", idx),
            "chapter":      chapter,
            "content_type": "in_chapter_questions",
            "heading":      f"Question {item.get('qid', idx + 1)}",
            "text":         text,
            "chunk_index":  idx,
        })

    return chunks


# ─────────────────────────────────────────────
# WHAT YOU HAVE LEARNT
# ─────────────────────────────────────────────

def chunk_what_you_have_learnt(data: list, chapter: str) -> list:
    """
    Chunks cleaned what_you_have_learnt data.

    Strategy: one chunk per point.
    These are high-signal summary sentences — keep them atomic.

    Args:
        data:    cleaned flat list of point dicts
        chapter: chapter id

    Returns:
        list of chunk dicts
    """
    chunks = []

    for idx, item in enumerate(data):
        text = item.get("text", "")
        if not text:
            continue

        chunks.append({
            "chunk_id":     build_chunk_id(chapter, "what_you_have_learnt", idx),
            "chapter":      chapter,
            "content_type": "what_you_have_learnt",
            "heading":      "Key Takeaway",
            "text":         text,
            "chunk_index":  idx,
        })

    return chunks


# ─────────────────────────────────────────────
# THINK AND ACT
# ─────────────────────────────────────────────

def chunk_think_and_act(data: list, chapter: str) -> list:
    """
    Chunks cleaned think_and_act data.

    Strategy: one chunk per item (already atomic).

    Args:
        data:    cleaned list of dicts
        chapter: chapter id

    Returns:
        list of chunk dicts
    """
    chunks = []

    for idx, item in enumerate(data):
        text = item.get("text", "")
        if not text:
            continue

        chunks.append({
            "chunk_id":     build_chunk_id(chapter, "think_and_act", idx),
            "chapter":      chapter,
            "content_type": "think_and_act",
            "heading":      "Think and Act",
            "text":         text,
            "chunk_index":  idx,
        })

    return chunks


# ─────────────────────────────────────────────
# DISPATCHER — maps content_type to its chunker
# ─────────────────────────────────────────────

CHUNKER_MAP = {
    "informational_text":   chunk_informational_text,
    "examples":             chunk_examples,
    "exercises":            chunk_exercises,
    "activities":           chunk_activities,
    "in_chapter_questions": chunk_in_chapter_questions,
    "what_you_have_learnt": chunk_what_you_have_learnt,
    "think_and_act":        chunk_think_and_act,
}