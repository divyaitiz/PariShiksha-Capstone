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
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from eval_pipeline import get_collection, get_groq, GROQ_MODEL
from groq import RateLimitError

OUT_FILE        = Path("./eval/golden_set_draft.jsonl")
CHECKPOINT_FILE = Path("./eval/.draft_checkpoint.json")  # tracks which chunk ids are done
N_PER_STRATUM = 2   # tune to hit ~80-120 total across chapters x section types
TARGET_ROWS   = 95  # content rows to keep after filtering (+ out-of-scope on top)
DIFFICULTIES = ["direct_factual", "conceptual_explanation", "cross_section_synthesis"]

# Drafted questions containing any of these (case-insensitive) get dropped —
# these are "about the document" questions, not real student science questions
BAD_QUESTION_MARKERS = [
    "given passage", "the passage", "given text", "the text",
    "ncert class", "chapter being discussed", "title of the chapter",
    "not specified", "purpose of the given", "context of the",
]

# Drafted ANSWERS containing any of these get dropped too — the model sometimes
# writes a fine-looking question but then hedges in the answer instead of
# actually answering ("the passage does not specify...")
BAD_ANSWER_MARKERS = [
    "does not explicitly state", "the passage does not", "not contain any scientific",
    "the text does not", "given passage", "the passage", "not explicitly named",
    "does not specify", "not specified in", "the text says",
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
    for cid, meta, doc in zip(all_data["ids"], all_data["metadatas"], all_data["documents"]):
        # skip image chunks — golden set is for text QA, not figure captions
        if meta.get("section_type") == "images":
            continue
        key = (meta.get("chapter_number"), meta.get("section_type"))
        by_stratum.setdefault(key, []).append((cid, meta, doc))

    sampled = []
    for key, items in by_stratum.items():
        sampled.extend(random.sample(items, min(n_per_stratum, len(items))))
    return sampled


def is_bad_question(question: str) -> bool:
    q_lower = question.lower()
    return any(marker in q_lower for marker in BAD_QUESTION_MARKERS)


def is_bad_answer(answer: str) -> bool:
    a_lower = answer.lower()
    return any(marker in a_lower for marker in BAD_ANSWER_MARKERS)


def stratified_trim(rows: list, target: int) -> list:
    """Round-robin one row per (chapter, section_type) stratum at a time, so
    every stratum gets represented before any gets a second pick. Keeps
    coverage even instead of e.g. letting one heavy section_type dominate."""
    content = [r for r in rows if not r.get("out_of_scope")]
    oos = [r for r in rows if r.get("out_of_scope")]

    by_stratum = defaultdict(list)
    for r in content:
        by_stratum[(r["chapter"], r["section_type"])].append(r)
    for pool in by_stratum.values():
        random.shuffle(pool)
    strata = list(by_stratum.keys())
    random.shuffle(strata)

    selected = []
    while len(selected) < target:
        progressed = False
        for k in strata:
            if by_stratum[k]:
                selected.append(by_stratum[k].pop())
                progressed = True
                if len(selected) >= target:
                    break
        if not progressed:
            break  # ran out of rows before hitting target

    return selected + oos


def normalize_for_dedup(question: str) -> str:
    """Rough normalization to catch near-duplicate questions from overlapping chunks."""
    words = question.lower().strip("?. ").split()
    # first 6 significant words is enough to catch "main component of the plant
    # cell wall" appearing twice with different trailing phrasing
    return " ".join(words[:6])


def load_checkpoint() -> tuple[set, list]:
    """Returns (set of already-processed chunk ids, list of already-written rows)."""
    done_ids = set()
    existing_rows = []
    if OUT_FILE.exists():
        with open(OUT_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    existing_rows.append(json.loads(line))
    if CHECKPOINT_FILE.exists():
        done_ids = set(json.loads(CHECKPOINT_FILE.read_text()))
    return done_ids, existing_rows


def save_checkpoint(done_ids: set):
    CHECKPOINT_FILE.write_text(json.dumps(list(done_ids)))


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
    random.seed(42)  # reproducible sampling — same sampled set every run
    OUT_FILE.parent.mkdir(exist_ok=True)
    collection = get_collection()
    groq = get_groq()

    done_ids, rows = load_checkpoint()
    seen_normalized = {normalize_for_dedup(r["question"]) for r in rows if not r.get("out_of_scope")}

    sampled = sample_chunks(collection, N_PER_STRATUM)
    remaining = [(cid, meta, doc) for cid, meta, doc in sampled if cid not in done_ids]

    n_strata = len(set((m.get("chapter_number"), m.get("section_type")) for _, m, _ in sampled))
    if done_ids:
        print(f"Resuming: {len(done_ids)} chunks already processed, {len(rows)} rows saved so far.")
    print(f"{len(remaining)} chunks remaining to draft (of {len(sampled)} total across {n_strata} strata)...")

    if not remaining:
        print("Nothing left to draft — all sampled chunks already processed.")
    n_skipped, n_bad, n_dupe = 0, 0, 0
    out_f = open(OUT_FILE, "a", encoding="utf-8")  # append — preserves earlier progress

    try:
        for i, (cid, meta, doc) in enumerate(remaining, 1):
            try:
                question, answer = draft_qa(doc, groq)
            except RateLimitError as e:
                print(f"\nRATE LIMITED at chunk {i}/{len(remaining)}. Progress saved — "
                      f"just re-run this script later and it'll resume from here.")
                print(f"  ({e})")
                break

            done_ids.add(cid)  # mark attempted regardless of outcome, so we never retry it

            if not question:
                n_skipped += 1
                print(f"  [{i}/{len(remaining)}] SKIPPED — model declined (fragmentary passage)")
                continue

            if is_bad_question(question):
                n_bad += 1
                print(f"  [{i}/{len(remaining)}] DROPPED (meta/doc-referencing question) — {question[:60]}")
                continue

            if is_bad_answer(answer):
                n_bad += 1
                print(f"  [{i}/{len(remaining)}] DROPPED (hedging/passage-referencing answer) — {question[:60]}")
                continue

            norm = normalize_for_dedup(question)
            if norm in seen_normalized:
                n_dupe += 1
                print(f"  [{i}/{len(remaining)}] DROPPED (near-duplicate) — {question[:60]}")
                continue
            seen_normalized.add(norm)

            row = {
                "id": f"draft_{cid}",
                "question": question,
                "expected_answer": answer,
                "chapter": meta.get("chapter_number"),
                "section_type": meta.get("section_type"),
                "section_id": meta.get("section_id"),
                "difficulty": random.choice(DIFFICULTIES),  # re-label by hand as you verify
                "out_of_scope": False,
                "verified": False,  # flip to true only after you've hand-checked it
            }
            rows.append(row)
            out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            out_f.flush()  # write through immediately — survives a crash/rate-limit mid-run
            save_checkpoint(done_ids)
            print(f"  [{i}/{len(remaining)}] {question[:70]}")
    finally:
        out_f.close()

    # Add out-of-scope seeds only once, on first run
    have_oos = any(r.get("id", "").startswith("oos_") for r in rows)
    if not have_oos:
        with open(OUT_FILE, "a", encoding="utf-8") as f:
            for j, q in enumerate(OUT_OF_SCOPE_SEED, 1):
                row = {
                    "id": f"oos_{j:03d}",
                    "question": q,
                    "expected_answer": "",
                    "chapter": None,
                    "section_type": None,
                    "section_id": None,
                    "difficulty": "out_of_scope",
                    "out_of_scope": True,
                    "verified": False,
                }
                rows.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    content_rows = sum(1 for r in rows if not r.get("out_of_scope"))
    oos_rows = len(rows) - content_rows
    print(f"\nThis run — filtered out: {n_skipped} fragmentary, {n_bad} bad question/answer, {n_dupe} near-duplicate")
    print(f"Total so far: {len(rows)} rows in {OUT_FILE} ({content_rows} content + {oos_rows} out-of-scope)")

    if len(done_ids) < len(sampled):
        print(f"Still {len(sampled) - len(done_ids)} chunks left — re-run the script to continue.")
        return

    if content_rows < 80:
        print(f"NOTE: below the 80-120 target after filtering — bump N_PER_STRATUM "
              f"(currently {N_PER_STRATUM}), delete {CHECKPOINT_FILE} and {OUT_FILE} "
              f"to force fresh sampling, and re-run")
        return

    # All chunks processed and we have enough rows — trim to an even,
    # target-sized set. This is the file you actually hand-verify.
    trimmed = stratified_trim(rows, TARGET_ROWS)
    trimmed_path = Path("./eval/golden_set_draft_trimmed.jsonl")
    with open(trimmed_path, "w", encoding="utf-8") as f:
        for r in trimmed:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_ch = defaultdict(int)
    for r in trimmed:
        if not r.get("out_of_scope"):
            by_ch[r["chapter"]] += 1

    print(f"\nTrimmed to {len(trimmed)} rows (even chapter/section-type coverage) → {trimmed_path}")
    print(f"Rows per chapter: {dict(sorted(by_ch.items(), key=lambda x: int(x[0])))}")
    print("\nNext steps:")
    print(f"  1. Open {trimmed_path.name}, hand-verify/correct every row")
    print("  2. Re-check difficulty labels (auto-assigned randomly — fix these)")
    print("  3. Add more out-of-scope cases if needed")
    print("  4. Copy verified rows into eval/golden_set.jsonl with verified=true")


if __name__ == "__main__":
    main()