import chromadb
import json
import re
import spacy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from sentence_transformers import SentenceTransformer
from typing import Dict, List, Any, Optional, Set, Tuple
from rich.console import Console
from rich.table import Table
from thefuzz import fuzz
from enum import Enum

class QueryIntent(Enum):
    GENERAL = "general"
    PERSON = "person"
    ORGANIZATION = "organization" 
    EVENT = "event"
    LOCATION = "location"

@dataclass
class SearchConfig:
    CHROMA_FILE: Path
    COLLECTION_NAME: str
    DEFAULT_RESULTS: int
    EMBEDDING_MODEL: str
    ENTITY_BOOST: float
    EVENT_BOOST: float
    EVENTS_FILE: Path
    EXACT_MATCH_BOOST: float
    HASHTAG_BOOST: float
    LOCATION_BOOST: float
    LOCATIONS_FILE: Path
    METADATA_BOOST_CAP: float
    MIN_RELEVANCE_SCORE: float
    MIN_TERM_MATCH: float
    MENTION_BOOST: float
    NAME_MATCH_THRESHOLD: float
    ORG_BOOST: float
    ORGS_FILE: Path
    PERSONS_FILE: Path
    PERSON_BOOST: float
    RESULTS_FILE: str
    TITLES_FILE: str
    
    @classmethod
    def create_default(cls) -> 'SearchConfig':
        return cls(
            CHROMA_FILE = Path("../outputs/chroma_db"),  
            COLLECTION_NAME = "nitk_knowledgebase",  
            DEFAULT_RESULTS = 5,  
            EMBEDDING_MODEL = 'all-MiniLM-L6-v2',  
            ENTITY_BOOST = 0.1,  
            EVENT_BOOST = 0.08,  
            EVENTS_FILE = Path("config/events.json"),  
            EXACT_MATCH_BOOST = 0.15,  
            HASHTAG_BOOST = 0.02,  
            LOCATION_BOOST = 0.08,  
            LOCATIONS_FILE = Path("config/locations.json"),  
            METADATA_BOOST_CAP = 0.1,  
            MIN_RELEVANCE_SCORE = 0.25,  
            MIN_TERM_MATCH = 0.7,  
            MENTION_BOOST = 0.02,  
            NAME_MATCH_THRESHOLD = 80.0,  
            ORG_BOOST = 0.1,  
            ORGS_FILE = Path("config/organizations.json"),  
            PERSONS_FILE = Path("config/persons.json"),  
            PERSON_BOOST = 0.15,  
            RESULTS_FILE = Path("results/query_results.json"),
            TITLES_FILE = Path("config/titles.json")
        )

