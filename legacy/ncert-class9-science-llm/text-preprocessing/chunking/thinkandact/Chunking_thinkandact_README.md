# Chunking_thinkandact — README

## Overview

This project extracts and structures **"Think and Act"** sections from a plain-text source file into a clean, metadata-enriched JSON format. It is designed for textbook content processing pipelines where pedagogical prompts (Think and Act boxes) need to be isolated, labelled with chapter and page metadata, and stored for downstream use (e.g., RAG systems, study tools, or content indexing).

---

## Files

| File | Description |
|------|-------------|
| `Chunking_thinkandact.ipynb` | Jupyter notebook containing the full parsing and JSON-generation pipeline |
| `chapter7_72_thinkandact_output.json` | Sample output JSON produced by the notebook for Chapter 7, Page 72 |

---

## How It Works

### Input

The script reads from a plain-text file named **`thinkandact.txt`**. This file is expected to contain one or more "Think and Act" blocks, each prefixed with the marker:

```
thinkandact: <content starts here>
```

Subsequent lines (without the prefix) are treated as continuation of the current block, until the next `thinkandact:` marker or end of file.

### Processing Steps

1. **`parse_file(filepath)`** — Reads the text file line by line, detects `thinkandact:` markers, and aggregates each block's lines into a single string entry.
2. **`build_json(entries)`** — Wraps each entry in a structured dictionary with manually configured metadata (`chapter`, `pg no`), and strips any leading "Think and Act" label from the content text.
3. **Main block** — Calls both functions in sequence and writes the result to a `.json` output file.

### Output

A JSON array where each element represents one Think and Act block:

```json
[
  {
    "chapter": "7",
    "pg no": "72",
    "thinkandact": "We sometimes are endangered by the motion of objects around us..."
  }
]
```

---

## Configuration

At the top of the notebook's main code cell, three variables must be **manually set** before each run:

```python
INPUT_FILE = "thinkandact.txt"   # Path to your input text file
OUTPUT_FILE = "chapter7_72_thinkandact_output.json"  # Desired output filename

CHAPTER = "7"    # Chapter number (string)
PAGE_NO = "72"   # Page number (string)
```

Update `CHAPTER`, `PAGE_NO`, and `OUTPUT_FILE` to match the section of the textbook being processed.

---

## Sample Output

`chapter7_72_thinkandact_output.json` contains the processed output for Chapter 7, Page 72:

> *"We sometimes are endangered by the motion of objects around us, especially if that motion is erratic and uncontrolled as observed in a flooded river, a hurricane or a tsunami. On the other hand, controlled motion can be a service to human beings such as in the generation of hydro-electric power. Do you feel the necessity to study the erratic motion of some objects and learn to control them?"*

---

## Requirements

- Python 3.x
- Standard library modules only: `json`, `re`
- A `thinkandact.txt` input file formatted with `thinkandact:` prefix markers

---

## Usage

1. Place your `thinkandact.txt` file in the same directory as the notebook (or update `INPUT_FILE` with the correct path).
2. Set `CHAPTER`, `PAGE_NO`, and `OUTPUT_FILE` in the config section.
3. Run all cells in `Chunking_thinkandact.ipynb`.
4. The output JSON will be saved to the path defined in `OUTPUT_FILE`.

```
Processed 1 entries → chapter7_72_thinkandact_output.json
```

---

## Notes

- The `thinkandact:` prefix is **case-insensitive** during detection.
- The phrase "Think and Act" at the start of extracted content is automatically stripped to avoid redundancy in the stored text.
- Each run processes one chapter/page pair. For bulk processing across multiple chapters, loop over multiple input files and update the config variables accordingly.
