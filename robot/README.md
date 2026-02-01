# Robot Controller - NITK Virtual Assistant

Physical robot interface for the NITK Virtual Assistant using TonyPi robot platform with voice interaction, emotion expressions, and gesture control.

## Overview

The Robot Controller brings the NITK Virtual Assistant to life through a physical TonyPi robot that can:
- Listen for wake words and voice commands
- Answer questions with synthesized speech
- Express emotions through gestures and LED colors
- Interact naturally with users in physical spaces

## Hardware Platform

**TonyPi Robot:**
- Raspberry Pi-based humanoid robot
- Servo-controlled joints (head, arms, legs)
- RGB LED arrays for visual feedback
- USB audio interface for speech
- GPIO pins for motor control

**Required Components:**
- TonyPi robot kit
- USB microphone
- Speakers (built-in or external)
- Power supply (battery pack)
- WiFi connection (for RAG service)

## Architecture

```
┌────────────────────────────────────────────────────┐
│              Robot Main Loop (main.py)             │
│                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐│
│  │ Wake Word    │→ │ Voice Input  │→ │ Process  ││
│  │ Detection    │  │ (STT)        │  │ Query    ││
│  └──────────────┘  └──────────────┘  └────┬─────┘│
│                                            │      │
│                                            ▼      │
│  ┌─────────────────────────────────────────────┐ │
│  │          RAG Client (rag_client.py)         │ │
│  │  • HTTP request to RAG service              │ │
│  │  • Emotion extraction from response         │ │
│  │  • Context management                       │ │
│  └────────────────┬────────────────────────────┘ │
│                   │                               │
│                   ▼                               │
│  ┌─────────────────────────────────────────────┐ │
│  │   Parallel Execution (Threading)            │ │
│  │  ┌─────────────────┐ ┌────────────────────┐│ │
│  │  │ Voice Response  │ │ Physical Movement  ││ │
│  │  │ (TTS + Audio)   │ │ (Gestures + LEDs)  ││ │
│  │  │                 │ │                    ││ │
│  │  │ voice_assistant │ │ robot_controller   ││ │
│  │  └─────────────────┘ └────────────────────┘│ │
│  └─────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐         ┌────────────────┐
│  RAG Service    │         │  TonyPi        │
│  (Network)      │         │  Hardware      │
│  Port 8000      │         │  /dev/ttyUSB0  │
└─────────────────┘         └────────────────┘
```

## Components

### 1. Main Controller (`main.py`)

**Responsibilities:**
- System initialization and cleanup
- Main interaction loop
- Wake word detection
- Query orchestration
- Parallel TTS + gesture execution

**Interaction Flow:**
```python
while True:
    # 1. Wait for wake word
    if voice_assistant.check_wakeup():

        # 2. Acknowledge and listen
        voice_assistant.play_wakeup_audio()
        question = voice_assistant.listen()

        # 3. Get response from RAG service
        response = rag_client.query(question)

        # 4. Execute in parallel:
        #    - Speak response (voice_assistant)
        #    - Express emotion (robot_controller)
        threading.Thread(speak).start()
        robot.express_emotion_with_speech(emotion, duration)
```

### 2. Robot Controller (`robot_controller.py`)

Hardware control for TonyPi robot.

**Features:**
- **Servo Control:** Head tilt, arm movements, leg positioning
- **LED Control:** RGB colors for emotion visualization
- **Gesture Library:** Pre-defined movements for each emotion
- **Position Management:** Track and reset to neutral position

**Emotion Expressions:**

| Emotion | Movement | LED Color | Duration |
|---------|----------|-----------|----------|
| happy | Arms up, head tilt | Green | 2s |
| excited | Jump, wave arms | Yellow | 3s |
| sad | Head down, arms down | Blue | 2s |
| confused | Head tilt left/right | Purple | 2s |
| thinking | Hand to chin | Cyan | Variable |
| neutral | Subtle breathing | White | Continuous |
| greeting | Wave, bow | Green | 3s |
| goodbye | Wave, turn | Orange | 3s |

**Key Methods:**
```python
def express_emotion(emotion: str, duration: float = 2.0)
def express_emotion_with_speech(emotion: str, speech_duration: float)
def return_to_neutral()
def reset_position()
```

### 3. Voice Assistant (`voice_assistant.py`)

Speech recognition and audio playback.

