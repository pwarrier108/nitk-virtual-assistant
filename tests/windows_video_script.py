#!/usr/bin/env python3
# encoding: utf-8
# Windows Video Script - Simplified for Windows with timing
# Uses real wake word but ignores STT, follows scripted Q&A sequence

import json
import time
import threading
import speech_recognition as sr
from datetime import datetime
import sys
import signal
import tempfile
import os
import pygame
from pathlib import Path
from google.cloud import texttospeech
from google.oauth2 import service_account

class WindowsVideoScript:
    """Windows-compatible video script with timing"""
    
    def __init__(self, script_file="video_script.json"):
        self.script_file = script_file
        self.qa_pairs = []
        self.current_qa_index = 0
        self.start_time = None
        self.end_time = None
        
        # Initialize Google TTS
        self.setup_google_tts()
        
        # Initialize pygame for audio playback
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Robot action mappings (from robot_controller.py + new ecstatic->chest)
        self.emotion_actions = {
            'bow': 'bow',
            'confused': 'twist',
            'ecstatic': 'chest',  # NEW: ecstatic emotion maps to chest action
            'excited': 'left_hand',
            'explaining': 'stand',
            'goodbye': 'bow',
            'greeting': 'wave',
            'happy': 'wave',
            'left_hand': 'left_hand',
            'neutral': 'stand',
            'right_hand': 'right_hand',
            'sad': 'bow',
            'surprised': 'right_hand',
            'thinking': 'twist',
            'wave': 'wave'
        }
        
        self.setup_signal_handler()
    
    def setup_google_tts(self):
        """Setup Google Cloud TTS client"""
        try:
            # Use hardcoded path directly
            credentials_path = Path("C:/Users/padma/Documents/Projects/nitkmodular/nitk-virtual-assistant-1f87354dcd8b.json")
            
            print(f"Looking for Google TTS credentials at: {credentials_path}")
            
            if not credentials_path.exists():
                print("❌ Google TTS credentials file not found!")
                print("Please check if the file exists and the path is correct.")
                exit(1)
            
            # Load credentials
            credentials = service_account.Credentials.from_service_account_file(str(credentials_path))
            self.tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
            print("✅ Google TTS initialized successfully")
            
        except Exception as e:
            print(f"❌ Error initializing Google TTS: {e}")
            exit(1)
    
    def setup_signal_handler(self):
        """Handle Ctrl+C gracefully"""
        def signal_handler(sig, frame):
            print('\n[INFO] Script interrupted')
            self.print_timing_summary()
            sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)
    
    def load_script(self):
        """Load Q&A script from JSON file"""
        try:
            with open(self.script_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.qa_pairs = data.get('qa_pairs', [])
            print(f"✅ Loaded {len(self.qa_pairs)} Q&A pairs from {self.script_file}")
            return True
        except Exception as e:
            print(f"❌ Error loading script: {e}")
            return False
    
    def log_robot_action(self, emotion, description=""):
        """Log robot action that would happen"""
        action = self.emotion_actions.get(emotion, 'stand')
        elapsed = time.time() - self.start_time if self.start_time else 0
        print(f"[ROBOT {elapsed:5.1f}s] {emotion.upper()} → {action.upper()} {description}")
    
    def speak(self, text, emotion="neutral"):
        """Speak text using Google Cloud TTS with robot action logging"""
        print(f"[TTS] {text[:80]}{'...' if len(text) > 80 else ''}")
        
        # Log robot emotion start
        if emotion in ['explaining', 'ecstatic']:
            # For longer emotions, log start of emotion expression
            self.log_robot_action(emotion, "(emotion with speech)")
        else:
            self.log_robot_action(emotion)
        
        # Use Google Cloud TTS
        try:
            print("[TTS] Generating speech with Google TTS...")
            
            # Build request
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-IN",
                name="en-IN-Wavenet-B"  # Male Indian voice
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            
            # Perform synthesis
            response = self.tts_client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            # Save and play audio with pygame
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                tmp_file.write(response.audio_content)
                tmp_path = tmp_file.name
            
            print("[TTS] Playing audio...")
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            
            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            # Stop mixer 
            pygame.mixer.music.stop()
            
            # Skip cleanup - temp files will be cleaned up when script ends
            print("[TTS] Speech completed successfully")
            
        except Exception as e:
            print(f"[TTS ERROR] Google TTS failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Log return to neutral for non-neutral emotions
        if emotion != 'neutral':
            self.log_robot_action('neutral', "(return to neutral)")
    
    def wait_for_wake_word(self):
        """Wait for any speech (don't actually match wake word)"""
        print(f"\n[WAKE] Waiting for speech (Question {self.current_qa_index + 1})")
        
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
        
        try:
            with self.microphone as source:
                print("[LISTENING] Say anything...")
                # Just wait for any speech to finish
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=8)
            
            print("[HEARD] Speech detected - proceeding!")
            return True
            
        except sr.WaitTimeoutError:
            print("[TIMEOUT] No speech detected, listening again...")
            return self.wait_for_wake_word()  # Try again
        except KeyboardInterrupt:
            return False
    
    def play_wakeup_response(self):
        """Play 'I'm here' response"""
        print("[WAKEUP] I'm here!")
        self.log_robot_action('neutral', "(wakeup confirmation)")
        
        # Use Google TTS for "I'm here"
        self.speak("I'm here", "neutral")
        time.sleep(0.5)
    
    def simulate_listening_for_question(self):
        """Simulate listening for question (ignore actual content)"""
        print("[LISTENING] Listening for question...")
        
        try:
            with self.microphone as source:
                # Brief listen period - ignore content
                audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=8)
                print("[HEARD] Question received (content ignored)")
        except sr.WaitTimeoutError:
            print("[TIMEOUT] No question heard, proceeding anyway")
        except Exception as e:
            print(f"[LISTENING] Error: {e}, proceeding anyway")
    
    def random_processing_delay(self):
        """Random delay to simulate server processing"""
        import random
        delay = random.uniform(1.0, 2.0)
        print(f"[PROCESSING] Simulating server delay: {delay:.1f}s")
        time.sleep(delay)
    
    def play_greeting(self):
        """Play greeting sequence"""
        print("\n" + "="*60)
        print("🤖 GREETING SEQUENCE")
        print("="*60)
        
        greeting_text = "Hey there! I'm here to help you learn about NITK. What would you like to know?"
        
        # Robot bow before speaking
        self.log_robot_action('bow', "(respectful greeting)")
        time.sleep(3.5)  # Time for bow completion
        
        # Speak greeting
        self.speak(greeting_text, 'greeting')
        time.sleep(1.0)
        
        print("✅ Greeting complete")
    
    def process_qa_interaction(self):
        """Process next Q&A interaction"""
        if self.current_qa_index >= len(self.qa_pairs):
            return False
        
        qa = self.qa_pairs[self.current_qa_index]
        
        print("\n" + "-"*60)
        print(f"📝 Q&A {self.current_qa_index + 1}/{len(self.qa_pairs)}")
        print(f"❓ Expected: {qa['question']}")
        print("-"*60)
        
        # 1. Wait for wake word
        if not self.wait_for_wake_word():
            return False
        
        # 2. Play "I'm here" response
        self.play_wakeup_response()
        
        # 3. Listen for question (ignore content)
        self.simulate_listening_for_question()
        
        # 4. Random processing delay
        self.random_processing_delay()
        
        # 5. Respond with scripted answer
        answer = qa['answer']
        emotion = qa['emotion']
        
        print(f"💬 Response ({emotion}): {answer[:100]}...")
        
        # Speak with emotion
        self.speak(answer, emotion)
        
        self.current_qa_index += 1
        time.sleep(0.5)  # Brief pause between interactions
        
        return True
    
    def play_goodbye(self):
        """Play goodbye sequence"""
        print("\n" + "="*60)
        print("👋 GOODBYE SEQUENCE")
        print("="*60)
        
        goodbye_text = "Goodbye! It was wonderful talking with you about NITK. Have a great day!"
        
        # Wait for final wake word
        print("🎬 Final interaction - waiting for goodbye trigger")
        if not self.wait_for_wake_word():
            return
        
        # Wave gesture
        self.log_robot_action('wave', "(goodbye wave)")
        time.sleep(2.0)
        
        # Speak goodbye
        self.speak(goodbye_text, 'goodbye')
        
        # Final bow
        self.log_robot_action('bow', "(final bow)")
        time.sleep(3.0)
        
        # Return to neutral
        self.log_robot_action('neutral', "(final neutral)")
        
        print("✅ Goodbye complete")
    
    def print_timing_summary(self):
        """Print timing summary"""
        if self.start_time and self.end_time:
            total_time = self.end_time - self.start_time
            minutes = int(total_time // 60)
            seconds = total_time % 60
            
            print("\n" + "="*60)
            print("⏱️  TIMING SUMMARY")
            print("="*60)
            print(f"🕐 Start Time: {datetime.fromtimestamp(self.start_time).strftime('%H:%M:%S')}")
            print(f"🕐 End Time:   {datetime.fromtimestamp(self.end_time).strftime('%H:%M:%S')}")
            print(f"⏱️  Total Duration: {minutes}m {seconds:.1f}s")
            print(f"📊 Q&A Pairs Completed: {self.current_qa_index}/{len(self.qa_pairs)}")
            print("="*60)
    
    def run_script(self):
        """Run the complete video script"""
        print("🎬 Windows Video Script Starting")
        print("="*60)
        print("🎙️  Windows TTS enabled")
        print("🎤 Windows microphone enabled")
        print("🤖 Robot actions logged to console")
        print("⏱️  Timing enabled")
        print("="*60)
        
        if not self.load_script():
            return
        
        try:
            # Start timing
            self.start_time = time.time()
            print(f"\n⏱️  Script started at {datetime.now().strftime('%H:%M:%S')}")
            
            # 1. Greeting
            self.play_greeting()
            
            # 2. Q&A interactions
            while self.process_qa_interaction():
                # Reset position every 3 interactions
                if self.current_qa_index % 3 == 0:
                    self.log_robot_action('neutral', "(periodic reset)")
            
            # 3. Goodbye
            self.play_goodbye()
            
            # End timing
            self.end_time = time.time()
            
            print("\n🎬 Script Complete!")
            self.print_timing_summary()
            
        except KeyboardInterrupt:
            print("\n🛑 Script interrupted")
            self.end_time = time.time()
            self.print_timing_summary()
        except Exception as e:
            print(f"\n❌ Script error: {e}")
            self.end_time = time.time()
            self.print_timing_summary()

def main():
    """Main entry point"""
    print("🎬 NITK Robot Video Script - Windows Version")
    print("=" * 50)
    
    script_file = input("Enter script file (default: video_script.json): ").strip()
    if not script_file:
        script_file = "video_script.json"
    
    script = WindowsVideoScript(script_file)
    
    print(f"\n📋 Using script file: {script_file}")
    print("🎙️  Make sure your microphone is working")
    print("🔊 Make sure your speakers are on")
    print("💡 Say 'Hello HiWonder' to trigger each response")
    
    input("\nPress Enter to start the video script...")
    script.run_script()

if __name__ == '__main__':
    main()
