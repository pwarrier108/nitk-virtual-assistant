#!/usr/bin/env python3
# encoding: utf-8
# Translation service for robot - adapted from web-ui

from deep_translator import GoogleTranslator
import logging
import time

class TranslationService:
    """Translation service for robot voice assistant"""
    
    def __init__(self, provider: str, config=None, logger=None):
        self.provider = provider
        self.config = config
        self.logger = logger if logger else logging.getLogger('translation')
        
        # Import centralized language mappings
        from config import LANGUAGE_CODES
        self.language_codes = LANGUAGE_CODES

    def translate(self, text: str, target_language: str) -> str:
        """
        Translate text to target language
        
        Args:
            text: Text to translate
            target_language: Target language name (e.g., "Hindi", "Tamil")
        
        Returns:
            Translated text
        """
        try:
            lang_code = self.language_codes.get(target_language)
            if not lang_code:
                raise ValueError(f"Unsupported language: {target_language}")
                
            # Don't translate if already in English
            if lang_code == "en":
                return text
                
            self.logger.info(f"Translating {len(text)} chars to {target_language}")
            translate_start = time.time()
            
            translator = GoogleTranslator(source='en', target=lang_code)
            translated = translator.translate(text)
            
            translate_time = time.time() - translate_start
            self.logger.info(f"Translation complete in {translate_time:.2f}s - input: {len(text)} chars, output: {len(translated)} chars")
            return translated
            
        except Exception as e:
            self.logger.error(f"Translation failed: {str(e)}", exc_info=True)
            return f"Translation error: {str(e)}"

    def get_supported_languages(self) -> dict:
        """Get dictionary of supported languages"""
        return self.language_codes.copy()
    
    def is_supported_language(self, language: str) -> bool:
        """Check if language is supported"""
        return language in self.language_codes
    
    def get_language_code(self, language_name: str) -> str:
        """Get language code for a language name"""
        return self.language_codes.get(language_name, "en")