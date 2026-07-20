"""
run_chunking.py — Orchestrator for the full chunking pipeline.

Loops through all chapter directories in extracted/,
runs cleaner + chunker for each available content type,
saves output to chunks/ and flagged items to flagged/.

Usage:
    python run_chunking.py

    # Process a single chapter only:
    python run_chunking.py --chapter iesc101

    # Dry run (no files written):
    python run_chunking.py --dry-run
"""

import os
import sys
import json
import argparse
from collections import defaultdict

# ── make sure sibling modules are importable ──────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from utils import get_available_jsons, load_json, save_json
from cleaner import (
    clean_informational_text,
    clean_examples,
    clean_exercises,
    clean_activities,
    clean_in_chapter_questions,
    clean_what_you_have_learnt,
    clean_think_and_act,
)
from chunker import CHUNKER_MAP


# ─────────────────────────────────────────────
# CONFIGURATION — adjust paths to match your project
# ─────────────────────────────────────────────

# Root of your project (one level above scripts/chunking/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

EXTRACTED_DIR = os.path.join(PROJECT_ROOT, "extracted")   # input
CHUNKS_DIR    = os.path.join(PROJECT_ROOT, "chunks")       # output chunks
FLAGGED_DIR   = os.path.join(PROJECT_ROOT, "flagged")      # output flagged items


# ─────────────────────────────────────────────
# CLEANER DISPATCHER
# maps content_type → its cleaner function
# ─────────────────────────────────────────────

CLEANER_MAP = {
    "informational_text":   clean_informational_text,
    "examples":             clean_examples,
    "exercises":            clean_exercises,
    "activities":           clean_activities,
    "in_chapter_questions": clean_in_chapter_questions,
    "what_you_have_learnt": clean_what_you_have_learnt,
    "think_and_act":        clean_think_and_act,
}


# ─────────────────────────────────────────────
# PROCESS A SINGLE CHAPTER
# ─────────────────────────────────────────────

def process_chapter(chapter_id: str, chapter_path: str, dry_run: bool = False) -> dict:
    """
    Runs the full clean → chunk pipeline for one chapter.

    Args:
        chapter_id:   e.g. "iesc101"
        chapter_path: full path to the chapter directory
        dry_run:      if True, skip writing output files

    Returns:
        summary dict with chunk counts per content type
    """
    print(f"\n{'='*55}")
    print(f"  Chapter: {chapter_id}")
    print(f"{'='*55}")

    available = get_available_jsons(chapter_path)

    if not available:
        print(f"  [SKIP] No JSON files found for {chapter_id}")
        return {}

    print(f"  Found {len(available)} content type(s): {', '.join(available.keys())}")

    all_chunks = []
    per_type_chunks = {}    # content_type → its own chunk list
    summary = {}

    for content_type, filepath in available.items():
        print(f"\n  ── {content_type}")

        # 1. Load raw JSON
        raw_data = load_json(filepath)
        if raw_data is None:
            print(f"     [SKIP] Could not load {filepath}")
            continue

        # 2. Clean
        cleaner_fn = CLEANER_MAP.get(content_type)
        if not cleaner_fn:
            print(f"     [SKIP] No cleaner defined for {content_type}")
            continue

        try:
            cleaned_data = cleaner_fn(raw_data, chapter_id, FLAGGED_DIR)
        except Exception as e:
            print(f"     [ERROR] Cleaner failed: {e}")
            continue

        # 3. Chunk
        chunker_fn = CHUNKER_MAP.get(content_type)
        if not chunker_fn:
            print(f"     [SKIP] No chunker defined for {content_type}")
            continue

        try:
            chunks = chunker_fn(cleaned_data, chapter_id)
        except Exception as e:
            print(f"     [ERROR] Chunker failed: {e}")
            continue

        count = len(chunks)
        summary[content_type] = count
        all_chunks.extend(chunks)
        per_type_chunks[content_type] = chunks    # keep separate for per-file saving
        print(f"     → {count} chunk(s) produced")

    # 4. Save separate chunk file per content type inside chapter folder
    total = len(all_chunks)
    print(f"\n  Total chunks for {chapter_id}: {total}")

    if not dry_run and all_chunks:
        chapter_chunks_dir = os.path.join(CHUNKS_DIR, chapter_id)
        os.makedirs(chapter_chunks_dir, exist_ok=True)

        # Save per-content-type files
        for content_type, chunk_list in per_type_chunks.items():
            output_path = os.path.join(chapter_chunks_dir, f"{content_type}_chunks.json")
            save_json(chunk_list, output_path)
            print(f"  Saved → chunks/{chapter_id}/{content_type}_chunks.json")

    elif dry_run:
        print(f"  [DRY RUN] Would save to chunks/{chapter_id}/<content_type>_chunks.json")

    return summary


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run the chunking pipeline.")
    parser.add_argument(
        "--chapter",
        type=str,
        default=None,
        help="Process a single chapter only (e.g. --chapter iesc101)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without writing any output files"
    )
    args = parser.parse_args()

    if not os.path.isdir(EXTRACTED_DIR):
        print(f"[ERROR] extracted/ directory not found at: {EXTRACTED_DIR}")
        print("  Adjust PROJECT_ROOT in run_chunking.py to match your project structure.")
        sys.exit(1)

    # Discover chapter directories
    if args.chapter:
        chapter_dirs = [args.chapter]
    else:
        chapter_dirs = sorted([
            d for d in os.listdir(EXTRACTED_DIR)
            if os.path.isdir(os.path.join(EXTRACTED_DIR, d))
        ])

    print(f"\nChunking pipeline starting")
    print(f"  Extracted dir : {EXTRACTED_DIR}")
    print(f"  Chunks dir    : {CHUNKS_DIR}")
    print(f"  Flagged dir   : {FLAGGED_DIR}")
    print(f"  Chapters found: {len(chapter_dirs)}")
    if args.dry_run:
        print(f"  Mode          : DRY RUN (no files written)")

    # Create output directories
    if not args.dry_run:
        os.makedirs(CHUNKS_DIR, exist_ok=True)
        os.makedirs(FLAGGED_DIR, exist_ok=True)

    # Process each chapter
    global_summary = defaultdict(int)
    global_total = 0

    for chapter_id in chapter_dirs:
        chapter_path = os.path.join(EXTRACTED_DIR, chapter_id)
        if not os.path.isdir(chapter_path):
            print(f"\n[WARN] Not a directory, skipping: {chapter_path}")
            continue

        chapter_summary = process_chapter(chapter_id, chapter_path, dry_run=args.dry_run)

        for content_type, count in chapter_summary.items():
            global_summary[content_type] += count
            global_total += count

    # Final summary
    print(f"\n{'='*55}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'='*55}")
    print(f"  Total chunks across all chapters: {global_total}")
    print(f"\n  Breakdown by content type:")
    for content_type, count in sorted(global_summary.items()):
        print(f"    {content_type:<28} {count:>5} chunks")

    if not args.dry_run:
        print(f"\n  Output saved to  : {CHUNKS_DIR}/")
        print(f"  Flagged items at : {FLAGGED_DIR}/")

    print()


if __name__ == "__main__":
    main()