# PariShiksha — NCERT Science QA Bot
### An End-to-End LLMOps Pipeline on Azure

> **Live URL:** `http://ncert-qa-bot.uaenorth.azurecontainer.io:8501`
> 
> **GitHub:** [github.com/divyaitiz/PariShiksha](https://github.com/divyaitiz/PariShiksha)

---

## Table of Contents

1. [What is PariShiksha?](#1-what-is-parishiksha)
2. [Previous Work](#2-previous-work)
3. [Architecture Overview](#3-architecture-overview)
4. [LLMOps Concepts Applied](#4-llmops-concepts-applied)
5. [Tech Stack](#5-tech-stack)
6. [Repository Structure](#6-repository-structure)
7. [What Lives Where](#7-what-lives-where)
8. [Pipeline Scripts — Run Order](#8-pipeline-scripts--run-order)
9. [Local Development Setup](#9-local-development-setup)
10. [Docker — Local Testing Journey](#10-docker--local-testing-journey)
11. [Azure Infrastructure Setup](#11-azure-infrastructure-setup)
12. [CI/CD Pipeline](#12-cicd-pipeline)
13. [Key Decisions Made](#13-key-decisions-made)
14. [Key Fixes and Errors Encountered](#14-key-fixes-and-errors-encountered)
15. [How a Query Works](#15-how-a-query-works)
16. [Cost Management](#16-cost-management)
17. [Platforms Used](#17-platforms-used)
18. [App Screenshots](#18-app-screenshots)

---

## 1. What is PariShiksha?

PariShiksha is an AI-powered Question Answering system built on top of NCERT Science textbooks (Class 9). Students can ask questions in natural language and get accurate, cited answers sourced directly from the textbook content — with chapter and section references included in every response.

**Example queries the app answers:**
- *"What is evaporation?"*
- *"Give formulas of motion"*
- *"What are the laws of motion?"*
- *"What is acceleration?"*

The app uses a two-stage retrieval pipeline (embedding similarity + reranking) before sending context to an LLM, making answers grounded, traceable, and accurate.

---

## 2. Previous Work

PariShiksha represents the progress made from the foundational work established in [ncert-class9-science-llm/final_pipeline](https://github.com/divyaitiz/ncert-class9-science-llm/tree/main/final_pipeline).

That repository handled the core data extraction pipeline — converting NCERT Class 9 Science PDFs into structured JSON across all section types: informational text, exercises, activities, examples, in-chapter questions, think-and-act, and what-you-have-learnt sections.

**PariShiksha takes that structured JSON output and builds the full LLMOps stack on top:**
 
| Previous Repo | PariShiksha Adds |
|---|---|
| PDF → structured JSON extraction | Docker containerization |
| Basic text processing | Azure Blob Storage for vector persistence |
| Raw JSON output | GitHub Actions CI/CD |
| Custom chunking strategy per section type |  Azure Container Instance deployment |
| BGE-large embeddings (bge-large-en-v1.5) | — |
| ChromaDB vector store with rich metadata | — |
| BGE-reranker-large cross-encoder | — |
| Groq LLM (Llama 3.3 70B) RAG chain | — |
| Streamlit UI with source citations | — |

---

## 3. Architecture Overview

```
Student Question
      ↓
BGE-large Embeddings
(query prefix applied)
      ↓
ChromaDB Vector Store
(top-10 candidates by cosine similarity)
      ↓
BGE-reranker-large
(cross-encoder rescores, top-3 kept)
      ↓
Context block built
(chapter + section metadata attached)
      ↓
Groq API — Llama 3.3 70B
(answers only from provided context)
      ↓
Streamlit UI
(answer + citations + timing)
```

**Data flow for vector store (one-time setup):**
```
PDFs
  ↓ run_pipeline.py
extracted/<chapter>/json/*.json
  ↓ json_to_chunks.py
chunks/all_chunks.jsonl
  ↓ chunks_to_embeddings.py
chroma_db/
  ↓ azure_sync.py --upload
Azure Blob Storage (ncert-chromadb)
  ↓ azure_sync.py (on container startup)
Container reads chroma_db/ → app ready
```

---

## 4. LLMOps Concepts Applied

| LLMOps Concept | Where Applied | File / Code |
|---|---|---|
| **Data Versioning & Lineage** | `processed.json` tracks which PDFs were processed and when. Each chunk carries `chunk_id`, `chapter_id`, `section_id`, `source_file`, `chunk_index` for full traceability | `run_pipeline.py`, `json_to_chunks.py` |
| **Experiment Tracking** | Two embedding approaches tested: `build_vectorstore.py` (bge-base, LangChain splitter, no reranker) vs `chunks_to_embeddings.py` (bge-large, custom chunker, reranker). Second approach won and became production | `build_vectorstore.py`, `chunks_to_embeddings.py` |
| **Model Registry & Versioning** | Docker images tagged with both `latest` and commit SHA — every deployment traceable to exact code. Models pinned: `GROQ_MODEL`, `EMBED_MODEL`, `RERANK_MODEL` as constants | `rag_chain.py`, `deploy.yml`, Azure Container Registry |
| **Serving Infrastructure** | Streamlit as serving layer. Groq handles LLM inference (serverless). BGE runs inside container (embedded serving). ChromaDB as vector index. Azure Container Instance as host | `rag_chain.py`, `Dockerfile`, Azure ACI |
| **Pipeline Automation (CI/CD)** | Every push to `main` auto-builds Docker image, pushes to ACR, deletes old container, creates new one. Zero manual steps after push | `.github/workflows/deploy.yml` |
| **Data Pipeline Orchestration** | `run_pipeline.py` orchestrates PDF → text → JSON with quality checks (min chars, junk ratio, repeated chars), flagging bad extractions, per-PDF logging, and skip logic for already-processed files | `run_pipeline.py` |
| **Feature Store** | ChromaDB stores pre-computed BGE-large embeddings — never recomputed at query time. Metadata stored alongside vectors. Azure Blob persists the store across container restarts | `chunks_to_embeddings.py`, `azure_sync.py`, Azure Blob |
| **Prompt Engineering** | `SYSTEM_PROMPT` constrains LLM to provided context only, handles not-found case, enforces chapter citation. `QUERY_PREFIX` applied correctly to queries only (not passages). `TEMPERATURE=0.2` for factual consistency | `rag_chain.py` |
| **Retrieval Quality** | Two-stage retrieval: cosine similarity (fast, approximate) → cross-encoder reranker (slow, precise). `TOP_K_RETRIEVE=10` → `TOP_K_RERANK=3`. Both scores shown in UI. `hnsw:space: cosine` for normalized vectors | `rag_chain.py`, `chunks_to_embeddings.py` |
| **Infrastructure as Code** | Container environment, deployment process, dependencies, gitignore rules, and data sync behaviour all defined in version-controlled files | `Dockerfile`, `deploy.yml`, `requirements.txt`, `.gitignore`, `azure_sync.py` |
| **Secret Management** | `.env` locally (gitignored). 9 GitHub Secrets for CI/CD. Azure environment variables injected at container runtime. Zero hardcoded credentials anywhere | `.env`, GitHub Secrets, Azure ACI env vars |
| **Cost Optimization** | Groq (free tier) instead of Azure OpenAI (unavailable on student tier). CPU torch instead of GPU instance. Azure Container Instance instead of AKS. Manual stop/start to avoid 24/7 costs. Blob Storage for ChromaDB persistence (cents/month) | `requirements.txt`, `Dockerfile`, Azure ACI config |

---

## 5. Tech Stack

| Component | Technology | Why Chosen |
|---|---|---|
| **UI** | Streamlit | Fast to build, shows sources and timing natively |
| **LLM** | Llama 3.3 70B via Groq | Free tier, faster than local, Azure OpenAI unavailable on student subscription |
| **Embeddings** | BAAI/bge-large-en-v1.5 | Best open-source embedding model, query prefix support |
| **Reranker** | BAAI/bge-reranker-large | Cross-encoder, significantly improves retrieval precision |
| **Vector Store** | ChromaDB | Local persistence, cosine similarity, rich metadata support |
| **Blob Storage** | Azure Blob Storage | Persists ChromaDB across container restarts, cheap |
| **Container Registry** | Azure Container Registry | Stores versioned Docker images, integrates with ACI |
| **Deployment** | Azure Container Instance | Simpler than AKS, sufficient for this scale |
| **CI/CD** | GitHub Actions | Native GitHub integration, free for public repos |
| **Containerization** | Docker | Reproducible environment, works locally and on Azure |
| **Language** | Python 3.11 | Compatible with all dependencies |

---

## 6. Repository Structure

```
PariShiksha/
│
├── .github/
│   └── workflows/
│       └── deploy.yml              ← CI/CD pipeline
│
├── images_running_app/             ← screenshots of live app
│
├── .gitignore                      ← excludes large data and secrets
├── Dockerfile                      ← container definition
├── requirements.txt                ← pinned Python dependencies
├── README.md                       ← this file
│
├── rag_chain.py                    ← main Streamlit QA app
├── azure_sync.py                   ← ChromaDB <-> Azure Blob sync
│
├── chunks_to_embeddings.py         ← builds ChromaDB from chunks (real pipeline)
├── json_to_chunks.py               ← converts extracted JSON to JSONL chunks
├── run_pipeline.py                 ← PDF -> text -> JSON orchestrator
├── check_chromadb_metadata.py      ← debug tool to verify ChromaDB contents
└── build_vectorstore.py            ← older approach, kept for reference only
```

**Note on `build_vectorstore.py`:** This was an earlier attempt at building the vector store using `bge-base` and LangChain's basic text splitter. It was replaced by `chunks_to_embeddings.py` which uses `bge-large`, custom per-section chunking, deduplication, and richer metadata. It is kept as a reference to show the evolution of the pipeline.

---

## 7. What Lives Where

| Content | Location | Why |
|---|---|---|
| Python source code | GitHub | Version controlled, CI/CD trigger |
| Docker image | Azure Container Registry | Versioned, pulled by ACI on deploy |
| `chroma_db/` | Azure Blob Storage | Too large for GitHub, needs to persist across container restarts |
| `chunks/` | Local machine only | Intermediate pipeline artifact, regeneratable |
| `extracted/` | Local machine only | Intermediate pipeline artifact, regeneratable |
| `pdfs/` | Local machine only | Source files, not needed by running app |
| `processed.json` | Local machine only | Tracks pipeline progress, not needed by app |
| `.env` | Local machine only | Contains secrets, never committed |
| Secrets (Groq, ACR, Azure) | GitHub Secrets + Azure env vars | Injected at runtime, never in code |

---

## 8. Pipeline Scripts — Run Order

> These scripts only need to be run when rebuilding the vector store from new or updated PDFs. For normal deployment, `chroma_db/` is pulled from Azure Blob Storage automatically on container startup.

```bash
# Step 1 — PDF to text to JSON (run_pipeline.py)
# Reads:  pdfs/*.pdf
# Writes: extracted/<chapter>/text/*.txt
#         extracted/<chapter>/json/*.json
#         processed.json (tracks what was processed)
#         logs/<chapter>.log
#         flagged/<chapter>/ (quality check failures)
python run_pipeline.py

# Step 2 — JSON to chunks (json_to_chunks.py)
# Reads:  extracted/<chapter>/json/*.json
# Writes: chunks/all_chunks.jsonl
python json_to_chunks.py

# Step 3 — Chunks to ChromaDB (chunks_to_embeddings.py)
# Reads:  chunks/all_chunks.jsonl
# Writes: chroma_db/ (ChromaDB vector store)
python chunks_to_embeddings.py

# Step 4 — Upload ChromaDB to Azure Blob
# Reads:  chroma_db/
# Writes: Azure Blob Storage (ncert-chromadb container)
python azure_sync.py --upload

# Step 5 — Run the app locally
streamlit run rag_chain.py
```

**What `processed.json` is:** A simple tracker file created by `run_pipeline.py` that records which PDFs have already been processed and when. If you re-run the pipeline, already-processed PDFs are skipped. It lives locally and is gitignored — the app does not use it.

**What `check_chromadb_metadata.py` is:** A debug script to inspect what's actually stored in ChromaDB — prints chunk metadata and lists all section types present. Useful after rebuilding the vector store to verify everything was indexed correctly.

---

## 9. Local Development Setup

### Prerequisites
- Python 3.11
- Docker Desktop
- Groq API key from [console.groq.com](https://console.groq.com)
- Azure Storage Account (for `azure_sync.py`)

### Setup

```bash
# Clone the repo
git clone https://github.com/divyaitiz/PariShiksha.git
cd PariShiksha

# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file in project root
# Add the following:
GROQ_API_KEY=gsk_...
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=ncertstorage;...
AZURE_BLOB_CONTAINER=ncert-chromadb

# Run the app (assumes chroma_db/ exists locally)
streamlit run rag_chain.py
```

### .gitignore (What Gets Excluded)

```gitignore
# Secrets
.env
.venv/

# Python
__pycache__/
*.pyc
*.pyo

# Large data — never go to GitHub
chroma_db/
chunks/
extracted/
pdfs/
flagged/
logs/
scripts/

# Pipeline artifacts
processed.json
extracted.zip

# VS Code
.vscode/
*.code-workspace
```

**Why this matters:** Without a proper `.gitignore`, git tried to track `chunks/`, `extracted/`, `pdfs/` — causing a 5.75GB context transfer during Docker build. Once `.gitignore` was corrected, Docker build context dropped to 5.51MB.

---

## 10. Docker — Local Testing Journey

### Why Docker Before Azure?
Testing locally with Docker Desktop catches environment issues before spending Azure credits. The Docker container is identical to what runs on Azure — same OS, same Python version, same dependencies.

### Build the Image

```bash
docker build -t ncert-qa-bot .
```

**Problem encountered — 5.75GB context transfer:**
First build attempted to copy all of `chunks/`, `extracted/`, `pdfs/` into the Docker context because `.dockerignore` did not exist. Build was extremely slow.

**Fix:** Docker respects `.gitignore` by default when no `.dockerignore` is present — but the `.gitignore` was incomplete. Once `.gitignore` was fixed to exclude all large data folders, context dropped to 5.51MB and build became fast.

**Problem encountered — CUDA torch network timeout:**
`requirements.txt` still had `langchain`, `langchain-community` etc. which pulled in full CUDA torch (532MB torch + 366MB nvidia_cudnn + nvidia_nccl etc.). Docker lost network connection mid-download of `nvidia_cuda_runtime`.

**Fix:** Replaced `requirements.txt` with only what `rag_chain.py` actually needs, and forced CPU-only torch:
```
--extra-index-url https://download.pytorch.org/whl/cpu
torch==2.5.1+cpu
```

### Run the Container Locally

```bash
# Windows PowerShell — all on ONE LINE (backslash does not work in PowerShell)
docker run -p 8501:8501 --env-file .env -v "C:/Users/Hp/Desktop/IITGN/NCERT LLM Project/Test2_Pipeline/chroma_db:/app/chroma_db" ncert-qa-bot
```

**Problem encountered — PowerShell line continuation:**
Multiline commands with `\` (bash style) fail in PowerShell with error `The term '-v' is not recognized`. PowerShell uses backtick `` ` `` for line continuation, or the entire command must be on one line.

**Problem encountered — Port already allocated:**
Running the command twice gave `Bind for 0.0.0.0:8501 failed: port is already allocated`. Previous container was still running.

**Fix:**
```bash
docker ps                          # find container ID
docker stop <container_id>         # stop it
```

**Problem encountered — Groq API key error:**
App loaded but gave `groq.AuthenticationError: Invalid API Key`. The `-e GROQ_API_KEY=gsk_...` value was a placeholder.

**Fix:** Use `--env-file .env` instead of `-e` flag so the actual key from `.env` is loaded automatically.

### Two Approaches for chroma_db in Docker

| Approach | Command | When to Use |
|---|---|---|
| Mount local folder | `-v "path/to/chroma_db:/app/chroma_db"` | Local testing — fast, no Azure needed |
| Azure Blob download | Set `AZURE_STORAGE_CONNECTION_STRING` in `.env` | Production flow — `azure_sync.py` downloads on startup |

---

## 11. Azure Infrastructure Setup

### Azure Tools Used:
 
#### 1. Resource Group — `PariShiksha`
A logical container that holds all Azure resources together. Every other resource (Storage, Registry, Container) was created inside it. Deleting the resource group deletes everything inside it.
 
#### 2. Azure Storage Account — `ncertstorage`
Cloud storage service for storing files. Used to persist `chroma_db/` across container restarts. Azure Container Instances are stateless — any local data is wiped on restart. Blob Storage solves this.
 
**Key thing copied from here:** Connection string from Access Keys → used as `AZURE_STORAGE_CONNECTION_STRING` in `.env` and GitHub Secrets.
 
#### 3. Azure Blob Container — `ncert-chromadb`
A folder inside the Storage Account holding 5 ChromaDB files:
```
chroma_db/chroma.sqlite3
chroma_db/401cf3b9-.../data_level0.bin
chroma_db/401cf3b9-.../header.bin
chroma_db/401cf3b9-.../length.bin
chroma_db/401cf3b9-.../link_lists.bin
```
These 5 files ARE your vector store — 702 chunks of NCERT content with their embeddings.
 
#### 4. Azure Container Registry (ACR) — `ncertregistry`
A private Docker image registry on Azure. GitHub Actions pushes your Docker image here on every build. Azure Container Instance pulls the image from here on every deploy.
 
**Key things copied from here:**
- Login server: `ncertregistry.azurecr.io`
- Username: `ncertregistry`
- Password: from Access Keys → used as GitHub Secrets `ACR_USERNAME` and `ACR_PASSWORD`
 
#### 5. Azure Container Instance (ACI) — `ncert-qa-bot`
Runs your Docker container in the cloud without managing servers. Created with 2 CPU + 4GB RAM, port 8501 exposed, DNS label `ncert-qa-bot`.
 
**What happens on every container startup:**
```
Container starts
    ↓
azure_sync.py runs → downloads chroma_db/ from Blob Storage
    ↓
streamlit run rag_chain.py
    ↓
BGE models load from HuggingFace (~2-3 minutes)
    ↓
App ready at ncert-qa-bot.uaenorth.azurecontainer.io:8501
```
 
#### 6. Azure Cloud Shell
Browser-based terminal inside Azure Portal with Azure CLI pre-installed. Used when local Azure CLI login was not working with the student account.
 
**Used for:**
- `az container create` — deploy the container
- `az container logs` — debug container issues
- `az container show` — check container status and IP
- `az ad sp create-for-rbac` — generate `AZURE_CREDENTIALS`
 
#### 7. Service Principal (`AZURE_CREDENTIALS`)
An identity created for GitHub Actions to log into Azure automatically. Generated via:
 
```bash
az ad sp create-for-rbac \
  --name "ncert-qa-bot" \
  --role contributor \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID/resourceGroups/PariShiksha \
  --sdk-auth
```
 
The JSON output was added as the `AZURE_CREDENTIALS` GitHub Secret — the bridge between GitHub Actions and Azure.

### Resources Created

| Resource | Name | Location | Purpose |
|---|---|---|---|
| Resource Group | `PariShiksha` | UAE North | Container for all resources |
| Storage Account | `ncertstorage` | UAE North | Hosts ChromaDB files |
| Blob Container | `ncert-chromadb` | UAE North | Stores `chroma_db/` folder |
| Container Registry | `ncertregistry` | UAE North | Stores Docker images |
| Container Instance | `ncert-qa-bot` | UAE North | Runs the live app |

### Upload ChromaDB to Azure Blob (One Time)

```bash
# Run locally after adding AZURE_STORAGE_CONNECTION_STRING to .env
python azure_sync.py --upload

# Expected output:
# [azure_sync] Uploading 5 files to Azure Blob Storage...
#   ↑ chroma_db/chroma.sqlite3
#   ↑ chroma_db/401cf3b9-.../data_level0.bin
#   ↑ chroma_db/401cf3b9-.../header.bin
#   ↑ chroma_db/401cf3b9-.../length.bin
#   ↑ chroma_db/401cf3b9-.../link_lists.bin
# [azure_sync] Upload complete — 5 files.
```

### Manual Deploy via Azure Cloud Shell

```bash
# Open Cloud Shell from portal.azure.com (>_ icon)
# Select Bash, No storage account required, Azure for Students subscription

# Delete existing container
az container delete --resource-group PariShiksha --name ncert-qa-bot --yes

# Create container
az container create \
  --resource-group PariShiksha \
  --name ncert-qa-bot \
  --image ncertregistry.azurecr.io/ncert-qa-bot:latest \
  --registry-login-server ncertregistry.azurecr.io \
  --registry-username ncertregistry \
  --registry-password "YOUR_ACR_PASSWORD" \
  --dns-name-label ncert-qa-bot \
  --ports 8501 \
  --os-type Linux \
  --cpu 2 \
  --memory 4 \
  --location uaenorth \
  --environment-variables \
    GROQ_API_KEY="YOUR_GROQ_KEY" \
    AZURE_STORAGE_CONNECTION_STRING="YOUR_CONNECTION_STRING" \
    AZURE_BLOB_CONTAINER="ncert-chromadb"
```

### Container Management Commands

```bash
# Check container status
az container show \
  --resource-group PariShiksha \
  --name ncert-qa-bot \
  --query "{status:containers[0].instanceView.currentState.state, ip:ipAddress.ip, fqdn:ipAddress.fqdn}" \
  -o json

# View logs
az container logs --resource-group PariShiksha --name ncert-qa-bot

# Stop (saves student credits)
az container stop --resource-group PariShiksha --name ncert-qa-bot

# Start again
az container start --resource-group PariShiksha --name ncert-qa-bot

# Restart
az container restart --resource-group PariShiksha --name ncert-qa-bot
```

**Note:** After every container recreation, the public IP address changes. The FQDN (`ncert-qa-bot.uaenorth.azurecontainer.io`) stays the same. Always use the FQDN for sharing.

---

## 12. CI/CD Pipeline

### How It Works

```
git push to main
      ↓
GitHub Actions triggered (.github/workflows/deploy.yml)
      ↓
Job 1: Build Docker Image (~3-4 minutes)
  - Checkout code
  - Login to ncertregistry.azurecr.io
  - Build Docker image
  - Push tagged with :latest and :<commit-sha>
      ↓
Job 2: Deploy to Azure (~30 seconds)
  - Login to Azure using AZURE_CREDENTIALS service principal
  - Delete existing container (az container delete)
  - Create new container with updated image (az container create)
  - App live at ncert-qa-bot.uaenorth.azurecontainer.io:8501
```

**Pull requests:** Only Job 1 runs (build only, no deploy). Protects production from unreviewed code.

### GitHub Secrets Required

| Secret | Value Source | Purpose |
|---|---|---|
| `ACR_LOGIN_SERVER` | `ncertregistry.azurecr.io` | ACR address |
| `ACR_USERNAME` | ACR → Access Keys → Username | ACR login |
| `ACR_PASSWORD` | ACR → Access Keys → Password | ACR login |
| `AZURE_CREDENTIALS` | `az ad sp create-for-rbac` JSON output | Azure login |
| `RESOURCE_GROUP` | `PariShiksha` | Target resource group |
| `CONTAINER_NAME` | `ncert-qa-bot` | Container to create/replace |
| `GROQ_API_KEY` | console.groq.com | LLM API access |
| `AZURE_STORAGE_CONNECTION_STRING` | Storage Account → Access Keys | Blob access |
| `AZURE_BLOB_CONTAINER` | `ncert-chromadb` | Blob container name |

### Generate AZURE_CREDENTIALS (Azure Cloud Shell)

```bash
az ad sp create-for-rbac \
  --name "ncert-qa-bot" \
  --role contributor \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID/resourceGroups/PariShiksha \
  --sdk-auth
```

Copy the entire JSON output as the `AZURE_CREDENTIALS` secret value.

### Node.js Deprecation Warnings
The pipeline shows warnings about Node.js 20 actions being deprecated. These are warnings only — the pipeline runs correctly. They will be resolved when GitHub Action maintainers update to Node.js 24 (June 2026).

---

## 13. Key Decisions Made

| Decision | Why |
|---|---|
| **Groq instead of Azure OpenAI** | Azure OpenAI is not available on student subscriptions. Groq is free tier, faster inference, and Llama 3.3 70B is a capable model |
| **Lift & Shift instead of full Azure LLMOps** | Student subscription does not support Azure ML Prompt Flow or Azure AI Studio at required scale. Direct containerization achieves the same result with lower cost |
| **CPU torch on Azure** | No GPU available on Azure Container Instance at student tier. CPU torch wheel is 10x smaller, making Docker builds faster |
| **2 CPU / 4GB RAM** | BGE-large model alone requires ~1.5GB RAM to load. With ChromaDB, Streamlit, and Groq client, 2GB was insufficient (container crashed silently). 4GB provides stable headroom |
| **UAE North region** | Student subscription restricts available regions. UAE North was the allowed region where Storage Account and ACR were created |
| **ChromaDB on Blob Storage** | Container instances are stateless — any local data is lost on restart. Blob Storage costs cents per month and persists the vector store permanently |
| **Direct `az container create` over `azure/aci-deploy@v1`** | The GitHub Action `azure/aci-deploy@v1` had a bug causing duplicate environment variables. Direct CLI gives full control |
| **`chunks_to_embeddings.py` over `build_vectorstore.py`** | `chunks_to_embeddings.py` uses bge-large (vs bge-base), custom per-section chunking (vs basic splitter), deduplication, richer metadata, and writes to the correct `chroma_db/` path |
| **Two-stage retrieval** | Single embedding similarity retrieves broadly but imprecisely. Adding a cross-encoder reranker on top dramatically improves answer relevance with minimal latency cost |

---

## 14. Key Fixes and Errors Encountered

| # | Problem | Error | Root Cause | Fix |
|---|---|---|---|---|
| 1 | ChromaDB path mismatch | App worked but wrong script credited | `build_vectorstore.py` saved to `./chromadb`, `rag_chain.py` read from `./chroma_db` | Identified `chunks_to_embeddings.py` as real builder. `build_vectorstore.py` marked as dead code |
| 2 | Docker CUDA torch network timeout | `HTTPSConnectionPool: Max retries exceeded` | Old `requirements.txt` pulled full CUDA torch (1GB+ NVIDIA packages) which timed out mid-download | Replaced with CPU torch: `--extra-index-url https://download.pytorch.org/whl/cpu` |
| 3 | `.gitignore` not working | `chunks/`, `extracted/` showed as untracked | `.gitignore` was missing `chunks/`, `extracted/`, `pdfs/`, `logs/`, `flagged/` | Added all large data folders to `.gitignore` |
| 4 | PowerShell line continuation | `The term '-v' is not recognized` | Used `\` (bash) instead of backtick in PowerShell for multiline commands | Put entire `docker run` command on one line |
| 5 | Port already allocated | `Bind for 0.0.0.0:8501 failed` | Previous container still running when trying to start a new one | `docker ps` → `docker stop <container_id>` |
| 6 | Groq API key invalid in Docker | `groq.AuthenticationError: Invalid API Key` | Used `-e GROQ_API_KEY=gsk_...` with placeholder value in command | Switched to `--env-file .env` to load actual key |
| 7 | `azure_sync.py` skipping silently | `AZURE_STORAGE_CONNECTION_STRING not set` | `azure_sync.py` used `os.environ.get()` but never called `load_dotenv()` | Added `from dotenv import load_dotenv` and `load_dotenv()` to top of file |
| 8 | Azure region policy | `Resource was disallowed: policy maintains best available regions` | `deploy.yml` used `eastus` but student subscription only allows UAE North | Changed `location: eastus` to `location: uaenorth` |
| 9 | Duplicate environment variables | `Duplicate env vars 'AZURE_BLOB_CONTAINER'` | `azure/aci-deploy@v1` GitHub Action internally duplicated env vars | Replaced Action with direct `az container create` CLI command |
| 10 | OS type not specified | `osType is invalid. Must be Windows or Linux` | Azure ACI API requires explicit OS type since 2017 | Added `--os-type Linux` to `az container create` |
| 11 | Resource requests not specified | `Both memory and CPU requests are required` | Azure ACI API requires explicit resource allocation | Added `--cpu 2 --memory 4` |
| 12 | Container running but app unreachable | `ERR_CONNECTION_RESET` | Container had only 2GB RAM — BGE-large model (~1.5GB) left insufficient memory for rest of app | Increased to `--memory 4` |
| 13 | Empty container logs | No output from `az container logs` | Container crashed before Streamlit could print anything (memory issue) | Fixed by increasing memory |
| 14 | IP address changed after recreation | Old IP stopped working | Every `az container delete` + `az container create` assigns a new public IP | Always use FQDN: `ncert-qa-bot.uaenorth.azurecontainer.io:8501` |
| 15 | ACR authentication failure in pipeline | `unauthorized: authentication required` | ACR password secret was wrong in GitHub Secrets | Regenerated from Azure Portal → ncertregistry → Access Keys → copied correctly |


**Screenshots of the errors encountered along the way and fixes: [screenshots/](https://github.com/divyaitiz/PariShiksha/tree/main/screenshots)**

Note: The screenshots folder also includes some proof screenshots as a validation for whether the activity was done or not.
---

## 15. How a Query Works

```
Step 1: Student types "What is evaporation?" in Streamlit

Step 2: BGE-large encodes the query
        Input: "Represent this sentence for searching relevant passages: What is evaporation?"
        Output: 1024-dimensional normalized vector

Step 3: ChromaDB cosine similarity search
        Returns top-10 chunks most similar to the query vector
        Each chunk has: content + metadata (chapter, section, type, topic)

Step 4: BGE-reranker cross-encodes all 10 pairs
        Input: [("What is evaporation?", chunk1), ..., ("What is evaporation?", chunk10)]
        Output: relevance scores for each pair
        Keeps top-3 by rerank score

Step 5: Context block assembled
        [Source 1] Chapter 1 — Matter in Our Surroundings | Section 1.10 | what_you_have_learnt
        Evaporation is a surface phenomenon...

Step 6: Groq API called (Llama 3.3 70B)
        System: "Answer only from context. Cite chapter and section."
        User: "Context: [top-3 chunks] \n\nQuestion: What is evaporation?"

Step 7: Streamlit displays
        Answer text
        Timing: Retrieve: 0.41s · Re-rank: 30.15s · LLM: 0.38s · Total: 30.93s
        Retrieved Sources (expandable): chapter, section, similarity, rerank score
```

---

## 16. Cost Management

| Resource | Cost | Notes |
|---|---|---|
| Container Instance (2 CPU, 4GB) | ~$0.09/hour running | Stop when not in use |
| Azure Blob Storage (~50MB) | ~$0.001/month | Negligible |
| Container Registry (Basic) | ~$5/month | Fixed cost |
| Groq API | Free tier | Generous limits for this use case |

**Running cost estimate:**
- 8 hours/day → ~$0.72/day → ~$22/month (container only)
- Always stop the container after use: Azure Portal → ncert-qa-bot → Stop
- Start before use: Azure Portal → ncert-qa-bot → Start
- App takes 2-3 minutes to be ready after start (BGE models load from HuggingFace)

---

## 17. Platforms Used

| Platform | Purpose |
|---|---|
| [Groq Console](https://console.groq.com) | Free LLM API — Llama 3.3 70B inference |
| [HuggingFace](https://huggingface.co) | BGE embedding and reranker model weights |
| [Azure Portal](https://portal.azure.com) | Storage Account, Container Registry, Container Instance |
| [Azure Cloud Shell](https://portal.azure.com) | Running `az container create` and logs commands from browser |
| [GitHub](https://github.com/divyaitiz/PariShiksha) | Code hosting, CI/CD via GitHub Actions, Secrets management |
| [Docker Desktop](https://docker.com) | Building and testing container locally |
| VS Code | Development, editing pipeline files |
| PowerShell | Running `git`, `docker`, `python` commands on Windows |

---

## 18. App Screenshots

Screenshots of the running application are available at:

**[images_running_app/](https://github.com/divyaitiz/PariShiksha/tree/main/images_running_app)**

Screenshots include the app answering:
- "What is motion?" — with retrieved sources from Chapter 7
- "Give formulas of motion" — with equations v=u+at, s=ut+½at², v²-u²=2as
- "Laws of motion" — with all three Newton's laws cited from Chapter 8
- "What is evaporation?" — with Chapter 1 source citations

---

*Built as part of IITGN LLMOps project — May 2026*
