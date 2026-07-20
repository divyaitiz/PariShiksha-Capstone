"""
eval/eval_pipeline.py
======================
Streamlit-free version of the RAG pipeline, for use in eval scripts and CI.
Keep constants in sync with rag_chain.py.

Run from the pipeline root (parent of eval/), or add the project root to
PYTHONPATH, so that ./chroma_db resolves correctly.
"""
import os
from pathlib import Path
from functools import lru_cache
import torch
from dotenv import load_dotenv
load_dotenv()

# ── Config (kept in sync with rag_chain.py) ────────────────────────────────
CHROMA_DIR      = Path("./chroma_db")
COLLECTION_NAME = "ncert_science"
EMBED_MODEL     = "BAAI/bge-large-en-v1.5"
RERANK_MODEL    = "BAAI/bge-reranker-large"
EMBED_DEVICE    = "cuda" if torch.cuda.is_available() else "cpu"
RERANK_DEVICE   = "cpu"
QUERY_PREFIX    = "Represent this sentence for searching relevant passages: "
TOP_K_RETRIEVE  = 10
TOP_K_RERANK    = 3
GROQ_MODEL      = "llama-3.3-70b-versatile"
MAX_TOKENS      = 1024
TEMPERATURE     = 0.2

SYSTEM_PROMPT = """You are a helpful NCERT Science tutor for Class 9 students.
Answer the student's question using ONLY the context provided below.
- Be clear and concise.
- If the context contains relevant formulas or steps, include them.
- If the question is a greeting, small talk, or not a real question, respond briefly and naturally — do NOT add a Sources line.
- If the answer is not found in the context, say: "This topic is not covered in the retrieved sections. Please refer to the relevant chapter directly." — do NOT add a Sources line.
- Only when you actually use information from the context: at the very end, on a new line, add exactly one line starting with "**Sources:**" listing the distinct chapter/section references used, comma-separated.
- Do NOT cite chapters/sections inline after every sentence."""


# ── Cached resource loaders (plain functools, no Streamlit) ────────────────

@lru_cache(maxsize=1)
def get_embedder():
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(EMBED_MODEL, device=EMBED_DEVICE)
    m.max_seq_length = 512
    return m


@lru_cache(maxsize=1)
def get_reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(RERANK_MODEL, device=RERANK_DEVICE, max_length=512)


@lru_cache(maxsize=1)
def get_collection():
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(COLLECTION_NAME)


@lru_cache(maxsize=1)
def get_groq():
    from groq import Groq
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    return Groq(api_key=api_key)


# ── Retrieval ────────────────────────────────────────────────────────────────

def retrieve(query: str) -> list[dict]:
    embedder, collection = get_embedder(), get_collection()
    q_vec = embedder.encode(
        QUERY_PREFIX + query,
        normalize_embeddings=True,
        device=EMBED_DEVICE,
    ).tolist()
    results = collection.query(
        query_embeddings=[q_vec],
        n_results=TOP_K_RETRIEVE,
        include=["documents", "metadatas", "distances"],
    )
    return [
        {"content": doc, "metadata": meta, "score": 1 - dist}
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        )
    ]


# ── Re-ranking ───────────────────────────────────────────────────────────────

def rerank(query: str, candidates: list[dict]) -> list[dict]:
    reranker = get_reranker()
    pairs = [[query, c["content"]] for c in candidates]
    scores = reranker.predict(pairs, show_progress_bar=False)
    for c, s in zip(candidates, scores):
        c["rerank_score"] = float(s)
    return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:TOP_K_RERANK]


# ── Prompt builder ─────────────────────────────────────────────────────────

def build_context_block(chunks: list[dict]) -> str:
    blocks = []
    for i, c in enumerate(chunks, 1):
        m = c["metadata"]
        header = (
            f"[Source {i}] "
            f"Chapter {m.get('chapter_number','?')} — {m.get('chapter_title','')}"
            f" | Section {m.get('section_id','?')}: {m.get('section_title','')}"
        )
        blocks.append(f"{header}\n{c['content']}")
    return "\n\n---\n\n".join(blocks)


# ── LLM call ─────────────────────────────────────────────────────────────────

def generate_answer(query: str, context: str) -> str:
    groq = get_groq()
    response = groq.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )
    return response.choices[0].message.content.strip()


# ── Full pipeline, single entry point for eval scripts ──────────────────────

def run_query(query: str) -> dict:
    """Runs one question through the full pipeline, returns everything an
    eval script needs: answer, retrieved contexts, and section references."""
    candidates = retrieve(query)
    top_chunks = rerank(query, candidates)
    context = build_context_block(top_chunks)
    answer = generate_answer(query, context)
    return {
        "question": query,
        "answer": answer,
        "contexts": [c["content"] for c in top_chunks],
        "retrieved_sections": [
            f"Ch.{c['metadata'].get('chapter_number','?')} §{c['metadata'].get('section_id','?')}"
            for c in top_chunks
        ],
    }
