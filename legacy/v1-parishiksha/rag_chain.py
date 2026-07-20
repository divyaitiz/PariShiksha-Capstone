"""
rag_chain.py
============
Streamlit QA bot for NCERT Science (Class 9).

Pipeline per query:
  1. Embed question with BGE-large (GPU, query prefix)
  2. ChromaDB → top-10 candidate chunks (cosine similarity)
  3. BGE-reranker-large → re-score top-10, keep top-3 (CPU)
  4. Build prompt with retrieved context
  5. Groq LLM (llama-3.3-70b-versatile) → answer
  6. Show answer + source citations in Streamlit

Requirements:
    pip install streamlit chromadb sentence-transformers \
                torch groq

Set your Groq API key:
    Windows PowerShell:
        $env:GROQ_API_KEY = "gsk_..."
    Or create a .env file in the project root:
        GROQ_API_KEY=gsk_...

Run:
    streamlit run rag_chain.py
"""

import os
import sys
import time
import torch
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
# ── Config ────────────────────────────────────────────────────────────────────
CHROMA_DIR       = Path("./chroma_db")
COLLECTION_NAME  = "ncert_science"

EMBED_MODEL      = "BAAI/bge-large-en-v1.5"
RERANK_MODEL     = "BAAI/bge-reranker-large"
EMBED_DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"
RERANK_DEVICE    = "cpu"   # keeps GPU free for embedding

# BGE query prefix — MUST be used on queries, not on passages
QUERY_PREFIX     = "Represent this sentence for searching relevant passages: "

TOP_K_RETRIEVE   = 10   # candidates from ChromaDB
TOP_K_RERANK     = 3    # final chunks sent to LLM

GROQ_MODEL       = "llama-3.3-70b-versatile"
MAX_TOKENS       = 1024
TEMPERATURE      = 0.2   # low = factual, consistent

SYSTEM_PROMPT = """You are a helpful NCERT Science tutor for Class 9 students.
Answer the student's question using ONLY the context provided below.
- Be clear and concise.
- If the context contains relevant formulas or steps, include them.
- If the answer is not found in the context, say: "This topic is not covered in the retrieved sections. Please refer to the relevant chapter directly."
- Always mention which chapter/section the answer comes from."""


# ── Load models (cached across Streamlit reruns) ──────────────────────────────

@st.cache_resource(show_spinner="Loading embedding model...")
def load_embedder():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBED_MODEL, device=EMBED_DEVICE)
    model.max_seq_length = 512
    return model


@st.cache_resource(show_spinner="Loading re-ranker model...")
def load_reranker():
    from sentence_transformers import CrossEncoder
    model = CrossEncoder(RERANK_MODEL, device=RERANK_DEVICE, max_length=512)
    return model


@st.cache_resource(show_spinner="Connecting to ChromaDB...")
def load_collection():
    import chromadb
    client     = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_collection(COLLECTION_NAME)
    return collection


@st.cache_resource(show_spinner="Connecting to Groq...")
def load_groq():
    from groq import Groq
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        st.error(
            "GROQ_API_KEY not set. "
            "Run: `$env:GROQ_API_KEY = 'gsk_...'` in PowerShell "
            "before launching Streamlit."
        )
        st.stop()
    return Groq(api_key=api_key)


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve(query: str, embedder, collection) -> list[dict]:
    """Embed query → ChromaDB top-K."""
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

    candidates = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        candidates.append({
            "content":  doc,
            "metadata": meta,
            "score":    1 - dist,   # cosine similarity (0–1)
        })
    return candidates


# ── Re-ranking ────────────────────────────────────────────────────────────────