class PersonsData:
    def __init__(self, persons_file: Path):
        self.persons: Set[str] = set()
        self.title_patterns: List[re.Pattern] = []
        self.role_patterns: List[re.Pattern] = []
        self.name_formats: List[Dict] = []
        self.transliterations: Dict[str, str] = {}
        
        try:
            with open(persons_file) as f:
                data = json.load(f)
                self.persons = set(data.get('persons', []))
                self.title_patterns = [re.compile(p, re.IGNORECASE) for p in data.get('title_patterns', [])]
                self.role_patterns = [re.compile(p, re.IGNORECASE) for p in data.get('role_patterns', [])]
                self.name_formats = data.get('name_formats', [])
                self.transliterations = data.get('transliterations', {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Error loading {persons_file}: {e}")
            print("Using empty defaults.")

    def standardize_name(self, name: str) -> str:
       name = self.transliterations.get(name.lower(), name)
       name = ' '.join(name.split())  # Normalize whitespace
       
       # Handle initials with periods
       name = re.sub(r'(\w)\.\s*', r'\1 ', name)
       
       for fmt in self.name_formats:
           name = re.sub(fmt['pattern'], fmt['replacement'], name, flags=re.IGNORECASE)
       return name.strip()
    
    def is_known_person(self, name: str) -> bool:
        std_name = self.standardize_name(name)
        return (std_name.lower() in {p.lower() for p in self.persons} or 
                any(fuzz.ratio(std_name.lower(), known.lower()) > 90 
                    for known in self.persons))

class TextProcessor:
    def __init__(self):
        self.stop_words = set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'])
    
    def extract_search_terms(self, text: str) -> List[str]:
        """Extract meaningful search terms from query text."""
        terms = []
        for term in text.lower().split():
            term = re.sub(r'[^\w\s]', '', term)
            if term and term not in self.stop_words:
                terms.append(term)
        return terms

    def calculate_term_overlap(self, query_terms: List[str], document: str) -> float:
        """Calculate what fraction of query terms appear in document."""
        doc_lower = document.lower()
        doc_terms = set(self.extract_search_terms(document))
        matches = sum(1 for term in query_terms if term in doc_terms)
        return matches / len(query_terms) if query_terms else 0.0

class NameMatcher:
    def __init__(self, persons_data: PersonsData):
        self.persons_data = persons_data
        self.initial_weight = 0.4
        self.exact_weight = 0.6

    def normalize_name(self, name: str) -> str:
        """Normalize name for comparison."""
        name = self.persons_data.standardize_name(name)
        return re.sub(r'[^\w\s]', '', name.lower())

    def extract_initials(self, name: str) -> str:
        """Extract initials from name."""
        name = re.sub(r'\.\s*', '.', name)
        parts = re.split(r'[\s\.]+', name)
        return ''.join(p[0].lower() for p in parts if p)

    def _compute_part_similarity(self, part1: str, part2: str) -> float:
        """Compute similarity between name parts."""
        if not part1 or not part2:
            return 0.0
            
        exact_match = part1.lower() == part2.lower()
        if exact_match:
            return 1.0
            
        initial_match = (part1[0].lower() == part2[0].lower() and 
                        (len(part1) == 1 or len(part2) == 1))
        if initial_match:
            return self.initial_weight
            
        fuzzy_ratio = fuzz.ratio(part1.lower(), part2.lower()) / 100
        return fuzzy_ratio * self.exact_weight

    def name_similarity(self, name1: str, name2: str) -> float:
        """Compute similarity between two names with strict limits."""
        if not name1 or not name2:
            return 0.0
            
        n1 = self.normalize_name(name1)
        n2 = self.normalize_name(name2)
        
        if n1 == n2:
            return 100.0
            
        parts1 = n1.split()
        parts2 = n2.split()
        
        if not parts1 or not parts2:
            return 0.0
            
        # Calculate similarities between corresponding parts
        similarities = []
        max_parts = max(len(parts1), len(parts2))
        
        for i in range(max_parts):
            if i >= len(parts1) or i >= len(parts2):
                similarities.append(0.0)
            else:
                sim = self._compute_part_similarity(parts1[i], parts2[i])
                similarities.append(sim)
                
        # Weight first and last parts more heavily
        weights = [1.2 if i == 0 or i == len(similarities)-1 else 1.0 
                  for i in range(len(similarities))]
                  
        weighted_sum = sum(s * w for s, w in zip(similarities, weights))
        final_score = (weighted_sum / sum(weights)) * 100
        
        # Apply known person boost if applicable
        if self.persons_data.is_known_person(name1) or self.persons_data.is_known_person(name2):
            final_score *= 1.1
            
        return min(final_score, 100.0)

class EntityExtractor:
    def __init__(self, config: SearchConfig):
        self.config = config
        self.entities = {
            'PERSON': self._load_json(config.PERSONS_FILE, 'persons'),
            'ORGANIZATION': self._load_json(config.ORGS_FILE, 'organizations'), 
            'LOCATION': self._load_json(config.LOCATIONS_FILE, 'locations'),
            'EVENT': self._load_json(config.EVENTS_FILE, 'events')
        }       
        self.persons_data = PersonsData(config.PERSONS_FILE)
        self.name_matcher = NameMatcher(self.persons_data)

    def _load_json(self, file_path: Path, key: str) -> Set[str]:
        try:
            with open(file_path) as f:
                data = json.load(f)
                if key == 'locations':
                    # Flatten locations into single set
                    locs = data[key]
                    return set().union(*[set(locs[k]) for k in ['cities', 'states', 'countries', 'campus_locations', 'other']])
                return set(data[key])
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return set()

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        text_parts = text.strip().split()
        candidates = text_parts + [' '.join(text_parts[i:i+2]) for i in range(len(text_parts)-1)]
        
        seen = set()
        for candidate in candidates:
            if candidate in seen:
                continue
                
            for entity_type, entity_set in self.entities.items():
                match = self._get_best_match(candidate, entity_type, entity_set)
                if match:
                    entities.append(match)
                    seen.add(candidate)
                    break
                        
        return entities

    def _get_best_match(self, text: str, entity_type: str, entity_set: Set[str]) -> Optional[Dict]:
        if entity_type == 'PERSON':
            best_match = max(entity_set, 
                        key=lambda x: self.name_matcher.name_similarity(text, x),
                        default=None)
            score = self.name_matcher.name_similarity(text, best_match) / 100 if best_match else 0
        else:
            best_match = max(entity_set,
                        key=lambda x: fuzz.ratio(text.lower(), x.lower()),
                        default=None)
            score = fuzz.ratio(text.lower(), best_match.lower()) / 100 if best_match else 0
                
        if score >= 0.8:
            return {
                "text": best_match,
                "label": entity_type
            }
        return None

    def _classify_entity_type(self, text: str, entities: List[Dict[str, Any]]) -> QueryIntent:
        if not entities:
            return QueryIntent.GENERAL
        return QueryIntent[entities[0]['label']]

class QueryResultFormatter:
    @staticmethod
    def format_result(raw_result: dict) -> dict:
        metadata = raw_result.get('metadata', {})
        return {
            'document': raw_result['document'],
            'source': {
                'id': metadata.get('source_id'),
                'date': metadata.get('created_date'),
                'author': metadata.get('author'),
                'platform': metadata.get('platform')
            },
            'entities': metadata.get('entities', {}),
            'relevance_score': raw_result.get('relevance_score', 0.0),
            'score_breakdown': raw_result.get('score_breakdown', {})
        }

    @staticmethod
    def format_results(results: list, query: str) -> dict:
        return {
            'query': query,
            'timestamp': datetime.now().isoformat(),
            'results': [QueryResultFormatter.format_result(r) for r in results]
        }

class ChromaSearch:
# Constructor
    def __init__(self, config: SearchConfig):
        self.config = config
        self.console = Console()
        self.client = chromadb.PersistentClient(path=str(config.CHROMA_FILE))
        self.collection = self.client.get_collection(config.COLLECTION_NAME)
        self.embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
        self.persons_data = PersonsData(config.PERSONS_FILE)
        self.entity_extractor = EntityExtractor(config)
        self.name_matcher = NameMatcher(self.persons_data)
        self.text_processor = TextProcessor()

# Core Search Methods
    def search(self, query_text: str, n_results: Optional[int] = None) -> List[Dict[str, Any]]:
        n_results = n_results or self.config.DEFAULT_RESULTS
        
        entities = self.entity_extractor.extract_entities(query_text)
        query_intent = QueryIntent.GENERAL
        
        # Check all entities for PERSON or ORGANIZATION
        for entity in entities:
            if entity["label"] in ["PERSON", "ORGANIZATION"]:
                query_intent = QueryIntent[entity["label"]]
                entity_results = self._entity_first_search(query_text, entity, query_intent)
                if entity_results:
                    return entity_results[:n_results]
        
        # Fall back to semantic search
        query_embedding = self.embedding_model.encode(query_text).tolist()
        results = self._semantic_search(query_embedding, n_results * 3)
        
        return self._rerank_results(results, query_text, entities[0] if entities else None, query_intent)[:n_results]

    def _entity_first_search(self, query_text: str, entity: Dict, query_intent: QueryIntent) -> List[Dict]:
        try:
            query_embedding = self.embedding_model.encode(query_text).tolist()
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                where_document={"$contains": entity["text"]},
                n_results=self.config.DEFAULT_RESULTS * 2
            )

            if not results.get('documents'):
                return []
            self.console.print ("got results from entity search")
            formatted_results = [
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
            
            return self._rerank_results(formatted_results, query_text, entity, query_intent)
                
        except Exception as e:
            print(f"Entity search error: {str(e)}")
            return []

    def _semantic_search(self, query_embedding: List[float], n_results: int) -> List[Dict]:
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        self.console.print ("got results from semantic search")
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

# Scoring and Ranking
    def _calculate_scores(self, initial_distance, query_terms, query_text, query_entity, doc_entities, metadata, query_intent, exact_match=False):
        initial_score = 1 - min(initial_distance, 1.0)
        
        term_overlap = self.text_processor.calculate_term_overlap(query_terms, metadata.get('text', ''))
        term_boost = term_overlap * self.config.EXACT_MATCH_BOOST if term_overlap >= self.config.MIN_TERM_MATCH else 0
        
        metadata_boost, metadata_reasons = self._calculate_metadata_boost(metadata, query_text)
        
        entity_boost, entity_reasons = self._calculate_entity_boost(
            [query_entity] if query_entity else [], doc_entities, query_intent, exact_match)
        
        person_boost, person_reasons = self._calculate_person_boost(
            [query_entity] if query_entity and query_entity['label'] == 'PERSON' else [], 
            doc_entities)

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

    def _calculate_entity_boost(self, query_entities: List[Dict], 
                        doc_entities: Dict[str, List],
                        query_intent: QueryIntent,
                        exact_match: bool = False) -> Tuple[float, List[str]]:
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
                    continue
                    
                match_score = fuzz.ratio(query_text.lower(), doc_ent.lower())/100
                if match_score >= 0.8:
                    type_boost = getattr(self.config, f'{ent_type}_BOOST', 0.1) * match_score
                    boost += type_boost
                    reasons.append(f"{ent_type.lower()} fuzzy match ({doc_ent}, {match_score:.2f}): +{type_boost:.3f}")
        
        return boost, reasons

    def _calculate_person_boost(self, query_entities: List[Dict], 
                            doc_entities: Dict[str, List]) -> Tuple[float, List[str]]:
        boost = 0.0
        reasons = []
        
        query_persons = [e for e in query_entities if e['label'] == 'PERSON']
        if not query_persons or 'PERSON' not in doc_entities:
            return boost, reasons
            
        for query_person in query_entities:
            query_name = self.persons_data.standardize_name(query_person['text'])
            # Find best matching name and its similarity score
            best_name, best_score = max(((name, self.name_matcher.name_similarity(query_name, name)) 
                                    for name in (self.persons_data.standardize_name(n) for n in doc_entities['PERSON'])), 
                                    key=lambda x: x[1], default=(None, 0))
            
            if best_score >= self.config.NAME_MATCH_THRESHOLD:
                match_quality = best_score / 100
                person_boost = self.config.PERSON_BOOST * match_quality
                boost += person_boost
                reasons.append(f"person match ({query_name} → {best_name}, {match_quality:.2f}): +{person_boost:.3f}")
                
        return boost, reasons

    def _calculate_metadata_boost(self, metadata: Dict, query_text: str) -> Tuple[float, List[str]]:
        boost = 0.0
        reasons = []
        
        # Standardize query terms
        query_terms = {self.persons_data.standardize_name(term.lower()) for term in query_text.split()}
        
        # Process hashtags and mentions using standardized names
        hashtags = [self.persons_data.standardize_name(tag.lower().lstrip('#')) for tag in metadata.get('hashtags', [])]
        mentions = [self.persons_data.standardize_name(mention.lower().lstrip('@')) for mention in metadata.get('mentions', [])]
        
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

    def _rerank_results(self, results: List[Dict], query_text: str, entity: Optional[Dict], query_intent: QueryIntent) -> List[Dict]:
        reranked = []
        query_terms = self.text_processor.extract_search_terms(query_text)
        
        for result in results:
            metadata = self.decode_metadata(result['metadata'])
            doc_entities = metadata.get('entities', {})
            exact_match = result.get('exact_match', False)
            
            scores = self._calculate_scores(
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
        
        return sorted(reranked, key=lambda x: x['relevance_score'], reverse=True)

# Utility Methods
    def decode_metadata(self, metadata: Dict) -> Dict:
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

    def save_results(self, results: List[Dict], query: str) -> None:
        formatted_output = QueryResultFormatter.format_results(results, query)
        
        Path("results").mkdir(exist_ok=True)
        file_path = Path(self.config.RESULTS_FILE)
        
        try:
            if not file_path.exists():
                all_results = {"queries": [formatted_output]}
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    all_results = json.load(f)
                    all_results["queries"].append(formatted_output)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)
                
            self.console.print(f"\nResults saved to {self.config.RESULTS_FILE}")
            
        except Exception as e:
            self.console.print(f"[red]Error saving results: {e}")

    def display_results(self, results: List[Dict], query: str) -> None:
        table = Table(title=f"Search Results for: {query}")
        table.add_column("Initial Score", justify="right", style="cyan", width=12)
        table.add_column("Final Score", justify="right", style="cyan", width=12) 
        table.add_column("Document", style="green", width=50)
        table.add_column("Source", style="blue", width=20)
        table.add_column("Matches", style="yellow", width=30)

        for result in results:
            scores = result['score_breakdown']
            matches = []
            
            # Include all boost types
            if scores.get('entity_reasons'):
                matches.extend(scores['entity_reasons'])
            if scores.get('person_reasons'):
                matches.extend(scores['person_reasons'])
            if scores.get('metadata_reasons'):
                matches.extend(scores['metadata_reasons'])
            if scores.get('term_boost') > 0:
                matches.append(f"term match: +{scores['term_boost']:.3f}")

            metadata = result.get('metadata', {})
            source_info = f"ID: {str(metadata.get('source_id', 'N/A'))[:15]}...\n"
            source_info += f"Platform: {metadata.get('platform', 'N/A')}"

            table.add_row(
                f"{scores['initial_score']:.3f}",
                f"{scores['final_score']:.3f}", 
                result['document'][:200] + "..." if len(result['document']) > 200 else result['document'],
                source_info,
                '\n'.join(matches)
            )

        self.console.print(table)

    def run_interactive(self) -> None:
        while True:
            query = self.console.input("\nEnter search query (or 'quit' to exit): ")
            if query.lower() == 'quit':
                break
                
            results = self.search(query)
            if results:
                self.display_results(results, query)
                self.save_results(results, query)
            else:
                self.console.print("[yellow]No results found")

if __name__ == "__main__":
    config = SearchConfig.create_default()
    searcher = ChromaSearch(config)
    searcher.run_interactive()