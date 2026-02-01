import emoji
import json
import logging
import re
import spacy
import tqdm
import unicodedata
from datetime import datetime 
from deep_translator import GoogleTranslator
from pathlib import Path
from transformers import pipeline
from typing import Dict, List, Optional, Set

class Config:
    DEBUG = True
    DUPLICATE_ENTITY_THRESHOLD = 0.85
    ENTITY_CONFIDENCE_THRESHOLD = 0.85
    EVENTS_FILE = "config/events.json"
    INPUT_FILE = "inputs/instagram_posts.json"
    LOCATIONS_FILE = "config/locations.json"
    LOG_DIR = "logs"
    MAX_RECORDS = 0
    MIN_ENTITY_LENGTH = 2
    MIN_ENTITY_LENGTH_SKIP = 3
    ORGS_FILE = "config/organizations.json"
    OUTPUT_FILE = "outputs/instagram/processed_instagram.json"
    PERSONS_FILE = "config/persons.json"
    SCRIPT_THRESHOLD = 0.3
    SIMILARITY_RATIO = 0.75
    SIMILARITY_THRESHOLD = 0.75
    TITLES_FILE = "config/titles.json"
    UPDATED_ENTITIES_FILE = "config/updated-entities-with-learning(instagram).json"

class Stats:
    matched_entities_count = 0
    new_entities_count = 0
    processed_entities_count = 0
    processed_records_count = 0
    translated_count = 0
    text_char_counts = []
    
    @classmethod
    def add_text_length(cls, text: str):
        if text:
            cls.text_char_counts.append(len(text))
    
    @classmethod
    def get_avg_text_length(cls) -> float:
        return sum(cls.text_char_counts) / len(cls.text_char_counts) if cls.text_char_counts else 0

