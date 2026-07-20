"""
rag_chain.py
============
Streamlit QA bot for NCERT Science (Class 9) — now with multi-turn
conversational memory.

Pipeline per query:
  1. Condense query using chat history (standalone question rewrite)
  2. Embed standalone question with BGE-large (GPU, query prefix)
  3. ChromaDB → top-10 candidate chunks (cosine similarity)
  4. BGE-reranker-large → re-score top-10, keep top-3 (CPU)
  5. Build prompt with retrieved context + recent chat history
  6. Groq LLM (llama-3.3-70b-versatile) → answer
  7. Show answer + source citations in Streamlit, append turn to history

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

HISTORY_TURNS    = 3     # how many past user/assistant pairs to keep in context (6 messages)

SYSTEM_PROMPT = """You are a helpful NCERT Science tutor for Class 9 students.
Answer the student's question using ONLY the context provided below.
- Be clear and concise.
- If the context contains relevant formulas or steps, include them.
- If the question is a greeting, small talk, or not a real question, respond briefly and naturally — do NOT add a Sources line.
- If the answer is not found in the context, say: "This topic is not covered in the retrieved sections. Please refer to the relevant chapter directly." — do NOT add a Sources line.
- Only when you actually use information from the context: at the very end, on a new line, add exactly one line starting with "**Sources:**" listing the distinct chapter/section references used, comma-separated.
- Do NOT cite chapters/sections inline after every sentence.
- Use the conversation history only to understand what the student is referring to — always ground the actual answer in the provided context."""

CONDENSE_PROMPT = """Given the conversation history and a follow-up question, rewrite the follow-up into a short standalone question.
- Only add the minimum context needed to resolve pronouns or vague references (e.g. "it", "that", "explain more").
- Do NOT summarize or repeat details from the previous answer.
- If the follow-up is already standalone, return it unchanged.
- Output ONLY the rewritten question, under 15 words — no preamble, no quotes."""

GREETING_PATTERNS = {"hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "bye", "goodbye"}

def is_chitchat(query: str) -> bool:
    """Catches greetings/small talk so we skip retrieval + generation entirely."""
    cleaned = query.strip().lower().rstrip("!.,? ")
    return cleaned in GREETING_PATTERNS or len(cleaned) < 3


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


# ── Query condensing (multi-turn memory) ───────────────────────────────────────

def condense_query(query: str, history: list[dict], groq_client) -> str:
    """Rewrite a follow-up question into a standalone one using chat history.
    No-op (returns query unchanged) if there's no history yet."""
    if not history:
        return query

    recent = history[-(HISTORY_TURNS * 2):]
    history_text = "\n".join(f"{h['role']}: {h['content']}" for h in recent)

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": CONDENSE_PROMPT},
            {"role": "user", "content": f"History:\n{history_text}\n\nFollow-up: {query}"},
        ],
        max_tokens=128,
        temperature=0.0,
    )
    return response.choices[0].message.content.strip()


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


# ── Image retrieval ──────────────────────────────────────────────────────────────────────────────

def retrieve_images_for_sections(section_ids: list[str],
                                  collection,
                                  max_images: int = 3) -> list[dict]:
    """
    Query ChromaDB for image chunks whose section_id matches any of the
    section_ids from the top retrieved text chunks.
    Uses metadata filter (no embedding needed).
    """
    if not section_ids:
        return []

    matched   = []
    seen_figs = set()

    for sec_id in section_ids:
        try:
            results = collection.get(
                where={
                    "$and": [
                        {"section_type": {"$eq": "images"}},
                        {"section_id":   {"$eq": sec_id}},
                    ]
                },
                include=["metadatas", "documents"],
            )
            for meta, doc in zip(results["metadatas"], results["documents"]):
                fig_id = meta.get("figure_id", "")
                if fig_id and fig_id not in seen_figs:
                    seen_figs.add(fig_id)
                    matched.append({"metadata": meta, "content": doc})
        except Exception:
            pass

    return matched[:max_images]

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

