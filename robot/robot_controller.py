#!/usr/bin/env python3
# encoding: utf-8
# @Author: Padmanand
# @Date: 2025/03/05
# Updated: 2025/07/13 - Fixed action mappings and dynamic neutral responses
# Updated: 2025/07/13 - Fixed emotion mappings and sorted alphabetically

import time
import threading
import logging

# TonyPi imports
try:
    import sys
    sys.path.append('/home/pi/TonyPi/')
    from hiwonder import ActionGroupControl as AGC
    TONYPI_AVAILABLE = True
except ImportError:
    print("Warning: TonyPi ActionGroupControl not available")
    AGC = None
    TONYPI_AVAILABLE = False

class TonyPiController:
    """Controls TonyPi robot movements and emotions with natural behavior"""
    
    def __init__(self):
        self.agc_available = TONYPI_AVAILABLE
        self.current_emotion = 'neutral'
        self.idle_thread = None
        self.stop_idle = False
        self.logger = logging.getLogger('robot_controller')
        
        if not self.agc_available:
            self.logger.warning("TonyPi ActionGroupControl not available - robot movements disabled")
    
    def return_to_neutral(self):
        """Return robot to neutral standing position - ensures proper reset"""
        if not self.agc_available:
            return
        try:
            self.current_emotion = 'neutral'
            self.stop_idle_animation()
            
            # Multiple stand commands to ensure proper reset
            AGC.runActionGroup('stand')
            time.sleep(0.5)  # Brief pause
            AGC.runActionGroup('stand')  # Second stand to ensure reset
            
            from config import LOG_MESSAGES
            self.logger.info(LOG_MESSAGES['robot_neutral'])
        except Exception as e:
            self.logger.error(f"Failed to return to neutral: {e}")
    
    def reset_position(self):
        """Force a complete position reset - use if robot gets disoriented"""
        if not self.agc_available:
            return
        try:
            self.stop_idle_animation()
            
            # More aggressive reset sequence
            AGC.runActionGroup('stand')
            time.sleep(0.3)
            AGC.runActionGroup('stand')
            time.sleep(0.3)
            AGC.runActionGroup('stand')
            
            self.current_emotion = 'neutral'
            from config import LOG_MESSAGES
            self.logger.info(LOG_MESSAGES['robot_position_reset'])
        except Exception as e:
            self.logger.error(f"Failed to reset position: {e}")
    
    def execute_action(self, action_name):
        """Execute a specific action group"""
        if not self.agc_available:
            self.logger.debug(f"Would execute action: {action_name}")
            return
        
        try:
            AGC.runActionGroup(action_name)
            self.logger.info(f"Executed action: {action_name}")
        except Exception as e:
            self.logger.error(f"Failed to execute action {action_name}: {e}")
    
    def _idle_animation_loop(self, emotion, response_length=None):
        """Subtle idle animations during speech with reduced frequency"""
        # Enhanced action variety with explaining mode
        idle_actions = {
            'happy': ['wave', 'left_hand', 'right_hand'],
            'ecstatic': ['chest'], 
            'excited': ['left_hand', 'right_hand', 'wave'],
            'sad': ['bow', 'stand'],
            'confused': ['twist', 'stand'],
            'thinking': ['twist', 'bow'],
            'surprised': ['right_hand', 'left_hand'],
            'neutral': ['stand'],
            'explaining': ['stand', 'wave', 'stand', 'wave'],  # Simple stand/wave cycle
            'greeting': ['wave', 'left_hand', 'right_hand'],
            'goodbye': ['wave', 'bow']
        }
        
        actions = idle_actions.get(emotion, ['stand'])
        action_index = 0
        
        # Dynamic timing based on emotion and response length
        if emotion == 'explaining':
            # Slower timing for smooth, non-abrupt transitions
            if response_length is None:
                timing = 4.0  # Increased for smoother flow
            elif response_length < 10:
                timing = 3.5  # Slower transitions
            elif response_length < 30:
                timing = 4.0  # Smooth natural pace
            else:
                timing = 4.5  # Even slower for very long explanations
        else:
            # Original timing for other emotions
            if response_length is None:
                timing = 5.0
            elif response_length < 10:
                timing = 4.0
            elif response_length < 30:
                timing = 5.0
            else:
                timing = 6.0
        
        self.logger.info(f"Starting idle animation for {emotion} with {timing}s timing")
        
        while not self.stop_idle and self.agc_available:
            try:
                # Cycle through actions for natural movement
                current_action = actions[action_index % len(actions)]
                AGC.runActionGroup(current_action)
                action_index += 1
                
                time.sleep(timing)
                
            except Exception as e:
                self.logger.error(f"Idle animation failed: {e}")
                break
    
    def start_idle_animation(self, emotion, response_length=None):
        """Start subtle idle animation for the given emotion with reduced frequency"""
        self.stop_idle_animation()
        self.stop_idle = False
        
        if self.agc_available:
            self.idle_thread = threading.Thread(
                target=self._idle_animation_loop, 
                args=(emotion, response_length),
                daemon=True
            )
            self.idle_thread.start()
    
    def stop_idle_animation(self):
        """Stop the current idle animation"""
        self.stop_idle = True
        if self.idle_thread and self.idle_thread.is_alive():
            self.idle_thread.join(timeout=1.0)
    
    def express_emotion(self, emotion):
        """Express emotion through robot movement - starts immediately"""
        if not self.agc_available:
            self.logger.debug(f"Would express emotion: {emotion}")
            return
        
        # Map emotions to TonyPi action groups - sorted alphabetically
        emotion_actions = {
            'bow': 'bow',
            'confused': 'twist',
            'excited': 'left_hand',
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
        
        action = emotion_actions.get(emotion, 'stand')
        self.current_emotion = emotion
        
        try:
            # Execute the initial emotion action immediately
            AGC.runActionGroup(action)
            self.logger.info(f"Expressing emotion: {emotion} -> {action}")
        except Exception as e:
            self.logger.error(f"Failed to express emotion {emotion}: {e}")
    
    def express_emotion_with_speech(self, emotion, response_length=None):
        """Express emotion and start idle animation for speech duration with dynamic neutral handling"""
        
        # Special handling for neutral emotion with long responses
        if emotion == 'neutral' and response_length and response_length > 10:
            self.logger.info(f"Long neutral response detected ({response_length:.1f}s) - using explaining mode")
            # Start with a gentle gesture for long explanations
            self.express_emotion('wave')
            # Use explaining animation mode for more natural movement
            self.start_idle_animation('explaining', response_length)
        else:
            # Normal emotion handling
            self.express_emotion(emotion)
            self.start_idle_animation(emotion, response_length)
    
    def prepare_for_next_interaction(self):
        """Prepare robot for next interaction - only return to neutral when needed"""
        # Stop any ongoing idle animation
        self.stop_idle_animation()
        
        # Only return to neutral if not already neutral
        if self.current_emotion != 'neutral':
            time.sleep(0.5)  # Brief pause before transitioning
            self.return_to_neutral()