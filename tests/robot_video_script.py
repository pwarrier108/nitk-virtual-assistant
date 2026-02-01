#!/usr/bin/env python3
# encoding: utf-8
# Robot Video Script - Hardware version for TonyPi robot
# Adapted from Windows version with real robot components

import json
import time
import threading
import os
import sys
import signal
from datetime import datetime
from pathlib import Path

# Import robot components
from robot_controller import TonyPiController
from voice_assistant import VoiceAssistant
from config import DEFAULT_PORT, DEFAULT_VOLUME

class RobotVideoScript:
    """Robot video script with hardware integration"""
    
    def __init__(self, script_file="video_script.json"):
        self.script_file = script_file
        self.qa_pairs = []
        self.current_qa_index = 0
        self.start_time = None
        self.end_time = None
        
        # Initialize robot hardware
        self.robot = TonyPiController()
        self.voice_assistant = VoiceAssistant(port=DEFAULT_PORT, volume=DEFAULT_VOLUME)
        
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
        self.setup_hardware()
    
    def setup_hardware(self):
        """Initialize robot hardware"""
        try:
            # Hardware initialization - matching main.py
            os.system('pinctrl FAN_PWM op dh')
            
            # Start wake word detection
            self.voice_assistant.start_wake_word_detection()
            
            # Set robot to neutral position
            self.robot.return_to_neutral()
            
            print("✅ Robot hardware initialized successfully")
            
        except Exception as e:
            print(f"❌ Error initializing robot hardware: {e}")
            exit(1)
    
    def setup_signal_handler(self):
        """Handle Ctrl+C gracefully"""
        def signal_handler(sig, frame):
            print('\n[INFO] Script interrupted')
            self.cleanup_hardware()
            self.print_timing_summary()
            sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)
    
    def cleanup_hardware(self):
        """Clean up robot hardware"""
        try:
            self.robot.stop_idle_animation()
            self.voice_assistant.exit()
            self.robot.return_to_neutral()
            os.system('pinctrl FAN_PWM a0')
            print("✅ Hardware cleanup complete")
        except Exception as e:
            print(f"⚠️ Hardware cleanup error: {e}")
    
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
        """Log robot action with timing"""
        action = self.emotion_actions.get(emotion, 'stand')
        elapsed = time.time() - self.start_time if self.start_time else 0
        print(f"[ROBOT {elapsed:5.1f}s] {emotion.upper()} → {action.upper()} {description}")
        print(f"[DEBUG] emotion='{emotion}', action='{action}', mapping exists: {emotion in self.emotion_actions}")
    
    def speak_with_emotion(self, text, emotion="neutral"):
        """Speak text using robot's voice assistant with emotion"""
        print(f"[TTS] {text[:80]}{'...' if len(text) > 80 else ''}")
        
        # Log robot emotion start
        self.log_robot_action(emotion, "(with speech)")
        
        # Estimate response duration for robot movements
        word_count = len(text.split())
        estimated_duration = (word_count / 150) * 60  # Convert to seconds
        
        try:
            # Start TTS and robot emotion in parallel
            def speak_response():
                self.voice_assistant.speak(text)
                time.sleep(0.2)  # Brief pause after TTS
            
            # Start speaking in parallel
            speak_thread = threading.Thread(target=speak_response, daemon=True)
            speak_thread.start()
            
            # Start robot emotion expression with speech timing
            if emotion in ['explaining', 'ecstatic']:
                # For longer emotions, use express_emotion_with_speech
                self.robot.express_emotion_with_speech(emotion, estimated_duration)
            else:
                # For shorter emotions, just express and return to neutral
                self.robot.express_emotion(emotion)
                time.sleep(min(2.0, estimated_duration))  # Brief emotion display
            
            # Wait for TTS to complete
            speak_thread.join()
            
            print("[TTS] Speech completed successfully")
            
        except Exception as e:
            print(f"[TTS ERROR] Speech failed: {e}")
        
        # Log return to neutral for non-neutral emotions
        if emotion != 'neutral':
            self.log_robot_action('neutral', "(return to neutral)")
    
    def wait_for_wake_word(self):
        """Wait for hardware wake word detection"""
        print(f"\n[WAKE] Waiting for wake word (Question {self.current_qa_index + 1})")
        
        try:
            # Wait for wake word with timeout
            timeout_start = time.time()
            timeout_duration = 30  # 30 second timeout
            
            while time.time() - timeout_start < timeout_duration:
                if self.voice_assistant.check_wakeup():
                    print("[HEARD] Wake word detected - proceeding!")
                    return True
                time.sleep(0.02)  # Small delay to prevent busy waiting
            
            print("[TIMEOUT] No wake word detected, listening again...")
            return self.wait_for_wake_word()  # Try again
            
        except KeyboardInterrupt:
            return False
        except Exception as e:
            print(f"[WAKE ERROR] {e}")
            return False
    
    def play_wakeup_response(self):
        """Play 'I'm here' response using robot audio"""
        print("[WAKEUP] I'm here!")
        self.log_robot_action('neutral', "(wakeup confirmation)")
        
        # Use robot's wakeup audio
        self.voice_assistant.play_wakeup_audio()
        time.sleep(0.5)
    
    def simulate_listening_for_question(self):
        """Simulate listening for question (ignore actual content)"""
        print("[LISTENING] Listening for question...")
        
        try:
            # Brief pause to simulate listening
            time.sleep(1.0)
            print("[HEARD] Question received (content ignored)")
        except Exception as e:
            print(f"[LISTENING] Error: {e}, proceeding anyway")
    
    def random_processing_delay(self):
        """Random delay to simulate server processing"""
        import random
        delay = random.uniform(1.0, 2.0)
        print(f"[PROCESSING] Simulating server delay: {delay:.1f}s")
        time.sleep(delay)
    
    def play_greeting(self):
        """Play greeting sequence using robot components"""
        print("\n" + "="*60)
        print("🤖 GREETING SEQUENCE")
        print("="*60)
        
        greeting_text = "Hey there! I'm here to help you learn about NITK. What would you like to know?"
        
        # Robot bow before speaking
        self.log_robot_action('bow', "(respectful greeting)")
        self.robot.express_emotion('bow')
        time.sleep(3.5)  # Time for bow completion
        
        # Use robot's greeting audio or speak text
        try:
            self.voice_assistant.play_greeting_audio()
        except:
            # Fallback to TTS if greeting audio not available
            self.speak_with_emotion(greeting_text, 'greeting')
        
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
        
        # Speak with emotion using robot
        self.speak_with_emotion(answer, emotion)
        
        # Prepare for next interaction
        self.robot.prepare_for_next_interaction()
        
        self.current_qa_index += 1
        time.sleep(0.5)  # Brief pause between interactions
        
        return True
    
    def play_goodbye(self):
        """Play goodbye sequence using robot components"""
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
        self.robot.express_emotion('wave')
        time.sleep(2.0)
        
        # Speak goodbye
        self.speak_with_emotion(goodbye_text, 'goodbye')
        
        # Final bow
        self.log_robot_action('bow', "(final bow)")
        self.robot.express_emotion('bow')
        time.sleep(3.0)
        
        # Return to neutral
        self.log_robot_action('neutral', "(final neutral)")
        self.robot.return_to_neutral()
        
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
        print("🎬 Robot Video Script Starting")
        print("="*60)
        print("🤖 Robot hardware enabled")
        print("🎤 Hardware wake word enabled")
        print("🔊 Robot TTS enabled")
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
                    self.robot.reset_position()
            
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
        finally:
            # Always cleanup hardware
            self.cleanup_hardware()

def main():
    """Main entry point"""
    print("🎬 NITK Robot Video Script - Hardware Version")
    print("=" * 50)
    
    script_file = input("Enter script file (default: video_script.json): ").strip()
    if not script_file:
        script_file = "video_script.json"
    
    script = RobotVideoScript(script_file)
    
    print(f"\n📋 Using script file: {script_file}")
    print("🤖 Make sure robot is connected and powered")
    print("🎙️  Hardware wake word detection active")
    print("💡 Say 'Hello HiWonder' to trigger each response")
    
    input("\nPress Enter to start the video script...")
    script.run_script()

if __name__ == '__main__':
    main()
