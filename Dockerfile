# ── Base image ────────────────────────────────────────────────
# Use slim Python; torch will handle CUDA at runtime if available
FROM python:3.11-slim

# ── System deps ───────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────
WORKDIR /app

# ── Install Python deps first (layer-cached) ──────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy project files ────────────────────────────────────────
COPY . .

# ── Streamlit config ──────────────────────────────────────────
RUN mkdir -p /root/.streamlit
RUN echo "\
[server]\n\
port = 8501\n\
address = '0.0.0.0'\n\
headless = true\n\
enableCORS = false\n\
enableXsrfProtection = false\n\
" > /root/.streamlit/config.toml

# ── Expose Streamlit port ─────────────────────────────────────
EXPOSE 8501

# ── Startup: sync ChromaDB from Azure Blob, then launch app ──
# azure_sync.py downloads chroma_db/ from Blob Storage on start
CMD ["sh", "-c", "python azure_sync.py && streamlit run rag_chain.py"]
