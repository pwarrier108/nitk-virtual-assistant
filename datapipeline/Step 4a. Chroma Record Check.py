from pathlib import Path
import chromadb

client = chromadb.PersistentClient(path=str(Path("outputs/chroma_db")))
collection = client.get_collection("nitk_knowledgebase")

# Get count and sample record
result = collection.get(limit=1)
print(f"Sample record metadata: {result['metadatas'][0] if result['metadatas'] else 'None'}")
count = collection.count()
print(f"\nTotal records in collection: {count}")