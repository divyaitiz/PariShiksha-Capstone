"""
scripts/text_to_json/images.py
================================
Reads TEXT_DIR/images.txt (produced by pdf_to_text/images.py),
sends each figure image to LLaVA via the local Ollama API,
and writes JSON_DIR/images.json.

Output schema (images.json):
{
  "chapter_id":   "iesc111",
  "source_file":  "iesc111.pdf",
  "figures": [
    {
      "figure_id":   "11.1",
      "section_id":  "11.1",
      "caption":     "Fig. 11.1: Vibrating tuning fork just touching ...",
      "description": "<LLaVA output describing the image>",
      "image_path":  "extracted/iesc111/images/fig_11_1.png",
      "page_number": 1
    },
    ...
  ]
}

Cache:
  Already-described figures are read from an existing images.json (if present)
  and skipped — re-runs are safe and fast.

Environment variables (set by run_pipeline.py):
  PDF_PATH      path to the chapter PDF (used only for source_file derivation)
  TEXT_DIR      directory containing images.txt
  JSON_DIR      directory to write images.json
  CHAPTER_NAME  e.g. "iesc111"

Requirements:
  pip install requests
  Ollama must be running: ollama serve
  LLaVA model must be pulled: ollama pull llava
"""

import os
import re
import sys
import json
import base64
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

try:
    import requests
except ImportError:
    print("ERROR: pip install requests")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
PDF_PATH     = Path(os.environ["PDF_PATH"])
TEXT_DIR     = Path(os.environ["TEXT_DIR"])
JSON_DIR     = Path(os.environ["JSON_DIR"])
CHAPTER_NAME = os.environ["CHAPTER_NAME"]

OLLAMA_HOST  = "http://localhost:11434"
OLLAMA_MODEL = "llava:7b"          # or "llava:13b" if you pulled a bigger variant

# LLaVA prompt — concise, educational, focused on what the figure shows
LLAVA_PROMPT = (
    "This is a figure from an NCERT Class 9 Science textbook. "
    "Describe what the figure shows in 2–4 clear sentences suitable for a student. "
    "Focus on labels, arrows, structures, or processes visible in the image. "
    "Do not mention that it is a textbook image; just describe the content."
)

# Retry config
MAX_RETRIES    = 3
RETRY_DELAY_S  = 5


# ── Helpers ───────────────────────────────────────────────────────────────────

def image_to_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def check_ollama_running() -> bool:
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def check_model_available(model: str) -> bool:
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if r.status_code != 200:
            return False
        models = [m["name"] for m in r.json().get("models", [])]
        # Accept "llava", "llava:latest", "llava:13b", etc.
        return any(m.split(":")[0] == model.split(":")[0] for m in models)
    except Exception:
        return False


def describe_image(image_path: Path) -> str:
    """
    Sends image to LLaVA via Ollama /api/generate and returns description text.
    Returns an error string (not raises) on failure so the pipeline continues.
    """
    if not image_path.exists():
        return f"[Image not found: {image_path}]"

    img_b64 = image_to_base64(image_path)

    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": LLAVA_PROMPT,
        "images": [img_b64],
        "stream": False,
        "options": {
            "temperature": 0.1,   # low = deterministic, factual
            "num_predict": 200,   # max tokens for description
        },
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json=payload,
                timeout=120,    # LLaVA can be slow on CPU
            )
            if r.status_code == 200:
                return r.json().get("response", "").strip()
            else:
                print(f"    Attempt {attempt}: HTTP {r.status_code} — {r.text[:100]}")
        except requests.exceptions.Timeout:
            print(f"    Attempt {attempt}: Timeout (120s)")
        except Exception as e:
            print(f"    Attempt {attempt}: {e}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_S)

    return "[Description unavailable — LLaVA request failed after retries]"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    source_file = PDF_PATH.name

    input_txt  = TEXT_DIR / "images.txt"
    output_json = JSON_DIR / "images.json"

    # Load records from images.txt
    if not input_txt.exists():
        print(f"images.txt not found at {input_txt}. Skipping.")
        return

    records = []
    with open(input_txt, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        print("images.txt is empty. Nothing to describe.")
        output_json.write_text(
            json.dumps({"chapter_id": CHAPTER_NAME, "source_file": source_file, "figures": []},
                       indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return

    # Load existing JSON to build cache (figure_id → description)
    cache: dict[str, str] = {}
    if output_json.exists():
        try:
            existing = json.loads(output_json.read_text(encoding="utf-8"))
            for fig in existing.get("figures", []):
                desc = fig.get("description", "")
                fid  = fig.get("figure_id", "")
                if fid and desc and not desc.startswith("["):
                    cache[fid] = desc
            print(f"Cache loaded: {len(cache)} already-described figures")
        except Exception as e:
            print(f"WARN: Could not load cache from {output_json}: {e}")

    # Determine which figures need describing
    to_describe = [r for r in records if r["figure_id"] not in cache]
    print(f"Figures to describe: {len(to_describe)} / {len(records)}")

    if to_describe:
        # Preflight: check Ollama is running
        if not check_ollama_running():
            print("ERROR: Ollama is not running. Start it with: ollama serve")
            sys.exit(1)

        if not check_model_available(OLLAMA_MODEL):
            print(f"ERROR: Model '{OLLAMA_MODEL}' not found in Ollama.")
            print(f"Pull it with: ollama pull {OLLAMA_MODEL}")
            sys.exit(1)

        print(f"Using Ollama model: {OLLAMA_MODEL}")

    # Process
    figures = []
    for rec in records:
        fig_id = rec["figure_id"]

        if fig_id in cache:
            description = cache[fig_id]
            print(f"  Fig {fig_id}: [cached]")
        else:
            img_path = Path(rec.get("image_path", ""))
            print(f"  Fig {fig_id}: describing via LLaVA...", end=" ", flush=True)
            t0 = time.time()
            description = describe_image(img_path)
            elapsed = time.time() - t0
            print(f"done ({elapsed:.1f}s)")

        figures.append({
            "figure_id":   fig_id,
            "section_id":  rec.get("section_id", ""),
            "caption":     rec.get("caption", ""),
            "description": description,
            "image_path":  rec.get("image_path", ""),
            "page_number": rec.get("page_number", 0),
        })

    output = {
        "chapter_id":  CHAPTER_NAME,
        "source_file": source_file,
        "figures":     figures,
    }

    JSON_DIR.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"Wrote {len(figures)} figures to {output_json}")


if __name__ == "__main__":
    main()
