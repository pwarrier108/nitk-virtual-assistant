#!/usr/bin/env python3
# encoding: utf-8
# @Author: Padmanand
# @Date: 2025/03/05
# Updated: 2025/07/08 - Added RAG service integration with context and translation
# Updated: 2025/07/13 - Added continuous conversation support
# Updated: 2025/07/13 - Fixed greeting, wave, and audio issues
# Updated: 2025/07/13 - Reverted to reliable wake word per interaction
# Updated: 2025/07/13 - Added emotion detection from RAG service and improved audio flow

import os
import time
import threading
import logging
import signal
import sys
import argparse
from config import *
from utils import get_startup_greeting

# Import our modular components
from robot_controller import TonyPiController
from voice_assistant import VoiceAssistant
from rag_client import RAGClient

def setup_logging(debug=False):
    """Setup logging configuration"""
    level = logging.DEBUG if debug else getattr(logging, LOG_LEVEL)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger('robot_main')

def signal_handler(sig, frame):
    """Handle Ctrl+C interrupt for immediate shutdown"""
    logger.info('Received interrupt signal, shutting down gracefully...')
    
    # Force cleanup and exit
    try:
        # Try to access global variables safely
        if 'robot' in globals():
            robot.stop_idle_animation()
            robot.return_to_neutral()
        if 'voice_assistant' in globals():
            voice_assistant.exit()
        os.system('pinctrl FAN_PWM a0')
    except Exception as e:
        logger.warning(f"Cleanup error: {e}")
    
    logger.info(LOG_MESSAGES['shutdown_complete'])
    sys.exit(0)

def cleanup_devices():
    """Clean up device conflicts before starting"""
    # TODO: Replace os.system() with subprocess.run() for better error handling and security
    # TODO: Check return codes and log specific errors
    try:
        logger.info("Cleaning up device conflicts...")
        os.system("sudo pkill -f 'speech|asr|tts' > /dev/null 2>&1")
        os.system("sudo fuser -k /dev/ttyUSB0 > /dev/null 2>&1")
        time.sleep(1)
        logger.info(LOG_MESSAGES['device_cleanup_complete'])
    except Exception as e:
        logger.warning(f"{LOG_MESSAGES['device_cleanup_failed']}: {e}")

def check_rag_service():
    """Check if RAG service is available and provide user feedback"""
    rag_client = RAGClient(RAG_SERVICE_URL)
    
    if rag_client.health_check():
        service_info = rag_client.get_service_info()
        logger.info(LOG_MESSAGES['rag_service_available'])
        if service_info:
            logger.info(f"  Service: {service_info.get('message', 'NITK RAG Service')}")
            # Check if emotion detection is supported
            features = service_info.get('features', [])
            if 'emotion_detection' in features:
                logger.info("  ✓ Emotion detection supported")
        return True
    else:
        logger.warning(LOG_MESSAGES['rag_service_unavailable'])
        logger.warning(f"  Tried connecting to: {RAG_SERVICE_URL}")
        logger.warning("  Make sure the RAG service is running with:")
        logger.warning("  cd rag-service && python main.py")
        return False

