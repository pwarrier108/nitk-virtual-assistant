# Standard library imports
import logging
import re
from functools import lru_cache
from typing import Any, Dict, List

# Third-party imports
from sentence_transformers import SentenceTransformer


logger = logging.getLogger(__name__)


class VectorSearchService:
    def __init__(self, config, embedder: SentenceTransformer):
        self.config = config
        self.embedder = embedder
    
    @lru_cache(maxsize=200)
    def preprocess_text(self, text: str) -> tuple[str, float]:
        """Preprocess and clean text for search."""
        import time
        preprocess_start = time.time()
        text = re.sub(r'@\w+', '', text)
        text = re.sub(r'#\w+', '', text)
        text = re.sub(r'http\S+|www.\S+', '', text)
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        text = text.strip()
        preprocess_time = time.time() - preprocess_start
        return text, preprocess_time

    @lru_cache(maxsize=200)
    def get_embedding(self, text: str) -> list:
        """Generate embedding for text."""
        return self.embedder.encode(text, show_progress_bar=False).tolist()

    def entity_first_search(self, collection, query_text: str, entity: Dict) -> List[Dict]:
        """Perform entity-focused search in collection."""
        try:
            query_embedding = self.get_embedding(query_text)
            results = collection.query(
                query_embeddings=[query_embedding],
                where_document={"$contains": entity["text"]},
                n_results=self.config.DEFAULT_RESULTS * 2
            )

            if not results.get('documents'):
                return []

            return [
                {
                    'document': doc,
                    'metadata': meta,
                    'distance': dist,
                    'exact_match': True
                }
                for doc, meta, dist in zip(
                    results['documents'][0],
                    results['metadatas'][0], 
                    results['distances'][0]
                )
            ]
                
        except Exception as e:
            logger.error(f"Entity search error: {str(e)}")
            return []

    def semantic_search(self, collection, query_text: str, n_results: int = None) -> List[Dict]:
        """Perform semantic search in collection."""
        if n_results is None:
            n_results = self.config.DEFAULT_RESULTS * 3
            
        query_embedding = self.get_embedding(query_text)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        return [
            {
                'document': doc,
                'metadata': meta,
                'distance': dist
            }
            for doc, meta, dist in zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )
        ]
