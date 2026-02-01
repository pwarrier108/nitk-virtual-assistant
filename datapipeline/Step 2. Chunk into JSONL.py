import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import nltk
from nltk.tokenize import sent_tokenize
import spacy
from tqdm import tqdm

def setup_nltk_resources():
   required_resources = ['punkt']
   for resource in required_resources:
       try:
           nltk.data.find(resource)
       except LookupError:
           nltk.download(resource)

class Config:
   def __init__(self):
       # Base directories
       # TODO: Fix cross-platform path handling - Use forward slashes or Path() for Windows/Linux compatibility
       # Current implementation uses Windows-specific backslashes which will fail on Linux/Mac
       self.INPUT_DIR = Path(r"outputs\instagram")
       self.OUTPUT_DIR = Path(r"outputs\instagram\output-chunks")
       self.LOG_DIR = Path("logs")

       # File configurations
       self.INPUT_FILENAME = "processed_instagram.json"
       self.OUTPUT_FILENAME = "processed_chunks.jsonl"
       self.LOG_FILENAME_PREFIX = "chunk_processing"
       self.LOG_FILENAME_EXT = ".log"

       # Processing parameters
       self.CHUNK_TARGET_SIZE = 512
       self.CHUNK_OVERLAP = 100
       self.DEBUG = True
       self.MIN_SENTENCES_PER_CHUNK = 2

   def setup_directories(self):
       for dir_path in [self.INPUT_DIR, self.OUTPUT_DIR, self.LOG_DIR]:
           dir_path.mkdir(parents=True, exist_ok=True)

   def get_input_filepath(self) -> Path:
       return self.INPUT_DIR / self.INPUT_FILENAME

   def get_output_filepath(self) -> Path:
       return self.OUTPUT_DIR / self.OUTPUT_FILENAME
       
   def get_log_filepath(self, timestamp: str) -> Path:
       return self.LOG_DIR / f"{self.LOG_FILENAME_PREFIX}_{timestamp}{self.LOG_FILENAME_EXT}"

