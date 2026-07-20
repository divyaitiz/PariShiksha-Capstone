"""
eval/generate_draft_golden_set.py
===================================
Samples chunks stratified by chapter + section_type, asks Groq to draft
question/answer pairs. Writes a DRAFT file — you must hand-verify every
row before it counts as part of the golden set.

Tune N_PER_STRATUM to land in the 80-120 total range required by W1.

Run from the pipeline root:
    python eval/generate_draft_golden_set.py
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from eval_pipeline import get_collection, get_groq, GROQ_MODEL

OUT_FILE = Path("./eval/golden_set_draft.jsonl")
N_PER_STRATUM = 2   # tune to hit ~80-120 total across chapters x section types
DIFFICULTIES = ["direct_factual", "conceptual_explanation", "cross_section_synthesis"]

# Drafted questions containing any of these (case-insensitive) get dropped —
# these are "about the document" questions, not real student science questions
BAD_QUESTION_MARKERS = [
    "given passage", "the passage", "given text", "the text",
    "ncert class", "chapter being discussed", "title of the chapter",
    "not specified", "purpose of the given", "context of the",
]

# Out-of-scope questions can't be auto-drafted from in-corpus chunks — seed
# these by hand. Add more that are plausible things a student might ask but
# that your 12 chapters genuinely don't cover.
OUT_OF_SCOPE_SEED = [
    "What is the boiling point of mercury?",
    "Explain Newton's law of gravitation in detail with derivation.",
    "What are the causes of the French Revolution?",
    "How do you solve a quadratic equation?",
    "What is the chemical formula for glucose metabolism (Krebs cycle)?",
]

DRAFT_PROMPT = """You are drafting an evaluation question for an NCERT Class 9 Science QA system.
Given this textbook passage, write ONE question a student might ask that this passage directly answers,
and the correct answer using ONLY this passage.

Rules:
- The question must be a self-contained science question, exactly as a student would type it.
- NEVER reference "the passage", "the text", "the chapter", or the document itself — the student
  doesn't know it exists. E.g. write "What is evaporation?" NOT "What does the passage say about evaporation?"
- If the passage is too fragmentary or unclear to write a good question from, respond with exactly: SKIP
- Do not invent facts not present in the passage.

Passage:
{content}

Respond in this exact format, nothing else:
QUESTION: <question>
ANSWER: <answer, 1-3 sentences>"""


def sample_chunks(collection, n_per_stratum: int):
    all_data = collection.get(include=["metadatas", "documents"])
    by_stratum = {}
    for meta, doc in zip(all_data["metadatas"], all_data["documents"]):
        # skip image chunks — golden set is for text QA, not figure captions
        if meta.get("section_type") == "images":
            continue
        key = (meta.get("chapter_number"), meta.get("section_type"))
        by_stratum.setdefault(key, []).append((meta, doc))

    sampled = []
    for key, items in by_stratum.items():
        sampled.extend(random.sample(items, min(n_per_stratum, len(items))))
    return sampled


def is_bad_question(question: str) -> bool:
    q_lower = question.lower()
    return any(marker in q_lower for marker in BAD_QUESTION_MARKERS)


def normalize_for_dedup(question: str) -> str:
    """Rough normalization to catch near-duplicate questions from overlapping chunks."""
    words = question.lower().strip("?. ").split()
    # first 6 significant words is enough to catch "main component of the plant
    # cell wall" appearing twice with different trailing phrasing
    return " ".join(words[:6])


def draft_qa(doc, groq):
    resp = groq.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": DRAFT_PROMPT.format(content=doc)}],
        max_tokens=300,
        temperature=0.3,
    )
    text = resp.choices[0].message.content.strip()
    if text.upper().startswith("SKIP"):
        return "", ""
    question, answer = "", ""
    for line in text.split("\n"):
        if line.startswith("QUESTION:"):
            question = line[len("QUESTION:"):].strip()
        elif line.startswith("ANSWER:"):
            answer = line[len("ANSWER:"):].strip()
    return question, answer


def main():
    random.seed(42)  # reproducible sampling
    collection = get_collection()
    groq = get_groq()

    sampled = sample_chunks(collection, N_PER_STRATUM)
    n_strata = len(set((m.get("chapter_number"), m.get("section_type")) for m, _ in sampled))
    print(f"Drafting {len(sampled)} Q/A pairs across {n_strata} strata...")

    rows = []
    seen_normalized = set()
    n_skipped, n_bad, n_dupe = 0, 0, 0

    for i, (meta, doc) in enumerate(sampled, 1):
        question, answer = draft_qa(doc, groq)

        if not question:
            n_skipped += 1
            print(f"  [{i}/{len(sampled)}] SKIPPED — model declined (fragmentary passage)")
            continue

        if is_bad_question(question):
            n_bad += 1
            print(f"  [{i}/{len(sampled)}] DROPPED (meta/doc-referencing) — {question[:60]}")
            continue

        norm = normalize_for_dedup(question)
        if norm in seen_normalized:
            n_dupe += 1
            print(f"  [{i}/{len(sampled)}] DROPPED (near-duplicate) — {question[:60]}")
            continue
        seen_normalized.add(norm)

        rows.append({
            "id": f"draft_{i:03d}",
            "question": question,
            "expected_answer": answer,
            "chapter": meta.get("chapter_number"),
            "section_type": meta.get("section_type"),
            "section_id": meta.get("section_id"),
            "difficulty": random.choice(DIFFICULTIES),  # re-label by hand as you verify
            "out_of_scope": False,
            "verified": False,  # flip to true only after you've hand-checked it
        })
        print(f"  [{i}/{len(sampled)}] {question[:70]}")

    for j, q in enumerate(OUT_OF_SCOPE_SEED, 1):
        rows.append({
            "id": f"oos_{j:03d}",
            "question": q,
            "expected_answer": "",
            "chapter": None,
            "section_type": None,
            "section_id": None,
            "difficulty": "out_of_scope",
            "out_of_scope": True,
            "verified": False,
        })

    OUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    content_rows = len(rows) - len(OUT_OF_SCOPE_SEED)
    print(f"\nFiltered out: {n_skipped} fragmentary, {n_bad} meta/doc-referencing, {n_dupe} near-duplicate")
    print(f"Wrote {len(rows)} draft rows to {OUT_FILE}")
    print(f"({content_rows} content questions + {len(OUT_OF_SCOPE_SEED)} out-of-scope)")
    if content_rows < 80:
        print(f"NOTE: below the 80-120 target — bump N_PER_STRATUM (currently {N_PER_STRATUM}) and re-run")
    print("\nNext steps:")
    print("  1. Open golden_set_draft.jsonl, hand-verify/correct every row")
    print("  2. Re-check difficulty labels (auto-assigned randomly — fix these)")
    print("  3. Add more out-of-scope cases if needed")
    print("  4. Copy verified rows into eval/golden_set.jsonl with verified=true")


if __name__ == "__main__":
    main()