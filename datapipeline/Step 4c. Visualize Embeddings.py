import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
from mpl_toolkits.mplot3d import Axes3D
from sklearn.cluster import DBSCAN
import chromadb
import numpy as np
import unicodedata
from typing import List, Dict, Any

def get_display_title(metadata, index):
    title = metadata.get("title", f"Doc {index+1}")
    return ''.join(char for char in unicodedata.normalize('NFKD', str(title)) 
                  if unicodedata.category(char)[0] != 'M' and ord(char) < 128)[:20]

def visualize_embeddings_2d(client, collection_name="nitk_knowledgebase"):
    collection = client.get_collection(name=collection_name)
    results = collection.get(include=["embeddings", "metadatas", "documents"])
    embeddings = np.array(results["embeddings"])
    
    tsne = TSNE(n_components=2, perplexity=30, early_exaggeration=12, 
                learning_rate=200, max_iter=1000, random_state=42)
    reduced_embeddings = tsne.fit_transform(embeddings)
    
    plt.figure(figsize=(14, 10))
    plt.subplots_adjust(right=0.85)
    
    for i, (x, y) in enumerate(reduced_embeddings):
        label = results["documents"][i] if results.get("documents") else f"Doc {i+1}"
        label = ''.join(c for c in label if ord(c) < 128)
        label = label[:30].strip()
        plt.scatter(x, y, label=label, s=50, alpha=0.6)
    
    plt.title(f"2D Document Embedding Visualization (n={len(embeddings)})")
    plt.xlabel("t-SNE 1")
    plt.ylabel("t-SNE 2")
    plt.legend(bbox_to_anchor=(1.05, 1), fontsize='xx-small')
    plt.show()
    return reduced_embeddings, results

def visualize_embeddings_3d(client, collection_name="nitk_knowledgebase"):
    collection = client.get_collection(name=collection_name)
    results = collection.get(include=["embeddings", "metadatas", "documents"])
    embeddings = np.array(results["embeddings"])
    
    tsne = TSNE(n_components=3, perplexity=30, early_exaggeration=12,
                learning_rate=200, max_iter=1000, random_state=42)
    reduced_embeddings = tsne.fit_transform(embeddings)
    
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')
    
    for i, (x, y, z) in enumerate(reduced_embeddings):
        label = results["documents"][i] if results.get("documents") else f"Doc {i+1}"
        label = ''.join(c for c in label if ord(c) < 128)
        label = label[:30].strip()
        ax.scatter(x, y, z, label=label, s=50, alpha=0.6)
    
    ax.set_title(f"3D Document Embedding Visualization (n={len(embeddings)})")
    ax.set_xlabel("t-SNE 1")
    ax.set_ylabel("t-SNE 2")
    ax.set_zlabel("t-SNE 3")
    plt.legend(bbox_to_anchor=(1.05, 1), fontsize='xx-small')
    plt.show()
    return reduced_embeddings, results

def analyze_clusters(embeddings: np.ndarray, results: Dict[str, Any], region: str) -> List[str]:
    # Define regions
    regions = {
        "lower_left": lambda x, y: x < -20 and y < -40,
        "top_right": lambda x, y: x > 20 and y > 20,
        "middle": lambda x, y: abs(x) < 20 and abs(y) < 20
    }
    
    # Filter points in the specified region
    mask = np.array([regions[region](x, y) for x, y in embeddings])
    region_embeddings = embeddings[mask]
    region_docs = np.array(results["documents"])[mask]
    
    # Cluster analysis using DBSCAN
    clustering = DBSCAN(eps=5, min_samples=3).fit(region_embeddings)
    
    # Group documents by cluster
    clusters = {}
    for doc, label in zip(region_docs, clustering.labels_):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(doc)
    
    # Return cluster summaries
    summaries = []
    for label, docs in clusters.items():
        if label != -1:  # Exclude noise points
            summaries.append(f"Cluster {label}: {len(docs)} documents")
            summaries.extend([f"- {doc[:100]}..." for doc in docs[:3]])
    
    return summaries

if __name__ == "__main__":
    client = chromadb.PersistentClient(path="outputs/chroma_db")
    
    # # 2D Visualization
    embeddings_2d, results = visualize_embeddings_2d(client)
    
    # 3D Visualization
    embeddings_3d, _ = visualize_embeddings_3d(client)
    
    # Cluster Analysis
    print("\nLower Left Cluster Analysis:")
    print("\n".join(analyze_clusters(embeddings_2d, results, "lower_left")))
    
    print("\nTop Right Cluster Analysis:")
    print("\n".join(analyze_clusters(embeddings_2d, results, "top_right")))
    
    print("\nMiddle Cluster Analysis:")
    print("\n".join(analyze_clusters(embeddings_2d, results, "middle")))