def generate_answer(query: str, context: str, history: list[dict], groq_client) -> str:
    """Generate the final answer, grounded in retrieved context, with recent
    chat history included so the model understands follow-up phrasing."""
    user_msg = f"Context:\n{context}\n\nQuestion: {query}"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    recent = history[-(HISTORY_TURNS * 2):]
    for h in recent:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_msg})

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
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

    # ── Chat history state ──────────────────────────────────────────────────
    if "messages" not in st.session_state:
        st.session_state.messages = []  # [{"role": "user"/"assistant", "content": str}]
    if "last_sources" not in st.session_state:
        st.session_state.last_sources = None
    if "last_images" not in st.session_state:
        st.session_state.last_images = None

    show_sources = st.toggle("Show retrieved sources", value=True)

    # Reset button — new conversation
    if st.button("🔄 New conversation"):
        st.session_state.messages = []
        st.session_state.last_sources = None
        st.session_state.last_images = None
        st.rerun()

    st.divider()

    # ── Render past turns ────────────────────────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Chat input ────────────────────────────────────────────────────────────
    query = st.chat_input("Ask a question, e.g. What is evaporation?")

    if not query or not query.strip():
        st.stop()

    with st.chat_message("user"):
        st.markdown(query)

    # ── Chitchat guard — skip retrieval/generation for greetings/small talk ────
    if is_chitchat(query):
        answer = ("Hi! Ask me anything about NCERT Class 9 Science — "
                  "e.g. \"What is evaporation?\" or \"How does refraction work?\"")
        with st.chat_message("assistant"):
            st.markdown(answer)
        st.session_state.messages.append({"role": "user", "content": query})
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.stop()

    # ── Pipeline ──────────────────────────────────────────────────────────────
    with st.spinner("Thinking about what you're asking..."):
        t_start = time.time()
        standalone_query = condense_query(query, st.session_state.messages, groq)
        t_condense = time.time() - t_start

    with st.spinner("Retrieving relevant sections..."):
        t0         = time.time()
        candidates = retrieve(standalone_query, embedder, collection)
        t_retrieve = time.time() - t0

    with st.spinner("Re-ranking..."):
        t1      = time.time()
        top_chunks = rerank(standalone_query, candidates, reranker)
        t_rerank   = time.time() - t1

    context = build_context_block(top_chunks)

    # Image retrieval: find figures linked to same section_ids as top text chunks
    top_section_ids = list(dict.fromkeys(
        c["metadata"].get("section_id", "") for c in top_chunks
        if c["metadata"].get("section_id", "")
    ))
    related_images = retrieve_images_for_sections(top_section_ids, collection)

    with st.spinner("Generating answer..."):
        t2     = time.time()
        answer = generate_answer(query, context, st.session_state.messages, groq)
        t_llm  = time.time() - t2

    # ── Update history ───────────────────────────────────────────────────────
    st.session_state.messages.append({"role": "user", "content": query})
    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.last_sources = top_chunks
    st.session_state.last_images  = related_images

    # ── Display answer ────────────────────────────────────────────────────────
    with st.chat_message("assistant"):
        st.markdown(answer)

        if standalone_query != query:
            st.caption(f"🔎 Searched as: _{standalone_query}_")

        st.caption(
            f"⏱ Condense: {t_condense:.2f}s · "
            f"Retrieve: {t_retrieve:.2f}s · "
            f"Re-rank: {t_rerank:.2f}s · "
            f"LLM: {t_llm:.2f}s · "
            f"Total: {t_condense+t_retrieve+t_rerank+t_llm:.2f}s"
        )

        # ── Related figures ──────────────────────────────────────────────────
        if related_images:
            st.divider()
            st.subheader("📷 Related Figures")
            cols = st.columns(min(len(related_images), 3))
            for col, img_rec in zip(cols, related_images):
                meta     = img_rec["metadata"]
                fig_id   = meta.get("figure_id", "")
                img_path = meta.get("image_path", "")
                sec_id   = meta.get("section_id", "")
                content_preview = img_rec.get("content", "")

                with col:
                    if img_path:
                        from pathlib import Path as _Path
                        p = _Path(img_path)
                        if p.exists():
                            st.image(
                                str(p),
                                caption=f"Fig {fig_id}  §{sec_id}",
                                use_container_width=True,
                            )
                        else:
                            st.info(f"Fig {fig_id}: image not yet extracted")
                    if content_preview:
                        with st.expander(f"Caption — Fig {fig_id}"):
                            st.write(content_preview)

        # ── Sources ───────────────────────────────────────────────────────────
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