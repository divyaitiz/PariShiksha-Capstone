#  PDF Text Cleaning Pipeline

A step-by-step text preprocessing pipeline built to extract, clean, and structure text from multi-column NCERT Science PDFs for use in downstream NLP tasks like retrieval-augmented generation (RAG), question answering, and LLM-based processing.

---

## Overview

Standard PDF extraction tools often fail on multi-column academic textbooks — they mix columns, break headings, and retain noisy elements like figure captions, activity blocks, and year markers. This pipeline addresses all of these issues systematically.

The source document used is an NCERT Science chapter (Chapter 7: Motion) in a two-column PDF format.

---

## Work Completed

### Step 1 — Column-wise PDF Text Extraction
Used `pdfplumber` to split each page into left and right column regions and extract text in the correct reading order. This prevents the common issue of sentences being jumbled across columns during default extraction.

### Step 2 — Fix Broken Headings
PDF extraction often splits headings across multiple lines (e.g., `U - NIFORM` or section numbers separated from their titles). A custom function merges these broken headings back into clean, readable single lines.

### Step 3 — Text Cleaning Pipeline
Applied a series of regex-based fixes:
- Removed repeated characters (e.g., `MMMOTION` → `MOTION`)
- Joined spaced-out letters (e.g., `M O T I O N` → `MOTION`)
- Fixed broken chapter headings
- Repositioned displaced chapter titles (e.g., ensuring "MOTION" follows "Chapter 7" correctly)

### Step 4 — Remove Figure References
Stripped all figure captions and inline references such as `Fig. 7.1`, `Figure 7.2`, and `(Fig. 7.3)` from the text. Also cleaned up leftover broken phrases like "shown in ." that remain after figure removal.

### Step 5 — Separate Non-Contextual Sections
Instead of deleting non-essential content, these sections were **extracted and saved separately** to avoid data loss:
- `Activity` blocks → `activities.txt`
- `Think and Act` blocks → `thinkandact.txt`

### Step 6 — Extract Questions Section
Detected and removed all `Questions` blocks from the main text, saving them to `Questions.txt`. These can be reused later for building evaluation or QA datasets.

### Step 7 — Extract Examples Section
Identified `Example` blocks (e.g., `Example 7.1`, `Example 7.2`) and saved them to `Examples.txt`. The main text now contains only core conceptual content, free of worked solutions and step-by-step illustrations.

### Step 8 — Clean Activities File
Removed the "What you have learnt" section from `activities.txt` and saved the result to `activities_cleaned.txt`.

---

## 📂 Output Files

| File | Contents |
|---|---|
| `final_cleaned_text.txt` | Core conceptual text — clean and ready for chunking |
| `activities.txt` / `activities_cleaned.txt` | Activity blocks |
| `thinkandact.txt` | Think and Act sections |
| `Questions.txt` | In-chapter questions |
| `Examples.txt` | Worked examples and solutions |

---

## 🔲 Remaining Work

- [ ] Fully handle the **"What have you learnt"** section — extract and save it separately from the main text
- [ ] Extract **Chapter End Questions** (end-of-chapter exercises, distinct from in-chapter questions)
- [ ] **Separate formulae** from the cleaned text — detect and isolate mathematical equations and expressions into a dedicated file

---

## 🛠️ Dependencies

```bash
pip install pdfplumber
```

Python standard libraries used: `re`

---

## 🚀 How to Use

1. Place your NCERT PDF in the working directory.
2. Update `pdf_path` in Step 1 to point to your file.
3. Run the notebook cells sequentially — each step builds on the previous output.
4. Final clean text will be saved to `final_cleaned_text.txt`.
