from gtts import gTTS
import logging
import pygame
import os
from pathlib import Path
from typing import Optional, Tuple
from text_sanitizer import sanitize_for_tts

logger = logging.getLogger(__name__)

class TextToSpeechService:
    def __init__(self, config, logger_instance, cache_manager=None):
        self.config = config
        self.logger = logger_instance
        self.cache_manager = cache_manager
        
        # Initialize pygame mixer
        try:
            pygame.mixer.init()
            self.pygame_available = True
        except Exception as e:
            self.logger.warning(f"Failed to initialize pygame mixer: {str(e)}")
            self.pygame_available = False

    def synthesize(self, text: str, language: str, cache_safe: bool = True) -> Tuple[Optional[Path], Optional[float]]:
        """
        Generate TTS audio with conditional caching support and text sanitization.
        
        Args:
            text: Text to convert to speech (may contain markdown)
            language: Language name (e.g., "Hindi")
            cache_safe: Whether to use caching (False for temporal content)
            
        Returns:
            Tuple of (audio_file_path, duration_seconds)
        """
        try:
            # Sanitize text for TTS (remove markdown formatting)
            clean_text = sanitize_for_tts(text)
            
            if not clean_text or not clean_text.strip():
                self.logger.warning("Text is empty after sanitization")
                return None, None
            
            self.logger.debug(f"Text sanitized: {len(text)} -> {len(clean_text)} chars")
            
            # Console logging for cache behavior
            if cache_safe:
                print(f"TTS - CACHED: {language} | {len(clean_text)} chars")
            else:
                print(f"TTS - TEMPORAL (no cache): {language} | {len(clean_text)} chars")
            
            # Check cache first using clean text ONLY if cache_safe is True
            if self.cache_manager and cache_safe:
                cached_result = self.cache_manager.get_audio_cache(clean_text, language)
                if cached_result:
                    audio_path, duration = cached_result
                    self.logger.info(f"Using cached audio for {language}: {len(clean_text)} chars")
                    return audio_path, duration
            
            # Get language code for gTTS
            lang_code = self.config.get_language_code(language)
            if not lang_code:
                raise ValueError(f"Unsupported language: {language}")
            
            cache_status = "cached" if cache_safe else "temporal"
            self.logger.info(f"Generating {len(clean_text)} char audio for {language} ({cache_status})")
            
            # Create TTS object with clean text
            tts = gTTS(text=clean_text, lang=lang_code)
            
            # Create audio directory if needed
            audio_dir = self.config.cache_dir / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate audio path
            if self.cache_manager and cache_safe:
                # Use cache manager's audio directory for cacheable content
                audio_path = self.cache_manager.audio_dir / f"temp_{os.urandom(8).hex()}.mp3"
            else:
                # Use temp directory for non-cacheable content
                audio_path = audio_dir / f"temp_{os.urandom(8).hex()}.mp3"
            
            # Generate audio file
            tts.save(str(audio_path))
            
            # Calculate duration 
            duration = self._calculate_audio_duration(audio_path)
            
            # Cache the result using clean text ONLY if cache_safe is True
            if self.cache_manager and cache_safe:
                self.cache_manager.cache_audio(clean_text, language, audio_path, duration)
                self.logger.info(f"Cached audio for {language}: {len(clean_text)} chars, {duration:.1f}s")
            elif not cache_safe:
                self.logger.info(f"Skipped caching audio for {language} (temporal content): {len(clean_text)} chars, {duration:.1f}s")
            
            self.logger.info(f"Generated audio: {len(clean_text)} chars -> {duration:.1f}s")
            return audio_path, duration
            
        except Exception as e:
            self.logger.error(f"TTS failed for {language}: {str(e)}", exc_info=True)
            return None, None

    def _calculate_audio_duration(self, audio_path: Path) -> Optional[float]:
        """Calculate audio file duration using pygame."""
        try:
            if not self.pygame_available:
                return None
                
            sound = pygame.mixer.Sound(str(audio_path))
            duration = sound.get_length()
            return duration
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate audio duration: {str(e)}")
            return None

    def play_audio(self, audio_path: Path) -> bool:
        """
        Play audio file using pygame.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            True if playback started successfully
        """
        try:
            if not self.pygame_available:
                self.logger.warning("Pygame not available for audio playback")
                return False
                
            # Load and play the audio file
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play()
            self.logger.info(f"Started audio playback: {audio_path.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Audio playback failed: {str(e)}")
            return False

    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        try:
            if not self.pygame_available:
                return False
            return pygame.mixer.music.get_busy()
        except:
            return False

    def stop_audio(self) -> bool:
        """Stop current audio playback."""
        try:
            if not self.pygame_available:
                return False
            pygame.mixer.music.stop()
            self.logger.info("Stopped audio playback")
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop audio: {str(e)}")
            return False

    def cleanup_temp_files(self):
        """Clean up temporary audio files (non-cached files)."""
        try:
            audio_dir = self.config.cache_dir / "audio"
            if not audio_dir.exists():
                return
                
            # Only clean up temp files, not cached files
            temp_files = list(audio_dir.glob("temp_*.mp3"))
            cleaned_count = 0
            
            for temp_file in temp_files:
                try:
                    temp_file.unlink(missing_ok=True)
                    cleaned_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to clean temp file {temp_file}: {str(e)}")
            
            if cleaned_count > 0:
                self.logger.info(f"Cleaned up {cleaned_count} temporary audio files")
                
        except Exception as e:
            self.logger.error(f"Temp file cleanup failed: {str(e)}")

    def get_supported_languages(self) -> dict:
        """Get supported languages and their codes."""
        return {
            "Hindi": "hi",
            "Kannada": "kn",
            "Malayalam": "ml",
            "Tamil": "ta",
            "Telugu": "te",
            "English": "en"
        }

    def validate_language(self, language: str) -> bool:
        """Check if language is supported."""
        return language in self.get_supported_languages()

    def get_cache_stats(self) -> dict:
        """Get TTS cache statistics if cache manager is available."""
        if self.cache_manager:
            cache_stats = self.cache_manager.get_cache_stats()
            return {
                'audio_hit_rate': cache_stats.get('audio_hit_rate', 0),
                'audio_files': cache_stats.get('audio_files', 0),
                'cache_enabled': True
            }
        else:
            return {
                'audio_hit_rate': 0,
                'audio_files': 0,
                'cache_enabled': False
            }

    def __del__(self):
        """Cleanup on destruction."""
        try:
            self.cleanup_temp_files()
        except:
            pass