#!/usr/bin/env python3
# encoding: utf-8
# Robot RAG Client with Context Window, Translation Support, and Emotion Detection

import requests
import logging
import time
import re
from typing import Optional, Tuple, Dict

class RAGResponse:
    """Data class to hold RAG service response with emotion"""
    def __init__(self, text: str, emotion: str = "neutral", metadata: dict = None):
        self.text = text
        self.emotion = emotion
        self.metadata = metadata or {}

class RAGClient:
    """
    RAG API client for robot interface with context window, translation support, and emotion detection
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
        
        # Context window for follow-up questions
        self.last_question = None
        self.last_response = None
        self.last_emotion = None
        self.last_translation = None
        self.last_language = None
        
        # Follow-up detection patterns
        self.followup_patterns = [
            r'\b(yes|yeah|yep|sure|okay|ok|definitely|please)\b',
            r'\b(more|tell me more|continue|go on|elaborate)\b',
            r'\b(what about|tell me about|about that|details?)\b',
            r'\b(explain|describe|how|why|when|where)\b'
        ]
        
        # Translation command patterns
        self.translation_patterns = {
            'hindi': r'\b(translate|convert|say).*\b(hindi|हिंदी)\b',
            'kannada': r'\b(translate|convert|say).*\b(kannada|ಕನ್ನಡ)\b',
            'malayalam': r'\b(translate|convert|say).*\b(malayalam|മലയാളം)\b',
            'tamil': r'\b(translate|convert|say).*\b(tamil|தமிழ்)\b',
            'telugu': r'\b(translate|convert|say).*\b(telugu|తెలుగు)\b',
            'english': r'\b(translate|convert|say).*\b(english|back to english)\b'
        }
        
        # Import centralized language mappings from config
        from config import LANGUAGE_KEY_TO_NAME
        self.supported_languages = LANGUAGE_KEY_TO_NAME
        
        # Setup logging
        self.logger = logging.getLogger('robot_rag_client')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def health_check(self) -> bool:
        """Check if the RAG service is available"""
        try:
            response = self.session.get(
                f"{self.base_url}/health", 
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def detect_command_type(self, question: str) -> Tuple[str, Optional[str]]:
        """
        Detect what type of command this is
        Returns: (command_type, language) where command_type is 'query', 'followup', or 'translate'
        """
        question_lower = question.lower().strip()
        
        # Check for translation commands first
        for lang_key, pattern in self.translation_patterns.items():
            if re.search(pattern, question_lower, re.IGNORECASE):
                return 'translate', lang_key
        
        # Check for follow-up patterns
        if self.last_response:  # Only if we have context
            for pattern in self.followup_patterns:
                if re.search(pattern, question_lower, re.IGNORECASE) and len(question.split()) <= 5:
                    return 'followup', None
        
        # Default to new query
        return 'query', None
    
    def query(self, question: str) -> RAGResponse:
        """
        Main query method that handles all types of interactions
        Returns: RAGResponse object with text, emotion, and metadata
        """
        command_type, language = self.detect_command_type(question)
        
        if command_type == 'translate':
            # Translation requests return the translation with preserved emotion
            text = self._handle_translation_request(language)
            return RAGResponse(text, self.last_emotion or "neutral")
        elif command_type == 'followup':
            return self._handle_followup_request(question)
        else:
            return self._handle_new_query(question)
    
    def _handle_translation_request(self, target_language: str) -> str:
        """Handle translation requests"""
        from config import ERROR_MESSAGES
        
        if not self.last_response:
            return ERROR_MESSAGES['no_context']
        
        if target_language not in self.supported_languages:
            return ERROR_MESSAGES['unsupported_language']
        
        # Import translation service
        try:
            from translation import TranslationService
            
            # Initialize translation service
            translator = TranslationService("google", config=None, logger=self.logger)
            
            # Translate the last response
            target_lang_name = self.supported_languages[target_language]
            
            if target_language == 'english':
                # If requesting English, return original response
                self.last_translation = self.last_response
                self.last_language = 'English'
                return self.last_response
            else:
                # Translate to target language
                translated_text = translator.translate(self.last_response, target_lang_name)
                self.last_translation = translated_text
                self.last_language = target_lang_name
                
                self.logger.info(f"Translated response to {target_lang_name}")
                return translated_text
                
        except ImportError:
            return "Translation service is not available right now."
        except Exception as e:
            self.logger.error(f"Translation failed: {str(e)}")
            return ERROR_MESSAGES['translation_failed']
    
    def _handle_followup_request(self, question: str) -> RAGResponse:
        """Handle follow-up questions using context"""
        if not self.last_question or not self.last_response:
            return self._handle_new_query(question)
        
        # Enhance the question with context
        enhanced_question = f"Previous question: '{self.last_question}'. Previous answer: '{self.last_response[:200]}...'. User follow-up: '{question}'. Please provide more details or continue the explanation."
        
        self.logger.info(f"Follow-up detected. Enhanced query: {enhanced_question[:100]}...")
        
        return self._call_rag_service(enhanced_question)
    
    def _handle_new_query(self, question: str) -> RAGResponse:
        """Handle new query and update context"""
        response = self._call_rag_service(question)
        
        # Update context window
        self.last_question = question
        self.last_response = response.text
        self.last_emotion = response.emotion
        # Clear translation context on new query
        self.last_translation = None
        self.last_language = None
        
        return response
    
    def _call_rag_service(self, question: str) -> RAGResponse:
        """Make the actual API call to RAG service with emotion detection"""
        from config import ERROR_MESSAGES
        
        try:
            self.logger.info(f"Querying RAG service: {question[:50]}...")
            
            # Make API call with voice format for robot
            response = self.session.post(
                f"{self.base_url}/query",
                json={
                    "question": question,
                    "format": "voice"  # Robot requests voice-optimized responses
                },
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                error_msg = f"RAG service error {response.status_code}: {response.text}"
                self.logger.error(error_msg)
                return RAGResponse(
                    ERROR_MESSAGES['rag_unavailable'],
                    "confused"
                )
            
            # Parse structured JSON response
            result = response.json()
            response_text = result.get('response', 'No response received')
            detected_emotion = result.get('emotion', 'neutral')
            metadata = result.get('metadata', {})
            
            self.logger.info(f"RAG response: {len(response_text)} chars, emotion: {detected_emotion}")
            
            return RAGResponse(response_text, detected_emotion, metadata)
            
        except requests.exceptions.Timeout:
            error_msg = "RAG service request timed out"
            self.logger.error(error_msg)
            return RAGResponse(
                ERROR_MESSAGES['timeout_error'],
                "confused"
            )
            
        except requests.exceptions.ConnectionError:
            error_msg = "Unable to connect to RAG service"
            self.logger.error(error_msg)
            return RAGResponse(
                ERROR_MESSAGES['rag_unavailable'],
                "sad"
            )
            
        except Exception as e:
            error_msg = f"Unexpected error querying RAG service: {str(e)}"
            self.logger.error(error_msg)
            return RAGResponse(
                ERROR_MESSAGES['general_error'],
                "confused"
            )
    
    def get_context_summary(self) -> dict:
        """Get current context for debugging"""
        return {
            'last_question': self.last_question,
            'last_response': self.last_response[:100] + '...' if self.last_response else None,
            'last_emotion': self.last_emotion,
            'last_translation': self.last_translation[:100] + '...' if self.last_translation else None,
            'last_language': self.last_language,
            'has_context': bool(self.last_question and self.last_response)
        }
    
    def clear_context(self):
        """Clear conversation context"""
        self.last_question = None
        self.last_response = None
        self.last_emotion = None
        self.last_translation = None
        self.last_language = None
        self.logger.info("Conversation context cleared")
    
    def get_service_info(self) -> Optional[dict]:
        """Get information about the RAG service"""
        try:
            response = self.session.get(f"{self.base_url}/")
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None