def rerank(query: str, candidates: list[dict], reranker) -> list[dict]:
    """Cross-encoder re-scores candidates, returns top-K sorted."""
    pairs  = [[query, c["content"]] for c in candidates]
    scores = reranker.predict(pairs, show_progress_bar=False)

    for c, s in zip(candidates, scores):
        c["rerank_score"] = float(s)

    ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    return ranked[:TOP_K_RERANK]


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_context_block(chunks: list[dict]) -> str:
    blocks = []
    for i, c in enumerate(chunks, 1):
        m = c["metadata"]
        header = (
            f"[Source {i}] "
            f"Chapter {m.get('chapter_number','?')} — {m.get('chapter_title','')}"
            f" | Section {m.get('section_id','?')}: {m.get('section_title','')}"
            f" | Type: {m.get('section_type','')}"
        )
        blocks.append(f"{header}\n{c['content']}")
    return "\n\n---\n\n".join(blocks)


# ── LLM call ──────────────────────────────────────────────────────────────────

def generate_answer(query: str, context: str, groq_client) -> str:
    user_msg = f"Context:\n{context}\n\nQuestion: {query}"

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )
    return response.choices[0].message.content.strip()


# ── Streamlit UI ──────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="NCERT Science QA",
        page_icon="📚",
        layout="wide",
    )

    st.title("📚 NCERT Science QA — Class 9")
    st.caption(
        "Powered by BGE-large embeddings · BGE-reranker · "
        "Llama 3.3 70B via Groq · ChromaDB"
    )

    # Load all resources
    embedder   = load_embedder()
    reranker   = load_reranker()
    collection = load_collection()
    groq       = load_groq()

    st.success(
        f"Ready — {collection.count()} chunks indexed across 12 chapters."
    )

    # ── Query input ───────────────────────────────────────────────────────────
    st.divider()
    query = st.text_input(
        "Ask a question:",
        placeholder="e.g. What is evaporation? How does acceleration relate to velocity?",
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        ask = st.button("Ask", type="primary", use_container_width=True)
    with col2:
        show_sources = st.toggle("Show retrieved sources", value=True)

    if not ask or not query.strip():
        st.stop()

    # ── Pipeline ──────────────────────────────────────────────────────────────
    with st.spinner("Retrieving relevant sections..."):
        t0         = time.time()
        candidates = retrieve(query, embedder, collection)
        t_retrieve = time.time() - t0

    with st.spinner("Re-ranking..."):
        t1      = time.time()
        top_chunks = rerank(query, candidates, reranker)
        t_rerank   = time.time() - t1

    context = build_context_block(top_chunks)

    with st.spinner("Generating answer..."):
        t2     = time.time()
        answer = generate_answer(query, context, groq)
        t_llm  = time.time() - t2

    # ── Display answer ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Answer")
    st.markdown(answer)

    # ── Timing ────────────────────────────────────────────────────────────────
    st.caption(
        f"⏱ Retrieve: {t_retrieve:.2f}s · "
        f"Re-rank: {t_rerank:.2f}s · "
        f"LLM: {t_llm:.2f}s · "
        f"Total: {t_retrieve+t_rerank+t_llm:.2f}s"
    )

    # ── Sources ───────────────────────────────────────────────────────────────
    if show_sources:
        st.divider()
        st.subheader("Retrieved Sources")
        for i, c in enumerate(top_chunks, 1):
            m = c["metadata"]
            label = (
                f"Source {i} · "
                f"Ch.{m.get('chapter_number','?')} {m.get('chapter_title','')} · "
                f"§{m.get('section_id','?')} {m.get('section_title','')[:40]} · "
                f"{m.get('section_type','')} · "
                f"rerank={c['rerank_score']:.3f}"
            )
            with st.expander(label):
                st.markdown(f"**Chapter:** {m.get('chapter_id','')} — "
                            f"{m.get('chapter_title','')}")
                st.markdown(f"**Section:** {m.get('section_id','')} — "
                            f"{m.get('section_title','')}")
                st.markdown(f"**Type:** {m.get('section_type','')}")
                if m.get("topic"):
                    st.markdown(f"**Topic:** {m.get('topic')}")
                st.markdown(f"**Similarity:** {c['score']:.4f} → "
                            f"**Re-rank score:** {c['rerank_score']:.4f}")
                st.divider()
                st.write(c["content"])


if __name__ == "__main__":
    main()