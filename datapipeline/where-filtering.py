import chromadb

def basic_filtering_example():
    client = chromadb.Client()
    
    # Create collection
    collection = client.create_collection(name="filter_example_collection")
    
    # Add data
    collection.add(
        embeddings=[
            [1.1, 2.3, 3.2],
            [4.5, 6.9, 4.4],
            [1.1, 2.3, 3.2],
            [4.5, 6.9, 4.4],
            [1.1, 2.3, 3.2],
            [4.5, 6.9, 4.4],
            [1.1, 2.3, 3.2],
            [4.5, 6.9, 4.4],
        ],
        metadatas=[
            {"status": "read"} for _ in range(4)
        ] + [{"status": "unread"} for _ in range(4)],
        documents=[
            "A document that discusses domestic policy",
            "A document that discusses international affairs",
            "A document that discusses kittens",
            "A document that discusses dogs",
            "A document that discusses chocolate",
            "A document that is sixth that discusses government",
            "A document that discusses international affairs",
            "A document that discusses global affairs"
        ],
        ids=[f"id{i}" for i in range(1, 9)]
    )
    
    # Example queries
    print("Documents that are read and about affairs:")
    print(collection.get(
        where={"status": "read"},
        where_document={"$contains": "affairs"}
    ))
    
    print("\nDocuments about global affairs or domestic policy:")
    print(collection.get(
        where_document={"$or": [
            {"$contains": "global affairs"},
            {"$contains": "domestic policy"}
        ]}
    ))
    
    print("\n5 closest vectors to [0,0,0] about affairs:")
    print(collection.query(
        query_embeddings=[[0, 0, 0]],
        where_document={"$contains": "affairs"},
        n_results=5
    ))

def logical_operators_example():
    client = chromadb.Client()
    collection = client.get_or_create_collection("test-where-list")
    
    # Add data with authors and categories
    collection.upsert(
        documents=[
            "Article by john",
            "Article by Jack",
            "Article by Jill"
        ],
        metadatas=[
            {"author": "john", "category": "chroma"},
            {"author": "jack", "category": "ml"},
            {"author": "jill", "category": "lifestyle"}
        ],
        ids=["1", "2", "3"]
    )
    
    print("OR operator - Articles by john or jack:")
    print(collection.get(
        where={"$or": [
            {"author": "john"},
            {"author": "jack"}
        ]}
    ))
    
    print("\nAND operator - Articles by john in chroma category:")
    print(collection.get(
        where={"$and": [
            {"category": "chroma"},
            {"author": "john"}
        ]}
    ))
    
    print("\nCombined AND/OR - Articles in chroma category by john or jack:")
    print(collection.get(
        where={"$and": [
            {"category": "chroma"},
            {"$or": [
                {"author": "john"},
                {"author": "jack"}
            ]}
        ]}
    ))

if __name__ == "__main__":
    print("=== Basic Filtering Examples ===")
    basic_filtering_example()
    print("\n=== Logical Operators Examples ===")
    logical_operators_example()