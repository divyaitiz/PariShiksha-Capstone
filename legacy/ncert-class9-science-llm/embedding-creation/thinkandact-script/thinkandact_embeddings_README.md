# thinkandact_embeddings — README

## Overview

This notebook takes the structured JSON output produced by `Chunking_thinkandact.ipynb` and converts it into **vector embeddings stored in a persistent ChromaDB collection**. It is the second stage in the Think and Act content processing pipeline, enabling semantic search and retrieval over extracted textbook prompts.

---

## File

| File | Description |
|------|-------------|
| `thinkandact_embeddings.ipynb` | Jupyter notebook for embedding generation, ChromaDB storage, and inspection |

### Dependencies

| Input | Description |
|-------|-------------|
| `chapter7_72_thinkandact_output.json` | JSON file produced by the chunking notebook (see `Chunking_thinkandact_README.md`) |

### Output Structure

```
data_embedding/
└── chapter7_72_thinkandact_db/
    ├── chroma.sqlite3               # ChromaDB persistent store
    ├── source_snapshot.json         # Copy of the original JSON data used for embedding
    └── <uuid>/                      # ChromaDB internal segment files
```

---

## Notebook Sections

### Section 1 — Initial ChromaDB Setup, Embedding Generation & Verification (Method 1)

Sets up ChromaDB from scratch and populates it with embeddings:

1. Defines `file_name`, `context_name`, and constructs the `db_path` under `data_embedding/`.
2. Loads the input JSON file and initialises a `PersistentClient` pointing to the database directory.
3. Creates (or retrieves) a ChromaDB collection named `{context_name}_embeddings` using the `DefaultEmbeddingFunction`.
4. Prepares three parallel lists for ChromaDB ingestion — `documents` (text), `metadatas` (chapter, page, source file), and `ids` (e.g. `chapter7_72_thinkandact_id_0`).
5. Calls `.add()` to generate and persist the embeddings.
6. Retrieves the stored data and prints a 10-dimension sample to confirm successful storage.

**Sample output:**
```
--- Process Complete ---
Database Path: data_embedding/chapter7_72_thinkandact_db
Collection Name: chapter7_72_thinkandact_embeddings
First Embedding Sample (10 dims): [ 0.00818573 -0.0441445  0.04858383 ...]
Total Vectors Stored: 1
```

---

### Section 2 — Refined Setup with Source Snapshot (Method 2)

An alternative, more robust version of Section 1, with one key addition:

- After embedding and storing the documents, it writes a **`source_snapshot.json`** file into the database directory. This snapshot is an exact copy of the input JSON, providing a human-readable audit trail of what data was used to populate the collection.

This method is recommended for production use or when traceability of embedded content is important.

**Sample output:**
```
Structure verified. Files created in: data_embedding/chapter7_72_thinkandact_db
```

---

### Section 3 — Inspecting Stored Embeddings

Retrieves and displays the contents of the ChromaDB collection in a tabular format for verification:

- Fetches all stored `ids`, `documents`, and `embeddings` from the collection.
- Prints a formatted table showing each entry's ID, a 37-character text preview, and the first 3 dimensions of its embedding vector.

**Sample output:**
```
ID              | TEXT PREVIEW                             | VECTOR SAMPLE
--------------------------------------------------------------------------------
chapter7_72_thinkandact_id_0 | We sometimes are endangered by the mo... | [0.0082, -0.0441, 0.0486...]
--------------------------------------------------------------------------------
Total entries in embedding variable: 1
```

---

## Configuration

The following variables at the top of each section control naming and paths:

```python
file_name     = "chapter7_72_thinkandact_output.json"  # Input JSON from chunking step
context_name  = "chapter7_72_thinkandact"              # Used for collection name and DB folder
base_dir      = "data_embedding"                       # Root folder for all ChromaDB stores
```

To process a different chapter/page, update `file_name` and `context_name` accordingly. The database folder and collection name are derived automatically from `context_name`.

---

## Requirements

```bash
pip install chromadb
```

| Dependency | Purpose |
|------------|---------|
| `chromadb` | Vector database for storing and querying embeddings |
| `chromadb.utils.embedding_functions` | Provides the `DefaultEmbeddingFunction` (based on `all-MiniLM-L6-v2`) |
| `json`, `os` | Standard library — file I/O and path management |

---

## Usage

1. Ensure `chapter7_72_thinkandact_output.json` (or your equivalent JSON) is in the same directory as the notebook.
2. Update `file_name` and `context_name` in the config block if processing a different chapter.
3. Run **Section 1** or **Section 2** to generate and persist embeddings (Section 2 is recommended for its snapshot feature).
4. Run **Section 3** to inspect and verify the stored vectors.

---

## Pipeline Position

```
thinkandact.txt
      │
      ▼
Chunking_thinkandact.ipynb  →  chapter7_72_thinkandact_output.json
                                              │
                                              ▼
                              thinkandact_embeddings.ipynb  →  ChromaDB collection
```

This notebook is the **second step** in the pipeline. Its output (the ChromaDB collection) is ready for semantic similarity search, retrieval-augmented generation (RAG), or other downstream NLP tasks.

---

## Notes

- The `DefaultEmbeddingFunction` uses the `all-MiniLM-L6-v2` sentence-transformer model, which produces 384-dimensional vectors.
- ChromaDB's `.get_or_create_collection()` is idempotent — re-running the notebook will not create duplicate collections, but calling `.add()` again with the same IDs will raise a conflict error. Clear the database folder or use `.upsert()` if re-processing is needed.
- The `source_snapshot.json` (Method 2) mirrors the original input exactly and is stored alongside the ChromaDB files for auditability.
