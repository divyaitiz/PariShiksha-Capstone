# PariShiksha — NCERT Class 9 Science RAG QA

A Retrieval-Augmented Generation (RAG) system that answers student questions about the **NCERT Class 9 Science** textbook in natural language, with chapter/section citations and (where available) related textbook figures — built as an ML Engineering capstone project.

> Solo ML Engineering capstone (Futurense AI Clinic track).

---

## Table of Contents

1. [What this is](#1-what-this-is)
2. [Repository layout](#2-repository-layout)
3. [How a query works](#3-how-a-query-works)
4. [Data pipeline (PDF → chunks → vector DB)](#4-data-pipeline-pdf--chunks--vector-db)
5. [Tech stack](#5-tech-stack)
6. [Getting started](#6-getting-started)
7. [Running the pipeline end-to-end](#7-running-the-pipeline-end-to-end)
8. [Evaluation harness](#8-evaluation-harness)
9. [Docker](#9-docker)
10. [Project history / legacy folders](#10-project-history--legacy-folders)
11. [Known limitations & next steps](#11-known-limitations--next-steps)

---

## 1. What this is

Students can ask a question like *"What is evaporation?"* or *"What are the laws of motion?"* and get an answer grounded strictly in the 12 chapters of the NCERT Class 9 Science textbook, with:

- **Chapter/section citations** appended to every substantive answer
- **Multi-turn memory** — follow-up questions like "explain more" or "give an example" are rewritten into standalone queries using recent chat history before retrieval
- **Related figures** — when a retrieved section has an associated textbook diagram, it's shown alongside the answer
- **Refusal behavior** — questions outside the textbook's scope get a clear "not covered" response instead of a hallucinated answer

The app is a single-file Streamlit chat interface (`rag_chain.py`) backed by a local ChromaDB vector store built by the data pipeline scripts in this repo.

## 2. Repository layout

```
PariShiksha-Capstone/
├── rag_chain.py                 # Streamlit app — the RAG pipeline + UI
├── run_pipeline.py               # Orchestrates PDF → text → JSON extraction per chapter
├── json_to_chunks.py             # extracted/*/json/*.json  →  chunks/all_chunks.jsonl
├── chunks_to_embeddings.py       # chunks/all_chunks.jsonl  →  ChromaDB (BGE-large embeddings)
├── check_chromadb_metadata.py    # Small utility to inspect what's stored in ChromaDB
├── requirements.txt
├── Dockerfile
├── processed.json                # Tracker: which chapter PDFs have been processed
├── extracted.zip                 # Snapshot of extracted/*/json + text for all 12 chapters
│
├── scripts/
│   ├── pdf_to_text/               # Step 1 per section type: PDF → raw .txt
│   │   ├── informational_text.py
│   │   ├── exercises.py
│   │   ├── activities.py
│   │   ├── examples.py
│   │   ├── in_chapter_questions.py
│   │   ├── think_and_act.py
│   │   ├── what_you_have_learnt.py
│   │   └── images.py              # Extracts figures/captions via pdfplumber + PyMuPDF
│   ├── text_to_json/              # Step 2 per section type: .txt → structured .json
│   │   └── (one script per section type, same names as above)
│   └── chunking/
│       ├── chunker.py             # Standalone chunking helpers (per content type)
│       ├── cleaner.py
│       ├── utils.py
│       └── run_chunking.py
│
├── eval/                          # Evaluation harness
│   ├── eval_pipeline.py           # Streamlit-free copy of the RAG pipeline, for scripted eval
│   ├── generate_draft_golden_set.py
│   ├── golden_set_draft.jsonl     # Auto-drafted Q/A pairs (pre hand-verification)
│   ├── golden_set.jsonl           # Hand-verified Q/A pairs used for scoring
│   ├── run_scorecard.py           # Runs the golden set through the pipeline, scores with Ragas
│   └── test_regression.py
│
└── legacy/                        # Earlier iterations of this project — kept for reference
    ├── ncert-class9-science-llm/  # Original PDF-extraction pipeline (7 section types)
    ├── v1-parishiksha/            # V1: full RAG pipeline + Streamlit UI + Azure/Docker/CI-CD
    └── v2-parishiksha/            # V2: pipeline refinements
```

## 3. How a query works

`rag_chain.py` runs this sequence for every user question:

1. **Condense** — if there's chat history, the follow-up question is rewritten into a short standalone question via a Groq LLM call (e.g. "explain more" → "Explain evaporation in more detail").
2. **Embed** — the standalone question is embedded with `BAAI/bge-large-en-v1.5` (GPU if available), using the required BGE query prefix.
3. **Retrieve** — ChromaDB returns the top 10 candidate chunks by cosine similarity.
4. **Re-rank** — `BAAI/bge-reranker-large` (a cross-encoder, run on CPU to keep the GPU free) re-scores those 10 and keeps the top 3.
5. **Build context** — the top 3 chunks are formatted into a labeled context block (chapter, section, section type).
6. **Generate** — `llama-3.3-70b-versatile` on Groq generates the answer, grounded only in that context, with a `**Sources:**` line appended when it actually used retrieved content.
7. **Images** — any figures whose `section_id` matches the top retrieved chunks are pulled from ChromaDB via metadata filtering (no extra embedding call) and shown alongside the answer.
8. **Chitchat guard** — greetings/small talk ("hi", "thanks", "bye") skip the whole pipeline and get a canned response, saving an LLM + retrieval round trip.

The app also exposes retrieval details in the UI: similarity + re-rank scores per source, and a per-stage timing breakdown (condense / retrieve / re-rank / LLM).

## 4. Data pipeline (PDF → chunks → vector DB)

The vector store is built offline, once per chapter PDF, in three stages:

**Stage 1 — `run_pipeline.py`** (orchestrator)
For each new PDF dropped into `./pdfs/`, and for each of 7 section types (`informational_text`, `exercises`, `activities`, `examples`, `in_chapter_questions`, `think_and_act`, `what_you_have_learnt`):
- Runs the matching `scripts/pdf_to_text/<section>.py` to extract raw text
- Runs a **quality check** (non-empty, minimum length, junk-character ratio, no repeated-character OCR artifacts) — anything that fails gets copied to `./flagged/<chapter>/` with a reason note instead of silently proceeding
- Runs the matching `scripts/text_to_json/<section>.py` to convert the checked text into structured JSON
- Tracks completed PDFs in `processed.json` so re-runs only process new files
- Logs progress per-chapter to `./logs/<chapter>.log`

Figures/diagrams are handled separately by `scripts/pdf_to_text/images.py`, which locates each figure by its caption (via `pdfplumber`) and clip-renders the page region above it (via `PyMuPDF`), associating each figure with the nearest section heading above it in the page flow.

**Stage 2 — `json_to_chunks.py`**
Reads every `extracted/<chapter>/json/*.json` and turns it into flat chunks with consistent metadata (chapter, section id/title, parent section, section type), writing everything to `chunks/all_chunks.jsonl`. Chunking strategy differs by section type — e.g. one chunk per exercise/activity/example/question, one chunk per subsection for informational text (with long blocks split at 200 words with 30-word overlap), and one chunk per figure (caption + description) for images. Section IDs that don't plausibly belong to their chapter are filtered out as extraction noise.

**Stage 3 — `chunks_to_embeddings.py`**
Embeds every chunk with `BAAI/bge-large-en-v1.5` (batches of 32, GPU) and upserts into a local ChromaDB collection (`ncert_science`, cosine similarity). Upserts are idempotent — chunks already present are skipped, and duplicate `chunk_id`s within a run are de-duplicated automatically. Ends with a sanity-check query ("What is evaporation?") printed to the console.

The repo currently ships `extracted.zip` (extraction output for all 12 chapters) and `processed.json` showing all 12 chapter PDFs (`iesc101.pdf`–`iesc112.pdf`) already processed.

## 5. Tech stack

| Layer | Choice |
|---|---|
| Embeddings | `BAAI/bge-large-en-v1.5` (sentence-transformers) |
| Re-ranking | `BAAI/bge-reranker-large` (cross-encoder) |
| Vector store | ChromaDB (persistent, local) |
| LLM | `llama-3.3-70b-versatile` via Groq API |
| Frontend | Streamlit |
| PDF extraction | `pdfplumber` (text/captions), `PyMuPDF` (figure rendering) |
| Evaluation | Ragas (faithfulness, answer relevancy, context precision/recall) + custom citation/refusal accuracy |
| Containerization | Docker (`python:3.11-slim` base) |
| Secrets | `python-dotenv` / `.env` file for `GROQ_API_KEY` |

Pinned versions are in `requirements.txt` — note `torch` is pinned to the CPU wheel (`+cpu`) for the runtime container; local development on a CUDA GPU works with the default `torch` install instead.

## 6. Getting started

```bash
git clone https://github.com/divyaitiz/PariShiksha-Capstone.git
cd PariShiksha-Capstone
pip install -r requirements.txt
```

Set your Groq API key — either as an environment variable:

```bash
# Windows PowerShell
$env:GROQ_API_KEY = "gsk_..."

# macOS/Linux
export GROQ_API_KEY="gsk_..."
```

or in a `.env` file in the project root:

```
GROQ_API_KEY=gsk_...
```

You'll also need a populated `./chroma_db/` (see [Section 7](#7-running-the-pipeline-end-to-end) — extract `extracted.zip` and run the chunking + embedding steps, or bring your own).

Then launch the app:

```bash
streamlit run rag_chain.py
```

## 7. Running the pipeline end-to-end

If you're rebuilding the vector store from scratch (e.g. adding a new chapter):

```bash
# 1. Drop chapter PDFs into ./pdfs/
# 2. Extract + structure each chapter (skips already-processed PDFs)
python run_pipeline.py

# 3. Flatten all extracted JSON into chunks
python json_to_chunks.py

# 4. Embed chunks and populate ChromaDB
python chunks_to_embeddings.py

# 5. (optional) Inspect what's stored
python check_chromadb_metadata.py
```

If you just want to run the app against the existing extraction output, unzip `extracted.zip` first, then run steps 3–4 above to (re)build `chroma_db/` locally — the compiled `chroma_db/` itself isn't checked into the repo (see `.gitignore`).

## 8. Evaluation harness

The `eval/` folder implements a golden-set-based evaluation loop, independent of the Streamlit UI:

- **`eval_pipeline.py`** — a Streamlit-free copy of the RAG pipeline (same constants/logic as `rag_chain.py`), used so evaluation scripts and CI don't need a Streamlit runtime.
- **`generate_draft_golden_set.py`** — samples chunks stratified by chapter × section type, asks Groq to draft a student-style question + answer per chunk, filters out document-referencing or duplicate questions, and adds a fixed set of hand-written out-of-scope questions. Output is a **draft** (`golden_set_draft.jsonl`) that must be hand-verified before use.
- **`golden_set.jsonl`** — the hand-verified set actually used for scoring (only rows marked `verified: true` are evaluated).
- **`run_scorecard.py`** — runs every golden-set question through `eval_pipeline.py` and computes:
  - Ragas metrics: faithfulness, answer relevancy, context precision, context recall (judged by Groq's Llama 3.3 70B instead of OpenAI, so no `OPENAI_API_KEY` is needed)
  - **Citation accuracy** — whether the expected chapter/section actually appears among retrieved sections
  - **Refusal accuracy** — whether out-of-scope questions correctly trigger the "not covered" response
  - A per-section-type breakdown, saved to `eval/results/scorecard_<timestamp>.json` and `eval/results/latest.json`
- **`test_regression.py`** — evaluation/regression scaffolding intended to gate changes against `eval/results/latest.json`.

Run it with:

```bash
pip install ragas datasets langchain-groq langchain-huggingface
python eval/run_scorecard.py
```

## 9. Docker

```bash
docker build -t parishiksha .
docker run -p 8501:8501 --env-file .env parishiksha
```

The image is `python:3.11-slim`-based, installs `requirements.txt`, and launches Streamlit on port 8501 with CORS/XSRF disabled for container-friendly access. Note that this repo's Dockerfile does not include Azure Blob sync of `chroma_db/` — see `legacy/v1-parishiksha` for the original Azure Container Instances + Blob Storage sync setup, which isn't part of this repo's current deployment target (see [Section 11](#11-known-limitations--next-steps)).

## 10. Project history / legacy folders

This repo consolidates several earlier iterations, kept for reference:

- **`legacy/ncert-class9-science-llm/`** — the original PDF extraction pipeline covering 7 section types, plus earlier embedding-creation and text-preprocessing experiments (this is where the current pipeline scripts trace back to).
- **`legacy/v1-parishiksha/`** — the first full end-to-end version: RAG pipeline, Streamlit UI, and a documented Azure deployment (Container Instances + Blob Storage sync + GitHub Actions CI/CD). Its README documents the full LLMOps journey, including infra setup, cost management, and issues encountered (e.g. a duplicate environment-variable error and a Groq 401 resolved via `.env`).
- **`legacy/v2-parishiksha/`** — a follow-up iteration refining the extraction/chunking pipeline.

## 11. Known limitations & next steps

- **No Azure deployment config in this repo** — the current repo excludes cloud deployment scripts (student credits exhausted); `legacy/v1-parishiksha` documents the original Azure Container Instances + Blob Storage + GitHub Actions setup for reference.
- **Golden set size** — the evaluation harness targets 80–120 verified questions; check `eval/golden_set.jsonl`'s current row count and `verified` flags before treating scorecard numbers as final.
- **Planned improvements**: a query router for navigational/metadata-filtered queries (e.g. "show me chapter 5"), and further refinement of the image/diagram retrieval and description pipeline.

---

*This README was generated from the repository contents. If any section drifts from actual behavior (e.g. `eval/test_regression.py`'s exact regression-gate logic), check the source file directly — it's the source of truth.*
