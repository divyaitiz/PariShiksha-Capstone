"""
run_pipeline.py
───────────────
Simple pipeline orchestrator — exercises section only.
Use this to verify the full flow before adding more section types.

Flow:
    pdfs/<book>.pdf
        ↓  [pdf_to_text/exercises.py]   ← your Set 1 script (plug in yours)
    extracted/<book>/text/exercises.txt
        ↓  quality check
    extracted/<book>/json/exercises.json
        ↓
    Done ✅  (LangChain vector store step comes later)
"""

from asyncio.log import logger
import sys
import os
import re
import json
import shutil
import subprocess
import logging
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

# ── Config ────────────────────────────────────────────────────
PDF_DIR      = Path("./pdfs")
EXTRACT_DIR  = Path("./extracted")
FLAGGED_DIR  = Path("./flagged")
LOGS_DIR     = Path("./logs")
SCRIPTS_DIR  = Path("./scripts")
TRACKER_FILE = Path("./processed.json")

# Only exercises for now — add more section types here later
SECTION_TYPES = ["exercises",
                 "think_and_act",
                 "what_you_have_learnt",
                 "in_chapter_questions",
                 "activities",
                 "examples"]

# Quality check thresholds
MIN_CHARS          = 100
JUNK_CHAR_THRESHOLD = 0.1


# ── Quality Check ─────────────────────────────────────────────
def quality_check(txt_file: Path) -> tuple[bool, str]:
    """Returns (passed, reason_if_failed)."""
    text = txt_file.read_text(encoding="utf-8", errors="ignore")

    if not text.strip():
        return False, "File is empty — nothing was extracted"

    if len(text.strip()) < MIN_CHARS:
        return False, f"Too short ({len(text.strip())} chars) — likely missed content"

    junk = len(re.findall(r"[^\x00-\x7F]", text))
    if junk / len(text) > JUNK_CHAR_THRESHOLD:
        return False, f"High junk character ratio ({junk/len(text):.0%}) — encoding issue"

    if re.search(r"(.)\1{10,}", text):
        return False, "Repeated character pattern — possible OCR failure"

    return True, ""


# ── Flag a Faulty Text File ───────────────────────────────────
def flag_file(txt_file: Path, pdf_name: str, reason: str, logger):
    flag_dir = FLAGGED_DIR / pdf_name
    flag_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(txt_file, flag_dir / txt_file.name)
    notes = flag_dir / f"{txt_file.stem}_issues.txt"
    notes.write_text(
        f"File   : {txt_file}\n"
        f"Flagged: {datetime.now()}\n"
        f"Reason : {reason}\n"
    )
    logger.warning(f"FLAGGED {txt_file.name}: {reason}")


# ── Run a Script ──────────────────────────────────────────────
def run_script(script_path: Path, env: dict, logger) -> bool:
    if not script_path.exists():
        logger.warning(f"⚠️  Script not found, skipping: {script_path}")
        print(f"    ⚠️  Script not found: {script_path.name}")
        return False

    result = subprocess.run(
        [sys.executable, str(script_path)],
        env={**os.environ, **env},
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        logger.info(f"✅ {script_path.name}: {result.stdout.strip()}")
        print(f"    ✅ {result.stdout.strip()}")
    else:
        logger.error(f"FAILED {script_path.name}:\n{result.stderr}")
        print(f"    ❌ {script_path.name} failed — see logs")

    return result.returncode == 0


# ── Process One PDF ───────────────────────────────────────────
def process_pdf(pdf_path: Path):
    pdf_name   = pdf_path.stem
    text_dir   = EXTRACT_DIR / pdf_name / "text"
    json_dir   = EXTRACT_DIR / pdf_name / "json"

    text_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)

    # Per-PDF log file
    # REPLACE WITH:
    log_file = LOGS_DIR / f"{pdf_name}.log"
    logger   = logging.getLogger(pdf_name)
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))
    logger.addHandler(fh)

    print(f"\n{'─'*50}")
    print(f"📄 Processing: {pdf_path.name}")
    print(f"{'─'*50}")
    logger.info(f"=== Processing {pdf_path.name} ===")

    env = {
        "PDF_PATH":     str(pdf_path),
        "TEXT_DIR":     str(text_dir),
        "JSON_DIR":     str(json_dir),
        "CHAPTER_NAME": pdf_name,       # used as chapter label in JSON
    }

    flagged   = []
    completed = []

    for section in SECTION_TYPES:
        print(f"\n  [{section.upper()}]")

        # ── Step 1: PDF → Text ──────────────────────────
        print(f"  Step 1 › PDF → Text")
        script1 = SCRIPTS_DIR / "pdf_to_text" / f"{section}.py"
        run_script(script1, env, logger)

        # ── Quality Check ───────────────────────────────
        txt_file = text_dir / f"{section}.txt"

        # REPLACE WITH:
        if not txt_file.exists():
            # script exited cleanly with SKIP — not an error
            print(f"    -- {section}: not present in this chapter, skipping")
            logger.info(f"{section}: not present, skipped")
            continue

        passed, reason = quality_check(txt_file)

        if not passed:
            flag_file(txt_file, pdf_name, reason, logger)
            print(f"    ⚠️  Quality check FAILED: {reason}")
            print(f"    📁 Flagged → ./flagged/{pdf_name}/{section}.txt")
            flagged.append(section)
            continue

        print(f"    ✅ Quality check passed")

        # ── Step 2: Text → JSON ─────────────────────────
        print(f"  Step 2 › Text → JSON")
        script2 = SCRIPTS_DIR / "text_to_json" / f"{section}.py"
        success = run_script(script2, env, logger)

        if success:
            completed.append(section)
        else:
            flagged.append(section)

    # ── Summary ─────────────────────────────────────────
    print(f"\n  {'─'*40}")
    print(f"  📊 Summary: {pdf_path.name}")
    print(f"     ✅ Completed : {len(completed)}/{len(SECTION_TYPES)} sections → {json_dir}")
    if flagged:
        print(f"     ⚠️  Flagged   : {', '.join(flagged)}")
        print(f"     📁 Review at : ./flagged/{pdf_name}/")
    print(f"     📝 Log at    : {log_file}")

    logger.info(f"Done. Completed: {completed}. Flagged: {flagged}")


# ── Tracker ───────────────────────────────────────────────────
def load_tracker():
    if TRACKER_FILE.exists():
        return json.loads(TRACKER_FILE.read_text())
    return {}

def save_tracker(tracker):
    TRACKER_FILE.write_text(json.dumps(tracker, indent=2))


# ── Main ──────────────────────────────────────────────────────
def main():
    for d in [PDF_DIR, EXTRACT_DIR, FLAGGED_DIR, LOGS_DIR]:
        d.mkdir(exist_ok=True)

    tracker  = load_tracker()
    all_pdfs = list(PDF_DIR.glob("*.pdf"))
    new_pdfs = [p for p in all_pdfs if p.name not in tracker]

    print(f"\n🔍 Found {len(all_pdfs)} PDF(s) in ./pdfs/")
    print(f"   {len(new_pdfs)} new | {len(all_pdfs) - len(new_pdfs)} already processed")

    if not new_pdfs:
        print("\nℹ️  Nothing new to process. Drop a PDF into ./pdfs/ and re-run.")
        return

    for pdf_path in new_pdfs:
        process_pdf(pdf_path)
        tracker[pdf_path.name] = {"processed_at": str(datetime.now()), "status": "done"}
        save_tracker(tracker)

    print(f"\n{'═'*50}")
    print(f"🎉 Pipeline complete!")
    print(f"{'═'*50}\n")


if __name__ == "__main__":
    main()
