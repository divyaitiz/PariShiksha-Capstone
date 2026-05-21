"""
azure_sync.py
=============
Downloads the chroma_db/ folder from Azure Blob Storage
on container startup so ChromaDB is available to rag_chain.py.

Run automatically by the Dockerfile CMD before Streamlit launches.

Environment variables required (set in Azure Web App settings):
    AZURE_STORAGE_CONNECTION_STRING   — from your Storage Account
    AZURE_BLOB_CONTAINER              — e.g. "ncert-chromadb"

Usage:
    python azure_sync.py              # download on startup
    python azure_sync.py --upload     # upload after rebuilding vectorstore
"""

import os
import sys
import argparse
from pathlib import Path

LOCAL_CHROMA_DIR = Path("./chroma_db")
BLOB_PREFIX      = "chroma_db/"          # folder prefix inside the container


def get_client():
    conn_str  = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    container = os.environ.get("AZURE_BLOB_CONTAINER", "ncert-chromadb")

    if not conn_str:
        print(
            "[azure_sync] WARNING: AZURE_STORAGE_CONNECTION_STRING not set.\n"
            "  Skipping sync — using local chroma_db/ if it exists."
        )
        return None, None

    from azure.storage.blob import BlobServiceClient
    service   = BlobServiceClient.from_connection_string(conn_str)
    container_client = service.get_container_client(container)

    # Create container if it doesn't exist yet
    try:
        container_client.create_container()
        print(f"[azure_sync] Created blob container: {container}")
    except Exception:
        pass  # already exists

    return service, container_client


def download(container_client):
    """Download all blobs under chroma_db/ prefix to local chroma_db/."""
    print("[azure_sync] Downloading chroma_db from Azure Blob Storage...")
    LOCAL_CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    blobs = list(container_client.list_blobs(name_starts_with=BLOB_PREFIX))

    if not blobs:
        print("[azure_sync] No blobs found — vectorstore not yet uploaded.")
        return

    for blob in blobs:
        # blob.name = "chroma_db/chroma.sqlite3" etc.
        relative  = blob.name[len(BLOB_PREFIX):]          # strip prefix
        local_path = LOCAL_CHROMA_DIR / relative

        local_path.parent.mkdir(parents=True, exist_ok=True)

        blob_client = container_client.get_blob_client(blob.name)
        with open(local_path, "wb") as f:
            data = blob_client.download_blob()
            data.readinto(f)

        print(f"  ✓ {blob.name}")

    print(f"[azure_sync] Download complete — {len(blobs)} files.")


def upload(container_client):
    """Upload local chroma_db/ folder to Azure Blob Storage."""
    if not LOCAL_CHROMA_DIR.exists():
        print("[azure_sync] ERROR: chroma_db/ not found locally. Run build_vectorstore.py first.")
        sys.exit(1)

    files = list(LOCAL_CHROMA_DIR.rglob("*"))
    files = [f for f in files if f.is_file()]

    print(f"[azure_sync] Uploading {len(files)} files to Azure Blob Storage...")

    for local_path in files:
        relative  = local_path.relative_to(LOCAL_CHROMA_DIR)
        blob_name = BLOB_PREFIX + str(relative).replace("\\", "/")

        blob_client = container_client.get_blob_client(blob_name)
        with open(local_path, "rb") as f:
            blob_client.upload_blob(f, overwrite=True)

        print(f"  ↑ {blob_name}")

    print(f"[azure_sync] Upload complete — {len(files)} files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", action="store_true",
                        help="Upload local chroma_db/ to Azure Blob")
    args = parser.parse_args()

    _, container_client = get_client()

    if container_client is None:
        sys.exit(0)   # no connection string — skip silently

    if args.upload:
        upload(container_client)
    else:
        download(container_client)