class SemanticChunker:
    def __init__(self, target_size: int, overlap_size: int, min_sentences: int):
        self.target_size = target_size
        self.overlap_size = overlap_size
        self.min_sentences = min_sentences
        # TODO: Add error handling if spaCy model not installed
        # Suggestion: try/except with helpful error message to run: python -m spacy download en_core_web_sm
        self.nlp = spacy.load("en_core_web_sm")

    def _create_metadata(self, post: Dict, chunk_index: int) -> Dict:
        # Updated metadata creation method
        metadata = {
            'source_id': post['source_id'],
            'created_date': post['created_date'],
            'author': post.get('author_name'),
            'platform': post['platform'],
            'entities': post['content'].get('entities', {}),
            'chunk_position': chunk_index + 1
        }
        
        # Add social media specific fields if they exist
        if 'hashtags' in post:
            metadata['hashtags'] = post['hashtags']
        if 'mentions' in post:
            metadata['mentions'] = post['mentions']
        if 'source_url' in post:
            metadata['source_url'] = post['source_url']
            
        return metadata

    def _merge_short_chunks(self, chunks: List[str], min_size: int = 100) -> List[str]:
        """Merge chunks that are too short with neighboring chunks."""
        if not chunks:
            return chunks

        result = []
        current_chunk = chunks[0]

        for next_chunk in chunks[1:]:
            if len(current_chunk) < min_size or len(next_chunk) < min_size:
                current_chunk = f"{current_chunk} {next_chunk}"
            else:
                result.append(current_chunk)
                current_chunk = next_chunk

        result.append(current_chunk)
        return result

    def _is_complete_sentence(self, text: str) -> bool:
        """Check if text ends with sentence-ending punctuation."""
        return bool(re.search(r'[.!?][\s]*$', text.strip()))

    def split_text(self, post: Dict) -> List[Dict[str, Any]]:
        text = post['content']['text']
        
        # Split on semantic boundaries first
        sections = self._split_into_sections(text)
        chunks = []
        
        for section in sections:
            if not section.strip():
                continue
            
            # Process each section
            sentences = list(self.nlp(section).sents)
            current_chunk = []
            current_size = 0
            
            for i, sent in enumerate(sentences):
                sent_text = sent.text.strip()
                sent_size = len(sent_text)
                
                # Handle very long sentences
                if sent_size > self.target_size:
                    if current_chunk:
                        chunks.append({
                            'text': ' '.join(current_chunk).strip(),
                            'metadata': self._create_metadata(post, len(chunks))
                        })
                        current_chunk = []
                        current_size = 0
                    
                    # TODO: Extract clause splitting logic to separate method for better testability
                    # TODO: Add unit tests for edge cases (nested clauses, complex sentences)
                    # Split long sentence on clauses or phrases
                    doc = self.nlp(sent_text)
                    clause_splits = []
                    for token in doc:
                        if token.dep_ in ['cc', 'punct'] and token.head.dep_ == 'ROOT':
                            clause_splits.append(token.i)
                    
                    if clause_splits:
                        prev_split = 0
                        for split_idx in clause_splits:
                            clause = doc[prev_split:split_idx].text.strip()
                            if clause:
                                chunks.append({
                                    'text': clause,
                                    'metadata': self._create_metadata(post, len(chunks))
                                })
                            prev_split = split_idx + 1
                        final_clause = doc[prev_split:].text.strip()
                        if final_clause:
                            chunks.append({
                                'text': final_clause,
                                'metadata': self._create_metadata(post, len(chunks))
                            })
                    else:
                        chunks.append({
                            'text': sent_text,
                            'metadata': self._create_metadata(post, len(chunks))
                        })
                    continue
                
                # Check if adding this sentence would exceed target size
                if current_size + sent_size > self.target_size:
                    # Only split if we have enough sentences or at a good breaking point
                    if len(current_chunk) >= self.min_sentences or self._is_complete_sentence(' '.join(current_chunk)):
                        chunks.append({
                            'text': ' '.join(current_chunk).strip(),
                            'metadata': self._create_metadata(post, len(chunks))
                        })
                        current_chunk = [sent_text]
                        current_size = sent_size
                    else:
                        current_chunk.append(sent_text)
                        current_size += sent_size
                else:
                    current_chunk.append(sent_text)
                    current_size += sent_size
                
                # Check if we're at a natural breaking point
                if i < len(sentences) - 1 and current_size >= self.target_size * 0.8:
                    if self._is_complete_sentence(' '.join(current_chunk)):
                        chunks.append({
                            'text': ' '.join(current_chunk).strip(),
                            'metadata': self._create_metadata(post, len(chunks))
                        })
                        current_chunk = []
                        current_size = 0
            
            # Add remaining sentences
            if current_chunk:
                chunks.append({
                    'text': ' '.join(current_chunk).strip(),
                    'metadata': self._create_metadata(post, len(chunks))
                })
        
        # Post-process: merge very short chunks
        if chunks:
            merged_chunks = []
            current = chunks[0]
            
            for next_chunk in chunks[1:]:
                # TODO: Extract magic number 100 to Config.MIN_CHUNK_SIZE constant
                if len(current['text']) < 100:  # Minimum chunk size threshold
                    current['text'] = f"{current['text']} {next_chunk['text']}"
                    current['metadata']['chunk_position'] = len(merged_chunks) + 1
                else:
                    merged_chunks.append(current)
                    current = next_chunk
                    current['metadata']['chunk_position'] = len(merged_chunks) + 1
            
            merged_chunks.append(current)
            chunks = merged_chunks
        
        return chunks

    def _split_into_sections(self, text: str) -> List[str]:
        # Previous section splitting logic remains the same
        patterns = [
            r'\n\s*[\u2022\u2023\u2043\u2219]',
            r'\n\s*\d+\.',
            r'\n\s*[A-Z]\.',
            r'\. [A-Z][^.!?]*:',
            r'\n\n',
            r'\(\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm|AM|PM)?\)',
            r'\d{1,2}(?:st|nd|rd|th)',
            r'Session:',
            r'Part:',
            r'Featuring',
            r'Highlights:',
            r'Include[s]?:',
            r'Following:',
            r'Venue:',
            r'Location:',
            r'Place:'
        ]
        
        pattern = '|'.join(patterns)
        segments = re.split(f'({pattern})', text)
        
        sections = []
        current_section = ""
        
        for i, segment in enumerate(segments):
            if not segment.strip():
                continue
                
            current_section += segment
            
            if re.match(pattern, segment):
                continue
                
            if i + 1 >= len(segments) or re.match(pattern, segments[i + 1]):
                if current_section.strip():
                    sections.append(current_section.strip())
                current_section = ""
        
        if current_section.strip():
            sections.append(current_section.strip())
        
        return sections

