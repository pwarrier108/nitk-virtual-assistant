import requests
import logging
import time
import re
from typing import Generator, Optional
from config import WebUIConfig

logger = logging.getLogger(__name__)

class RAGClient:
    """
    Simple API client for RAG service that mimics the original assistant.query() behavior
    Now with cache control support - respects cache_safe flag from service
    """
    
    def __init__(self, config: WebUIConfig):
        self.config = config
        self.base_url = config.rag_service_url
        self.session = requests.Session()
        self.last_response_cache_safe = True
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
        
    def query(self, question: str, response_format: str) -> Generator[str, None, None]:
        """
        Query the RAG service and yield response chunks with cache-aware formatting.
        Now respects cache_safe flag from service to control client-side processing.
        """
        try:
            logger.info(f"Sending query to RAG service: {question[:50]}...")
            
            # Make API call with specified format
            response = self.session.post(
                f"{self.base_url}/query",
                json={
                    "question": question,
                    "format": response_format
                },
                timeout=self.config.rag_service_timeout
            )
            
            if response.status_code != 200:
                error_msg = f"API Error {response.status_code}: {response.text}"
                logger.error(error_msg)
                yield f"Error: {error_msg}"
                return
            
            # Parse response
            result = response.json()
            response_text = result.get('response', 'No response received')
            cache_safe = result.get('cache_safe', True)  # Default to cache-safe for backward compatibility
            self.last_response_cache_safe = cache_safe
            
            # Log cache status for debugging
            cache_status = "cache-safe" if cache_safe else "temporal (no-cache)"
            logger.info(f"Received response: {len(response_text)} characters ({cache_status})")
            
            # Choose chunking strategy based on cache safety
            if cache_safe:
                # Cache-safe content: Use smart chunking for better presentation
                if self.config.smart_chunking:
                    yield from self._smart_chunk_response(response_text)
                else:
                    yield from self._simple_chunk_response(response_text)
            else:
                # Temporal content: Stream more naturally (no aggressive caching optimizations)
                yield from self._temporal_stream_response(response_text)
            
        except requests.exceptions.Timeout:
            error_msg = "Request timed out. Please try again."
            logger.error(error_msg)
            yield error_msg
            
        except requests.exceptions.ConnectionError:
            error_msg = "Unable to connect to RAG service. Please ensure the service is running."
            logger.error(error_msg)
            yield error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            yield error_msg
    
    def _smart_chunk_response(self, response_text: str) -> Generator[str, None, None]:
        """
        Smart chunking for cache-safe content that respects markdown structure.
        Used for static RAG responses that benefit from structured presentation.
        """
        # Split by lines first to handle bullets and numbered lists
        lines = response_text.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                # Empty line - yield newline and pause
                yield '\n'
                time.sleep(self.config.paragraph_pause)
                continue
            
            # Check if this is a bullet point or numbered list
            is_bullet = re.match(r'^[*\-•]\s+', line)
            is_numbered = re.match(r'^\d+\.\s+', line)
            is_header = re.match(r'^#+\s+', line)
            
            if is_bullet or is_numbered or is_header:
                # Yield the entire bullet/numbered item at once
                yield line
                if i < len(lines) - 1:  # Not the last line
                    yield '\n'
                time.sleep(self.config.bullet_pause)
            else:
                # Regular text - chunk by sentences
                yield from self._chunk_by_sentences(line)
                if i < len(lines) - 1:  # Not the last line
                    yield '\n'
                    time.sleep(self.config.sentence_pause)
    
    def _temporal_stream_response(self, response_text: str) -> Generator[str, None, None]:
        """
        Natural streaming for temporal content (current information).
        More fluid delivery appropriate for fresh, time-sensitive information.
        """
        # For temporal content, use word-by-word streaming for more natural flow
        words = response_text.split()
        chunk_size = min(self.config.streaming_chunk_size, 2)  # Smaller chunks for temporal
        
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i + chunk_size])
            if i + chunk_size < len(words):
                chunk += ' '
            yield chunk
            # Slightly faster streaming for temporal content
            time.sleep(self.config.streaming_delay * 0.8)
    
    def _chunk_by_sentences(self, text: str) -> Generator[str, None, None]:
        """
        Chunk regular text by sentences for better readability.
        Used for cache-safe content where structure matters.
        """
        # Split by sentence endings but keep the punctuation
        sentences = re.split(r'([.!?]+\s*)', text)
        
        current_chunk = ""
        for part in sentences:
            current_chunk += part
            
            # If this part ends with sentence punctuation, yield the chunk
            if re.match(r'[.!?]+\s*$', part):
                if current_chunk.strip():
                    yield current_chunk
                    current_chunk = ""
                    time.sleep(self.config.sentence_pause)
        
        # Yield any remaining text
        if current_chunk.strip():
            yield current_chunk
    
    def _simple_chunk_response(self, response_text: str) -> Generator[str, None, None]:
        """
        Fallback simple chunking by words (original behavior).
        Used when smart chunking is disabled.
        """
        words = response_text.split()
        chunk_size = self.config.streaming_chunk_size
        
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i + chunk_size])
            if i + chunk_size < len(words):
                chunk += ' '
            yield chunk
            time.sleep(self.config.streaming_delay)
    
    def health_check(self) -> bool:
        """
        Check if the RAG service is available.
        """
        try:
            response = self.session.get(
                f"{self.base_url}/health", 
                timeout=self.config.rag_service_health_timeout
            )
            return response.status_code == 200
        except:
            return False
    
    def get_stats(self) -> Optional[dict]:
        """
        Get service statistics including cache control features.
        """
        try:
            response = self.session.get(
                f"{self.base_url}/stats", 
                timeout=self.config.rag_service_health_timeout
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def get_cache_stats(self) -> Optional[dict]:
        """
        Get cache statistics from the service.
        """
        try:
            response = self.session.get(
                f"{self.base_url}/cache/stats", 
                timeout=self.config.rag_service_health_timeout
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # Cache not enabled on service
                return {"cache_enabled": False, "message": "Service cache not enabled"}
        except:
            pass
        return None
