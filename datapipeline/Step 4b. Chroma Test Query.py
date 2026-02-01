from pathlib import Path
import chromadb
import json

def run_queries():
    client = chromadb.PersistentClient(path=str(Path("outputs/chroma_db")))
    collection = client.get_collection("nitk_knowledgebase")
    
    results = {
        "first_document": collection.get(limit=1),
        "convocation_documents": collection.get(
            where_document={"$contains": "Convocation"}
        ),
        "constitution_day_documents": collection.get(
            where={"created_date": "2024-11-27T05:24:06.000Z"}
        ),
        "ambedkar_documents": collection.get(
            where_document={"$contains": "Ambedkar"}
        ),
        "instagram_nov22_documents": collection.get(
            where={
                "$and": [
                    {"platform": "instagram"},
                    {"created_date": "2024-11-22T14:30:30.000Z"}
                ]
            }
        )
    }
    
    results_dir = Path('results')
    results_dir.mkdir(exist_ok=True)
    
    with open(results_dir / 'testresults.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    run_queries()