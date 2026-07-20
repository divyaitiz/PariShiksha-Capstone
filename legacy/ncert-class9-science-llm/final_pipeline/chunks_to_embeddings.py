"""
chunks_to_embeddings.py
=======================
Reads chunks/all_chunks.jsonl, embeds every chunk with
BAAI/bge-large-en-v1.5 on CUDA, and upserts into a local ChromaDB
collection.

Requirements:
    pip install chromadb sentence-transformers torch

Run from pipeline root:
    python chunks_to_embeddings.py

ChromaDB persists to ./chroma_db/ — run again safely (upsert is idempotent).
"""

import sys
import json
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ── Config ────────────────────────────────────────────────────────────────────
CHUNKS_FILE     = Path("./chunks/all_chunks.jsonl")
CHROMA_DIR      = Path("./chroma_db")
COLLECTION_NAME = "ncert_science"
MODEL_NAME      = "BAAI/bge-large-en-v1.5"
BATCH_SIZE      = 32     # safe for RTX 3050 6 GB with bge-large
DEVICE          = "cuda"

# BGE models perform best with this prefix on the query side,
# but for passages (what we store) no prefix is needed.
PASSAGE_PREFIX  = ""     # empty — BGE-large doesn't need a passage prefix


# ── Load model ────────────────────────────────────────────────────────────────

def load_model():
    from sentence_transformers import SentenceTransformer
    print(f"Loading {MODEL_NAME} on {DEVICE}...")
    model = SentenceTransformer(MODEL_NAME, device=DEVICE)
    model.max_seq_length = 512   # bge-large max
    dim = getattr(model, "get_embedding_dimension",
                  model.get_sentence_embedding_dimension)()
    print(f"Model loaded. Embedding dim: {dim}")
    return model


# ── Load chunks ───────────────────────────────────────────────────────────────

def load_chunks(path: Path) -> list[dict]:
    if not path.exists():
        print(f"ERROR: {path} not found. Run json_to_chunks.py first.")
        sys.exit(1)
    chunks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    print(f"Loaded {len(chunks)} chunks from {path}")
    return chunks


# ── Build ChromaDB collection ─────────────────────────────────────────────────

def get_collection():
    import chromadb
    client     = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},  # cosine similarity
    )
    print(f"ChromaDB collection '{COLLECTION_NAME}' ready "
          f"(existing docs: {collection.count()})")
    return collection


# ── Embed + upsert in batches ─────────────────────────────────────────────────

def embed_and_upsert(chunks: list[dict], model, collection):
    # Deduplicate within the JSONL itself (duplicate section IDs in source JSON
    # produce duplicate chunk_ids — keep first occurrence)
    seen       = {}
    for c in chunks:
        cid = c["chunk_id"]
        if cid not in seen:
            seen[cid] = c
        else:
            # Make the duplicate unique by appending a suffix
            base = cid
            n    = 1
            while f"{base}_dup{n}" in seen:
                n += 1
            new_id        = f"{base}_dup{n}"
            c             = dict(c)
            c["chunk_id"] = new_id
            seen[new_id]  = c
    chunks = list(seen.values())

    # Skip chunks that are already in the collection
    existing_ids = set(collection.get(include=[])["ids"])
    new_chunks   = [c for c in chunks if c["chunk_id"] not in existing_ids]

    if not new_chunks:
        print("All chunks already embedded. Nothing to do.")
        return

    print(f"Embedding {len(new_chunks)} new chunks "
          f"({len(chunks) - len(new_chunks)} already present)...")

    t0          = time.time()
    total       = len(new_chunks)
    upserted    = 0

    for start in range(0, total, BATCH_SIZE):
        batch  = new_chunks[start : start + BATCH_SIZE]
        texts  = [PASSAGE_PREFIX + c["content"] for c in batch]

        # Embed
        vectors = model.encode(
            texts,
            batch_size=BATCH_SIZE,
            show_progress_bar=False,
            normalize_embeddings=True,   # cosine sim works on unit vectors
            device=DEVICE,
        )

        # Build ChromaDB upsert payload
        ids        = [c["chunk_id"] for c in batch]
        embeddings = [v.tolist() for v in vectors]
        documents  = texts
        metadatas  = [
            {
                "chapter_id":     c["chapter_id"],
                "chapter_number": c["chapter_number"],
                "chapter_title":  c["chapter_title"],
                "source_file":    c["source_file"],
                "section_type":   c["section_type"],
                "section_id":     c["section_id"],
                "section_title":  c["section_title"],
                "parent_id":      c["parent_id"],
                "parent_title":   c["parent_title"],
                "topic":          c["topic"],
                "chunk_index":    c["chunk_index"],
            }
            for c in batch
        ]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        upserted += len(batch)
        elapsed   = time.time() - t0
        rate      = upserted / elapsed
        remaining = (total - upserted) / rate if rate > 0 else 0

        print(f"  [{upserted}/{total}]  "
              f"{elapsed:.1f}s elapsed  "
              f"~{remaining:.0f}s remaining  "
              f"({rate:.1f} chunks/s)")

    print(f"\nDone. {upserted} chunks upserted in {time.time()-t0:.1f}s")
    print(f"Collection now has {collection.count()} total documents.")
    print(f"ChromaDB stored at: {CHROMA_DIR.resolve()}")


# ── Quick sanity check ────────────────────────────────────────────────────────

def sanity_check(model, collection):
    print("\nSanity check — querying: 'What is evaporation?'")
    query   = "What is evaporation?"
    q_vec   = model.encode(
        query,
        normalize_embeddings=True,
        device=DEVICE,
    ).tolist()

    results = collection.query(
        query_embeddings=[q_vec],
        n_results=3,
        include=["documents", "metadatas", "distances"],
    )

    for i, (doc, meta, dist) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    )):
        print(f"\n  Result {i+1}  (distance={dist:.4f})")
        print(f"  Chapter  : {meta['chapter_id']}  |  "
              f"Section: {meta['section_id']}  |  "
              f"Type: {meta['section_type']}")
        print(f"  Title    : {meta['section_title'][:60]}")
        print(f"  Content  : {doc[:120]}...")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    chunks     = load_chunks(CHUNKS_FILE)
    model      = load_model()
    collection = get_collection()
    embed_and_upsert(chunks, model, collection)
    sanity_check(model, collection)


if __name__ == "__main__":
    main()