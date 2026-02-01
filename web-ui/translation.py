from deep_translator import GoogleTranslator
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

class TranslationService:
    def __init__(self, provider: str, config, logger_instance, cache_manager=None):
        self.provider = provider
        self.config = config
        self.logger = logger_instance
        self.cache_manager = cache_manager
        
        # Language code mapping
        self.language_codes = {
            "Hindi": "hi",
            "Kannada": "kn", 
            "Malayalam": "ml",
            "Tamil": "ta", 
            "Telugu": "te",
            "English": "en"
        }
        
        # Translation statistics
        self.translation_stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'api_calls': 0,
            'total_chars_translated': 0,
            'avg_translation_time': 0
        }

    def translate(self, text: str, target_language: str, cache_safe: bool = True) -> str:
        """
        Translate text with conditional caching support.
        
        Args:
            text: Text to translate
            target_language: Target language name (e.g., "Hindi")
            cache_safe: Whether to use caching (False for temporal content)
            
        Returns:
            Translated text
        """
        try:
            # Validate inputs
            if not text or not text.strip():
                return ""
            
            if target_language == "English":
                return text  # No translation needed
            
            # Console logging for cache behavior
            if cache_safe:
                print(f"Translation - CACHED: {target_language} | {len(text)} chars")
            else:
                print(f"Translation - TEMPORAL (no cache): {target_language} | {len(text)} chars")
            
            # Check cache first if cache manager is available AND cache_safe is True
            if self.cache_manager and cache_safe:
                cached_translation = self.cache_manager.get_translation_cache(text, target_language)
                if cached_translation:
                    self.translation_stats['cache_hits'] += 1
                    self.logger.info(f"Using cached translation for {target_language}: {len(text)} chars")
                    return cached_translation
                else:
                    self.translation_stats['cache_misses'] += 1
            elif not cache_safe:
                # Skip cache lookup for temporal content
                self.translation_stats['cache_misses'] += 1
            
            # Get language code
            lang_code = self.language_codes.get(target_language)
            if not lang_code:
                raise ValueError(f"Unsupported language: {target_language}")
            
            # Perform translation
            cache_status = "cached" if cache_safe else "temporal"
            self.logger.info(f"Translating {len(text)} chars to {target_language} ({cache_status})")
            translate_start = time.time()
            
            translator = GoogleTranslator(source='en', target=lang_code)
            translated = translator.translate(text)
            
            translate_time = time.time() - translate_start
            
            # Update statistics
            self.translation_stats['api_calls'] += 1
            self.translation_stats['total_chars_translated'] += len(text)
            self._update_avg_translation_time(translate_time)
            
            # Cache the result ONLY if cache_safe is True and cache manager is available
            if self.cache_manager and cache_safe and translated:
                self.cache_manager.cache_translation(text, target_language, translated)
                self.logger.info(f"Cached translation for {target_language}: {len(text)} chars")
            elif not cache_safe:
                self.logger.info(f"Skipped caching translation for {target_language} (temporal content): {len(text)} chars")
            
            self.logger.info(f"Translation complete in {translate_time:.2f}s - input: {len(text)} chars, output: {len(translated)} chars")
            return translated
            
        except Exception as e:
            self.logger.error(f"Translation failed for {target_language}: {str(e)}", exc_info=True)
            return f"Translation error: {str(e)}"

    def _update_avg_translation_time(self, new_time: float):
        """Update running average of translation times."""
        current_avg = self.translation_stats['avg_translation_time']
        api_calls = self.translation_stats['api_calls']
        
        if api_calls == 1:
            self.translation_stats['avg_translation_time'] = new_time
        else:
            # Running average calculation
            self.translation_stats['avg_translation_time'] = ((current_avg * (api_calls - 1)) + new_time) / api_calls

    def batch_translate(self, texts: list, target_language: str, cache_safe: bool = True) -> list:
        """
        Translate multiple texts efficiently with conditional caching.
        
        Args:
            texts: List of texts to translate
            target_language: Target language name
            cache_safe: Whether to use caching (False for temporal content)
            
        Returns:
            List of translated texts
        """
        try:
            if target_language == "English":
                return texts
            
            translations = []
            uncached_texts = []
            uncached_indices = []
            
            # Check cache for each text ONLY if cache_safe is True
            for i, text in enumerate(texts):
                if self.cache_manager and cache_safe:
                    cached = self.cache_manager.get_translation_cache(text, target_language)
                    if cached:
                        translations.append(cached)
                        self.translation_stats['cache_hits'] += 1
                        continue
                    else:
                        self.translation_stats['cache_misses'] += 1
                else:
                    # Skip cache for temporal content
                    self.translation_stats['cache_misses'] += 1
                
                # Text not cached, add to batch for translation
                translations.append(None)  # Placeholder
                uncached_texts.append(text)
                uncached_indices.append(i)
            
            # Translate uncached texts
            if uncached_texts:
                cache_status = "cached" if cache_safe else "temporal"
                self.logger.info(f"Batch translating {len(uncached_texts)} texts to {target_language} ({cache_status})")
                
                for j, text in enumerate(uncached_texts):
                    translated = self.translate(text, target_language, cache_safe)
                    original_index = uncached_indices[j]
                    translations[original_index] = translated
            
            return translations
            
        except Exception as e:
            self.logger.error(f"Batch translation failed: {str(e)}")
            return [f"Translation error: {str(e)}" for _ in texts]

    def get_supported_languages(self) -> dict:
        """Get supported languages and their codes."""
        return self.language_codes.copy()

    def validate_language(self, language: str) -> bool:
        """Check if language is supported."""
        return language in self.language_codes

    def get_translation_stats(self) -> dict:
        """Get comprehensive translation statistics."""
        stats = self.translation_stats.copy()
        
        # Calculate additional metrics
        total_requests = stats['cache_hits'] + stats['cache_misses']
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['cache_hits'] / total_requests
        else:
            stats['cache_hit_rate'] = 0
        
        # Add cache manager stats if available
        if self.cache_manager:
            cache_stats = self.cache_manager.get_cache_stats()
            stats['cache_enabled'] = True
            stats['translation_files'] = cache_stats.get('translation_files', 0)
            stats['total_cache_size_mb'] = cache_stats.get('total_cache_size_mb', 0)
        else:
            stats['cache_enabled'] = False
            stats['translation_files'] = 0
            stats['total_cache_size_mb'] = 0
        
        return stats

    def clear_translation_cache(self):
        """Clear only translation cache."""
        if self.cache_manager:
            self.cache_manager.clear_cache("translations")
            self.logger.info("Translation cache cleared")
        else:
            self.logger.warning("No cache manager available")

    def optimize_cache(self):
        """Trigger cache optimization (cleanup expired, size management)."""
        if self.cache_manager:
            self.cache_manager.cleanup_expired()
            self.cache_manager.check_size_limit()
            self.logger.info("Translation cache optimized")

    def test_translation(self, test_phrase: str = "Hello, how are you?") -> dict:
        """
        Test translation service with a simple phrase.
        
        Args:
            test_phrase: Phrase to test translation with
            
        Returns:
            Dictionary with test results for all supported languages
        """
        test_results = {}
        
        for language in self.language_codes.keys():
            if language == "English":
                continue
                
            try:
                start_time = time.time()
                translated = self.translate(test_phrase, language, cache_safe=True)  # Use caching for tests
                duration = time.time() - start_time
                
                test_results[language] = {
                    'success': True,
                    'translated_text': translated,
                    'duration': duration,
                    'was_cached': duration < 0.1  # Assume cached if very fast
                }
                
            except Exception as e:
                test_results[language] = {
                    'success': False,
                    'error': str(e),
                    'duration': 0,
                    'was_cached': False
                }
        
        return test_results

    def __del__(self):
        """Cleanup on destruction."""
        try:
            if self.cache_manager:
                self.optimize_cache()
        except:
            pass