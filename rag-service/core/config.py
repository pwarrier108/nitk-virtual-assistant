# Standard library imports
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional


class QueryIntent(Enum):
    GENERAL = "general"
    PERSON = "person"
    ORGANIZATION = "organization" 
    EVENT = "event"
    LOCATION = "location"

@dataclass
class Config:
    # Global settings
    # TODO: Read debug from environment variable instead of hardcoding to True
    # Suggestion: debug: bool = field(default_factory=lambda: os.getenv('DEBUG', 'False') == 'True')
    debug: bool = True
    
    # API configuration
    api_title: str = "RAG Service API"
    api_description: str = "API service for RAG-based question answering"
    api_version: str = "1.0.0"
    
    # Cache settings - point to parent directory (RAG responses only)
    cache_dir: Path = Path("../cache")
    cache_max_age_days: int = 7
    cache_max_size_gb: int = 1 
    cache_cleanup_interval_hours: int = 24
    cache_max_entries: int = 10000
    
    # Chroma DB settings - point to parent directory
    chroma_path: Path = Path("../outputs/chroma_db")
    hnsw_config: dict = field(default_factory=lambda: {
        "ef_construction": 450,
        "ef_search": 100,
        "M": 64,
        "num_threads": 1
    })

    # Collection settings
    COLLECTION_NAME: str = "nitk_knowledgebase"
    DEFAULT_RESULTS: int = 5

    # CORS configuration
    # TODO: SECURITY - Restrict CORS origins in production! Using "*" allows all origins which is a security risk
    # TODO: Set cors_allow_origins to specific domains: ["http://localhost:3000", "http://192.168.1.x"]
    # TODO: Consider setting cors_allow_credentials to False if not needed
    cors_allow_origins: List[str] = field(default_factory=lambda: ["*"])
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = field(default_factory=lambda: ["*"])
    cors_allow_headers: List[str] = field(default_factory=lambda: ["*"])
    
    # Entity and search parameter files - point to parent directory
    PERSONS_FILE: Path = Path("../config/persons.json")
    ORGS_FILE: Path = Path("../config/organizations.json") 
    LOCATIONS_FILE: Path = Path("../config/locations.json")
    EVENTS_FILE: Path = Path("../config/events.json")
    TITLES_FILE: Path = Path("../config/titles.json")
    
    # Entity recognition 
    name_patterns: List[str] = field(default_factory=lambda: [
        r'(?:Prof|Dr|Mr|Mrs|Ms|Shri)\.?\s+(?:[A-Z]\.\s*)*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',
        r'[A-Z][a-z]+\s+(?:[A-Z]\.\s*)*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*'
    ])
    spacy_model: str = "en_core_web_sm"

    # Logging settings - point to parent directory
    log_file: str = f"rag_{datetime.now().strftime('%Y%m%d')}.log"
    log_path: Path = Path("../logs")
    results_file: str = f"rag_queries_{datetime.now().strftime('%Y%m%d')}.jsonl"
    results_log: bool = True
    results_path: Path = Path("../results")
    
    # Language support (kept for compatibility, but not used for caching)
    supported_languages: dict = field(default_factory=lambda: {
        "Hindi": "hi",
        "Kannada": "kn",
        "Malayalam": "ml",
        "Tamil": "ta",
        "Telugu": "te",
        "English": "en"
    })

    # Perplexity settings
    perplexity_enabled: bool = True
    perplexity_model: str = "sonar"
    perplexity_timeout: int = 60

    # Query settings
    embedding_model: str = 'all-MiniLM-L6-v2'
    openai_model: str = "gpt-4o-mini"
    temperature: float = 0.4

    # Request limits and timeouts
    max_query_length: int = 1000
    request_timeout: int = 60
    health_check_timeout: int = 5
    detailed_error_responses: bool = True  # Set False for production

    # Search and scoring parameters
    PERSON_BOOST: float = 0.15
    ORG_BOOST: float = 0.1
    LOCATION_BOOST: float = 0.08
    EVENT_BOOST: float = 0.08
    ENTITY_BOOST: float = 0.1
    EXACT_MATCH_BOOST: float = 0.15
    HASHTAG_BOOST: float = 0.02
    MENTION_BOOST: float = 0.02
    METADATA_BOOST_CAP: float = 0.1
    MIN_RELEVANCE_SCORE: float = 0.25
    MIN_TERM_MATCH: float = 0.7
    NAME_MATCH_THRESHOLD: float = 80.0
    INITIAL_WEIGHT: float = 0.4
    EXACT_WEIGHT: float = 0.6

    # Server configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    server_reload: bool = True
    server_log_level: str = "info"
    
    # Service provider settings (kept for compatibility)
    tts_provider: str = "google"
    translation_provider: str = "google"

    # System prompt settings
    system_prompt: str = """You are NITK's knowledgeable virtual assistant. Current date: {current_date}
    About NITK: The National Institute of Technology Karnataka (NITK) in Surathkal was known as Karnataka Regional Engineering College (KREC) until 2002.
    MANDATORY DATE LOGIC:
    Before responding about ANY event, you MUST determine if the event date is before or after {current_date}.
    - If event date is BEFORE {current_date}: Use past tense only ("took place", "was held", "happened")
    - If event date is AFTER {current_date}: Use future tense only ("will take place", "is scheduled")

    When you see "February 2025" and today is {current_date}, February 2025 is PAST - you must use past tense.
    When you see "December 2024" and today is {current_date}, December 2024 is PAST - you must use past tense.

    PROHIBITED: Do not use vague time references like "recently," "last week," "lately," "just happened" for events with specific dates. Instead, use the actual timeframe ("in February 2025") or be specific about timing.
    Do not say "is scheduled for" or "will take place" for any date that has already passed.
    For uncertain information: Use "Based on available information..." or "The most recent data shows..."
    Engage warmly and professionally while being temporally accurate."""
    system_prompt_path: Optional[Path] = None

    # Synthesis settings
    synthesis_model: str = "gpt-4o-mini"
    synthesis_temperature: float = 0.3
    synthesis_max_tokens: int = 400
    
    # UI settings 
    chat_container_height: int = 350
    card_max_width: str = "4xl"

    # Temporal detection settings
    temporal_keywords: List[str] = field(default_factory=lambda: ["latest", "recent", "current", "new", "now", "today", "this year"])
    status_keywords: List[str] = field(default_factory=lambda: ["updates", "announcements", "changes", "progress", "news"])
    relative_time_keywords: List[str] = field(default_factory=lambda: ["last month", "past year", "recently announced"])
    current_year_range: int = 1  # ±1 year from current