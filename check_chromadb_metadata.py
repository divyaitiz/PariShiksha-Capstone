import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("ncert_science")

results = collection.get(limit=3, include=["metadatas"])

for i, meta in enumerate(results["metadatas"]):
    print(f"\n--- Chunk {i+1} ---")
    for key, value in meta.items():
        print(f"  {key}: {value}")


#checks sections available in the metadata
results = collection.get(limit=500, include=["metadatas"])
types = set(m["section_type"] for m in results["metadatas"])
print(types)