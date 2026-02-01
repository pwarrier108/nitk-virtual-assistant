#!/usr/bin/env python3
# encoding: utf-8
# @Author: Padmanand
# @Date: 2025/03/05
# Updated: 2025/07/15 - Added simple text sanitization for TTS
# Updated: Replaced OpenAI Whisper with Google STT
# Updated: 2025/07/17 - Changed to Google Cloud TTS with male voice

import pygame
import re
import speech_recognition as sr
from speech import awake
from speech import speech
from google.cloud import texttospeech
import tempfile
import os
import time
import logging

def clean_for_speech(text: str) -> str:
    """Simple text cleanup for TTS - removes markdown artifacts"""
    if not text:
        return text
    
    # Remove markdown formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # **bold** → bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # *italic* → italic  
    text = re.sub(r'`(.*?)`', r'\1', text)        # `code` → code
    text = re.sub(r'\*+', '', text)               # Remove stray asterisks
    text = re.sub(r'#+', '', text)                # Remove stray hashes
    
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

class GoogleTTSWrapper:
    """Google Cloud TTS wrapper with male Indian voice"""
    
    def __init__(self):
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        self.client = texttospeech.TextToSpeechClient()
        self.logger = logging.getLogger('google_tts')
        
    def tts(self, text, lang='en'):
        """Convert text to speech using Google Cloud TTS"""
        if not text or not text.strip():
            return
            
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text.strip())
            
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-IN",
                name="en-IN-Wavenet-B"  # Male Indian voice
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            
            response = self.client.synthesize_speech(
                input=synthesis_input, 
                voice=voice, 
                audio_config=audio_config
            )
            
            # Save and play audio with pygame
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                tmp_file.write(response.audio_content)
                tmp_path = tmp_file.name
            
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            # Clean up
            os.unlink(tmp_path)
            
        except Exception as e:
            self.logger.error(f"Google Cloud TTS failed: {e}")

