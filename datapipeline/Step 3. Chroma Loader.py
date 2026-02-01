from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import chromadb
import json
import logging
import re
import spacy

class Config:
    def __init__(self):
        self.INPUT_FILE = Path(r"outputs\website\output-chunks\processed_nitk_chunks.jsonl")
        # self.INPUT_FILE = Path(r"outputs\website\output-chunks\processed_irisblog_chunks.jsonl")
        # self.INPUT_FILE = Path(r"outputs\linkedin\output-chunks\processed_chunks.jsonl")
        # self.INPUT_FILE = Path(r"outputs\instagram\output-chunks\processed_chunks.jsonl")
        self.PERSIST_DIRECTORY = Path(r"outputs\chroma_db")
        self.LOG_DIR = Path("logs")
        self.COLLECTION_NAME = "nitk_knowledgebase"
        self.EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
        self.BATCH_SIZE = 500
        self.MIN_RELEVANCE_SCORE = 0.7
        self.DEFAULT_RESULTS = 5
        self.MAX_RECORDS = -1  # Process all records
        self.DEBUG = True

    def setup_directories(self):
        self.PERSIST_DIRECTORY.mkdir(parents=True, exist_ok=True)
        if self.DEBUG:
            self.LOG_DIR.mkdir(parents=True, exist_ok=True)

class ChromaLoader:
    def __init__(self, config: Config):
        self.config = config
        self.config.setup_directories()
        self.client = chromadb.PersistentClient(
            path=str(self.config.PERSIST_DIRECTORY)
        )
        self.embedding_model = SentenceTransformer(self.config.EMBEDDING_MODEL)
        self.nlp = spacy.load("en_core_web_sm")
        self.stats = {'total': 0, 'loaded': 0, 'skipped': 0, 'errors': []}
        
        if self.config.DEBUG:
            self._setup_logging()

    def _setup_logging(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.config.LOG_DIR / f'chroma_loading_{timestamp}.log'
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
        )
        self.logger = logging.getLogger(__name__)

    def _flatten_metadata(self, metadata: Dict) -> Dict:
        flat_metadata = {}
        
        if 'entities' in metadata:
            try:
                entities = json.loads(metadata['entities']) if isinstance(metadata['entities'], str) else metadata['entities']
                for entity_type, values in entities.items():
                    flat_key = f"{entity_type.lower()}s"
                    if isinstance(values, list):
                        flat_metadata[flat_key] = json.dumps(values)
                    else:
                        if self.config.DEBUG:
                            self.logger.warning(f"Unexpected entity values format: {values}")
                del metadata['entities']
            except Exception as e:
                if self.config.DEBUG:
                    self.logger.error(f"Failed to process entities: {str(e)}")
                self.stats['errors'].append(f"Entity processing error: {str(e)}")

        for k, v in metadata.items():
            if isinstance(v, (str, int, float)):
                flat_metadata[k] = v
            else:
                try:
                    flat_metadata[k] = json.dumps(v)
                except Exception as e:
                    if self.config.DEBUG:
                        self.logger.error(f"Failed to process metadata field {k}: {str(e)}")
                    self.stats['errors'].append(f"Metadata processing error for {k}: {str(e)}")

        return flat_metadata

    def load_jsonl(self):
        if self.config.DEBUG:
            self.logger.info("Starting document loading process...")
        
        collection = self.client.get_or_create_collection(
            name=self.config.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        
        documents, metadatas, ids = [], [], []
        processed_ids = set()
        
        # Count total records
        with open(self.config.INPUT_FILE, 'r', encoding='utf-8') as f:
            for i, _ in enumerate(f):
                if self.config.MAX_RECORDS > 0 and i >= self.config.MAX_RECORDS:
                    break
                self.stats['total'] += 1
        
        with open(self.config.INPUT_FILE, 'r', encoding='utf-8') as f:
            for line in tqdm(f, total=self.stats['total'], desc="Processing documents"):
                try:
                    record = json.loads(line)
                    content = record.get('text')
                    metadata = record.get('metadata', {})
                    source_id = metadata.get('source_id')
                    chunk_position = metadata.get('chunk_position')
                    
                    unique_id = f"{source_id}_{chunk_position}"
                    
                    if not content or not source_id or unique_id in processed_ids:
                        self.stats['skipped'] += 1
                        continue
                        
                    processed_ids.add(unique_id)
                    flattened_metadata = self._flatten_metadata(metadata)
                    
                    documents.append(content)
                    metadatas.append(flattened_metadata)
                    ids.append(unique_id)
                    
                    if len(documents) >= self.config.BATCH_SIZE:
                        self._process_batch(collection, documents, metadatas, ids)
                        documents, metadatas, ids = [], [], []
                        
                except Exception as e:
                    if self.config.DEBUG:
                        self.logger.error(f"Error processing record: {str(e)}")
                    self.stats['errors'].append(f"Record processing error: {str(e)}")
                    self.stats['skipped'] += 1
                    continue
        
        if documents:
            self._process_batch(collection, documents, metadatas, ids)
        
        if self.config.DEBUG:
            self.logger.info("\nProcessing complete. Final statistics:")
            self.logger.info(f"Total processed: {self.stats['total']}")
            self.logger.info(f"Successfully loaded: {self.stats['loaded']}")
            self.logger.info(f"Skipped: {self.stats['skipped']}")
            self.logger.info("\nErrors encountered:")
            for error in self.stats['errors']:
                self.logger.info(f"- {error}")
        
        return self.stats

    def _process_batch(self, collection, documents, metadatas, ids):
        try:
            embeddings = self.embedding_model.encode(documents, show_progress_bar=False)
            
            collection.add(
                documents=documents,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
                ids=ids
            )
            self.stats['loaded'] += len(documents)
            
            if self.config.DEBUG:
                self.logger.info(f"Successfully added {len(documents)} documents to collection")
            
        except Exception as e:
            if self.config.DEBUG:
                self.logger.error(f"Batch processing error: {str(e)}")
            self.stats['errors'].append(f"Batch processing error: {str(e)}")

def main():
    config = Config()
    loader = ChromaLoader(config)
    loader.load_jsonl()

if __name__ == "__main__":
    main()