**Features:**
- **Wake Word Detection:** Continuous listening for activation phrase
- **Speech-to-Text:** Google Speech Recognition
- **Text-to-Speech:** gTTS (Google TTS)
- **Audio Playback:** Pre-recorded and synthesized audio
- **Noise Handling:** Background noise filtering

**Audio Files:**
```
audio/
  ├── greeting.wav         # Startup greeting
  ├── start_audio.wav      # Recording started
  ├── record_finish.wav    # Recording complete
  ├── error.wav            # General error
  ├── rag_error.wav        # RAG service error
  ├── translation_error.wav
  └── timeout_error.wav
```

**Key Methods:**
```python
def check_wakeup() -> bool
def listen() -> str
def speak(text: str)
def play_wakeup_audio()
def play_greeting_audio()
def play_error_audio(error_type: str)
```

### 4. RAG Client (`rag_client.py`)

Communication with RAG service.

**Features:**
- Health checking
- Query execution with emotion extraction
- Context management (conversation history)
- Translation support
- Error handling and retries

**Response Object:**
```python
@dataclass
class RAGResponse:
    text: str
    emotion: str
    translation: str = None
    language: str = None
```

**Context Management:**
```python
# Maintains last 5 Q&A pairs for context
context_history = [
    {"question": "...", "response": "...", "emotion": "..."},
    ...
]
```

**Key Methods:**
```python
def query(question: str, language: str = "English") -> RAGResponse
def health_check() -> bool
def get_context_summary() -> dict
def clear_context()
```

### 5. Configuration (`config.py`)

Robot settings and constants.

**Key Configurations:**
```python
# Network
RAG_SERVICE_URL = "http://192.168.1.100:8000"
RAG_HEALTH_CHECK_INTERVAL = 300  # 5 minutes

# Audio
DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_VOLUME = 80
WAKE_WORD = "hey robot"

# Behavior
ENABLE_STARTUP_SPEECH = True
STARTUP_GREETING = "Hello! I am your NITK assistant."
INTERACTION_RESET_INTERVAL = 10  # Reset position every 10 interactions

# Emotions
EMOTION_TO_GESTURE = {
    'happy': 'arms_up',
    'excited': 'jump',
    'sad': 'head_down',
    # ...
}

ERROR_MESSAGES = {
    'rag_error': "Sorry, I cannot access my knowledge base right now.",
    'timeout': "I did not hear anything. Please try again.",
    # ...
}
```

### 6. Translation (`translation.py`)

Multi-language translation for robot responses.

**Supported Languages:**
- Hindi, Kannada, Malayalam, Tamil, Telugu

**Usage:**
```python
response = rag_client.query("Who is the director?", language="Hindi")
robot.speak(response.translation)  # Speaks in Hindi
```

### 7. Utilities (`utils.py`)

Helper functions for robot operations.

```python
def get_startup_greeting() -> str
def estimate_speech_duration(text: str) -> float
def sanitize_for_tts(text: str) -> str
```

## Installation

### Prerequisites

- TonyPi robot with Raspberry Pi
- Python 3.10+ on Raspberry Pi
- WiFi connection to RAG service
- USB microphone and speakers

### Hardware Setup

1. **Assemble TonyPi robot** (follow manufacturer instructions)

2. **Connect peripherals:**
   ```bash
   # Check USB audio device
   arecord -l  # List recording devices
   aplay -l    # List playback devices

   # Test microphone
   arecord -d 5 test.wav
   aplay test.wav
   ```

3. **Configure GPIO:**
   ```bash
   # Enable necessary GPIO pins
   sudo raspi-config
   # Interface Options → Serial Port → Enable
   ```

4. **Test servo control:**
   ```bash
   # Test TonyPi servos
   ls /dev/ttyUSB0  # Should exist
   sudo chmod 666 /dev/ttyUSB0
   ```

### Software Setup

```bash
cd robot

# Install system dependencies
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio espeak ffmpeg

# Install Python packages
pip install -r requirements.txt

# Download speech recognition models (if needed)
# (Google Speech Recognition uses online API)
```

### Network Configuration

1. **Find RAG service IP:**
   ```bash
   # On RAG service machine
   python -c "import socket; print(socket.gethostbyname(socket.gethostname()))"
   ```

2. **Update robot config:**
   ```python
   # config.py
   RAG_SERVICE_URL = "http://192.168.1.XXX:8000"
   ```

3. **Test connectivity:**
   ```bash
   curl http://192.168.1.XXX:8000/health
   ```

## Usage

### Starting the Robot

```bash
cd robot
python main.py

# With debug logging
python main.py --debug
```

