# Chunking What You Have Learnt — Data Processing for Chapter 7

A Python utility that parses a plain-text "What You Have Learnt" summary section into a structured JSON format, with built-in support for header normalisation and physics formula extraction.

---

## Overview

This notebook reads a raw text file (`ch7_whathaveyoulearnt.txt`) containing a bullet-pointed summary section, normalises inconsistent formatting, detects embedded equations, and writes the structured result to `whathaveyoulearnt.json`.

---

## Files

| File | Description |
|---|---|
| `chunking_whathaveyoulearnt.ipynb` | Main notebook containing all parsing logic |
| `ch7_whathaveyoulearnt.txt` | Input — raw text file of the Chapter 7 summary section |
| `whathaveyoulearnt.json` | Output — structured JSON of parsed points |

---

## Functions

### `normalize_text(text: str) → str`
Cleans up raw input text before parsing.

- Repairs broken header lines where `"What you have learnt"` is split across multiple lines (e.g. `What \n you have \n learnt`)
- Strips carriage returns (`\r`)
- Collapses multiple consecutive newlines into a single newline

### `split_bullets(text: str) → tuple`
Divides the normalised text into a header and individual bullet points.

- Splits on the bullet symbol `•`
- Returns `(header: str, bullets: list[str])`
- The first segment (before the first `•`) is treated as the section header

### `extract_formulas(text: str) → list[str] | None`
Identifies physics-like equations within a string using a regex heuristic.

- Matches patterns of the form `variable = expression` (e.g. `v = u + at`, `s = ut + ½ at2`)
- Returns a list of matched formula strings, or `None` if none are found

### `parse_points(bullets: list[str]) → list[dict]`
Iterates over extracted bullet points and builds structured point objects.

- Skips empty bullets
- Calls `extract_formulas` on each bullet
- Returns a list of dicts with a `"text"` key, and an optional `"formulas"` key when equations are detected

### `parse_file(file_path: str) → dict`
Orchestrates the full parsing pipeline.

1. Reads the input text file
2. Calls `normalize_text` to clean the raw content
3. Calls `split_bullets` to segment header and points
4. Calls `parse_points` to structure each bullet
5. Returns a dict with `"section"` and `"points"` keys

---

## Output Format

The generated `whathaveyoulearnt.json` follows this structure:

```json
{
  "section": "What you have learnt",
  "points": [
    {
      "text": "Bullet point text containing v = u + at and s = ut + ½ at2",
      "formulas": ["v = u + at", "s = ut + ½ at2"]
    },
    {
      "text": "Bullet point text with no formula"
    }
  ]
}
```

- `section` — the normalised header extracted from the top of the file
- `points` — array of parsed bullet points
  - `text` — the full bullet point text
  - `formulas` — *(optional)* list of detected equations; omitted when none are found

---

## Usage

1. Place your summary text file in the working directory as `ch7_whathaveyoulearnt.txt`.
2. Run all cells in `chunking_whathaveyoulearnt.ipynb`, or execute the script directly:

```bash
python chunking_whathaveyoulearnt.py
```

3. The parsed output will be saved to `whathaveyoulearnt.json` and a summary printed:

```
Parsed 7 points → whathaveyoulearnt.json
```

---

## Requirements

- Python 3.x
- Standard library only (`re`, `json`) — no additional dependencies needed
