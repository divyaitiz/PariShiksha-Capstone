# Chunking Exercises — Exercise Parser for Chapter 7

A Python utility that parses a plain-text file of chapter exercises into a structured JSON format, splitting questions and extracting labeled sub-parts automatically.

---

## Overview

This notebook reads a raw text file of end-of-chapter exercises (`ch7_end_exercises.txt`), identifies individual numbered questions, detects any lettered sub-parts within each question, and writes the result to a clean `exercises.json` file.

---

## Files

| File | Description |
|---|---|
| `Chunking_exercises.ipynb` | Main notebook containing all parsing logic |
| `ch7_end_exercises.txt` | Input — raw text file of Chapter 7 exercises |
| `exercises.json` | Output — structured JSON of parsed exercises |

---

## Functions

### `split_questions(text: str) → list[tuple]`
Splits the raw text content into individual questions by detecting numbered patterns (e.g., `1. Question text`).

- Normalises line endings and whitespace
- Uses regex `^\s*(\d+)\.\s+(?=[A-Z])` to identify real question starts
- Returns a list of `(question_id, question_text)` tuples

### `extract_subparts(q_text: str) → tuple`
Processes a single question's text to detect and extract lettered sub-parts (e.g., `(a)`, `(b)`).

- Returns `(main_question_text, None)` if no sub-parts are found
- Returns `(main_question_text, list_of_subparts)` if sub-parts exist
- Each sub-part is a dict with `label` and `text` keys

### `parse_exercises(file_path: str) → dict`
Orchestrates the full parsing pipeline.

1. Reads the input text file
2. Calls `split_questions` to segment the content
3. Calls `extract_subparts` on each question
4. Returns a dict with `"chapter"` and `"exercises"` keys

---

## Output Format

The generated `exercises.json` follows this structure:

```json
{
  "chapter": "Chapter 7",
  "exercises": [
    {
      "id": 1,
      "question": "Main question text",
      "subparts": [
        { "label": "a", "text": "Subpart (a) text" },
        { "label": "b", "text": "Subpart (b) text" }
      ]
    }
  ]
}
```

- `id` — the question number from the source text
- `question` — the main question body (text before any sub-parts)
- `subparts` — *(optional)* array of labeled sub-parts; omitted when none exist

---

## Usage

1. Place your exercise text file in the working directory as `ch7_end_exercises.txt`.
2. Run all cells in `Chunking_exercises.ipynb`, or execute the script directly:

```bash
python chunking_exercises.py
```

3. The parsed output will be saved to `exercises.json` and a summary will be printed:

```
Parsed 10 exercises → exercises.json
```

---

## Requirements

- Python 3.x
- Standard library only (`re`, `json`) — no additional dependencies needed