def print_context_info(llm_client):
    """Print current conversation context for debugging"""
    if hasattr(llm_client, 'get_context_summary'):
        context = llm_client.get_context_summary()
        if context['has_context']:
            logger.info(f"Context: Q='{context['last_question'][:50]}...' | R='{context['last_response'][:50]}...' | Emotion: {context.get('last_emotion', 'unknown')}")
            if context['last_translation']:
                logger.info(f"Translation: '{context['last_translation'][:50]}...' ({context['last_language']})")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='NITK Robot Assistant')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Setup logging
    global logger
    logger = setup_logging(args.debug)
    
    logger.info(LOG_MESSAGES['startup'])
    
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Clean up any device conflicts first
    cleanup_devices()
    
    # Check RAG service availability
    rag_available = check_rag_service()
    
    # Initialize all components
    llm_client = RAGClient(RAG_SERVICE_URL)
    logger.info("Initialized RAG client")
    
    voice_assistant = VoiceAssistant(port=DEFAULT_PORT, volume=DEFAULT_VOLUME)
    robot = TonyPiController()
    
    # Make robot and voice_assistant available to signal handler
    globals()['robot'] = robot
    globals()['voice_assistant'] = voice_assistant
    
    # Hardware initialization - matching the working example
    try:
        os.system('pinctrl FAN_PWM op dh')
    except:
        pass
    
    # Startup sequence with improved audio flow - NO hardware "I'm ready"
    logger.info("Waiting for hardware initialization...")
    time.sleep(2.0)  # Brief wait for hardware setup
    
    print('NITK Robot Assistant started with enhanced features:')
    print('✓ Voice-optimized responses from RAG service')
    print('✓ Integrated emotion detection from RAG service')
    print('✓ Context-aware follow-up questions')
    print('✓ Multi-language translation support')
    print('✓ Reliable wake word per interaction')

    if rag_available:
        print('✓ Connected to NITK knowledge base')
    else:
        print('⚠ Using fallback mode - limited NITK knowledge')

    # Custom startup greeting with improved flow
    if ENABLE_STARTUP_SPEECH:
        from config import STARTUP_GREETING
        logger.info(f'Greeting: {STARTUP_GREETING}')
        
        # Bow first as a respectful greeting
        logger.info("Robot bowing...")
        robot.express_emotion('bow')  # Professional bow before speaking
        time.sleep(3.5)  # Time for full bow completion
        
        # Play prerecorded greeting instead of TTS
        voice_assistant.play_greeting_audio()
        time.sleep(0.5)  # Brief pause after speech
        
        # Wait after complete greeting sequence
        #time.sleep(2.0) - not needed

    # Start voice detection and set robot to neutral
    voice_assistant.start_wake_word_detection()
    robot.return_to_neutral()
    
    # Main interaction loop with integrated emotion detection
    interaction_count = 0
    last_health_check = time.time()
    
    logger.info(LOG_MESSAGES['wake_word_ready'])
    
    while True:
        try:
            current_time = time.time()
            
            # Periodic health check for RAG service
            if current_time - last_health_check > RAG_HEALTH_CHECK_INTERVAL:
                rag_status = llm_client.health_check()
                if not rag_status:
                    logger.warning(LOG_MESSAGES['rag_health_check_failed'])
                last_health_check = current_time
            
            # Wake word detection - reliable and simple
            if voice_assistant.check_wakeup():
                interaction_count += 1
                
                # Play "I'm here" audio only - no visual action
                voice_assistant.play_wakeup_audio()  # "I'm here"
                time.sleep(0.1)  # Brief pause to prevent audio conflicts
                
                asr_result = voice_assistant.listen()
                logger.info(f'[Interaction #{interaction_count}] Question: {asr_result}')
                
                if asr_result:
                    # Print current context for debugging
                    print_context_info(llm_client)
                    
                    # Get response with emotion from RAG service
                    rag_response = llm_client.query(asr_result)
                    response = rag_response.text
                    emotion = rag_response.emotion
                    
                    logger.info(f'Response: {response}')
                    logger.info(f'Detected emotion: {emotion}')
                    
                    # Check if this is an error response that needs audio
                    from config import ERROR_MESSAGES, ERROR_TO_AUDIO
                    is_error = response in ERROR_MESSAGES.values()
                    
                    if is_error:
                        # Find error type and play audio
                        error_type = next((k for k, v in ERROR_MESSAGES.items() if v == response), 'general_error')
                        if error_type in ERROR_TO_AUDIO:
                            voice_assistant.play_error_audio(error_type)
                        else:
                            voice_assistant.speak(response)  # Fallback to TTS
                    else:
                        # Normal response - use TTS
                        # Log which service was used
                        logger.info("Response from RAG service with integrated emotion detection")
                        
                        # Check if this was a translation request
                        is_translation = llm_client.last_translation and response == llm_client.last_translation
                        
                        if is_translation:
                            logger.info(f'Translation to {llm_client.last_language}: {response}')
                        
                        # Estimate response length for dynamic timing
                        word_count = len(response.split())
                        estimated_duration = (word_count / 150) * 60  # Convert to seconds
                        
                        # Start TTS immediately
                        def speak_response():
                            voice_assistant.speak(response)
                            time.sleep(0.2)  # Brief pause after TTS to prevent audio conflicts
                        
                        # TODO: Consider removing daemon=True to ensure audio completes before shutdown
                        # TODO: Add proper thread coordination (Event, Lock) instead of daemon threads
                        # Start speaking in parallel
                        speak_thread = threading.Thread(target=speak_response, daemon=True)
                        speak_thread.start()
                        
                        # Use emotion from RAG service (no separate emotion detection needed)
                        logger.debug(f'Emotion from RAG: {emotion}, Duration: {estimated_duration:.1f}s, Dynamic neutral: {emotion == "neutral" and estimated_duration > 10}')
                        
                        # Start emotion expression - robot will move gently during speech
                        robot.express_emotion_with_speech(emotion, estimated_duration)
                        
                        # Wait for TTS to complete
                        speak_thread.join()
                    
                    # Prepare for next interaction
                    robot.prepare_for_next_interaction()
                    
                    # TODO: Move magic number 10 to INTERACTION_RESET_INTERVAL constant in config
                    # Periodic position reset to prevent drift (every 10 interactions)
                    if interaction_count % INTERACTION_RESET_INTERVAL == 0:
                        logger.info(f"{LOG_MESSAGES['interaction_reset']} (interaction #{interaction_count})")
                        robot.reset_position()
                        
                        # Optional: Clear context every 10 interactions to prevent memory buildup
                        if hasattr(llm_client, 'clear_context'):
                            llm_client.clear_context()
                            logger.info(LOG_MESSAGES['context_cleared'])
                    
                else:
                    voice_assistant.play_no_voice_audio()
                    # Brief confused expression when no voice detected
                    robot.express_emotion('confused')
                    time.sleep(1)
                    robot.return_to_neutral()
            
            time.sleep(0.02)  # Main loop timing
            
        except KeyboardInterrupt:
            logger.info("Shutting down gracefully...")
            
            # Save context info before shutdown
            if hasattr(llm_client, 'get_context_summary'):
                context = llm_client.get_context_summary()
                if context['has_context']:
                    logger.info(f"Final context: {context['last_question']} -> {context['last_response'][:100]}...")
                    logger.info(f"Final emotion: {context.get('last_emotion', 'unknown')}")
            
            robot.stop_idle_animation()
            voice_assistant.exit()
            robot.return_to_neutral()
            
            try:
                os.system('pinctrl FAN_PWM a0')
            except:
                pass
            break
            
        except Exception as e:
            # TODO: Categorize exceptions (HardwareError, NetworkError, AudioError)
            # TODO: Handle critical hardware failures differently (emergency stop + exit)
            # TODO: Add error recovery strategies based on error type
            logger.error(f"Error in main loop: {e}")
            logger.error(f"Main loop error: {e}", exc_info=True)

            # On error, ensure robot returns to safe state
            robot.stop_idle_animation()
            robot.return_to_neutral()
            time.sleep(1)  # Brief pause before continuing

if __name__ == '__main__':
    main()