# Standard library imports
import logging
import time
from typing import Any, Dict, List, Optional

# Local application imports
from .config import Config, QueryIntent
from .text_processing import TextProcessor

logger = logging.getLogger(__name__)


class ScoringService:
    def __init__(self, config: Config, text_processor: TextProcessor, name_matcher=None, entity_extractor=None):
        self.config = config
        self.text_processor = text_processor
        self.name_matcher = name_matcher
        self.entity_extractor = entity_extractor
        self._entity_cache = {}
        self._MAX_CACHE_SIZE = 1000
        logger.debug(f"Initialized entity cache with max size {self._MAX_CACHE_SIZE}")

    def extract_doc_entities(self, document: str) -> Dict[str, List]:
        """Extract entities from document with caching."""
        # Only extract entities if entity_extractor is available
        if not self.entity_extractor:
            return {}
            
        doc_hash = hash(document.strip())
        if doc_hash in self._entity_cache:
            logger.debug(f"Entity cache hit for doc hash {doc_hash}")
            return self._entity_cache[doc_hash]
            
        start = time.time()
        entities = self.entity_extractor.extract_entities(document)
        
        if len(self._entity_cache) >= self._MAX_CACHE_SIZE:
            logger.debug("Entity cache full - clearing")
            self._entity_cache.clear()
            
        self._entity_cache[doc_hash] = entities
        return entities

    def calculate_scores(self, initial_distance, query_terms, query_text, query_entity, doc_entities, metadata, query_intent, exact_match=False):
        """Calculate comprehensive relevance scores for a document."""
        start = time.time()
        
        initial_score = 1 - min(initial_distance, 1.0)
        
        # Calculate term overlap only if needed
        term_overlap = (self.text_processor.calculate_term_overlap(query_terms, metadata.get('text', ''))
                    if query_terms else 0)
        term_boost = term_overlap * self.config.EXACT_MATCH_BOOST if term_overlap >= self.config.MIN_TERM_MATCH else 0
        
        # Calculate boosts only if we have the necessary data
        metadata_boost = entity_boost = person_boost = 0.0
        metadata_reasons = entity_reasons = person_reasons = []
        
        if metadata:
            metadata_boost, metadata_reasons = self._calculate_metadata_boost(metadata, query_text)
        
        if query_entity and doc_entities:
            entity_boost, entity_reasons = self._calculate_entity_boost(
                [query_entity], doc_entities, query_intent, exact_match)
            
            if query_entity.get('label') == 'PERSON' and self.name_matcher:
                person_boost, person_reasons = self._calculate_person_boost(
                    [query_entity], doc_entities)
        
        final_score = initial_score + term_boost + metadata_boost + entity_boost + person_boost
        
        return {
            'initial_score': initial_score,  
            'term_boost': term_boost,
            'metadata_boost': metadata_boost,
            'metadata_reasons': metadata_reasons,
            'entity_boost': entity_boost,
            'entity_reasons': entity_reasons,
            'person_boost': person_boost,
            'person_reasons': person_reasons,
            'final_score': final_score
        }

    def _calculate_entity_boost(self, query_entities: List[Dict], doc_entities: Dict[str, List],
                            query_intent: QueryIntent, exact_match: bool = False) -> tuple[float, List[str]]:
        """Calculate boost score based on entity matches."""
        boost = 0.0
        reasons = []
        
        for query_ent in query_entities:
            if not isinstance(query_ent, dict) or 'label' not in query_ent:
                continue
                
            ent_type = query_ent['label']
            query_text = query_ent['text']
            
            if exact_match:
                type_boost = getattr(self.config, f'{ent_type}_BOOST', 0.1)
                boost += type_boost
                reasons.append(f"exact {ent_type.lower()} match ({query_text}): +{type_boost:.3f}")
                continue
                
            if ent_type not in doc_entities:
                continue
                
            for doc_ent in doc_entities[ent_type]:
                if doc_ent.lower() == query_text.lower():
                    type_boost = getattr(self.config, f'{ent_type}_BOOST', 0.1)
                    boost += type_boost
                    reasons.append(f"{ent_type.lower()} match ({doc_ent}): +{type_boost:.3f}")
                    
        return boost, reasons

    def _calculate_person_boost(self, query_entities: List[Dict], 
                            doc_entities: Dict[str, List]) -> tuple[float, List[str]]:
        """Calculate boost score for person name matches."""
        boost = 0.0
        reasons = []
        
        # Only calculate if name_matcher is available
        if not self.name_matcher:
            return boost, reasons
        
        query_persons = [e for e in query_entities if e['label'] == 'PERSON']
        if not query_persons or 'PERSON' not in doc_entities:
            return boost, reasons
            
        for query_person in query_entities:
            query_name = self.name_matcher.normalize_name(query_person['text'])
            best_match = max(
                ((name, self.name_matcher.name_similarity(query_name, name)) 
                for name in doc_entities['PERSON']),
                key=lambda x: x[1], 
                default=(None, 0)
            )
            
            if best_match[1] >= self.config.NAME_MATCH_THRESHOLD:
                match_quality = best_match[1] / 100
                person_boost = self.config.PERSON_BOOST * match_quality
                boost += person_boost
                reasons.append(f"person match ({query_name} → {best_match[0]}, {match_quality:.2f}): +{person_boost:.3f}")
                
        return boost, reasons

    def _calculate_metadata_boost(self, metadata: Dict, query_text: str) -> tuple[float, List[str]]:
        """Calculate boost score based on metadata matches."""
        boost = 0.0
        reasons = []
        
        query_terms = {term.lower() for term in query_text.split()}
        
        hashtags = [tag.lower().lstrip('#') for tag in metadata.get('hashtags', [])]
        mentions = [mention.lower().lstrip('@') for mention in metadata.get('mentions', [])]
        
        relevant_hashtags = sum(1 for tag in hashtags if any(term in tag for term in query_terms))
        relevant_mentions = sum(1 for mention in mentions if any(term in mention for term in query_terms))
        
        if relevant_hashtags:
            tag_boost = relevant_hashtags * self.config.HASHTAG_BOOST
            boost += tag_boost
            reasons.append(f"hashtags: +{tag_boost:.3f}")
            
        if relevant_mentions:
            mention_boost = relevant_mentions * self.config.MENTION_BOOST
            boost += mention_boost
            reasons.append(f"mentions: +{mention_boost:.3f}")
            
        return boost, reasons

    def rerank_results(self, results: List[Dict], query_text: str, entity: Optional[Dict], query_intent: QueryIntent) -> List[Dict]:
        """Rerank search results based on comprehensive scoring."""
        try:
            start_time = time.time()
            reranked = []
            seen_content = set()
            logger.debug(f"Starting reranking of {len(results)} documents")
            
            query_terms = self.text_processor.extract_search_terms(query_text)
            processed = 0
            
            for result in results:
                doc = result['document'].strip()
                doc_hash = hash(doc)
                if doc_hash not in seen_content:
                    processed += 1
                    seen_content.add(doc_hash)

                    metadata = self._decode_metadata(result['metadata'])
                    doc_entities = self.extract_doc_entities(doc)
                    exact_match = result.get('exact_match', False)
                    
                    scores = self.calculate_scores(
                        result['distance'],
                        query_terms,
                        query_text,
                        entity,
                        doc_entities,
                        metadata,
                        query_intent,
                        exact_match
                    )
                    
                    if scores['final_score'] >= self.config.MIN_RELEVANCE_SCORE:
                        reranked.append({
                            'document': result['document'],
                            'metadata': metadata,
                            'relevance_score': scores['final_score'],
                            'score_breakdown': scores
                        })
                        
                        if len(reranked) >= self.config.DEFAULT_RESULTS:
                            scores = [r['relevance_score'] for r in reranked]
                            min_acceptable = scores[0] * self.config.MIN_RELEVANCE_SCORE * 4
                            if scores[-1] < min_acceptable:
                                reranked.sort(key=lambda x: x['relevance_score'], reverse=True)
                                logger.debug(f"Early exit after processing {processed}/{len(results)} docs")
                                return reranked
                    
                    seen_content.remove(doc_hash)
            
            return sorted(reranked, key=lambda x: x['relevance_score'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error in reranking: {str(e)}")
            return []

    @staticmethod
    def _decode_metadata(metadata: Dict) -> Dict:
        """Convert JSON strings in metadata to Python objects."""
        import json
        decoded = {}
        for k, v in metadata.items():
            if isinstance(v, str):
                try:
                    decoded[k] = json.loads(v)
                except json.JSONDecodeError:
                    decoded[k] = v
            else:
                decoded[k] = v
        return decoded
