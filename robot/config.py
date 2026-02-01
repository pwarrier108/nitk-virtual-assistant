import os

# ==========================================
# Audio Configuration
# ==========================================

# Audio file paths
AUDIO_PATHS = {
    'wakeup': './resources/audio/en/wakeup.wav',
    'start': './resources/audio/en/start_audio.wav',
    'no_voice': './resources/audio/en/no_voice.wav',
    'greeting': './resources/audio/en/greeting.wav',
    'error': './resources/audio/en/error.wav',
    'rag_error': './resources/audio/en/rag_error.wav',
    'timeout_error': './resources/audio/en/timeout_error.wav',
    'translation_error': './resources/audio/en/translation_error.wav'
}

# Audio settings
DEFAULT_VOLUME = 80                # Audio volume (0-100)

# ==========================================
# Context and Follow-up Detection
# ==========================================

# Context Window Settings
ENABLE_CONTEXT_WINDOW = True       # Enable follow-up question support
FOLLOWUP_DETECTION_THRESHOLD = 5   # Max words for follow-up detection
MAX_CONTEXT_AGE = 300              # Seconds to keep context active

# Follow-up patterns for detection
FOLLOWUP_PATTERNS = [
    r'\b(yes|yeah|yep|sure|okay|ok|definitely|please)\b',
    r'\b(more|tell me more|continue|go on|elaborate)\b', 
    r'\b(what about|tell me about|about that|details?)\b',
    r'\b(explain|describe|how|why|when|where)\b'
]

# ==========================================
# Error Handling and Fallback
# ==========================================

# Error messages - must match audio content exactly
ERROR_MESSAGES = {
    'general_error': "Sorry I can't do that",
    'no_context': "I don't have anything to follow up on. Please ask me a question first.",
    'rag_unavailable': "Sorry, I'm having trouble accessing my knowledge base right now",
    'timeout_error': "Sorry, that's taking too long to process. Please try asking again",
    'translation_failed': "Sorry I couldn't translate that right now. Please try again",
    'unsupported_language': "I don't speak that language currently, but I can help in Hindi, Kannada, Malayalam, Tamil, or Telugu."
}

# Map error messages to audio files
ERROR_TO_AUDIO = {
    'general_error': 'error',
    'rag_unavailable': 'rag_error', 
    'timeout_error': 'timeout_error',
    'translation_failed': 'translation_error'
}

# Service availability
GRACEFUL_DEGRADATION = True        # Continue operation when services fail
RAG_SERVICE_RETRY_ATTEMPTS = 3     # Retry attempts for RAG service

# ==========================================
# Hardware Configuration
# ==========================================

# Hardware settings
DEFAULT_PORT = '/dev/ttyUSB0'      # TonyPi communication port

# Robot Movement Settings
EMOTION_TIMING_MULTIPLIER = 1.0    # Adjust robot movement timing
IDLE_ANIMATION_FREQUENCY = 5.0     # Seconds between idle movements
POSITION_RESET_THRESHOLD = 10      # Interactions before position reset

# ==========================================
# Logging Configuration
# ==========================================

# Logging levels and settings
LOG_LEVEL = "INFO"                 # DEBUG, INFO, WARNING, ERROR
ENABLE_CONTEXT_LOGGING = True      # Log conversation context
ENABLE_PERFORMANCE_LOGGING = True  # Log response times and performance

# Standardized log messages
LOG_MESSAGES = {
    'audio_operation_failed': "Audio operation failed",
    'context_cleared': "Conversation context cleared", 
    'device_cleanup_complete': "Device cleanup complete",
    'device_cleanup_failed': "Device cleanup failed",
    'hardware_init_complete': "Hardware initialization complete",
    'interaction_reset': "Performing periodic position reset",
    'listening': "Listening...",
    'rag_health_check_failed': "RAG service health check failed",
    'rag_service_available': "RAG service is available and ready",
    'rag_service_unavailable': "RAG service is not available",
    'robot_neutral': "Robot returned to neutral position",
    'robot_position_reset': "Robot position forcefully reset",
    'shutdown_complete': "Shutdown complete",
    'startup': "Starting NITK Robot Assistant with Enhanced Features...",
    'tts_failed': "TTS failed",
    'wake_word_issue': "Wake word detection issue",
    'wake_word_ready': "Ready for interactions - say 'Hello HiWonder' to start"
}

