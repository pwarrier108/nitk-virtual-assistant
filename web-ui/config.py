from dataclasses import dataclass, field
from typing import List
from pathlib import Path

@dataclass
class WebUIConfig:
    # ========== CACHE SETTINGS ==========
    audio_cache_dir: Path = Path("../cache/audio")
    audio_cache_enabled: bool = True
    cache_cleanup_interval_hours: int = 24
    cache_dir: Path = Path("../cache")
    cache_max_size_mb: int = 500
    cache_translation_ttl_days: int = 7
    cache_audio_ttl_days: int = 7
    translation_cache_enabled: bool = True
    
    # ========== ERROR HANDLING ==========
    connection_retry_attempts: int = 3
    connection_retry_delay: float = 1.0
    fallback_error_message: str = "Service temporarily unavailable. Please try again."
    show_detailed_errors: bool = True
    
    # ========== RAG SERVICE CONNECTION ==========
    rag_service_host: str = "localhost"
    rag_service_port: int = 8000
    rag_service_timeout: int = 60
    rag_service_health_timeout: int = 5
    
    # ========== SESSION STATE MANAGEMENT ==========
    session_vars: dict = field(default_factory=lambda: {
        'messages': [],
        'translated_text': "",
        'processing': False,
        'last_response': "",
        'generating_audio': False,
        'current_audio': None,
        'current_translation_key': None,
        'selected_language': None,
        'language_selector': "Hindi"
    })
    
    # ========== STREAMING SETTINGS ==========
    bullet_pause: float = 0.15     # longer pause after bullet points
    paragraph_pause: float = 0.2   # longer pause after paragraphs
    sentence_pause: float = 0.1    # longer pause after sentences
    smart_chunking: bool = True    # respect markdown structure
    streaming_chunk_size: int = 3  # words for fallback chunking
    streaming_delay: float = 0.01  # seconds between chunks
    streaming_enabled: bool = True
    
    # ========== TRANSLATION SETTINGS ==========
    default_language: str = "Hindi"
    supported_languages: List[str] = field(default_factory=lambda: [
        "Hindi", "Kannada", "Malayalam", "Tamil", "Telugu"
    ])
    translation_provider: str = "google"
    translation_timeout: int = 10
    
    # ========== TTS SETTINGS ==========
    audio_generation_timeout: int = 30
    tts_provider: str = "google"
    tts_timeout: int = 15
    
    # ========== UI LAYOUT SETTINGS ==========
    card_max_width: str = "4xl"
    chat_container_border: bool = True
    chat_container_height: int = 350
    
    # ========== UI MESSAGES AND TEXT ==========
    chat_input_placeholder: str = "Ask a question about NITK"
    generating_button_text: str = "Generating... ⏳"
    play_audio_button_text: str = "Play Audio"
    translate_section_title: str = "Translate into"
    welcome_message: str = (
        "Ask me anything about NITK - I'm here to help! "
        "However, I can make mistakes so please bear with me."
    )
    
    # ========== UI PAGE SETTINGS ==========
    page_icon: str = "🎓"
    page_layout: str = "centered"
    page_title: str = "NITK Information Assistant"
    sidebar_state: str = "collapsed"
    
    # ========== UI STYLING ==========
    primary_button_color: str = "#E9967A"
    primary_button_hover_color: str = "#D2691E"
    primary_button_opacity: float = 0.7  # when disabled
    
    # ========== COMPUTED PROPERTIES ==========
    @property
    def rag_service_url(self) -> str:
        """Construct RAG service URL from host and port."""
        return f"http://{self.rag_service_host}:{self.rag_service_port}"
    
    # ========== UTILITY METHODS ==========
    def ensure_cache_dirs(self) -> None:
        """Ensure all cache directories exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.audio_cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_language_code(self, language_name: str) -> str:
        """Get language code for translation services."""
        language_codes = {
            "Hindi": "hi",
            "Kannada": "kn",
            "Malayalam": "ml",
            "Tamil": "ta",
            "Telugu": "te",
            "English": "en"
        }
        return language_codes.get(language_name, "en")