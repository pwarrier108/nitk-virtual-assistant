# Standard library imports
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Third-party imports
from thefuzz import fuzz

# Local application imports
from .config import Config, QueryIntent


logger = logging.getLogger(__name__)

class PersonsData:
    def __init__(self, persons_file: Path):
        self.persons = set()
        self.title_patterns = []
        self.role_patterns = []
        self.name_formats = []
        self.transliterations = {}
        self.persons_lower = set()
        
        try:
            with open(persons_file) as f:
                data = json.load(f)
                self.persons = set(data.get('persons', []))
                self.persons_lower = {p.lower() for p in self.persons}
                self.title_patterns = [re.compile(p, re.IGNORECASE) for p in data.get('title_patterns', [])]
                self.role_patterns = [re.compile(p, re.IGNORECASE) for p in data.get('role_patterns', [])]
                self.name_formats = data.get('name_formats', [])
                self.transliterations = data.get('transliterations', {})
        except Exception as e:
            logger.error(f"Error loading {persons_file}: {e}")

    def standardize_name(self, name: str) -> str:
        name = self.transliterations.get(name.lower(), name)
        name = ' '.join(name.split())
        name = re.sub(r'(\w)\.\s*', r'\1 ', name)
        
        for fmt in self.name_formats:
            name = re.sub(fmt['pattern'], fmt['replacement'], name, flags=re.IGNORECASE)
        return name.strip()

    def is_known_person(self, name: str) -> bool:
        std_name = self.standardize_name(name).lower()
        return (std_name in self.persons_lower or 
                any(fuzz.ratio(std_name, known) > 90 
                    for known in self.persons_lower))

class NameMatcher:
    def __init__(self, config: Config):
        self.persons_data = PersonsData(config.PERSONS_FILE)
        self.initial_weight = config.INITIAL_WEIGHT
        self.exact_weight = config.EXACT_WEIGHT

    def normalize_name(self, name: str) -> str:
        name = self.persons_data.standardize_name(name)
        return re.sub(r'[^\w\s]', '', name.lower())

    def _compute_part_similarity(self, part1: str, part2: str) -> float:
        if not part1 or not part2:
            return 0.0
            
        exact_match = part1 == part2
        if exact_match:
            return 1.0
            
        initial_match = (part1[0] == part2[0] and 
                        (len(part1) == 1 or len(part2) == 1))
        if initial_match:
            return self.initial_weight
            
        fuzzy_ratio = fuzz.ratio(part1, part2) / 100
        return fuzzy_ratio * self.exact_weight

    def name_similarity(self, name1: str, name2: str) -> float:
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
            
        similarities = []
        max_parts = max(len(parts1), len(parts2))
        
        for i in range(max_parts):
            if i >= len(parts1) or i >= len(parts2):
                similarities.append(0.0)
            else:
                sim = self._compute_part_similarity(parts1[i], parts2[i])
                similarities.append(sim)
                
        weights = [1.2 if i == 0 or i == len(similarities)-1 else 1.0 
                  for i in range(len(similarities))]
                  
        weighted_sum = sum(s * w for s, w in zip(similarities, weights))
        final_score = (weighted_sum / sum(weights)) * 100
        
        if self.persons_data.is_known_person(name1) or self.persons_data.is_known_person(name2):
            final_score *= 1.1
            
        return min(final_score, 100.0)

class EntityExtractor:
    def __init__(self, config: Config):
        self.config = config
        self.entities = {}
        self.entities_lower = {}
        self._load_entities()
        self.persons_data = PersonsData(config.PERSONS_FILE)
        self.name_matcher = NameMatcher(config)
        
    def _load_entities(self):
        entity_files = {
            'PERSON': (self.config.PERSONS_FILE, 'persons'),
            'ORGANIZATION': (self.config.ORGS_FILE, 'organizations'),
            'LOCATION': (self.config.LOCATIONS_FILE, 'locations'),
            'EVENT': (self.config.EVENTS_FILE, 'events')
        }
        
        for entity_type, (file_path, key) in entity_files.items():
            try:
                with open(file_path) as f:
                    data = json.load(f)
                    if key == 'locations':
                        locs = data[key]
                        entities = set().union(*[set(locs[k]) for k in ['cities', 'states', 'countries', 'campus_locations', 'other']])
                    else:
                        entities = set(data[key])
                    self.entities[entity_type] = entities
                    self.entities_lower[entity_type] = {e.lower() for e in entities}
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
                self.entities[entity_type] = set()
                self.entities_lower[entity_type] = set()

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        text_lower = text.strip().lower()
        
        # Check exact matches
        for entity_type, entity_lower_set in self.entities_lower.items():
            if text_lower in entity_lower_set:
                matching_entity = next(e for e in self.entities[entity_type] 
                                    if e.lower() == text_lower)
                return [{"text": matching_entity, "label": entity_type}]
        
        # Process chunks with early exit
        text_parts = text.strip().split()
        chunk_size = 5
        chunks = [' '.join(text_parts[i:i+chunk_size]) 
                for i in range(0, len(text_parts), chunk_size)]
        seen = set()
        
        for chunk in chunks:
            if chunk in seen:
                continue
            seen.add(chunk)
            chunk_lower = chunk.lower()
            
            # Try high-confidence non-PERSON matches first
            for entity_type, entity_set in self.entities.items():
                if entity_type == 'PERSON':
                    continue
                
                match = self._get_best_match(chunk_lower, entity_type)
                if match and match.get('confidence', 0) > 0.9:
                    return [match]
        
        # Check PERSON entities last
        for chunk in chunks:
            if chunk_lower := chunk.lower():
                match = self._get_best_match(chunk_lower, 'PERSON')
                if match:
                    return [match]
        
        return []

    def _get_best_match(self, text_lower: str, entity_type: str) -> Optional[Dict]:
        if not text_lower or not self.entities[entity_type]:
            return None
            
        if entity_type == 'PERSON':
            best_match = max(self.entities[entity_type],
                key=lambda x: self.name_matcher.name_similarity(text_lower, x),
                default=None)
            score = self.name_matcher.name_similarity(text_lower, best_match) / 100 if best_match else 0
            
            if score >= 0.8:
                return {"text": best_match, "label": entity_type}
                
        else:
            entity_lower_set = self.entities_lower[entity_type]
            if text_lower in entity_lower_set:
                matching_entity = next(e for e in self.entities[entity_type] 
                                    if e.lower() == text_lower)
                return {"text": matching_entity, "label": entity_type}
            
            best_score = 0
            best_match = None
            
            for entity in self.entities[entity_type]:
                score = fuzz.token_sort_ratio(text_lower, entity.lower()) / 100
                if score > best_score:
                    best_score = score
                    best_match = entity
                if score >= 0.9:
                    break
                    
            if best_score >= 0.8:
                return {"text": best_match, "label": entity_type}
        
        return None