class VoiceAssistant:
    """Handles all voice-related functionality: wake word detection, ASR, and TTS"""
    
    def __init__(self, port='/dev/ttyUSB0', volume=80):
        # Setup logging
        self.logger = logging.getLogger('voice_assistant')
        
        # Import audio paths from config
        from config import AUDIO_PATHS
        self.audio_paths = AUDIO_PATHS
        
        # Hardware setup
        self.port = port
        self.kws = awake.WonderEchoPro(port)
        
        # Speech services
        self.recognizer = sr.Recognizer()
        self.tts = GoogleTTSWrapper()
        
        # Set volume
        speech.set_volume(volume)
        
        # Audio state tracking
        self.last_audio_operation = 0
        self.min_audio_gap = 0.1
        self.audio_in_use = False
    
    def _safe_audio_operation(self, operation_func, *args, **kwargs):
        """Safely execute audio operations with timing control"""
        current_time = time.time()
        time_since_last = current_time - self.last_audio_operation
        
        if time_since_last < self.min_audio_gap:
            time.sleep(self.min_audio_gap - time_since_last)
        
        try:
            self.audio_in_use = True
            result = operation_func(*args, **kwargs)
            self.last_audio_operation = time.time()
            return result
        except Exception as e:
            from config import LOG_MESSAGES
            self.logger.error(f"{LOG_MESSAGES['audio_operation_failed']}: {e}")
            raise e
        finally:
            self.audio_in_use = False
    
    def start_wake_word_detection(self):
        """Start wake word detection"""
        self.kws.start()
    
    def check_wakeup(self):
        """Check if wake word was detected"""
        # Skip wake word check if audio is in use
        if self.audio_in_use:
            return False
            
        try:
            return self.kws.wakeup()
        except Exception as e:
            error_msg = str(e).lower()
            if "device disconnected" in error_msg or "multiple access" in error_msg or "no data" in error_msg:
                # Suppress repeated warnings - only show every 10th occurrence
                if not hasattr(self, '_warning_count'):
                    self._warning_count = 0
                self._warning_count += 1
                if self._warning_count % 10 == 1:
                    from config import LOG_MESSAGES
                    self.logger.warning(f"{LOG_MESSAGES['wake_word_issue']} (showing 1/{self._warning_count}): {e}")
                time.sleep(0.5)
                return False
            raise e
    
    def play_wakeup_audio(self):
        """Play wake up confirmation audio"""
        def _play():
            return speech.play_audio(self.audio_paths['wakeup'])
        return self._safe_audio_operation(_play)
    
    def play_start_audio(self):
        """Play startup audio"""
        def _play():
            return speech.play_audio(self.audio_paths['start'])
        return self._safe_audio_operation(_play)
    
    def play_no_voice_audio(self):
        """Play no voice detected audio"""
        def _play():
            return speech.play_audio(self.audio_paths['no_voice'])
        return self._safe_audio_operation(_play)
    
    def play_greeting_audio(self):
        """Play greeting audio"""
        def _play():
            return speech.play_audio(self.audio_paths['greeting'])
        return self._safe_audio_operation(_play)
    
    def play_error_audio(self, error_type='general_error'):
        """Play error audio based on error type"""
        from config import ERROR_TO_AUDIO
        audio_key = ERROR_TO_AUDIO.get(error_type, 'error')
        def _play():
            return speech.play_audio(self.audio_paths[audio_key])
        return self._safe_audio_operation(_play)
    
    def listen(self):
        """Start voice recognition using Google STT and return transcribed text"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                with sr.Microphone() as source:
                    from config import LOG_MESSAGES
                    self.logger.info(LOG_MESSAGES['listening'])
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    # Fixed: Longer timeouts to prevent cutoff
                    self.recognizer.pause_threshold = 1.0
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=15)
                
                # Use Google STT
                result = self.recognizer.recognize_google(audio)
                
                if result and result.strip():
                    self.logger.info(f"Google STT: {result}")
                    return result.strip()
                
                if attempt < max_retries - 1:
                    self.logger.info(f"Empty result - retry {attempt + 1}/{max_retries}")
                    time.sleep(0.3)
                    continue
                    
                return result
                
            except sr.RequestError as e:
                self.logger.error(f"Google STT API error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                return None
                
            except sr.UnknownValueError:
                self.logger.info("No speech detected")
                if attempt < max_retries - 1:
                    time.sleep(0.3)
                    continue
                return None
                
            except Exception as e:
                error_msg = str(e).lower()
                
                if any(issue in error_msg for issue in ["overrun", "underrun", "no such device", "device busy"]):
                    self.logger.warning(f"Audio {error_msg.split()[0]} - retry {attempt + 1}/{max_retries}")
                    
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    else:
                        self.logger.error(f"Audio issues persist after {max_retries} attempts: {e}")
                        return None
                        
                else:
                    self.logger.error(f"Speech recognition failed: {e}")
                    return None
        
        return None
    
    def speak(self, text):
        """Convert text to speech using Google Cloud TTS"""
        try:
            # Clean text once, right before TTS
            clean_text = clean_for_speech(text)
            
            if not clean_text:
                self.logger.warning("Text is empty after cleaning")
                return
            
            def _speak():
                return self.tts.tts(clean_text)
            
            return self._safe_audio_operation(_speak)
            
        except Exception as e:
            error_msg = str(e).lower()
            if any(issue in error_msg for issue in ["overrun", "underrun", "device busy"]):
                self.logger.warning(f"TTS audio issue: {e}")
                try:
                    time.sleep(0.5)
                    return self._safe_audio_operation(lambda: self.tts.tts(clean_text))
                except:
                    from config import LOG_MESSAGES
                    self.logger.error(f"{LOG_MESSAGES['tts_failed']} completely: {e}")
            else:
                from config import LOG_MESSAGES
                self.logger.error(f"{LOG_MESSAGES['tts_failed']}: {e}")
    
    def exit(self):
        """Clean up voice assistant resources"""
        try:
            self.kws.exit()
        except Exception as e:
            self.logger.warning(f"Wake word cleanup failed: {e}")
    
    def set_volume(self, volume):
        """Set audio volume"""
        try:
            speech.set_volume(volume)
        except Exception as e:
            self.logger.warning(f"Volume setting failed: {e}")