class DocumentProcessor:
    def __init__(self):
        self.location_processor = LocationProcessor()
        self.entity_processor = EntityProcessor(self.location_processor)
        self.text_processor = TextProcessor()
        self._setup_logging()  

    def _setup_logging(self):
        if Config.DEBUG:
            log_file = Path(Config.LOG_DIR) / f"processor_{datetime.now().strftime('%Y%m%d')}.log"
            log_file.parent.mkdir(exist_ok=True)
            
            # Configure root logger
            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)
            
            # Remove existing handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
                
            # Create and configure file handler with UTF-8 encoding
            handler = logging.FileHandler(str(log_file), encoding='utf-8')
            handler.setFormatter(logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            logger.addHandler(handler)

    def process_document(self, source_type: str, input_json: Dict) -> Dict:
        try:
            if source_type == "instagram":
                result = self._process_instagram(input_json)
                Stats.processed_records_count += 1
                return result
            raise ValueError(f"Unknown source type: {source_type}")
        except Exception as e:
            logging.error(f"Error processing {source_type}: {str(e)}")
            raise

    def _process_instagram(self, input_json: Dict) -> Dict:
        original_text = input_json.get("caption", "")
        cleaned_english, original_text, detected_lang = self.text_processor.process_text_workflow(original_text)
        
        # Get non-location entities
        entities = self.entity_processor.detect_entities(cleaned_english)
        
        # Process locations from multiple sources 
        locations = set()
        
        # Get NER locations
        ner_results = self.entity_processor.matcher.match_entities(cleaned_english)
        locations.update(self.location_processor.process_location_entities(ner_results))
        
        # Get locations from text context
        locations.update(self.location_processor.extract_locations_from_text(cleaned_english))
        
        # Get venue/building locations
        locations.update(self.location_processor.extract_venue_locations(cleaned_english))
        
        # Process metadata location
        input_location = input_json.get("locationName")
        if input_location:
            locations.update(self.location_processor.clean_location(input_location))

        # Add locations to entities
        entities["LOCATION"] = list(locations)

        return {
            "source_id": input_json.get("id", ""),
            "source_url": input_json.get("url", ""),
            "platform": "instagram",
            "content": {
                "text": cleaned_english,
                "original_text": original_text, 
                "text_length": len(cleaned_english),
                "language": detected_lang,
                "entities": entities
            },
            "created_date": input_json.get("timestamp", ""),
            "author_name": input_json.get("ownerFullName", ""),
            "hashtags": ["#" + tag for tag in input_json.get("hashtags", [])],
            "mentions": ["@" + mention for mention in input_json.get("mentions", [])]
        }

class EntityCleaner:
    @staticmethod
    def standardize_org_name(name: str) -> str:
        name = re.sub(r'^(the|a|an)\s+', '', name, flags=re.IGNORECASE)
        patterns = {
            r'Govt\.?\s+of': 'Government of',
            r'(?:G\.?O\.?I\.?|GoI)': 'Government of India',
            r'Ministry of ([^,]+?)(?:\s*,\s*Government of India)?$': 'Ministry of \\1',
            r'Department of ([^,]+?)(?:\s*,\s*Government of India)?$': 'Department of \\1',
            r'(?:NITK|NIT-K|NIT Karnataka|National Institute of Technology Karnataka)(?:\s+Surathkal)?': 'National Institute of Technology Karnataka',
            r'Institute of National Importance': 'Institute of National Importance under Ministry of Education',
            r'(?:The\s+)?([^,]+)\s+Department': '\\1 Department',
            r'(?:The\s+)?([^,]+)\s+Ministry': '\\1 Ministry'
        }
        for pattern, repl in patterns.items():
            name = re.sub(pattern, repl, name, flags=re.IGNORECASE)
        return name.strip()

    @staticmethod
    def clean_title(title: str) -> str:
        title = re.sub(r'[^\w\s]', '', title)
        title = ' '.join(w.capitalize() for w in title.split())
        return title.strip()

    @staticmethod
    def standardize_person_name(name: str, context: str = "") -> str:
        name = re.sub(r'[\w\.-]+@[\w\.-]+|https?://\S+', '', name)
        name = re.sub(r'[^\w\s.-]', '', name)
        parts = name.split()

        for i, part in enumerate(parts):
            if re.match(r'^[A-Z]$', part):
                parts[i] = part + '.'
            elif re.match(r'^[A-Z]\.$', part):
                continue
            elif re.match(r'^[A-Z][A-Z]+$', part):
                parts[i] = '.'.join(list(part)) + '.'

        if context:
            titles = re.findall(r'(Prof\.|Dr\.|Shri|Director|Chairman|Dean)\s+([A-Z][A-Za-z\s.]+)', context)
            if titles:
                for title, full_name in titles:
                    if name in full_name:
                        name = full_name
                        parts = name.split()

        for i, part in enumerate(parts):
            if re.match(r'^[A-Z]\.?$', part):
                parts[i] = part.upper()
            else:
                parts[i] = part.capitalize()

        return ' '.join(parts).strip()

    @staticmethod
    def is_duplicate_entity(entity1: str, entity2: str, threshold: float = Config.DUPLICATE_ENTITY_THRESHOLD) -> bool:
        e1 = re.sub(r'[^\w\s]', '', entity1.lower())
        e2 = re.sub(r'[^\w\s]', '', entity2.lower())

        if e1 in e2 or e2 in e1:
            return True

        s1 = set(e1.split())
        s2 = set(e2.split())

        if not s1 or not s2:
            return False

        intersection = len(s1.intersection(s2))
        union = len(s1.union(s2))

        return (intersection / union) > threshold

class EntityMatcher:
    def __init__(self):
        self.model = pipeline('ner', model='dslim/bert-base-NER')
        self.confidence_threshold = Config.ENTITY_CONFIDENCE_THRESHOLD

    def match_entities(self, text: str) -> List[Dict]:
        try:
            results = self.model(text)
            return [{'text': r['word'], 'score': r['score'], 'label': r['entity']} 
                   for r in results if r['score'] > self.confidence_threshold]
        except Exception as e:
            logging.error(f"Entity matching error: {str(e)}")
            return []
            
    def is_match(self, candidate: str, known_entity: str, category: str) -> bool:
        if not candidate or not known_entity:
            return False
            
        if category == 'LOCATION':
            return candidate.lower() in self.location_data['known_locations']
            
        return EntityCleaner.is_duplicate_entity(candidate, known_entity, Config.SIMILARITY_THRESHOLD)

class LocationProcessor:
    def __init__(self):
        self.location_data = self._load_location_data()
        self.location_patterns = {
            'qualifiers': r'(?:near|in|at|behind|next to|across from|opposite|inside|within)\s+',
            'buildings': r'(?:Building|Block|Hall|Complex|Centre|Center|Lab|Laboratory|Department|Dept)',
            'venues': r'(?:Auditorium|Ground|Stadium|Field|Court|Room|Theatre|Theater|Arena)'
        }
        self._init_known_locations()
        self._init_venue_mappings()

    def _init_known_locations(self):
        known_locations = {}
        for category in self.location_data['locations'].values():
            if isinstance(category, list):
                for loc in category:
                    known_locations[loc.lower()] = loc
        self.location_data['known_locations'] = known_locations

    def _init_venue_mappings(self):
        # Initialize from campus_locations
        campus_locs = self.location_data['locations'].get('campus_locations', [])
        
        # Create building_locations mapping
        building_locations = {}
        for loc in campus_locs:
            building_locations[loc.lower()] = loc
        self.location_data['building_locations'] = building_locations
        
        # Create venue_mappings (same as building_locations for now)
        self.location_data['venue_mappings'] = building_locations.copy()

    def get_all_locations(self) -> List[str]:
        all_locations = []
        for category in self.location_data['locations'].values():
            if isinstance(category, list):
                all_locations.extend(category)
        return sorted(list(set(all_locations)))

    def _load_location_data(self) -> Dict:
        try:
            with open(Config.LOCATIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"Location data file not found: {Config.LOCATIONS_FILE}")
            return {
                'locations': {},
                'address_patterns': {},
                'city_synonyms': {},
                'state_codes': {},
                'location_hierarchy': {},
                'venue_mappings': {},
                'building_locations': {}
            }
 
    def process_location_entities(self, ner_results: List[Dict]) -> List[str]:
        locations = set()
        for entity in ner_results:
            if entity['label'] in ['FAC', 'GPE', 'LOC']:
                clean_locs = self.clean_location(entity['text'])
                if clean_locs:
                    locations.update(clean_locs)
                    
        # Get parent locations from hierarchy
        parent_locations = set()
        for loc in locations:
            if loc in self.location_data['location_hierarchy']:
                parent_locations.update(self.location_data['location_hierarchy'][loc])
                
        return list(locations | parent_locations)

    def clean_location(self, loc: str) -> Set[str]:
        if not loc or len(loc.strip()) < 2:
            return set()

        cleaned_locations = set()
        location = loc.strip()
        
        # Apply address patterns
        for pattern, replacement in self.location_data['address_patterns'].items():
            location = re.sub(pattern, replacement, location, flags=re.IGNORECASE)
        
        # Handle state codes
        for code, state in self.location_data['state_codes'].items():
            location = re.sub(rf'\b{code}\b', state, location, flags=re.IGNORECASE)
            
        # Handle city synonyms
        words = location.split()
        for i, word in enumerate(words):
            lower_word = word.lower()
            if lower_word in self.location_data['city_synonyms']:
                words[i] = self.location_data['city_synonyms'][lower_word]
        location = ' '.join(words)
        
        # Split hierarchical locations
        parts = [p.strip() for p in re.split(r'[,/]', location)]
        
        # Process each part
        for part in parts:
            clean_part = re.sub(r'[^\w\s.-]', '', part).strip()
            if clean_part.lower() in self.location_data['known_locations']:
                cleaned_locations.add(self.location_data['known_locations'][clean_part.lower()])
                
        return cleaned_locations

    def extract_locations_from_text(self, text: str) -> Set[str]:
        locations = set()
        
        # Extract locations with qualifiers
        qualifier_pattern = f"{self.location_patterns['qualifiers']}([A-Z][A-Za-z\\s,.-]+?)(?=[,.!?]|$)"
        matches = re.finditer(qualifier_pattern, text, re.IGNORECASE)
        for match in matches:
            clean_locs = self.clean_location(match.group(1))
            locations.update(clean_locs)
            
        # Extract locations without qualifiers
        location_pattern = r'\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*(?:\s*,\s*[A-Z][A-Za-z]+)*)\b'
        matches = re.finditer(location_pattern, text)
        for match in matches:
            clean_locs = self.clean_location(match.group(1))
            locations.update(clean_locs)
            
        return locations

    def extract_venue_locations(self, text: str) -> Set[str]:
        venues = set()
        
        # Match building patterns
        building_pattern = f"{self.location_patterns['buildings']}\\s+([A-Z][A-Za-z\\s-]+)"
        matches = re.finditer(building_pattern, text, re.IGNORECASE)
        for match in matches:
            venue = match.group(1).strip()
            if venue.lower() in self.location_data['building_locations']:
                venues.add(self.location_data['building_locations'][venue.lower()])
                
        # Match venue patterns
        venue_pattern = f"{self.location_patterns['venues']}\\s+([A-Z][A-Za-z\\s-]+)"
        matches = re.finditer(venue_pattern, text, re.IGNORECASE)
        for match in matches:
            venue = match.group(1).strip()
            if venue.lower() in self.location_data['venue_mappings']:
                venues.add(self.location_data['venue_mappings'][venue.lower()])
                
        return venues

    def is_known_location(self, location: str) -> bool:
       normalized = re.sub(r'\s*,\s*', ', ', location.strip())
       return normalized in self.location_data['known_locations']

class EntityProcessor:
    def __init__(self, location_processor: LocationProcessor):
        self.location_processor = location_processor
        self.matcher = EntityMatcher()
        self.new_entities = {k: set() for k in ['PERSON', 'ORG', 'EVENT', 'TITLE','LOCATION']}
        self.seen_entities = {k: set() for k in ['PERSON', 'ORG', 'EVENT', 'TITLE', 'LOCATION']}
        self.entities = self.load_entities()

    def load_entities(self) -> Dict:
        entities = {
            'PERSON': self._load_entity_file(Config.PERSONS_FILE, 'persons'),
            'ORG': self._load_entity_file(Config.ORGS_FILE, 'organizations'),  
            'EVENT': self._load_entity_file(Config.EVENTS_FILE, 'events'),
            'TITLE': self._load_entity_file(Config.TITLES_FILE, 'titles'),
            'LOCATION': self.location_processor.get_all_locations()
        }
        if Config.DEBUG:
            print("\nLoaded entities from files:")
            for category, items in entities.items():
                print(f"{category}: {len(items)} entities")
        return entities

    def _load_entity_file(self, filepath: str, key: str) -> List[str]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get(key, []) if isinstance(data, dict) else data
        except FileNotFoundError:
            if Config.DEBUG:
                print(f"\nWarning: {filepath} not found, using empty list")
            return []

    def detect_entities(self, text: str) -> Dict[str, List[str]]:
        entities = {
            'PERSON': [], 'ORG': [], 'EVENT': [], 
            'TITLE': [], 'LOCATION': []
        }
        
        ner_results = self.matcher.match_entities(text)
        
        # Process locations
        location_entities = self.location_processor.process_location_entities(ner_results)
        entities['LOCATION'] = location_entities
        Stats.processed_entities_count += len(location_entities)
        for loc in location_entities:
            if loc in self.entities['LOCATION']:
                Stats.matched_entities_count += 1
            else:
                Stats.new_entities_count += 1
                self.new_entities['LOCATION'].add(loc)

        # Process NER entities    
        for result in ner_results:
            if result['label'] != 'LOCATION':
                clean_entity = self._clean_entity(result['text'], result['label'])
                if clean_entity:
                    category = self._map_ner_label(result['label'])
                    if category and category != 'LOCATION':
                        if clean_entity not in entities[category]:
                            entities[category].append(clean_entity)
                            Stats.processed_entities_count += 1
                            
                            if clean_entity in self.entities[category]:
                                Stats.matched_entities_count += 1 
                            else:
                                Stats.new_entities_count += 1
                                self.new_entities[category].add(clean_entity)

        # Process person patterns
        person_data = self.entities['PERSON']
        title_patterns = [pattern for pattern in person_data if isinstance(pattern, str)]
        for pattern in title_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                clean_entity = self._clean_entity(match.group(0), 'PERSON')
                if clean_entity and clean_entity not in entities['PERSON']:
                    entities['PERSON'].append(clean_entity)
                    Stats.processed_entities_count += 1
                    
                    if clean_entity in self.entities['PERSON']:
                        Stats.matched_entities_count += 1
                    else:
                        Stats.new_entities_count += 1
                        self.new_entities['PERSON'].add(clean_entity)
        
        return entities

    def _is_similar_entity(self, text1: str, text2: str) -> bool:
        t1, t2 = text1.lower(), text2.lower()

        if t1 in t2 or t2 in t1:
            return True

        words1 = set(t1.split())
        words2 = set(t2.split())

        if not words1 or not words2:
            return False

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        similarity = intersection / union

        return (similarity > Config.SIMILARITY_THRESHOLD and 
                intersection >= min(len(words1), len(words2)) * Config.SIMILARITY_RATIO)

    def _remove_noise(self, text: str) -> str:
        text = TextCleaner.normalize_unicode(text)
        clean_text = text
        for pattern in self.exclude_patterns:
            clean_text = re.sub(pattern, ' ', clean_text)
        return ' '.join(clean_text.split())

    def _get_entity_context(self, doc, ent):
        start_idx = max(0, ent.start - Config.CONTEXT_WINDOW)
        end_idx = min(len(doc), ent.end + Config.CONTEXT_WINDOW)
        return doc[start_idx:end_idx].text

    def _apply_boundary_patterns(self, text: str, label: str) -> Optional[str]:
        mapped_category = self._map_spacy_label(label)
        if not mapped_category or mapped_category not in self.boundary_patterns:
            return None

        for pattern in self.boundary_patterns[mapped_category]:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None

    def _should_skip_entity(self, ent) -> bool:
        return (
            ent.label_ in ['CARDINAL', 'DATE', 'TIME', 'MONEY', 'PERCENT', 'QUANTITY'] or
            len(ent.text.strip()) < Config.MIN_ENTITY_LENGTH_SKIP or
            ent.text.isnumeric() or
            all(c in '.,!?-_@#' for c in ent.text) or
            any(re.search(pattern, ent.text) for pattern in self.exclude_patterns)
        )

    def _clean_entity(self, entity: str, label: str) -> Optional[str]:
        if not entity or len(entity.strip()) < Config.MIN_ENTITY_LENGTH:
            return None
                
        if label == 'LOCATION':
            clean_locs = self.location_processor.clean_location(entity)
            cleaned = list(clean_locs)[0] if clean_locs else None
            if cleaned:
                Stats.processed_entities_count += 1
            return cleaned
                
        if label == 'PERSON':
            person_data = self.entities['PERSON']
            name_formats = [item for item in person_data if isinstance(item, dict)]
            clean_name = entity.strip()
            for format in name_formats:
                clean_name = re.sub(format['pattern'], format['replacement'], clean_name)
            if clean_name.strip():
                Stats.processed_entities_count += 1
            return clean_name.strip()
                
        Stats.processed_entities_count += 1    
        return entity.strip()

    def _map_ner_label(self, ner_label: str) -> Optional[str]:
        mapping = {
            'PER': 'PERSON',
            'ORG': 'ORG', 
            'LOC': 'LOCATION',
            'MISC': None
        }
        return mapping.get(ner_label)

    def save_discovered_entities(self):
        for category in self.new_entities:
            for entity in self.new_entities[category]:
                if len(entity.strip()) > 2 and entity not in self.entities[category]:
                    self.seen_entities[category].add(entity)

        with open(Config.UPDATED_ENTITIES_FILE, 'w', encoding='utf-8') as f:
            entities_to_save = {k: sorted(list(v)) for k, v in self.seen_entities.items()}
            json.dump(entities_to_save, f, indent=2, ensure_ascii=False)

class TextCleaner:
    @staticmethod
    def normalize_unicode(text: str) -> str:
        text = unicodedata.normalize('NFKD', text)
        for c in text:
            if 0x1D400 <= ord(c) <= 0x1D7FF or 0xFF21 <= ord(c) <= 0xFF3A or 0xFF41 <= ord(c) <= 0xFF5A:
                text = text.replace(c, chr(ord('A') + (ord(c) - 0x1D400) % 26))
        return text

    @staticmethod
    def remove_emojis(text: str) -> str:
        return emoji.replace_emoji(text, '')
    
    @staticmethod 
    def extract_social_elements(text: str) -> tuple:
        hashtags = re.findall(r'#\w+', text)
        mentions = re.findall(r'@\w+', text)
        return hashtags, mentions

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""
        text = TextCleaner.normalize_unicode(text)
        text = re.sub(r'#\w+|@[\w.-]+', '', text)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'[\w\.-]+@[\w\.-]+', '', text)
        text = TextCleaner.remove_emojis(text)
        text = re.sub(r'[^\w\s.,!?:;()-]', ' ', text)
        text = re.sub(r'(\d+)\s*:\s*(\d+)', r'\1:\2', text)
        text = re.sub(r'[\n\r\t]+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

class TextProcessor:
    def __init__(self):
        self.cleaner = TextCleaner()
        self._script_ranges = {
            'devanagari': ((0x0900, 0x097F), (0xA8E0, 0xA8FF), (0x1CD0, 0x1CFF)),
            'kannada': ((0x0C80, 0x0CFF),)
        }

    def _get_script_ratio(self, text: str, script_ranges: tuple) -> float:
        if not text:
            return 0.0
        # Normalize text before counting script characters
        text = self.cleaner.normalize_unicode(text)
        script_chars = sum(1 for char in text if any(start <= ord(char) <= end 
                                                   for start, end in script_ranges))
        return script_chars / len(text)

    def detect_language(self, text: str) -> str:
        if not text or text.isspace():
            return 'en'
            
        # Normalize text before language detection
        text = self.cleaner.normalize_unicode(text)
        
        text = re.sub(r'[\d\s!"#$%&\'()*+,-./:;<=>?@\[\]^_`{|}~]', '', text)
        
        script_counts = {
            'latin': 0,
            'devanagari': 0,
            'kannada': 0
        }
        
        for char in text:
            char_code = ord(char)
            
            if any(start <= char_code <= end for start, end in self._script_ranges['devanagari']):
                script_counts['devanagari'] += 1
            elif any(start <= char_code <= end for start, end in self._script_ranges['kannada']):
                script_counts['kannada'] += 1
            elif char.isalpha():
                script_counts['latin'] += 1
        
        total_chars = sum(script_counts.values())
        if total_chars == 0:
            return 'hi'
            
        script_ratios = {script: count/total_chars for script, count in script_counts.items()}
        
       
        if script_ratios['kannada'] > Config.SCRIPT_THRESHOLD and script_ratios['kannada'] > script_ratios['devanagari']:
            return 'kn'
        elif script_ratios['devanagari'] > Config.SCRIPT_THRESHOLD:
            return 'hi'
        elif script_ratios['latin'] > Config.SCRIPT_THRESHOLD:
            return 'en'
            
        return 'hi'

    def translate_if_needed(self, text: str, detected_lang: str) -> Optional[str]:
        if detected_lang in ['hi', 'kn']:
            try:
                text = self.cleaner.normalize_unicode(text)
                message = (
                    f"\nTranslation Request:\n"
                    f"Language: {detected_lang}\n" 
                    f"Original text:\n{text}\n"
                    f"{'-' * 80}"
                )
                logging.debug(message)
                
                translator = GoogleTranslator(source=detected_lang, target='en')
                translation = translator.translate(text)
                
                if translation:
                    result = (
                        f"Translation Result:\n"
                        f"English translation:\n{translation}\n"
                        f"{'=' * 80}"
                    )
                    logging.debug(result)
                    Stats.translated_count += 1  # Moved here after successful translation
                    return translation
            except Exception as e:
                logging.error(f"Translation failed: {str(e)}")

    def clean_text(self, text: str) -> str:
        return self.cleaner.clean_text(text)
 
    def process_text_workflow(self, text: str) -> tuple[str, str, Optional[str]]:
        if not text:
            return "", "", "en"
            
        original_text = text  # Keep completely unchanged
        detected_lang = self.detect_language(text)
        english_text = self.translate_if_needed(text, detected_lang) or text
        # Apply cleaning only to output text, not original
        cleaned_english = self.cleaner.clean_text(english_text)
        Stats.add_text_length(cleaned_english)
        
        return cleaned_english, original_text, detected_lang

def main():
    processor = DocumentProcessor()
    try:
        if Config.DEBUG:
            print(f"Reading input file: {Config.INPUT_FILE}")
            
        with open(Config.INPUT_FILE, 'r', encoding='utf-8') as f:
            input_json = json.load(f)
            if Config.DEBUG:
                print("Successfully loaded input JSON")
                
        if isinstance(input_json, list):
            # Apply record limit if configured
            records_to_process = input_json[:Config.MAX_RECORDS] if Config.MAX_RECORDS > 0 else input_json
            total_records = len(records_to_process)
            
            if Config.DEBUG:
                print(f"\nProcessing {total_records} records...")
            
            output = []
            # Create progress bar
            with tqdm.tqdm(total=total_records, desc="Processing posts", unit="post") as pbar:
                for post in records_to_process:
                    output.append(processor.process_document("instagram", post))
                    pbar.update(1)
        else:
            output = processor.process_document("instagram", input_json)
        
        processor.entity_processor.save_discovered_entities()
        
        Path(Config.OUTPUT_FILE).parent.mkdir(exist_ok=True)
        
        with open(Config.OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        if Config.DEBUG:
            print(f"\nProcessing Summary:")
            print(f"Total records processed: {Stats.processed_records_count}")
            print(f"Records translated: {Stats.translated_count}") 
            print(f"Processed entities: {Stats.processed_entities_count}")
            print(f"New entities discovered: {Stats.new_entities_count}")
            print(f"Matched entities: {Stats.matched_entities_count}")
            print(f"Average text length: {Stats.get_avg_text_length():.1f}")
            
    except Exception as e:
        if Config.DEBUG:
            print(f"ERROR: {str(e)}")
        logging.error(f"Failed to process document: {str(e)}")

if __name__ == "__main__":
    main()