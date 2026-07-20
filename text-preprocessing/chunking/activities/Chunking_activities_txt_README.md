# Chunking_activities_txt — README

## Overview

This notebook parses a plain-text file (`activities.txt`) that contains numbered educational activities, extracts each activity's text and page number into structured Python dictionaries, and lays the groundwork for exporting the result as JSON.

---

## Input

| File | Description |
|------|-------------|
| `activities.txt` | Plain-text source file containing sequentially numbered activities (e.g. `Activity 7.1`, `Activity 7.2`, …) interleaved with bare page numbers. |

---

## What the Notebook Does

### 1. Activity Parsing (`chunk_activities_to_json`)

A regex-based function splits the raw text into individual activity chunks. For each line it:

- **Skips** blank lines.
- **Detects page numbers** — bare 2–3 digit integers (e.g. `73`) are captured as the current page.
- **Detects activity headers** — lines matching `Activity <N>.<M>` (case-insensitive) trigger a new chunk.
- **Accumulates body text** for the current activity until the next header is found.

Each completed chunk is stored as a Python dict:

```python
{
    "type": "activity",
    "activity_number": "7.3",   # e.g. "7.1" – "7.11"
    "text": "<full activity text>",
    "page": 73                  # integer page number
}
```

### 2. Page Number Correction

Automatic page detection from the raw text was found to be unreliable (page numbers embedded in the file do not always align with activities as expected). A manual mapping overrides the extracted values:

| Activity | Correct Page |
|----------|-------------|
| 7.1 | 72 |
| 7.2 | 72 |
| 7.3 | 73 |
| 7.4 | 73 |
| 7.5 | 74 |
| 7.6 | 75 |
| 7.7 | 76 |
| 7.8 | 77 |
| 7.9 | 80 |
| 7.10 | 81 |
| 7.11 | 84 |

### 3. Consolidated Run & Verification

A final cell re-executes parsing and page correction together and prints each activity's text alongside its corrected page number for quick visual verification.

---

## Output

At the end of the notebook, `chunks` is a **Python list of dicts** (one per activity) with correct page numbers applied. This is ready to be serialised to JSON using Python's built-in `json` library — that conversion step is noted as the immediate next task.

---

## Known Limitations

- **Table data**: Structured tables embedded within activity text are not parsed accurately by the current regex approach. This is acknowledged in the notebook and marked as a potential future improvement.
- **Page detection**: Automatic page detection from the source file is unreliable; manual correction is currently required if the activity set changes.
- **JSON export**: The final `json.dumps()` / `json.dump()` step is not yet implemented in this notebook.

---

## Dependencies

| Library | Usage |
|---------|-------|
| `re` (stdlib) | Regex-based line parsing |

No third-party packages are required.

---

## How to Run

1. Place `activities.txt` in the same directory as the notebook.
2. Run all cells in order (Kernel → Restart & Run All).
3. Inspect the printed output to verify activity text and page numbers.
4. Add a `json.dump(chunks, ...)` call to write the final JSON file.
