# Chunking Exercises — README

## Overview

This project extracts and structures physics word problems (examples) from a raw text file into clean, machine-readable JSON. It targets **Chapter 7** examples covering motion, speed, velocity, and acceleration — typical Class 9 NCERT-style content.

---

## Files

| File | Description |
|---|---|
| `chunking_examples.ipynb` | Jupyter notebook containing the full extraction and parsing pipeline |
| `clean_output.json` | Structured JSON output with one object per parsed example |

---

## Pipeline Overview (`chunking_examples.ipynb`)

The notebook reads a raw `.txt` file (`ch7_examples.txt`) and runs it through a multi-step parsing pipeline:

### 1. `normalize_text(text)`
Cleans up raw text before parsing:
- Replaces en-dashes (`–`) with hyphens and `×` with `*`
- Normalizes unit notation: `m s-1` → `m/s`, `km h-1` → `km/h`
- Adds spaces between digits and letters (e.g. `6s` → `6 s`)
- Collapses duplicate operators and extra whitespace (preserving newlines)

### 2. `split_examples(text)`
Splits the full text into individual examples by detecting the pattern `Example X.Y` using regex, returning a list of `(example_id, content)` tuples.

### 3. `extract_problem_and_solution(content)`
Splits each example at the `Solution:` delimiter into a **problem** string and a **solution** string.

### 4. `extract_given(problem)`
Extracts numerical values from the problem statement using regex:
- **Distances** — values with units `m` or `km`
- **Times** — values with units `s`, `h`, `min`, or `minutes`

### 5. `extract_steps(solution)`
Parses the solution line by line and retains only meaningful mathematical lines (those containing `=` and longer than 5 characters), filtering out junk-only lines.

### 6. `extract_final_answer(solution)`
Scans solution lines in reverse to find the last occurrence of a numeric value with a speed unit (`m/s` or `km/h`), returning the value and unit separately.

### 7. `detect_formulas(text)`
Detects which standard physics formulas are referenced in the text:
- `average speed = total distance / total time`
- `v = u + at`
- `s = ut + 1/2 at²`

### 8. `parse_example(example_id, content)`
Orchestrates all of the above into a single structured dictionary per example.

### 9. `process_file(file_path)`
Reads the source file, normalizes, splits, and parses all examples, returning a list of structured records.

---

## Output Format (`clean_output.json`)

Each entry in the JSON array represents one parsed example:

```json
{
  "chapter": "7",
  "example_id": "7.1",
  "problem": "An object travels 16 m in 4 s ...",
  "given": {
    "distances": ["16 m"],
    "times": ["2 s", "4 s"]
  },
  "steps": [
    "16 m + 16 m = 32 m",
    "Total time taken = 4 s + 2 s = 6 s",
    "= 32 m / 6 s = 5.33 m/s"
  ],
  "formulas_used": ["average speed = total distance / total time"],
  "final_answer": "5.33m/s",
  "units": "m/s"
}
```

### Fields

| Field | Type | Description |
|---|---|---|
| `chapter` | string | Chapter number extracted from the example ID |
| `example_id` | string | Full example identifier (e.g. `"7.3"`) |
| `problem` | string | Raw problem statement text |
| `given` | object | Extracted distances and times from the problem |
| `steps` | array | Equation lines parsed from the solution |
| `formulas_used` | array | Physics formulas detected in the example |
| `final_answer` | string | Last numeric answer with unit (e.g. `"5.33m/s"`) |
| `units` | string | Unit of the final answer (`"m/s"` or `"km/h"`) |

---

## Examples Covered

| Example | Topic |
|---|---|
| 7.1 | Average speed — two-leg journey |
| 7.2 | Average speed from odometer readings (km/h and m/s) |
| 7.3 | Average speed vs. average velocity (swimming pool) |
| 7.4 | Acceleration — speeding up and braking |
| 7.5 | Uniform acceleration — train from rest |
| 7.6 | Uniform acceleration — car between two speeds |
| 7.7 | Braking distance using equations of motion |

---

## Known Limitations

- `extract_given()` may misidentify velocity values (e.g. `6 m/s`) as distances (`6 m`) since the regex matches `m` broadly.
- `extract_final_answer()` only captures `m/s` and `km/h`; answers in `m s⁻²` (acceleration) are missed (e.g. Examples 7.4–7.6 return incorrect final answers).
- `detect_formulas()` relies on exact string matches, so paraphrased or partial formula references are not detected.
- The pipeline currently handles only Chapter 7 conventions; adapting to other chapters may require regex updates.

---

## How to Run

1. Upload your raw text file to the Colab environment (or update the path in the script).
2. Open `chunking_examples.ipynb` in Google Colab or Jupyter.
3. Run all cells. The output will be saved as `clean_output.json` in the working directory.

```python
# Entry point (bottom of notebook)
output = process_file("/content/ch7_examples.txt")
with open("clean_output.json", "w") as f:
    json.dump(output, f, indent=2)
```
