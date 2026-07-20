# NCERT PDF Extraction Pipeline

A fully automated pipeline to extract structured content from NCERT Science
textbook PDFs (iesc101 – iesc112), convert them to JSON, and prepare them
for a LangChain + ChromaDB Q&A system.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Folder Structure](#2-folder-structure)
3. [What Gets Extracted](#3-what-gets-extracted)
4. [Setup & Installation](#4-setup--installation)
5. [How to Run](#5-how-to-run)
6. [How the Pipeline Works](#6-how-the-pipeline-works)
7. [Script Reference](#7-script-reference)
8. [Output JSON Schemas](#8-output-json-schemas)
9. [Quality Checks & Flagging](#9-quality-checks--flagging)
10. [Tracker & Reprocessing](#10-tracker--reprocessing)
11. [Troubleshooting](#11-troubleshooting)
12. [Next Steps — LangChain + ChromaDB](#12-next-steps--langchain--chromadb)

---

## 1. Project Overview

This pipeline takes 12 NCERT Science PDF chapters as input and produces
structured JSON files for each section type within every chapter.

```
PDFs (12 chapters)
      ↓
  run_pipeline.py          ← orchestrates everything
      ↓
Text Files (audit layer)   ← verify extraction quality
      ↓
JSON Files (final output)  ← ready for LangChain ingestion
```

The pipeline is designed to be:
- **Modular** — each section type has its own dedicated scripts
- **Auditable** — text files are kept as an intermediate verification layer
- **Resilient** — quality checks flag bad extractions without stopping the run
- **Incremental** — already processed PDFs are skipped automatically

---

## 2. Folder Structure

```
pipeline/
│
├── pdfs/                          ← DROP YOUR PDFs HERE
│   ├── iesc101.pdf
│   ├── iesc102.pdf
│   └── ... (up to iesc112.pdf)
│
├── extracted/                     ← AUTO-CREATED on first run
│   └── iesc107/
│       ├── text/                  ← intermediate text files (audit layer)
│       │   ├── exercises.txt
│       │   ├── think_and_act.txt
│       │   ├── what_you_have_learnt.txt
│       │   ├── in_chapter_questions.txt
│       │   ├── activities.txt
│       │   └── examples.txt
│       └── json/                  ← final structured output
│           ├── exercises.json
│           ├── think_and_act.json
│           ├── what_you_have_learnt.json
│           ├── in_chapter_questions.json
│           ├── activities.json
│           └── examples.json
│
├── flagged/                       ← extractions that failed quality check
│   └── iesc107/
│       ├── exercises.txt          ← the bad extraction
│       └── exercises_issues.txt   ← reason it was flagged
│
├── logs/                          ← one log file per PDF
│   ├── iesc101.log
│   └── iesc107.log
│
├── scripts/
│   ├── pdf_to_text/               ← SET 1: PDF → Text (extraction logic)
│   │   ├── exercises.py
│   │   ├── think_and_act.py
│   │   ├── what_you_have_learnt.py
│   │   ├── in_chapter_questions.py
│   │   ├── activities.py
│   │   └── examples.py
│   │
│   └── text_to_json/              ← SET 2: Text → JSON (chunking logic)
│       ├── exercises.py
│       ├── think_and_act.py
│       ├── what_you_have_learnt.py
│       ├── in_chapter_questions.py
│       ├── activities.py
│       └── examples.py
│
├── run_pipeline.py                ← MAIN ORCHESTRATOR
├── processed.json                 ← auto-created, tracks processed PDFs
└── README.md                      ← this file
```

---

## 3. What Gets Extracted

| Section | Script Name | Present In |
|---|---|---|
| Chapter end exercises | `exercises` | All 12 chapters |
| Think and Act boxes | `think_and_act` | Some chapters only |
| What You Have Learnt | `what_you_have_learnt` | All 12 chapters |
| In-chapter questions | `in_chapter_questions` | Most chapters |
| Activities | `activities` | Most chapters |
| Worked examples | `examples` | Most chapters |

Sections not found in a chapter are silently skipped — no error is raised.

---

## 4. Setup & Installation

### Step 1 — Prerequisites

- Python 3.10 or higher
- VSCode (recommended)

### Step 2 — Open the pipeline folder in VSCode

```
File → Open Folder → select the pipeline folder
```

### Step 3 — Open the terminal

```
Terminal → New Terminal   (or Ctrl + `)
```

### Step 4 — Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

You should see `(.venv)` in your terminal prompt.

### Step 5 — Install dependencies

```powershell
pip install pdfplumber
```

All other libraries (`re`, `json`, `os`, `subprocess`, `logging`, `pathlib`)
are part of Python's standard library — no additional installs needed.

### Step 6 — Verify installation

```powershell
python -c "import pdfplumber; print('pdfplumber OK')"
```

---

## 5. How to Run

### Full run — all 12 PDFs, all sections

```powershell
# Step 1: Drop all 12 PDFs into the pdfs/ folder
# Step 2: Activate virtual environment
.venv\Scripts\activate

# Step 3: Run the pipeline
python run_pipeline.py
```

### Expected terminal output

```
Found 12 PDF(s) in ./pdfs/
   12 new | 0 already processed

--------------------------------------------------
Processing: iesc107.pdf
--------------------------------------------------

  [EXERCISES]
  Step 1 > PDF -> Text
    [exercises.py] Extracted exercises -> extracted\iesc107\text\exercises.txt
    Quality check passed
  Step 2 > Text -> JSON
    [exercises.py] Parsed 10 exercises -> extracted\iesc107\json\exercises.json

  [THINK_AND_ACT]
  Step 1 > PDF -> Text
    [think_and_act.py] Extracted 1 blocks -> extracted\iesc107\text\think_and_act.txt
    Quality check passed
  Step 2 > Text -> JSON
    [think_and_act.py] Parsed 1 entries -> extracted\iesc107\json\think_and_act.json

  ... (repeats for each section)

  Summary: iesc107.pdf
     Completed : 6/6 sections -> extracted\iesc107\json\
     Log at    : logs\iesc107.log

==================================================
Pipeline complete!
==================================================
```

### Reset and rerun from scratch

```powershell
del processed.json
Remove-Item -Recurse -Force extracted, flagged, logs
python run_pipeline.py
```

### Check output for a specific chapter

```powershell
# View extracted text (audit layer)
type extracted\iesc107\text\exercises.txt

# View generated JSON
type extracted\iesc107\json\exercises.json
```

---

## 6. How the Pipeline Works

The orchestrator (`run_pipeline.py`) processes each PDF through this flow:

```
For each new PDF in pdfs/:
│
├── For each section in SECTION_TYPES:
│   │
│   ├── STEP 1: Run scripts/pdf_to_text/<section>.py
│   │     Receives: PDF_PATH, TEXT_DIR, JSON_DIR, CHAPTER_NAME
│   │     Writes:   TEXT_DIR/<section>.txt
│   │
│   ├── QUALITY CHECK on the .txt file
│   │     Pass  → proceed to Step 2
│   │     Fail  → copy to flagged/, write issue notes, skip Step 2
│   │     Skip  → section not in this chapter, continue silently
│   │
│   └── STEP 2: Run scripts/text_to_json/<section>.py
│         Reads:  TEXT_DIR/<section>.txt
│         Writes: JSON_DIR/<section>.json
│
└── Mark PDF as done in processed.json
```

### Environment variables passed to every script automatically

| Variable | Description | Example |
|---|---|---|
| `PDF_PATH` | Full path to the PDF | `pdfs\iesc107.pdf` |
| `TEXT_DIR` | Where to write `.txt` files | `extracted\iesc107\text` |
| `JSON_DIR` | Where to write `.json` files | `extracted\iesc107\json` |
| `CHAPTER_NAME` | PDF filename without extension | `iesc107` |

---

## 7. Script Reference

### pdf_to_text scripts (Set 1)

Each script finds its section in the PDF using heading detection,
extracts and cleans the text, and writes it to `TEXT_DIR/<section>.txt`.
If the section is not found, the script prints `SKIP` and exits — no file
is created and no error is raised.

| Script | How it finds the section |
|---|---|
| `exercises.py` | Looks for a standalone `"Exercises"` line |
| `think_and_act.py` | Looks for `"Think and Act"` heading pattern, uses two-column extraction |
| `what_you_have_learnt.py` | Handles both single-line and split (3-line) heading format |
| `in_chapter_questions.py` | Finds `"Questions"` / `"Q uestions"` headers, handles OCR artifacts |
| `activities.py` | Finds `"Activity X.X"` numbered headings, uses two-column extraction |
| `examples.py` | Finds `"Example X.X"` blocks containing a `Solution` section |

### text_to_json scripts (Set 2)

Each script reads the `.txt` file and converts it to structured JSON.
Logic is identical to the original Colab notebooks — only file paths
are replaced with environment variables.

| Script | What it produces |
|---|---|
| `exercises.py` | Numbered question list with optional subparts |
| `think_and_act.py` | List of think-and-act blocks with chapter metadata |
| `what_you_have_learnt.py` | Numbered bullet points with optional formula extraction |
| `in_chapter_questions.py` | Sectioned questions with topic inference and unique IDs |
| `activities.py` | Activity blocks with numbered steps if present |
| `examples.py` | Problem + solution with given values, steps, formulas, final answer |

---

## 8. Output JSON Schemas

### exercises.json

```json
{
  "chapter": "Chapter 7",
  "exercises": [
    {
      "id": 1,
      "question": "An object has moved through a distance...",
      "subparts": [
        { "label": "a", "text": "It cannot be zero." },
        { "label": "b", "text": "Its magnitude is greater than..." }
      ]
    }
  ]
}
```

### think_and_act.json

```json
[
  {
    "chapter": "7",
    "thinkandact": "We sometimes are endangered by the motion of objects..."
  }
]
```

### what_you_have_learnt.json

```json
{
  "section": "What you have learnt",
  "total_points": 7,
  "points": [
    { "id": 1, "text": "Motion is a change of position..." },
    { "id": 6, "text": "v = u + at ...", "formulas": ["v = u + at"] }
  ]
}
```

### in_chapter_questions.json

```json
{
  "sections": [
    {
      "section_id": 1,
      "section_key": "section_1",
      "title": "Questions",
      "topic": "Motion and Displacement",
      "questions": [
        {
          "id": 1,
          "qid": "S1Q1",
          "question": "An object has moved through a distance...",
          "subparts": [
            { "label": "a", "text": "It cannot be zero." }
          ]
        }
      ]
    }
  ]
}
```

### activities.json

```json
{
  "activities": [
    {
      "id": 1,
      "activity_id": "7.1",
      "chapter": "7",
      "title": "Activity 7.1",
      "content": "Full activity text...",
      "steps": ["Measure the length of the path..."]
    }
  ]
}
```

### examples.json

```json
[
  {
    "chapter": "7",
    "example_id": "7.1",
    "problem": "An object travels 16 m in 4 s and then another 16 m in 2 s...",
    "given": {
      "distances": ["16 m"],
      "times": ["4 s", "2 s"]
    },
    "steps": [
      "Total distance = 16 m + 16 m = 32 m",
      "Average speed = 32 m / 6 s = 5.33 m/s"
    ],
    "formulas_used": ["average speed = total distance / total time"],
    "final_answer": "5.33m/s",
    "units": "m/s"
  }
]
```

---

## 9. Quality Checks & Flagging

Every `.txt` file is automatically checked after extraction:

| Check | Condition | Action |
|---|---|---|
| Empty file | No content at all | Flag |
| Too short | Less than 100 characters | Flag |
| Encoding issues | More than 10% non-ASCII characters | Flag |
| OCR failure | Any character repeated 10+ times in a row | Flag |
| Section absent | Script exits with SKIP (no file created) | Silent skip |

### Reviewing flagged files

```
flagged/
└── iesc107/
    ├── activities.txt          ← extracted text to inspect
    └── activities_issues.txt   ← exact reason it was flagged
```

Open `activities_issues.txt` to read the reason. To fix:

1. Manually correct the text in `extracted/iesc107/text/activities.txt`
2. Run only the text_to_json script for that section:

```powershell
$env:TEXT_DIR = "extracted\iesc107\text"
$env:JSON_DIR = "extracted\iesc107\json"
$env:CHAPTER_NAME = "iesc107"
python scripts\text_to_json\activities.py
```

---

## 10. Tracker & Reprocessing

`processed.json` is auto-created and tracks every processed PDF:

```json
{
  "iesc101.pdf": { "processed_at": "2026-04-29 11:30:00", "status": "done" },
  "iesc107.pdf": { "processed_at": "2026-04-29 11:45:00", "status": "done" }
}
```

Any PDF listed here is skipped on subsequent runs.

### Reprocess everything

```powershell
del processed.json
Remove-Item -Recurse -Force extracted, flagged, logs
python run_pipeline.py
```

### Reprocess a single PDF

Remove only that PDF's entry from `processed.json` and re-run.

### Add a new PDF later

Just drop it into `pdfs/` and run `python run_pipeline.py` — only the
new file will be processed.

---

## 11. Troubleshooting

### ModuleNotFoundError: No module named 'pdfplumber'

The virtual environment is not active or pdfplumber is installed in the
wrong Python.

```powershell
.venv\Scripts\activate
pip install pdfplumber
python -c "import pdfplumber; print('OK')"
```

### UnicodeEncodeError in terminal

Windows terminal encoding issue. Ensure `run_pipeline.py` has this at the top:

```python
import sys
sys.stdout.reconfigure(encoding="utf-8")
```

And that `FileHandler` uses UTF-8:

```python
fh = logging.FileHandler(log_file, encoding='utf-8')
```

### Section skipped for all 12 chapters

The heading detection pattern doesn't match the raw PDF text. Run a quick
debug to see how the heading appears:

```powershell
python -c "
import pdfplumber
with pdfplumber.open('pdfs/iesc101.pdf') as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text and 'your_keyword' in text.lower():
            for line in text.splitlines():
                if 'your_keyword' in line.lower():
                    print(repr(line))
"
```

### All PDFs show 0 completed sections

The orchestrator is calling system Python instead of the venv Python.
Check that `run_pipeline.py` uses `sys.executable`:

```python
result = subprocess.run(
    [sys.executable, str(script_path)],   # NOT "python"
    ...
)
```

### Pipeline runs very slowly

`pdfplumber` is thorough but slower than alternatives. Expected times:

| PDF size | Approximate time per section |
|---|---|
| Small (< 10 pages) | 5–15 seconds |
| Medium (20–30 pages) | 30–60 seconds |
| Large (50+ pages) | 2–5 minutes |

For 12 PDFs × 6 sections, allow 15–30 minutes for a full run.

---

## 12. Next Steps — LangChain + ChromaDB

Once all JSON files are generated, the next phase loads them into ChromaDB
for semantic search and Q&A across all 12 chapters.

### Phase 2 Architecture

```
extracted/ (all JSONs)
      ↓
LangChain Document Loader    ← load JSONs as Documents with metadata
      ↓
ChromaDB Vector Store        ← persistent embeddings on disk
      ↓
RetrievalQA Chain            ← semantic search + answer generation
      ↓
Q&A Chatbot
```

### What you will be able to do

```python
# Query across all chapters and section types
qa.invoke("What are the equations of motion?")
qa.invoke("List all activities related to acceleration")
qa.invoke("What does Chapter 3 say about atoms?")

# Filter by section type or chapter
retriever = vectorstore.as_retriever(
    search_kwargs={
        "filter": {"section": "exercises", "chapter": "7"}
    }
)
```

### Install dependencies for Phase 2

```powershell
pip install langchain langchain-community langchain-openai chromadb
```

Phase 2 implementation will load all JSONs from the `extracted/` folder,
create a ChromaDB vector store with metadata (chapter, section type, question
ID), and expose a RetrievalQA chain for natural language querying.
