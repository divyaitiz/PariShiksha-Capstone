# NCERT Science QA — Class 9
### A Retrieval-Augmented Generation (RAG) pipeline for NCERT Class 9 Science textbooks

> **Live Demo (Local):** Ask questions like *"What are the formulas of motion?"* and get accurate, cited answers from the correct chapter and section.

![NCERT QA Bot](screenshots/app_working.png)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Folder Structure](#2-folder-structure)
3. [Pipeline Architecture](#3-pipeline-architecture)
4. [Tools & Models Used](#4-tools--models-used)
5. [High-Level Design (HLD)](#5-high-level-design-hld)
6. [Low-Level Design (LLD)](#6-low-level-design-lld)
7. [Dependencies & How They Connect](#7-dependencies--how-they-connect)
8. [Setup & Running](#8-setup--running)
9. [Limitations & Gaps](#9-limitations--gaps)
10. [Future Scope](#10-future-scope)

---

## 1. Project Overview

This project builds a **domain-specific Question Answering chatbot** over the 12 chapters of the NCERT Class 9 Science textbook (PDF). It uses a full RAG pipeline:

- Extracts structured content from PDFs (informational text, exercises, activities, examples, in-chapter questions, think-and-act, what-you-have-learnt)
- Converts extracted text into structured JSON per section type
- Chunks the JSON into semantically meaningful units
- Embeds chunks using a state-of-the-art BGE embedding model
- Stores vectors in a local ChromaDB vector store
- At query time: retrieves top-10 candidates, re-ranks with a cross-encoder, and generates a grounded answer using Llama 3.3 70B via Groq
- Presents everything in a clean Streamlit web UI

---

## 2. Folder Structure

```
Test2_Pipeline/
│
├── 📄 run_pipeline.py              # Orchestrator: PDF → text → JSON for all chapters
├── 📄 json_to_chunks.py            # JSON → flat chunks (all section types, all chapters)
├── 📄 chunks_to_embeddings.py      # Chunks → BGE embeddings → ChromaDB
├── 📄 rag_chain.py                 # Streamlit QA app (retrieve → rerank → generate)
├── 📄 processed.json               # Tracks which PDFs have been processed
├── 📄 requirements.txt             # All Python dependencies
├── 📄 README.md                    # This file
│
├── 📁 pdfs/                        # Source NCERT PDF files (12 chapters)
│   ├── iesc101.pdf                 # Chapter 1: Matter in Our Surroundings
│   ├── iesc102.pdf                 # Chapter 2: Is Matter Around Us Pure?
│   └── ... (iesc103 – iesc112)
│
├── 📁 scripts/                     # Extraction scripts (one per section type)
│   ├── pdf_to_text/                # Step 1: PDF → .txt per section type
│   │   ├── informational_text.py   # Extracts body text (sections + subsections)
│   │   ├── exercises.py            # Extracts end-of-chapter exercises
│   │   ├── activities.py           # Extracts in-chapter activities
│   │   ├── examples.py             # Extracts worked examples
│   │   ├── in_chapter_questions.py # Extracts mid-section questions
│   │   ├── think_and_act.py        # Extracts Think and Act boxes
│   │   └── what_you_have_learnt.py # Extracts summary points
│   │
│   └── text_to_json/               # Step 2: .txt → structured .json
│       ├── informational_text.py   # Parses sections/subsections with hierarchy
│       ├── exercises.py
│       ├── activities.py
│       ├── examples.py
│       ├── in_chapter_questions.py
│       ├── think_and_act.py
│       └── what_you_have_learnt.py
│
├── 📁 extracted/                   # Output of run_pipeline.py
│   ├── iesc101/
│   │   ├── text/                   # Raw extracted .txt files
│   │   │   ├── informational_text.txt
│   │   │   ├── exercises.txt
│   │   │   └── ...
│   │   └── json/                   # Structured JSON files
│   │       ├── informational_text.json
│   │       ├── exercises.json
│   │       └── ...
│   └── iesc102/ ... iesc112/
│
├── 📁 chunks/
│   └── all_chunks.jsonl            # Flat file: one JSON chunk per line (all chapters × all types)
│
├── 📁 chroma_db/                   # Persistent ChromaDB vector store
│   └── ncert_science/              # Collection with 702+ embedded chunks
│
├── 📁 logs/                        # Per-chapter pipeline logs
│   ├── iesc101.log
│   └── ...
│
├── 📁 flagged/                     # Chapters/sections that failed quality checks
│   └── iesc10x/
│       ├── <section>.txt
│       └── <section>_issues.txt
│
└── 📁 reference/                   # Reference materials, schema docs, notes
```

### What each folder does

| Folder | Role |
|--------|------|
| `pdfs/` | Source truth — 12 NCERT PDFs, never modified |
| `scripts/pdf_to_text/` | Stateful extractors — know how to find each section type in NCERT's two-column layout |
| `scripts/text_to_json/` | Parsers — convert flat text to structured JSON with section hierarchy |
| `extracted/` | Intermediate artifacts — text and JSON per chapter |
| `chunks/` | Embedding-ready units — each chunk is self-contained with metadata |
| `chroma_db/` | The searchable knowledge base — vectors + metadata, persisted to disk |
| `logs/` | Audit trail — every extraction step logged with timestamps |
| `flagged/` | Quality failures — sections that were too short, had encoding issues, or failed OCR checks |

---

## 3. Pipeline Architecture

The pipeline has two phases: **build-time** (run once) and **query-time** (run on every question).

### Build-time (one-time setup)

```
pdfs/iesc10x.pdf  (×12 chapters)
        │
        ▼
scripts/pdf_to_text/*.py          ← pdfplumber extracts text per section type
        │                            two-column layout handled, footnotes cropped,
        │                            split headings rejoined
        ▼
extracted/iesc10x/text/*.txt      ← one .txt per section type per chapter
        │
        │  quality check (min chars, junk ratio, repeat patterns)
        │  → flagged/ if failed
        ▼
scripts/text_to_json/*.py         ← parse flat text into structured JSON
        │                            section hierarchy, metadata, schema validation
        ▼
extracted/iesc10x/json/*.json     ← 7 JSON files per chapter (84 total)
        │
        ▼
json_to_chunks.py                 ← chunk each JSON by semantic unit
        │                            (subsection / question / activity / point)
        │                            split long blocks with overlap
        ▼
chunks/all_chunks.jsonl           ← 702+ chunks, each with full metadata
        │
        ▼
chunks_to_embeddings.py           ← BGE-large-en-v1.5 (CUDA, batch=32)
        │                            normalize vectors, upsert to ChromaDB
        ▼
chroma_db/ncert_science           ← persistent vector store, cosine similarity
```

### Query-time (per question)

```
User question
        │
        ▼  BGE-large encode (query prefix + question, CUDA)
        │
        ▼  ChromaDB cosine search → top-10 candidate chunks
        │
        ▼  BGE-reranker-large cross-encode (question, chunk) × 10  [CPU]
        │  → sort by score, keep top-3
        │
        ▼  Prompt builder
        │  system prompt + chapter/section context + question
        │
        ▼  Groq API → Llama 3.3 70B
        │
        ▼  Streamlit UI
           Answer + source cards (chapter, section, type, scores)
```

---

## 4. Tools & Models Used

### Embedding Model — `BAAI/bge-large-en-v1.5`

**What it is:** A 335M parameter bi-encoder from Beijing Academy of AI, specifically trained for dense retrieval tasks.

**Why we chose it over alternatives:**

| Model | Dim | Reason not chosen |
|-------|-----|-------------------|
| `text-embedding-3-small` (OpenAI) | 1536 | Paid API, data leaves machine |
| `all-MiniLM-L6-v2` | 384 | Low quality on domain-specific scientific text |
| `all-mpnet-base-v2` | 768 | Outperformed by BGE on BEIR benchmarks |
| `bge-base-en-v1.5` | 768 | BGE-large gives significantly better recall |
| `bge-large-en-v1.5` ✅ | 1024 | Best open-source retrieval quality, fits in 6GB VRAM |

**Key benefit for our use case:** NCERT text has specific scientific vocabulary and numbered section references. BGE-large's larger context and higher-dimensional embeddings capture these domain nuances better than smaller models.

**Important detail:** BGE requires a query-time prefix:
```
"Represent this sentence for searching relevant passages: <query>"
```
This prefix is NOT used when embedding passages — only queries. We handle this correctly in `rag_chain.py`.

---

### Re-ranker — `BAAI/bge-reranker-large`

**What it is:** A cross-encoder that reads the query AND a passage together (not separately like the bi-encoder) and outputs a relevance score.

**Why re-ranking matters:** Vector similarity is fast but imprecise — it finds chunks that are semantically close in embedding space but doesn't deeply understand relevance. The cross-encoder reads both texts jointly and scores true relevance far more accurately.

**Why BGE-reranker-large over alternatives:**

| Model | Notes |
|-------|-------|
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Smaller, less accurate |
| `cohere-rerank` | Paid API |
| `bge-reranker-base` | Same family, lower accuracy |
| `bge-reranker-large` ✅ | Best free cross-encoder, same family as our embedder |

**Hardware note:** Runs on CPU in our setup — the GPU is occupied by BGE-large during embedding. Re-ranking only 10 short chunks takes < 5 seconds on CPU, which is acceptable.

---

### Vector Database — ChromaDB

**What it is:** An open-source, local-first vector database with a Python-native API and persistent storage.

**Why ChromaDB over alternatives:**

| Tool | Reason not chosen |
|------|-------------------|
| Pinecone | Cloud-only, paid beyond free tier, data leaves machine |
| Weaviate | Requires Docker, complex setup |
| Qdrant | Docker-preferred, heavier setup |
| FAISS | No persistence, no metadata filtering, manual management |
| ChromaDB ✅ | Zero setup, persists to disk, metadata filtering, Python-native |

**Key benefit:** ChromaDB stores vectors AND metadata (chapter, section, type) in the same record, enabling future metadata-filtered search (e.g. "search only in exercises" or "search only chapter 7").

---

### LLM — Llama 3.3 70B via Groq

**What it is:** Meta's Llama 3.3 70B instruction-tuned model, served via Groq's LPU (Language Processing Unit) infrastructure.

**Why Groq + Llama 3.3:**

| Option | Issue |
|--------|-------|
| GPT-4o | Paid, expensive at scale |
| Claude API | Paid |
| Local Ollama (7B) | 7B models hallucinate more on scientific content |
| Gemini Free | Lower quality on structured scientific Q&A |
| Groq + Llama 3.3 70B ✅ | Free tier, extremely fast (~0.5s), 70B quality |

**Key benefit for our use case:** 70B models follow the "answer only from context" instruction reliably. Smaller models tend to mix in training knowledge even when told not to.

---

### PDF Extraction — pdfplumber

**Why pdfplumber:**
- Native two-column bbox extraction (critical for NCERT's two-column layout)
- `within_bbox()` lets us crop footnote zones before extraction
- Better than PyMuPDF for text ordering in multi-column layouts
- Better than pdfminer directly (pdfplumber wraps it with a better API)

---

### UI — Streamlit

Lightweight Python-native web framework. Zero HTML/CSS needed. `@st.cache_resource` ensures models load once and persist across reruns — critical since BGE-large takes ~30s to load.

---

## 5. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────┐
│                        BUILD PHASE (once)                       │
│                                                                  │
│  ┌──────────┐    ┌─────────────┐    ┌──────────┐    ┌────────┐ │
│  │  12 NCERT│    │  pdf_to_text│    │text_to_  │    │  json_ │ │
│  │  PDFs    │───▶│  scripts    │───▶│json      │───▶│  to_   │ │
│  │          │    │  (×7 types) │    │scripts   │    │ chunks │ │
│  └──────────┘    └─────────────┘    └──────────┘    └───┬────┘ │
│                                                          │       │
│                                               ┌──────────▼────┐ │
│                                               │ BGE-large-en  │ │
│                                               │ (CUDA embed)  │ │
│                                               └──────────┬────┘ │
│                                                          │       │
│                                               ┌──────────▼────┐ │
│                                               │   ChromaDB    │ │
│                                               │ (702+ chunks) │ │
│                                               └───────────────┘ │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       QUERY PHASE (per question)                 │
│                                                                  │
│  ┌──────────┐    ┌─────────────┐    ┌──────────────┐           │
│  │  Student │    │  BGE-large  │    │   ChromaDB   │           │
│  │ Question │───▶│  (CUDA)     │───▶│  cosine top10│           │
│  └──────────┘    └─────────────┘    └──────┬───────┘           │
│                                             │                    │
│                                    ┌────────▼──────────┐        │
│                                    │ BGE-reranker-large│        │
│                                    │ (CPU, top-3)      │        │
│                                    └────────┬──────────┘        │
│                                             │                    │
│                                    ┌────────▼──────────┐        │
│                                    │  Prompt Builder   │        │
│                                    │ (system + context)│        │
│                                    └────────┬──────────┘        │
│                                             │                    │
│                                    ┌────────▼──────────┐        │
│                                    │  Groq Llama 3.3   │        │
│                                    │  70B (cloud)      │        │
│                                    └────────┬──────────┘        │
│                                             │                    │
│                                    ┌────────▼──────────┐        │
│                                    │  Streamlit UI     │        │
│                                    │  Answer + Sources │        │
│                                    └───────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Low-Level Design (LLD)

### PDF Extraction Detail

```
pdfplumber.open(pdf)
    │
    ├── for each page:
    │       ├── crop to top 87% (removes footnotes)
    │       ├── left column  = within_bbox(0, 0, mid, h*0.87)
    │       └── right column = within_bbox(mid, 0, w, h*0.87)
    │
    ├── join_split_headings()
    │       └── detect "1.2 Characteristics of Particles of"
    │               + next line "Matter"
    │           → merge into "1.2 Characteristics of Particles of Matter"
    │
    ├── extract_informational()
    │       ├── HARD STOP on: Exercises, What You Have Learnt, Summary
    │       ├── SKIP blocks: Activity N, Think and Act, Questions
    │       ├── RESUME skip on: next valid section heading
    │       ├── is_noise(): page numbers, figure captions, running headers
    │       └── is_footnote_fragment(): broken words from cropped footnotes
    │
    └── write to extracted/<chapter>/text/informational_text.txt
```

### Chunking Detail

```
json_to_chunks.py
    │
    ├── informational_text.json
    │       ├── intro → 1 chunk (or split if > 200 words)
    │       ├── section with no subsections → 1 chunk per section
    │       └── section with subsections:
    │               ├── section-level prose → 1 chunk
    │               └── each subsection → 1 chunk (split if long)
    │
    ├── exercises.json
    │       └── each exercise + subparts → 1 chunk
    │
    ├── activities.json
    │       └── each activity + steps → 1 chunk
    │
    ├── examples.json
    │       └── problem + solution steps + answer → 1 chunk
    │
    ├── in_chapter_questions.json
    │       └── each question + short subparts → 1 chunk
    │               (topic carried as metadata)
    │
    ├── think_and_act.json
    │       └── each item → 1 chunk
    │
    └── what_you_have_learnt.json
            └── each bullet point → 1 chunk

Long block splitting (> 200 words):
    words = content.split()
    for start in range(0, len(words), 200-30):
        chunk = words[start : start+200]   ← 30-word overlap
```

### Chunk Metadata Schema

```json
{
  "chunk_id":       "iesc101_informational_text_1.2.1_0",
  "chapter_id":     "iesc101",
  "chapter_number": "1",
  "chapter_title":  "Matter in Our Surroundings",
  "source_file":    "iesc101.pdf",
  "section_type":   "informational_text",
  "section_id":     "1.2.1",
  "section_title":  "Particles Of Matter Have Space Between Them",
  "parent_id":      "1.2",
  "parent_title":   "Characteristics of Particles of Matter",
  "topic":          "",
  "content":        "In activities 1.1 and 1.2 we saw that...",
  "chunk_index":    0
}
```

### Embedding + Retrieval Detail

```
chunks_to_embeddings.py:
    ├── SentenceTransformer("BAAI/bge-large-en-v1.5", device="cuda")
    ├── max_seq_length = 512 tokens
    ├── encode(content, normalize_embeddings=True)  ← L2 normalized
    ├── batch_size = 32  (safe for RTX 3050 6GB)
    └── collection.upsert(ids, embeddings, documents, metadatas)

rag_chain.py — retrieve():
    ├── query_vec = encode(QUERY_PREFIX + question, normalize=True)
    └── collection.query(query_embeddings=[query_vec], n_results=10)
        └── distance metric: cosine (hnsw:space=cosine)

rag_chain.py — rerank():
    ├── CrossEncoder("BAAI/bge-reranker-large", device="cpu")
    ├── pairs = [[question, chunk_content] for each of 10 candidates]
    ├── scores = model.predict(pairs)
    └── sort by score DESC, return top 3
```

### Prompt Structure

```
SYSTEM:
  You are a helpful NCERT Science tutor for Class 9 students.
  Answer using ONLY the context provided.
  Mention which chapter/section the answer comes from.

USER:
  Context:
  [Source 1] Chapter 7 — Motion | Section 7.5: Equations of Motion | informational_text
  When an object moves along a straight line with uniform acceleration...

  [Source 2] Chapter 7 — Motion | Section 6: Point 6 | what_you_have_learnt
  v = u + at, s = ut + ½at², 2as = v² – u²...

  [Source 3] ...

  Question: What are the formulas of motion?
```

---

## 7. Dependencies & How They Connect

```
requirements.txt

pdfplumber          ← PDF text extraction (two-column bbox)
sentence-transformers ← BGE-large (embed) + BGE-reranker (rerank)
torch               ← GPU backend for sentence-transformers
chromadb            ← vector store (persist, upsert, query)
groq                ← Groq API client for Llama 3.3 70B
streamlit           ← web UI framework
```

### Dependency graph

```
pdfplumber
    └── feeds text → scripts/pdf_to_text/*.py
                          └── feeds .txt → scripts/text_to_json/*.py
                                               └── feeds .json → json_to_chunks.py
                                                                      └── feeds chunks → chunks_to_embeddings.py
                                                                                              │
                                                                    sentence-transformers ────┤
                                                                    (BGE-large, CUDA)         │
                                                                                              ▼
                                                                                          chromadb
                                                                                              │
                                                                                    ┌─────────┘
                                                                                    │
                                                                              rag_chain.py
                                                                                    │
                                                                    sentence-transformers (BGE-large query)
                                                                                    │
                                                                    chromadb (top-10 retrieve)
                                                                                    │
                                                                    sentence-transformers (BGE-reranker, CPU)
                                                                                    │
                                                                    groq (Llama 3.3 70B)
                                                                                    │
                                                                    streamlit (UI)
```

---

## 8. Setup & Running

### Prerequisites

- Python 3.10+
- NVIDIA GPU with CUDA (tested on RTX 3050 6GB)
- Groq API key (free at [console.groq.com](https://console.groq.com))

### Installation

```powershell
# Clone / open project
cd "Test2_Pipeline"

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate

# Install dependencies
pip install pdfplumber sentence-transformers chromadb streamlit groq
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### Run Order

```powershell
# Step 1 — Extract all chapters (takes ~15-20 min for 12 PDFs)
python run_pipeline.py

# Step 2 — Create chunks
python json_to_chunks.py

# Step 3 — Embed and store (takes ~5-10 min, downloads BGE-large ~1.3GB first time)
python chunks_to_embeddings.py

# Step 4 — Launch QA bot
$env:GROQ_API_KEY = "gsk_your_key_here"
streamlit run rag_chain.py
```

Open browser at `http://localhost:8501`

### Adding new PDFs (future chapters / other books)

1. Drop PDF into `pdfs/`
2. Delete its entry from `processed.json` (or delete the file entirely)
3. Re-run steps 1–3
4. Step 4 picks up new chunks automatically (upsert is idempotent)

---

## 9. Limitations & Gaps

### Content Extraction

| Limitation | Impact |
|------------|--------|
| **Tables not extracted** | NCERT has many data tables (e.g. motion data in Chapter 7). pdfplumber reads table cells as flat text, losing row/column structure. Questions about tabular data may get wrong answers. |
| **Images and diagrams ignored** | Figures like force diagrams, circuit diagrams, cell diagrams are skipped entirely. Questions like "What does Fig 8.2 show?" cannot be answered. |
| **Mathematical equations corrupted** | Superscripts/subscripts (m s⁻², H₂O) sometimes extracted as plain text (`m s-2`, `H2O`), losing formatting. Complex equations (integration, matrices) are garbled. |
| **Two-column split errors** | Some pages have non-standard layouts (full-width boxes, three-column sections). The fixed midpoint column split breaks on these pages. |
| **Footnote bleed** | Despite 87% crop, some footnotes span page boundaries and leak into content. |
| **Running headers** | Chapter titles printed at the top of every page (e.g. "MATTER IN OUR SURROUNDINGS") occasionally survive filtering and appear in chunks. |
| **Chapter title empty** | The chapter title is not reliably extractable from the PDF — currently left blank in JSON, which means source citations in the UI show empty chapter titles for some chapters. |

### Retrieval

| Limitation | Impact |
|------------|--------|
| **Fixed chunk size** | 200-word chunks may split a concept mid-explanation, causing the retrieved chunk to lack necessary context. |
| **No metadata filtering in UI** | Users cannot restrict search to a specific chapter or section type (e.g. "only look in exercises"). |
| **Re-ranker runs on CPU** | Re-ranking 10 chunks takes 60–80 seconds on CPU. This is the biggest latency bottleneck. |
| **702 chunks for 12 chapters** | Relatively small corpus — some questions may not find a good match if the concept is in a section that wasn't extracted correctly. |

### Generation

| Limitation | Impact |
|------------|--------|
| **No conversation memory** | Each question is independent. Follow-up questions like "Can you explain the second formula?" don't work. |
| **Groq rate limits** | Free tier has requests-per-minute limits. Heavy use will hit rate limit errors. |
| **No answer verification** | The LLM is trusted to follow the "answer only from context" instruction, but it occasionally adds information from training data. |

---

## 10. Future Scope

### Short-term improvements

**1. Table extraction**
Use `pdfplumber`'s `extract_tables()` instead of `extract_text()` for pages containing tables. Convert tables to natural language descriptions or markdown before chunking.

**2. Image/diagram captioning**
Extract page images using `pdfplumber` + `PIL`, pass through a vision model (e.g. `LLaVA`, `Qwen-VL`, or `GPT-4o vision`) to generate text descriptions. Store captions as additional chunks.

**3. Move re-ranker to GPU**
Load BGE-large on GPU only during embedding, release GPU memory, then load re-ranker on GPU. This would cut re-rank time from ~70s to ~2s.

**4. Metadata-filtered search**
Add sidebar filters in Streamlit (chapter selector, section type selector). Pass filters to `collection.query(where={"chapter_id": "iesc107"})`.

**5. Conversation memory**
Add `st.session_state` message history. Pass last N turns to Groq for follow-up question support.

### Medium-term improvements

**6. Hierarchical chunking**
Store both subsection-level chunks (for precise retrieval) and section-level summaries (for broader context). Retrieve at subsection level, augment with parent section for context.

**7. Equation handling**
Use a LaTeX-aware PDF parser (e.g. `nougat` by Meta) for pages with mathematical content. Store equations in LaTeX format and render them in the UI with MathJax.

**8. Automatic chapter title extraction**
Maintain a `chapter_metadata.json` mapping `iesc10x → chapter title` extracted from the PDF's table of contents page.

**9. Multi-book support**
Extend to Class 8, 10 Science and other subjects (Maths, Social Science). The pipeline is fully generalized — only the `SECTION_TYPES` list and extraction scripts need updating.

### Long-term improvements

**10. Fine-tuned embedding model**
Fine-tune BGE-large on NCERT-specific QA pairs (generated using the LLM) to improve retrieval precision for domain-specific terminology.

**11. Answer evaluation**
Build an automated evaluation pipeline using a teacher LLM to score answer correctness against a gold-standard QA dataset.

**12. Student performance tracking**
Log questions asked, sections retrieved, and answers given. Build analytics to identify which concepts students ask about most — useful for teachers.

---

## App Screenshots

### Working QA Bot — Formulas of Motion

![App Screenshot](screenshots/app_working.png)

*Query: "What are the formulas of motion?" — Answer retrieved from Chapter 7, Section 7.5 and What You Have Learnt, with re-rank scores and source citations.*

---

## Credits

- **NCERT** — Source textbook content
- **BAAI** — BGE embedding and reranker models
- **Meta** — Llama 3.3 70B
- **Groq** — LPU inference infrastructure
- **ChromaDB** — Vector store
- **Streamlit** — UI framework
- **pdfplumber** — PDF extraction

---

*Built as part of IITGN NCERT LLM Project — 2026*
