"""
test_exercises.py
──────────────────
Quick test to verify your text → JSON script works correctly.

Since you already have a verified exercises.txt, this test:
1. Runs scripts/text_to_json/exercises.py directly
2. Compares output against your known-good JSON
3. Reports any differences

Run with: python test_exercises.py
"""

import sys
import json
import subprocess
import os
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ── Paths ─────────────────────────────────────────────────────
TEST_DIR       = Path("./test_run")
TEXT_DIR       = TEST_DIR / "text"
JSON_DIR       = TEST_DIR / "json"
REFERENCE_JSON = Path("./reference/chapter7_exercises_output.json")

TEXT_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT = Path("./scripts/text_to_json/exercises.py")

# ── Step 1: Check reference JSON exists ───────────────────────
if not REFERENCE_JSON.exists():
    print(f"❌ Reference JSON not found at: {REFERENCE_JSON}")
    print("   Copy your chapter7_exercises_output.json to ./reference/")
    exit(1)

# ── Step 2: Check exercises.txt exists ────────────────────────
txt_file = TEXT_DIR / "exercises.txt"
if not txt_file.exists():
    print(f"❌ Test input not found: {txt_file}")
    print("   Copy your ch7_end_exercises.txt to ./test_run/text/exercises.txt")
    exit(1)

# ── Step 3: Run the script ────────────────────────────────────
print("▶ Running scripts/text_to_json/exercises.py ...")
result = subprocess.run(
    ["python", str(SCRIPT)],
    env={
        **os.environ,
        "TEXT_DIR":     str(TEXT_DIR),
        "JSON_DIR":     str(JSON_DIR),
        "CHAPTER_NAME": "Chapter 7",
    },
    capture_output=True,
    text=True
)

if result.returncode != 0:
    print(f"❌ Script failed:\n{result.stderr}")
    exit(1)

print(f"✅ Script ran: {result.stdout.strip()}")

# ── Step 4: Compare output vs reference ───────────────────────
output_json = JSON_DIR / "exercises.json"
if not output_json.exists():
    print("❌ Output JSON not created")
    exit(1)

with open(output_json)    as f: output    = json.load(f)
with open(REFERENCE_JSON) as f: reference = json.load(f)

output_exercises    = output.get("exercises", [])
reference_exercises = reference.get("exercises", [])

print(f"\n{'─'*45}")
print(f"📊 Comparison Results")
print(f"{'─'*45}")
print(f"  Reference : {len(reference_exercises)} exercises")
print(f"  Output    : {len(output_exercises)} exercises")

if len(output_exercises) != len(reference_exercises):
    print(f"\n  ⚠️  Count mismatch — check extraction logic")

mismatches = 0
for ref, out in zip(reference_exercises, output_exercises):
    issues = []
    if ref["id"] != out["id"]:
        issues.append(f"id: expected {ref['id']}, got {out['id']}")
    if ref.get("subparts") and not out.get("subparts"):
        issues.append("missing subparts")
    if not ref.get("subparts") and out.get("subparts"):
        issues.append("unexpected subparts")

    if issues:
        mismatches += 1
        print(f"\n  ❌ Q{ref['id']}: {', '.join(issues)}")
    else:
        print(f"  ✅ Q{ref['id']}: OK")

print(f"\n{'─'*45}")
if mismatches == 0:
    print(f"🎉 All {len(reference_exercises)} exercises match reference!")
else:
    print(f"⚠️  {mismatches} mismatch(es) found — review flagged questions")
print(f"{'─'*45}\n")
print(f"Output saved to: {output_json}")
