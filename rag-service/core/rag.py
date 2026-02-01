# Standard library imports
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

# Third-party imports
import chromadb
from openai import OpenAI
from sentence_transformers import SentenceTransformer

# Local application imports
from .config import Config, QueryIntent
from .perplexity_client import PerplexityClient
from .query_formatting import QueryResultFormatter
from .scoring_service import ScoringService
from .temporal_detector import TemporalDetector
from .text_processing import TextProcessor
from .vector_search_service import VectorSearchService

class RAGAssistant:
    """Main RAG Assistant orchestrating all search and response generation."""
    
    def __init__(self, config: Config, logger: logging.Logger, translation_service=None, 
                 tts_service=None, name_matcher=None, entity_extractor=None, cache_manager=None):
        self.config = config
        self.logger = logger
        
        # Optional services (None for API service, present for UI client)
        self.translation_service = translation_service 
        self.tts_service = tts_service
        self.name_matcher = name_matcher
        self.entity_extractor = entity_extractor
        self.cache_manager = cache_manager
        
        # Core services
        self.temporal_detector = TemporalDetector(config)
        self.perplexity_client = PerplexityClient(config)
        self.text_processor = TextProcessor()
        
        # Setup infrastructure
        self._setup_dirs()
        self._setup_database()
        self._setup_ai_services()
        self._setup_search_and_scoring()
        
        # Runtime state
        self.normalized_query = None
        self.current_date = datetime.now().strftime('%Y-%m-%d')
        self._last_detected_emotion = "neutral"
        self._current_cache_key = None
        self._current_query_data = None  # Track query data for cache control

    # ========== SETUP METHODS (alphabetical) ==========
    
    def _setup_ai_services(self):
        """Initialize AI models and services."""
        self.embedder = SentenceTransformer(self.config.embedding_model, device='cpu')
        self.embedder.show_progress_bar = False
        # TODO: Add validation that API key exists before creating client
        # TODO: Raise clear error message if OPENAI_API_KEY not found in environment
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def _setup_database(self):
        """Initialize ChromaDB collection."""
        self.client = chromadb.PersistentClient(path=str(self.config.chroma_path))
        try:
            self.collection = self.client.get_collection(self.config.COLLECTION_NAME)
        except ValueError:
            self.collection = self.client.create_collection(
                self.config.COLLECTION_NAME,
                hnsw_config=self.config.hnsw_config
            )

    def _setup_dirs(self):
        """Create necessary directories."""
        dirs = [
            self.config.chroma_path,
            self.config.log_path,
            self.config.results_path,
            self.config.cache_dir,
            self.config.cache_dir / "llm",
            self.config.cache_dir / "translations", 
            self.config.cache_dir / "audio"
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _setup_search_and_scoring(self):
        """Initialize search and scoring services."""
        self.vector_search_service = VectorSearchService(self.config, self.embedder)
        self.scoring_service = ScoringService(
            self.config, 
            self.text_processor, 
            self.name_matcher, 
            self.entity_extractor
        )

    # ========== CACHE CONTROL METHODS ==========

    def _is_temporal_query(self, question: str) -> bool:
        """Check if query requires current information (not suitable for caching)."""
        if not self.config.perplexity_enabled:
            return False
        return self.temporal_detector.needs_current_info(question)

    def _mark_cache_safe(self, cache_safe: bool = True):
        """Mark current query as cache-safe or temporal."""
        if self._current_query_data:
            self._current_query_data["cache_safe"] = cache_safe
            if self.config.debug:
                self.logger.debug(f"Query marked as {'cache-safe' if cache_safe else 'temporal (no cache)'}")

    def _should_use_cache(self, question: str, response_format: str) -> bool:
        """Determine if this query should use cache."""
        if not self.cache_manager:
            return False
        
        # Don't cache temporal queries
        if self._is_temporal_query(question):
            return False
            
        return True

    def _get_cache_response(self, question: str, response_format: str) -> Optional[dict]:
        """Get cached response if available and appropriate."""
        if not self._should_use_cache(question, response_format):
            return None
            
        cache_query = self.normalized_query or question
        cache_key = self.cache_manager.get_cache_key(cache_query, response_format)
        self._current_cache_key = cache_key
        
        cached = self.cache_manager.get_cached_response(cache_key)
        if cached and 'llm_response' in cached:
            if self.config.debug:
                self.logger.debug(f"Cache HIT for key: {cache_key}")
            return cached
        else:
            if self.config.debug:
                self.logger.debug(f"Cache MISS for key: {cache_key}")
            return None

    def _cache_response_if_appropriate(self, response_text: str, response_format: str):
        """Cache response only if it's cache-safe."""
        if (self._current_cache_key and 
            self.cache_manager and 
            self._current_query_data and 
            self._current_query_data.get("cache_safe", True)):
            
            response_data = {
                'llm_response': response_text,
                'response_format': response_format,
                'metadata': self._current_query_data
            }
            self.cache_manager.cache_response(self._current_cache_key, response_data)
            if self.config.debug:
                self.logger.debug(f"Response cached with key: {self._current_cache_key}")
        else:
            if self.config.debug:
                self.logger.debug("Response NOT cached (temporal or cache disabled)")

    # ========== EMOTION DETECTION METHODS ==========

    def _detect_emotion_from_content(self, text: str, question: str = "") -> str:
        """
        Unified emotion detection based on response content and question context.
        Works consistently regardless of response source (LLM or Perplexity).
        """
        # TODO: Refactor emotion detection to config-driven approach
        # TODO: Move keyword lists to config/emotions.json for easier maintenance
        # TODO: Consider using sentiment analysis library (TextBlob, VADER) for more robust detection
        if not text:
            return "neutral"

        text_lower = text.lower()
        question_lower = question.lower()

        # Check for explicit emotion keywords in response
        if any(word in text_lower for word in ['congratulations', 'excellent', 'wonderful', 'amazing', 'fantastic']):
            return 'happy'
        elif any(word in text_lower for word in ['exciting', 'thrilled', 'incredible']):
            return 'excited'
        elif any(word in text_lower for word in ['sorry', 'unfortunately', 'problem', 'issue', 'error']):
            return 'sad'
        elif any(word in text_lower for word in ['interesting', 'surprising', 'remarkable', 'wow']):
            return 'surprised'
        elif any(word in text_lower for word in ['unclear', 'confusing', 'not sure', 'difficult to']):
            return 'confused'
        elif any(word in text_lower for word in ['think', 'consider', 'analyze', 'complex', 'depends']):
            return 'thinking'
        
        # Check question context for greeting/goodbye
        if any(word in question_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
            return 'greeting'
        elif any(word in question_lower for word in ['bye', 'goodbye', 'see you', 'farewell']):
            return 'goodbye'
        
        # Default to neutral
        return 'neutral'

    def _parse_llm_response(self, full_response: str, question: str = "") -> tuple[str, str]:
        """
        Parse response and detect emotion using unified content-based detection.
        """
        try:
            # Clean text and detect emotion from content
            cleaned_text = full_response.strip()
            emotion = self._detect_emotion_from_content(cleaned_text, question)
            return cleaned_text, emotion
                
        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {str(e)}")
            return full_response.strip(), "neutral"

    # ========== RESPONSE PROCESSING METHODS (alphabetical) ==========

    def _get_system_prompt(self, response_format="web"):
        """Get appropriate system prompt based on response format - WITHOUT emotion requirements."""
        # TODO: Use template system (Jinja2) instead of string manipulation for prompt management
        # TODO: Store prompts in separate files (prompts/web.txt, prompts/voice.txt)
        current_date = datetime.now().strftime("%d-%m-%Y")
        base_prompt = self.config.system_prompt.format(current_date=current_date)

        # Remove the emotion detection section from base prompt
        base_prompt_lines = base_prompt.split('\n')
        cleaned_lines = []
        skip_emotion_section = False

        for line in base_prompt_lines:
            if 'EMOTION DETECTION:' in line:
                skip_emotion_section = True
                continue
            elif skip_emotion_section and line.strip() and not line.startswith('- ') and not line.startswith('Choose'):
                skip_emotion_section = False
            
            if not skip_emotion_section:
                cleaned_lines.append(line)
        
        base_prompt = '\n'.join(cleaned_lines).strip()
        
        if response_format == "voice":
            return f"""{base_prompt}

RESPONSE FORMAT FOR VOICE INTERFACE:
Respond in a conversational, voice-friendly manner. Keep responses brief and natural for text-to-speech (around 50-80 words max). Use simple sentences. When discussing:

Events:
- Use base event names without years (e.g., "NITKonnect", "Tech Summit")  
- For specific instances: Include full date (DD-MM-YYYY) for confirmed events
- For tentative events: Specify month and year only
- Convert relative dates to actual dates

Be warm, helpful, and concise. End with follow-up offers only when truly relevant. Avoid long lists or complex explanations in voice responses."""
        
        else:  # web format
            return f"""{base_prompt}

RESPONSE FORMAT FOR WEB INTERFACE:
Provide structured, informative responses that are detailed but concise. Guidelines:

Structure: Use clear sections and bullet points for readability
Length: Aim for 2-4 paragraphs (150-300 words) - detailed enough for web reading, reasonable for audio
Detail: Include key facts, dates, names, and context without excessive elaboration
Focus: Answer the specific question directly, then add relevant supporting details
Background: Provide essential context but avoid lengthy explanations
Format: Use bullet points for lists, but keep them focused and essential
Authenticity: Only include specific dates, names, and historical details if highly confident. Avoid detailed lists of previous officials or historical timelines unless verified.

Be informative and well-structured while remaining practical for both reading and potential audio conversion."""

    def _handle_cached_response(self, cached, query_data):
        """Handle response from cache."""
        self.logger.info("Using cached response")
        query_data.update({
            "cached": True,
            "cache_safe": True,  # Cached responses are always from cache-safe queries
            "response": {
                "text": cached['llm_response'],
                "translation": cached.get('translation'),
                "audio_path": cached.get('audio_path'),
                "chunks_received": 1,
                "total_length": len(cached['llm_response'])
            }
        })
        
        # Parse emotion from cached response using unified detection
        cached_text, emotion = self._parse_llm_response(cached['llm_response'])
        self._last_detected_emotion = emotion
        
        lines = cached_text.split('\n')
        for i, line in enumerate(lines):
            words = line.split()
            for word in words:
                yield word + ' '
            if i < len(lines) - 1:
                yield '\n'
        
        self._log_query(query_data)

    def _handle_response_completion(self, response_text, query_data, response_format="web"):
        """Handle response completion with format-aware caching."""
        query_data["response"]["text"] = response_text
        
        # Cache only if appropriate (cache-safe queries)
        self._cache_response_if_appropriate(response_text, response_format)
        self._log_query(query_data)

    def _log_query(self, query_data):
        """Log query data to results file."""
        if self.config.results_log:
            log_file = self.config.results_path / self.config.results_file
            with open(log_file, 'a') as f:
                f.write(f"{json.dumps(query_data)}\n")

    def _process_rag_query(self, question: str, response_format: str, query_data: Dict) -> Generator[str, None, None]:
        """Process query through RAG pipeline."""
        self.normalized_query = None
        clean_question, preprocess_time = self.vector_search_service.preprocess_text(question)
        
        # Mark as cache-safe (static RAG content)
        self._mark_cache_safe(True)
        
        # Entity extraction and normalization
        query_entities = []
        if self.entity_extractor:
            query_entities = self.entity_extractor.extract_entities(clean_question)
            if query_entities and query_entities[0]["label"] == "PERSON" and self.name_matcher:
                self.normalized_query = self.name_matcher.normalize_name(question)
        
        # Check cache for cache-safe queries
        cached = self._get_cache_response(question, response_format)
        if cached and 'llm_response' in cached:
            for chunk in self._handle_cached_response(cached, query_data):
                yield chunk
            return

        query_data["metrics"]["steps"]["preprocess"] = preprocess_time
        
        # Determine search strategy
        query_intent = QueryIntent.GENERAL
        
        # Entity-first search if we have specific entities
        if query_entities:
            for entity in query_entities:
                if entity["label"] in ["PERSON", "ORGANIZATION"]:
                    query_intent = QueryIntent[entity["label"]]
                    self.logger.info(f"Searching for {entity['label']} entity: {entity['text']}")
                    results = self.vector_search_service.entity_first_search(self.collection, clean_question, entity)
                    if results:
                        self.logger.info(f"Entity search found {len(results)} documents")
                        reranked_results = self.scoring_service.rerank_results(
                            results, clean_question, entity, query_intent
                        )[:self.config.DEFAULT_RESULTS]
                        self.logger.info(f"Reranked to {len(reranked_results)} results")
                        for chunk in self._process_results(reranked_results, clean_question, query_data, response_format, question):
                            yield chunk
                        return

        # Fall back to semantic search
        self.logger.info(f"Performing semantic search for: {clean_question}")
        results = self.vector_search_service.semantic_search(self.collection, clean_question)
        
        self.logger.info(f"Semantic search found {len(results)} documents")
        reranked_results = self.scoring_service.rerank_results(
            results, clean_question, 
            query_entities[0] if query_entities else None, 
            query_intent
        )
        self.logger.info(f"Reranked to {len(reranked_results)} results")
        
        for chunk in self._process_results(reranked_results[:self.config.DEFAULT_RESULTS], clean_question, query_data, response_format, question):
            yield chunk

    def _process_results(self, results: List[Dict], question: str, query_data: Dict, response_format: str = "web", original_question: str = "") -> Generator[str, None, None]:
        """Process results with format-aware system prompt and unified emotion detection."""
        context = "\n".join(r['document'] for r in results)
        query_data["context"].update({
            "num_chunks": len(results),
            "total_length": len(context),
            "relevance_scores": [r["relevance_score"] for r in results],
            "full_context": context
        })

        # Use format-specific system prompt (without emotion requirements)
        system_prompt = self._get_system_prompt(response_format)
        prompt = f"{system_prompt}\n\nContext:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        query_data["prompt"] = prompt
        query_data["response_format"] = response_format
        response_text = ""

        for chunk in self._stream_response_with_emotion(prompt, original_question or question):
            response_text += chunk
            query_data["response"]["chunks_received"] += 1
            query_data["response"]["total_length"] = len(response_text)
            yield chunk

        self._handle_response_completion(response_text, query_data, response_format)

    def _query_perplexity(self, question: str, response_format: str, query_data: Dict) -> Generator[str, None, None]:
        """Query Perplexity for current information without format enforcement."""
        # Mark as NOT cache-safe (temporal content)
        self._mark_cache_safe(False)
        
        try:
            self.logger.info(f"Querying Perplexity for temporal information: {question[:50]}...")
            
            response_text = ""
            chunk_count = 0

            # TODO: Make citation removal more robust (handle edge cases like [1][2], [[1]], etc.)
            # Collect full response from Perplexity
            for chunk in self.perplexity_client.query(question, response_format):
                # Remove citation brackets [1], [2-3], etc.
                cleaned_chunk = re.sub(r'\[\d+(?:[-,]\d+)*\]', '', chunk)
                response_text += cleaned_chunk
                chunk_count += 1
            
            # NO format enforcement - trust Perplexity's format handling
            # Parse emotion from Perplexity response using unified detection
            cleaned_response, emotion = self._parse_llm_response(response_text, question)
            self._last_detected_emotion = emotion
            
            # Update query data for temporal response
            query_data.update({
                "source": "perplexity",
                "cache_safe": False,
                "response": {
                    "text": cleaned_response,
                    "chunks_received": chunk_count,
                    "total_length": len(cleaned_response)
                }
            })
            
            # Stream the response (no truncation)
            for chunk in self._stream_text(cleaned_response):
                yield chunk
            
            # Log temporal query (no caching)
            self._log_query(query_data)
                
        except Exception as e:
            self.logger.error(f"Perplexity query failed: {str(e)}")
            error_response = "I can't access current information right now." if response_format == "voice" else "I'm unable to access current information at the moment. Please try again later."
            
            # Update query data for error
            query_data.update({
                "source": "perplexity_error",
                "cache_safe": False,
                "error": str(e),
                "response": {"text": error_response, "chunks_received": 1, "total_length": len(error_response)}
            })
            
            # Detect emotion for error response
            self._last_detected_emotion = self._detect_emotion_from_content(error_response, question)
            
            yield error_response
            self._log_query(query_data)

    def _stream_response_with_emotion(self, prompt: str, original_question: str = "") -> Generator[str, None, None]:
        """
        Stream response from OpenAI and detect emotion when complete using unified detection.
        """
        # TODO: Add timeout to OpenAI API call (prevent indefinite hanging)
        # TODO: Add retry logic with exponential backoff for transient failures
        try:
            response = self.openai_client.chat.completions.create(
                model=self.config.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                stream=True
            )
            
            # TODO: Use list and join instead of string concatenation for better performance (O(n) vs O(n²))
            full_response = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    chunk_text = chunk.choices[0].delta.content
                    full_response += chunk_text
                    yield chunk_text
            
            # Parse emotion from complete response using unified detection
            cleaned_text, emotion = self._parse_llm_response(full_response, original_question)
            # Store emotion for route handler to access
            self._last_detected_emotion = emotion
            
        except Exception as e:
            self.logger.error(f"Streaming failed: {str(e)}")
            self._last_detected_emotion = "neutral"
            yield "Error generating response"

    def _stream_text(self, text: str) -> Generator[str, None, None]:
        """Stream text in word chunks for consistent delivery."""
        words = text.split()
        for i, word in enumerate(words):
            if i < len(words) - 1:
                yield word + " "
            else:
                yield word

    def _truncate_at_sentence(self, words: list, max_words: int) -> list:
        """Truncate text at the nearest sentence boundary before max_words."""
        if len(words) <= max_words:
            return words
        
        # Look for sentence endings near the limit
        for i in range(min(max_words, len(words)) - 1, max(0, max_words - 20), -1):
            if words[i].endswith(('.', '!', '?')):
                return words[:i + 1]
        
        # If no sentence boundary found, truncate at word limit
        return words[:max_words]

    # ========== PUBLIC INTERFACE METHODS ==========

    def query(self, question: str, response_format: str = "web") -> Generator[str, None, None]:
        """
        Process query with format-aware responses and unified emotion detection.

        Args:
            question: The user's question
            response_format: "web" for detailed responses, "voice" for brief responses
        """
        # TODO: Add input validation (max length, special characters, empty string)
        # TODO: Add rate limiting per client/IP to prevent abuse
        query_start = time.time()
        query_id = str(uuid.uuid4())
        metrics = {"steps": {}}
        query_data = {
            "query": question,
            "response_format": response_format,
            "timestamp": datetime.now().isoformat(),
            "log_id": query_id,
            "metrics": metrics,
            "context": {},
            "response": {"chunks_received": 0, "total_length": 0},
            "cache_safe": True  # Default to cache-safe, will be updated if temporal
        }
        
        # Store current query data for cache control
        self._current_query_data = query_data

        try:
            # Temporal Detection - route to Perplexity for current info
            if self.config.perplexity_enabled and self._is_temporal_query(question):
                if self.perplexity_client.is_available():
                    for chunk in self._query_perplexity(question, response_format, query_data):
                        yield chunk
                    return
                else:
                    self.logger.warning("Temporal query detected but Perplexity not available, falling back to RAG")
                    
            # Normal RAG query handling (cache-safe)
            yield from self._process_rag_query(question, response_format, query_data)

        except Exception as e:
            self.logger.error(f"Query failed: {str(e)}", exc_info=True)
            query_data["error"] = str(e)
            query_data["cache_safe"] = False  # Don't cache error responses
            self._log_query(query_data)
            self._last_detected_emotion = "confused"
            yield "An error occurred"
            
        finally:
            # Clean up current query tracking
            self._current_query_data = None
            self._current_cache_key = None

    # ========== UTILITY METHODS ==========
    
    def get_last_detected_emotion(self) -> str:
        """Get the emotion detected from the last response."""
        return getattr(self, '_last_detected_emotion', 'neutral')
    
    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled and available."""
        return self.cache_manager is not None
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics if cache manager is available."""
        if self.cache_manager and hasattr(self.cache_manager, 'get_stats'):
            return self.cache_manager.get_stats()
        return {"cache_enabled": False}