**Startup Sequence:**
1. Hardware initialization (2s)
2. Greeting gesture (bow)
3. Greeting speech
4. Wake word detection active

### Interaction

**1. Wake the Robot:**
- Say: "Hey Robot" (or configured wake word)
- Robot responds: "I'm here" (audio only)

**2. Ask Question:**
- Robot plays recording indicator
- Speak your question clearly
- Robot plays recording complete sound

**3. Get Response:**
- Robot speaks answer (TTS)
- Simultaneously performs emotion gesture
- Returns to neutral position

**4. Follow-up:**
- Can ask related questions (context maintained)
- Say wake word again for new interaction

### Example Interaction

```
User: "Hey Robot"
Robot: [Audio: "I'm here"]

User: "Who is the director of NITK?"
Robot: [Speaks: "The current director of NITK is Prof. ..."]
       [Gesture: Neutral with subtle movement]

User: "Hey Robot"
Robot: [Audio: "I'm here"]

User: "Tell me more about him"
Robot: [Speaks: "He has served since..."]
       [Gesture: Thinking pose]
```

## Configuration

### Wake Word Customization

```python
# config.py
WAKE_WORD = "hey robot"  # Change to your preference
WAKE_WORD_SENSITIVITY = 0.7  # 0.0-1.0 (higher = less sensitive)
```

### Emotion Mapping

```python
# Add new emotion
EMOTION_TO_GESTURE = {
    'surprised': 'head_back_arms_up',
    # ...
}

# Implement gesture in robot_controller.py
def gesture_head_back_arms_up(self):
    # Servo commands
    pass
```

### Audio Volume

```python
# config.py
DEFAULT_VOLUME = 80  # 0-100

# Or runtime adjustment
voice_assistant.set_volume(60)
```

### Language Support

```python
# Query in specific language
response = rag_client.query("Who is director?", language="Hindi")
```

## Troubleshooting

### Wake Word Not Detecting

**Issue:** Robot doesn't respond to wake word

**Solutions:**
1. Check microphone:
   ```bash
   arecord -l
   # Adjust microphone in config if needed
   ```

2. Test background noise:
   ```bash
   # Lower sensitivity
   WAKE_WORD_SENSITIVITY = 0.5
   ```

3. Check audio input level:
   ```bash
   alsamixer  # Adjust capture volume
   ```

### RAG Service Connection Failed

**Issue:** "RAG service unavailable"

**Solutions:**
1. Verify service running:
   ```bash
   curl http://<rag-service-ip>:8000/health
   ```

2. Check network:
   ```bash
   ping <rag-service-ip>
   ```

3. Check firewall:
   ```bash
   # On RAG service machine
   sudo ufw allow 8000
   ```

### Servo Errors

**Issue:** Robot movements jerky or not working

**Solutions:**
1. Check serial port:
   ```bash
   ls -l /dev/ttyUSB0
   sudo chmod 666 /dev/ttyUSB0
   ```

2. Check power supply:
   - Ensure battery is charged
   - Servos need sufficient power

3. Reset servos:
   ```python
   robot.reset_position()
   ```

### Audio Playback Issues

**Issue:** No sound or distorted audio

**Solutions:**
1. Check speakers:
   ```bash
   speaker-test -t wav
   ```

2. Adjust volume:
   ```bash
   alsamixer  # Set PCM volume
   ```

3. Check audio output device:
   ```python
   # config.py
   AUDIO_OUTPUT_DEVICE = "hw:0,0"  # Adjust for your device
   ```

### TTS Errors

**Issue:** "Audio generation failed"

**Solutions:**
1. Check internet connection (gTTS requires internet)
2. Install espeak as fallback:
   ```bash
   sudo apt-get install espeak
   ```

3. Clear audio cache:
   ```bash
   rm -rf ../cache/audio/*
   ```

## Best Practices

### For Optimal Interaction

1. **Speak Clearly:** Enunciate questions clearly
2. **Quiet Environment:** Reduce background noise
3. **Natural Language:** Ask questions naturally
4. **Wait for Response:** Don't interrupt robot's response

### For Maintenance

1. **Periodic Reset:** Reset robot position every 10 interactions (automatic)
2. **Battery Charging:** Keep robot charged for consistent servo performance
3. **Cache Cleanup:** Clear audio cache weekly if disk space limited
4. **Log Monitoring:** Check logs for errors

### For Development