# ==========================================
# RAG Service Configuration
# ==========================================

RAG_SERVICE_HOST = "192.168.29.202"  # Change to your server IP if running on different machine
RAG_SERVICE_PORT = 8000
RAG_SERVICE_TIMEOUT = 30
RAG_SERVICE_URL = f"http://{RAG_SERVICE_HOST}:{RAG_SERVICE_PORT}"

# Network configuration for RAG service
RAG_CONNECTION_RETRY_DELAY = 5   # Seconds to wait before retrying connection
RAG_HEALTH_CHECK_INTERVAL = 30  # Seconds between health checks

# ==========================================
# Robot Behavior Configuration
# ==========================================

# RAG Integration Settings
INTERACTION_RESET_INTERVAL = 10    # Reset robot position every N interactions
RESPONSE_LENGTH_LIMIT = 300        # Characters - for TTS optimization (not used with voice format)

# ==========================================
# Startup Greeting Configuration
# ==========================================

# Startup behavior settings
ENABLE_STARTUP_SPEECH = True           # Speak the greeting

# Startup greeting - simplified to single option
STARTUP_GREETING = "Hey there! I'm here to help you learn about NITK. What would you like to know?"

# ==========================================
# Text-to-Speech Configuration
# ==========================================

# Text-to-Speech Settings
TTS_PROVIDER = "openai"            # TTS provider
TTS_SPEED = 1.0                    # Speech speed multiplier
TTS_VOICE = "nova"                 # OpenAI TTS voice

# ==========================================
# Translation Configuration
# ==========================================

# Translation Settings
ENABLE_TRANSLATION = True          # Enable translation commands
SUPPORTED_LANGUAGES = [
    'Hindi', 'Kannada', 'Malayalam', 'Tamil', 'Telugu', 'English'
]
TRANSLATION_PROVIDER = "google"    # Translation service provider
TRANSLATION_TIMEOUT = 10           # Seconds for translation requests

# Translation command patterns
TRANSLATION_PATTERNS = {
    'english': r'\b(translate|convert|say).*\b(english|back to english)\b',
    'hindi': r'\b(translate|convert|say).*\b(hindi|हिंदी)\b',
    'kannada': r'\b(translate|convert|say).*\b(kannada|ಕನ್ನಡ)\b', 
    'malayalam': r'\b(translate|convert|say).*\b(malayalam|മലയാളം)\b',
    'tamil': r'\b(translate|convert|say).*\b(tamil|தமிழ்)\b',
    'telugu': r'\b(translate|convert|say).*\b(telugu|తెలుగు)\b'
}

# Note: Helper functions moved to respective modules
# - get_language_code() → utils.py 
# - get_startup_greeting() → replaced with direct STARTUP_GREETING usage

# ==========================================
# Language and Translation Configuration
# ==========================================

# Language mappings - centralized for all modules
LANGUAGE_CODES = {
    "English": "en",
    "Hindi": "hi", 
    "Kannada": "kn",
    "Malayalam": "ml", 
    "Tamil": "ta",
    "Telugu": "te"
}

# Language key to name mapping for translation detection
LANGUAGE_KEY_TO_NAME = {
    'english': 'English',
    'hindi': 'Hindi',
    'kannada': 'Kannada', 
    'malayalam': 'Malayalam',
    'tamil': 'Tamil',
    'telugu': 'Telugu'
}

if __name__ == "__main__":
    print("✅ Configuration loaded successfully!")
    print(f"🤖 Robot configured for RAG service at: {RAG_SERVICE_URL}")
    print(f"🗣️  Supported languages: {', '.join(SUPPORTED_LANGUAGES)}")
    print(f"🎵 Audio volume: {DEFAULT_VOLUME}%")