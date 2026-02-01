import logging
import warnings
import os
from pathlib import Path

import streamlit as st
from streamlit import session_state

# Suppress pygame and pkg_resources warnings
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
warnings.filterwarnings("ignore", message=".*pkg_resources.*")
warnings.filterwarnings("ignore", message=".*pygame.*")

from cache_manager import WebUICacheManager
from config import WebUIConfig
from rag_client import RAGClient
from translation import TranslationService
from tts import TextToSpeechService
from ui import create_ui

warnings.filterwarnings("ignore", message=".*torch.classes.*")

class SingletonLogger:
   _instance = None
   
   @classmethod
   def get_logger(cls):
       if cls._instance is None:
           cls._instance = cls._setup_logger()
       return cls._instance

   @staticmethod 
   def _setup_logger():
       logging.getLogger().setLevel(logging.INFO)
       logger = logging.getLogger('web-ui')
       if logger.handlers:
           logger.handlers.clear()
           
       logger.setLevel(logging.INFO)
       
       # TODO: Use Path relative to module location instead of hardcoded relative path
       # Suggestion: Path(__file__).parent.parent / "logs"
       # Create logs directory if it doesn't exist
       log_dir = Path("../logs")
       log_dir.mkdir(parents=True, exist_ok=True)
       
       file_handler = logging.FileHandler(log_dir / "web_ui.log")
       formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
       file_handler.setFormatter(formatter)
       logger.addHandler(file_handler)
       
       # Console handler for debug
       console_handler = logging.StreamHandler()
       console_handler.setFormatter(formatter)
       logger.addHandler(console_handler)
           
       return logger

def create_client_assistant(config: WebUIConfig):
    """
    Create a simplified assistant that combines API client with local services
    and caching support.
    """
    logger = SingletonLogger.get_logger()
    
    # Create API client for RAG queries
    rag_client = RAGClient(config)
    
    # Check if RAG service is available
    # TODO: Add graceful degradation instead of st.stop() (allow viewing cached responses)
    # TODO: Use context manager for cleanup before st.stop()
    if not rag_client.health_check():
        st.error("⚠️ RAG Service is not available. Please ensure the service is running on port 8000.")
        st.stop()
    
    logger.info("RAG service connection verified")
    
    # Ensure cache directories exist
    config.ensure_cache_dirs()
    
    # Initialize cache manager
    cache_manager = WebUICacheManager(config, logger)
    logger.info("Cache manager initialized")
    
    # Initialize services with cache manager
    translation_service = TranslationService(
        provider=config.translation_provider, 
        config=config, 
        logger_instance=logger,
        cache_manager=cache_manager
    )
    
    tts_service = TextToSpeechService(
        config=config, 
        logger_instance=logger,
        cache_manager=cache_manager
    )
    
    logger.info("Translation and TTS services initialized with caching")
    
    # Create a combined assistant object that the UI expects
    class ClientAssistant:
        def __init__(self, rag_client, translation_service, tts_service, cache_manager, config):
            self.rag_client = rag_client
            self.translation_service = translation_service
            self.tts_service = tts_service
            self.cache_manager = cache_manager
            self.config = config
            
        def query(self, question: str, response_format: str = "web"):
            """Delegate to RAG client"""
            return self.rag_client.query(question, response_format)
            
        def translate_text(self, text: str, target_language: str) -> str:
            """Use local translation service with caching"""
            return self.translation_service.translate(text, target_language)
        
        # TODO: Add type hints to all methods for better IDE support and code clarity
        def get_audio(self, text: str, language: str):
            """Use local TTS service with caching and text sanitization"""
            audio_path, _ = self.tts_service.synthesize(text, language)
            return audio_path
        
        def get_cache_stats(self) -> dict:
            """Get comprehensive cache statistics"""
            return self.cache_manager.get_cache_stats()
        
        def get_translation_stats(self) -> dict:
            """Get translation service statistics"""
            return self.translation_service.get_translation_stats()
        
        def get_tts_stats(self) -> dict:
            """Get TTS service statistics"""
            return self.tts_service.get_cache_stats()
        
        def clear_cache(self, cache_type: str = "all"):
            """Clear cache with optional type specification"""
            self.cache_manager.clear_cache(cache_type)
        
        def optimize_cache(self):
            """Trigger cache optimization"""
            self.cache_manager.cleanup_expired()
            self.cache_manager.check_size_limit()
        
        def test_services(self) -> dict:
            """Test all services for debugging"""
            test_results = {
                'rag_service': self.rag_client.health_check(),
                'translation_service': {},
                'tts_service': {},
                'cache_service': True
            }
            
            # Test translation service
            try:
                translation_test = self.translation_service.test_translation("Hello, this is a test.")
                test_results['translation_service'] = {
                    'available': True,
                    'test_results': translation_test
                }
            except Exception as e:
                test_results['translation_service'] = {
                    'available': False,
                    'error': str(e)
                }
            
            # Test TTS service
            try:
                test_audio, test_duration = self.tts_service.synthesize("Test", "English")
                test_results['tts_service'] = {
                    'available': test_audio is not None,
                    'duration': test_duration,
                    'pygame_available': self.tts_service.pygame_available
                }
                # Clean up test file
                if test_audio and test_audio.exists():
                    test_audio.unlink(missing_ok=True)
            except Exception as e:
                test_results['tts_service'] = {
                    'available': False,
                    'error': str(e)
                }
            
            return test_results
    
    assistant = ClientAssistant(rag_client, translation_service, tts_service, cache_manager, config)
    
    # Perform initial cache maintenance
    try:
        assistant.optimize_cache()
        cache_stats = assistant.get_cache_stats()
        logger.info(f"Cache initialized - Translation files: {cache_stats.get('translation_files', 0)}, "
                   f"Audio files: {cache_stats.get('audio_files', 0)}")
    except Exception as e:
        logger.warning(f"Initial cache optimization failed: {str(e)}")
    
    logger.info("Client assistant initialized successfully with caching support")
    return assistant

def main():
    if 'initialized' not in st.session_state:
        logger = SingletonLogger.get_logger()
        logger.info("Initializing web UI client with caching support")
        
        try:
            config = WebUIConfig()
            assistant = create_client_assistant(config)
            st.session_state.assistant = assistant
            st.session_state.config = config
            st.session_state.initialized = True
            logger.info("Web UI client initialization completed with caching")
        except Exception as e:
            logger.error(f"Failed to initialize client: {str(e)}")
            st.error(f"Failed to initialize application: {str(e)}")
            st.stop()
        
    create_ui(st.session_state.assistant, st.session_state.config)
   
if __name__ == "__main__":
   main()