class JSONChunkProcessor:
   def __init__(self, config: Config):
       self.config = config
       self.config.setup_directories()
       self.chunker = SemanticChunker(
           config.CHUNK_TARGET_SIZE,
           config.CHUNK_OVERLAP,
           config.MIN_SENTENCES_PER_CHUNK
       )
       
       if self.config.DEBUG:
           self._setup_logging()

   def _setup_logging(self):
       timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
       log_file = self.config.get_log_filepath(timestamp)
       
       logging.basicConfig(
           level=logging.DEBUG,
           format='%(asctime)s - %(levelname)s - %(message)s',
           handlers=[
               logging.FileHandler(log_file),
               logging.StreamHandler()
           ]
       )
       self.logger = logging.getLogger(__name__)

   def process_document(self, json_post: Dict) -> List[Dict[str, Any]]:
       if self.config.DEBUG:
           self.logger.debug(f"Processing post: {json_post['source_id']}")
       
       try:
           chunks = self.chunker.split_text(json_post)
           
           if self.config.DEBUG:
               self.logger.debug(f"Created {len(chunks)} chunks for {json_post['source_id']}")
           
           return chunks
           
       except Exception as e:
           if self.config.DEBUG:
               self.logger.error(f"Error processing {json_post['source_id']}: {str(e)}")
           return []

   def process_all(self):
       if not self.config.INPUT_DIR.exists():
           raise FileNotFoundError(f"Input folder {self.config.INPUT_DIR} does not exist")

       input_file = self.config.get_input_filepath()
       if not input_file.exists():
           raise FileNotFoundError(f"Input file {input_file} does not exist")
           
       if self.config.DEBUG:
           self.logger.info(f"Processing input file: {input_file}")

       all_chunks = []
       # TODO: Add file size validation before loading into memory (prevent OOM errors)
       # TODO: Implement streaming JSON parser for large files (use ijson library)
       try:
           with open(input_file, 'r', encoding='utf-8') as f:
               json_posts = json.load(f)
               
           if not isinstance(json_posts, list):
               json_posts = [json_posts]
               
           for post in tqdm(json_posts, desc="Processing posts"):
               chunks = self.process_document(post)
               all_chunks.extend(chunks)
               
       except Exception as e:
           if self.config.DEBUG:
               self.logger.error(f"Error processing {input_file}: {str(e)}")

       if not all_chunks:
           raise ValueError("No chunks were processed")

       output_file = self.config.get_output_filepath()
       with open(output_file, 'w', encoding='utf-8') as f:
           for chunk in all_chunks:
               f.write(json.dumps(chunk) + "\n")

       if self.config.DEBUG:
           self.logger.info(f"Successfully processed {len(all_chunks)} chunks")
           self.logger.info(f"Output saved to {output_file}")

       return len(all_chunks)

def main():
   setup_nltk_resources()
   
   config = Config()
   config.DEBUG = True
   processor = JSONChunkProcessor(config)
   
   try:
       total_chunks = processor.process_all()
       print(f"Successfully processed {total_chunks} chunks")
   except Exception as e:
       print(f"Error during processing: {str(e)}")
       if config.DEBUG:
           import traceback
           traceback.print_exc()

if __name__ == "__main__":
   main()