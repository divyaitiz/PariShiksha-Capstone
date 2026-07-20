"""
eval/run_scorecard.py
=======================
Runs golden_set.jsonl through the RAG pipeline, computes Ragas metrics +
a custom citation accuracy / refusal accuracy metric, saves + prints a
scorecard.

Ragas defaults to OpenAI as its judge LLM/embeddings — we override both to
use Groq (judge) and the same BGE-large embedder already used for retrieval,
so no OPENAI_API_KEY is required.

Requires:
    pip install ragas datasets langchain-groq langchain-huggingface

Run from the pipeline root:
    python eval/run_scorecard.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from eval_pipeline import run_query, GROQ_MODEL, EMBED_MODEL

from datasets import Dataset
from ragas import evaluate, RunConfig
from ragas.metrics import faithfulness, context_precision, context_recall
from ragas.metrics import AnswerRelevancy
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings

# Groq's API rejects n>1 (multiple parallel generations per call). Ragas'
# default AnswerRelevancy uses strictness=3 (asks for 3 generations to
# average). Force strictness=1 so each call only ever asks for n=1.
answer_relevancy = AnswerRelevancy(strictness=1)

GOLDEN_SET  = Path("./eval/golden_set.jsonl")
RESULTS_DIR = Path("./eval/results")


def get_ragas_llm():
    """Groq-backed judge LLM for Ragas, so we don't need an OpenAI key."""
    chat = ChatGroq(model=GROQ_MODEL, temperature=0.0)
    return LangchainLLMWrapper(chat)


def get_ragas_embeddings():
    """Reuse the same BGE-large embedder as retrieval, wrapped for Ragas."""
    hf_embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    return LangchainEmbeddingsWrapper(hf_embeddings)


def load_golden_set():
    if not GOLDEN_SET.exists():
        print(f"ERROR: {GOLDEN_SET} not found.")
        print("Run eval/generate_draft_golden_set.py first, hand-verify the draft,")
        print("then save verified rows as eval/golden_set.jsonl.")
        sys.exit(1)

    rows = [json.loads(l) for l in open(GOLDEN_SET, encoding="utf-8") if l.strip()]
    verified = [r for r in rows if r.get("verified")]
    if len(verified) < len(rows):
        print(f"WARNING: {len(rows) - len(verified)} unverified rows skipped "
              f"(set verified: true once you've hand-checked them).")
    if not verified:
        print("ERROR: no verified rows to evaluate.")
        sys.exit(1)
    return verified


def citation_accuracy(row, result) -> bool:
    """Does the cited chapter/section actually appear among retrieved sections?"""
    if row["out_of_scope"]:
        return True  # nothing to cite for a correct refusal
    expected = f"Ch.{row['chapter']} §{row['section_id']}"
    return any(expected in s for s in result["retrieved_sections"])


def refusal_correct(row, result):
    if not row["out_of_scope"]:
        return None
    return "not covered in the retrieved sections" in result["answer"].lower()


def main():
    golden = load_golden_set()
    print(f"Running {len(golden)} golden questions through the pipeline...")

    records, citation_flags, refusal_flags = [], [], []
    per_stratum = defaultdict(list)

    for i, row in enumerate(golden, 1):
        result = run_query(row["question"])

        # Ragas needs a non-empty ground_truth string even for out-of-scope rows
        ground_truth = row["expected_answer"] or "This topic is not covered in the retrieved sections."

        records.append({
            "question": row["question"],
            "answer": result["answer"],
            "contexts": result["contexts"] or [""],
            "ground_truth": ground_truth,
        })

        cit = citation_accuracy(row, result)
        citation_flags.append(cit)
        ref = refusal_correct(row, result)
        if ref is not None:
            refusal_flags.append(ref)

        stratum = row.get("section_type") or "out_of_scope"
        per_stratum[stratum].append({"citation": cit, "refusal": ref})
        status = "OK" if cit else "MISS"
        print(f"  [{i}/{len(golden)}] [{status}] {row['question'][:60]}")

    print("\nComputing Ragas metrics (this calls an LLM judge per row, may take a while)...")
    dataset = Dataset.from_list(records)
    ragas_llm = get_ragas_llm()
    ragas_embeddings = get_ragas_embeddings()
    ragas_result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=ragas_llm,
        embeddings=ragas_embeddings,
        run_config=RunConfig(max_workers=2, max_retries=2, max_wait=30),
    )
    ragas_scores = {k: float(v) for k, v in ragas_result.items()}

    scorecard = {
        "timestamp": datetime.now().isoformat(),
        "n_questions": len(golden),
        "metrics": {
            **ragas_scores,
            "citation_accuracy": sum(citation_flags) / len(citation_flags),
            "refusal_accuracy": (sum(refusal_flags) / len(refusal_flags)) if refusal_flags else None,
        },
        "by_section_type": {
            k: {"citation_accuracy": sum(x["citation"] for x in v) / len(v)}
            for k, v in per_stratum.items()
        },
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"scorecard_{datetime.now():%Y%m%d_%H%M%S}.json"
    out_path.write_text(json.dumps(scorecard, indent=2))
    (RESULTS_DIR / "latest.json").write_text(json.dumps(scorecard, indent=2))

    print("\n" + "=" * 50)
    print("SCORECARD")
    print("=" * 50)
    for k, v in scorecard["metrics"].items():
        print(f"  {k:25s}: {v:.3f}" if v is not None else f"  {k:25s}: n/a")

    print("\nBy section type (citation accuracy):")
    for k, v in scorecard["by_section_type"].items():
        print(f"  {k:25s}: {v['citation_accuracy']:.3f}")

    print(f"\nSaved to {out_path}")
    print(f"Also written to {RESULTS_DIR / 'latest.json'} (used by test_regression.py)")


if __name__ == "__main__":
    main()