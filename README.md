# PariShiksha — NCERT Class 9 Science RAG QA

Futurense AI Clinic Capstone · ML Engineering track (solo)

## Current codebase (this repo root)
- `rag_chain.py` — Streamlit app, RAG pipeline with multi-turn conversational memory
- `eval/` — W1 evaluation harness (Ragas scorecard, DeepEval regression gate)
- `run_pipeline.py`, `json_to_chunks.py`, `chunks_to_embeddings.py` — data pipeline

## Project history
- `legacy/ncert-class9-science-llm/` — original PDF extraction pipeline (7 section types)
- `legacy/v1-parishiksha/` — V1: full RAG pipeline, Streamlit UI
- `legacy/v2-parishiksha/` — V2: multimodal extension (image/figure retrieval)

Note: this repo excludes Azure deployment config (no student credits remaining).
See `legacy/v1-parishiksha` for the original Docker/ACI/CI-CD setup for reference.
