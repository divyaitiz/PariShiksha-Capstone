# Exercises Pipeline — Quick Start

## Folder Structure
```
pipeline/
│
├── pdfs/                          ← DROP PDFs HERE
│
├── extracted/
│   └── <book_name>/
│       ├── text/
│       │   └── exercises.txt      ← Set 1 output (audit layer)
│       └── json/
│           └── exercises.json     ← Set 2 output (final data)
│
├── flagged/                       ← faulty extractions land here
│   └── <book_name>/
│       ├── exercises.txt
│       └── exercises_issues.txt   ← why it was flagged
│
├── logs/                          ← one log per PDF
│   └── <book_name>.log
│
├── reference/                     ← put your known-good JSONs here
│   └── chapter7_exercises_output.json
│
├── test_run/                      ← used by test_exercises.py
│   └── text/
│       └── exercises.txt          ← put your verified txt here
│
├── scripts/
│   ├── pdf_to_text/
│   │   └── exercises.py           ← ⚠️  PLUG IN YOUR SET 1 LOGIC
│   └── text_to_json/
│       └── exercises.py           ← ✅  converted from your notebook
│
├── run_pipeline.py                ← main orchestrator
├── test_exercises.py              ← verify text→JSON flow
└── processed.json                 ← auto-created, tracks processed PDFs
```

## How to Run

### Step 1 — Test text→JSON first (no PDF needed)
```bash
# Put your ch7_end_exercises.txt here:
cp ch7_end_exercises.txt test_run/text/exercises.txt

# Put your reference JSON here:
cp chapter7_exercises_output.json reference/chapter7_exercises_output.json

# Run the test
python test_exercises.py
```

### Step 2 — Plug in your PDF→Text script
Open `scripts/pdf_to_text/exercises.py` and paste your existing extraction logic.
It receives `PDF_PATH` and `TEXT_DIR` as environment variables.

### Step 3 — Run the full pipeline
```bash
# Drop a PDF into pdfs/
cp mybook.pdf pdfs/

# Run
python run_pipeline.py
```

## Environment Variables (passed automatically by orchestrator)
| Variable       | Description                        |
|----------------|------------------------------------|
| `PDF_PATH`     | Full path to the PDF               |
| `TEXT_DIR`     | Where to write .txt files (Set 1)  |
| `JSON_DIR`     | Where to write .json files (Set 2) |
| `CHAPTER_NAME` | Used as the chapter label in JSON  |

## Adding More Section Types Later
In `run_pipeline.py`, just add to the list:
```python
SECTION_TYPES = [
    "exercises",
    "activities",        # add these when ready
    "examples",
    "informational",
    "what_have_you_learnt",
]
```
And add the corresponding scripts in `scripts/pdf_to_text/` and `scripts/text_to_json/`.
