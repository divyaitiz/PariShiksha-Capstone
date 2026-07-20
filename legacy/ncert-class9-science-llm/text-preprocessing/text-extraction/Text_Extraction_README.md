# PDF Text Extraction Pipeline

A Python pipeline for extracting and cleaning text from digital PDFs — specifically designed to handle layout distortion issues common in structured documents like textbooks.

---

## Overview

This script uses `pdfplumber` to extract text from digital PDFs and applies a series of post-processing functions to fix common extraction artifacts such as repeated characters, spaced-out letters, and broken headings.

> **Note:** This pipeline works only with **digital (selectable-text) PDFs**. For scanned PDFs, OCR tools (e.g., Tesseract) are required instead.

---

## Requirements

```bash
pip install pdfplumber
```

---

## Pipeline Steps

### Step 1 — Verify Your PDF Type
Before running, confirm your PDF has selectable text (i.e., you can click and drag to highlight text). If so, `pdfplumber` will work. If the PDF is scanned/image-based, OCR is needed.

### Step 2 — Extract Text from a Single Page (Test)
Test extraction on the first page to inspect raw output before processing the entire document.

```python
import pdfplumber

with pdfplumber.open("your_file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
print(text)
```

### Step 3 — Tune Extraction with Tolerances
Apply `x_tolerance` and `y_tolerance` to improve character grouping:

```python
text = page.extract_text(x_tolerance=2, y_tolerance=2)
```

| Parameter     | Effect                                      |
|---------------|---------------------------------------------|
| `x_tolerance` | Controls horizontal merging of characters   |
| `y_tolerance` | Controls vertical line grouping             |

### Step 4 — Fix Repeated Characters
Handles artifacts like `MMMMM` or `OOOOOTTTTTIIIIIOOOOONNNNN` caused by stylized PDF fonts.

```python
import re

def fix_repeated_chars(text):
    return re.sub(r'(.)\1{2,}', r'\1', text)
```

### Step 5 — Fix Spaced Words & Broken Headings
Handles fragmentation like `"C hapter"` or `"M\nOTION"` caused by character-by-character PDF storage.

```python
def fix_spaced_words(text):
    return re.sub(r'\b(?:[A-Za-z]\s){2,}[A-Za-z]\b',
                  lambda m: m.group(0).replace(" ", ""),
                  text)

def fix_heading_lines(text):
    # Reconstructs broken chapter headings and ALL CAPS words split across lines
    ...
```

### Step 6 — Full Pipeline
Combines all steps into a single function that processes all pages:

```python
cleaned_text = extract_clean_text("your_file.pdf")
print(cleaned_text)
```

---

## Usage

```python
from text_extraction import extract_clean_text

cleaned_text = extract_clean_text("/path/to/your/file.pdf")
print(cleaned_text)
```

---

## Known Limitations

The current pipeline does not fully handle the following cases:

| Issue | Description |
|---|---|
| Activity sections | Not distinctly separated from main content |
| 'Think and Act' sections | Lack clear demarcation |
| Image data | No handling for embedded images or figures |
| Irrelevant text | Footer text like `"Reprint 2025-26"` is not filtered |
| Mixed content | Questions are mixed in with informational text |
| Tables | Table data is not structured or extracted properly |
| Formulas | Mathematical formulas lack consistent representation |

---

## File Structure

```
text_extraction.py     # Main extraction script with all helper functions
README.md              # This file
```

---

## Function Reference

| Function | Purpose |
|---|---|
| `fix_repeated_chars(text)` | Removes repeated characters caused by stylized fonts |
| `fix_spaced_words(text)` | Joins single characters separated by spaces |
| `fix_heading_lines(text)` | Reconstructs broken chapter headings and ALL CAPS words |
| `extract_clean_text(pdf_path)` | Full pipeline — extracts and cleans all pages |