1. **Test Without Hardware:** Use mock robot controller for development
2. **Gradual Movement:** Test servo movements slowly first
3. **Error Handling:** Always catch hardware exceptions
4. **Context Clearing:** Clear context periodically to prevent memory buildup

## Safety

### Physical Safety

1. **Stable Surface:** Place robot on stable, level surface
2. **Clear Space:** Ensure 1m clearance around robot for movements
3. **Supervision:** Supervise robot during operation
4. **Emergency Stop:** Be ready to unplug if malfunction occurs

### Software Safety

```python
# Signal handler for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)

# Emergency shutdown
def signal_handler(sig, frame):
    robot.stop_idle_animation()
    robot.return_to_neutral()
    voice_assistant.exit()
    sys.exit(0)
```

## Performance

### Optimization Tips

1. **Preload Audio:** Pre-generate common responses
2. **Reduce Latency:** Use local TTS (espeak) for faster response
3. **Parallel Execution:** TTS + gesture already parallelized
4. **Context Pruning:** Limit context to last 5 interactions

### Benchmarks

| Operation | Time (Avg) | Notes |
|-----------|-----------|-------|
| Wake word detection | < 1s | Continuous listening |
| Speech recognition | 2-3s | Google STT |
| RAG query | 2-5s | Network + LLM |
| TTS generation | 1-2s | gTTS online |
| Total interaction | 5-10s | End-to-end |

## TODO: Future Improvements

### High Priority
- [ ] Add offline wake word detection (Porcupine, Snowboy)
- [ ] Implement offline TTS (espeak, pyttsx3)
- [ ] Add face detection (turn toward user)
- [ ] Improve gesture smoothness (interpolation)
- [ ] Add battery level monitoring

### Medium Priority
- [ ] Implement gesture recording (teach new gestures)
- [ ] Add LCD display for text responses
- [ ] Create mobile app for remote control
- [ ] Add camera for visual Q&A (image recognition)
- [ ] Implement obstacle avoidance (for movement)

### Low Priority
- [ ] Add personality modes (friendly, professional, playful)
- [ ] Implement dance mode (entertainment)
- [ ] Add gesture recognition (respond to hand signals)
- [ ] Create gesture sequences for storytelling
- [ ] Add LED animations (dynamic patterns)

### Code Quality
- [ ] Add hardware abstraction layer (support other robots)
- [ ] Implement comprehensive error recovery
- [ ] Add unit tests with hardware mocks
- [ ] Improve servo position caching
- [ ] Extract magic numbers to config

## Hardware Abstraction

To support other robot platforms:

```python
# robot_interface.py
class RobotInterface(ABC):
    @abstractmethod
    def move_head(self, angle: float): pass

    @abstractmethod
    def move_arm(self, arm: str, angle: float): pass

    @abstractmethod
    def set_led_color(self, r: int, g: int, b: int): pass

# tonypi_controller.py
class TonyPiController(RobotInterface):
    # Implementation for TonyPi

# other_robot_controller.py
class OtherRobotController(RobotInterface):
    # Implementation for other platforms
```

## Development Without Hardware

Create mock controller for testing:

```python
# mock_robot_controller.py
class MockRobotController:
    def express_emotion(self, emotion, duration=2.0):
        print(f"[MOCK] Expressing {emotion} for {duration}s")

    def return_to_neutral(self):
        print("[MOCK] Returning to neutral")
```

```python
# main.py
if DEVELOPMENT_MODE:
    from mock_robot_controller import MockRobotController as RobotController
else:
    from robot_controller import TonyPiController as RobotController
```

## Advanced Features

### Multi-turn Conversation

```python
# Robot remembers context
User: "Who is the director?"
Robot: "Prof. XYZ is the director."

User: "When did he join?"  # "he" refers to director
Robot: "He joined in 2020."  # Uses context
```

### Emotion Chaining

```python
# Combine multiple emotions
robot.express_emotion_sequence([
    ('greeting', 2.0),
    ('happy', 1.5),
    ('neutral', 0.0)  # Return to neutral
])
```

### Dynamic Gestures

```python
# Adjust gesture based on response length
speech_duration = estimate_duration(response.text)
if speech_duration > 10:
    robot.dynamic_neutral_movement(speech_duration)
else:
    robot.express_emotion(emotion, speech_duration)
```

---

**Integration Complete:** Robot now provides physical embodiment for the NITK Virtual Assistant with natural voice interaction and emotional expressiveness.

For API details, see [../rag-service/README.md](../rag-service/README.md)
