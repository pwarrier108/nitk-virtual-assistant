from dotenv import load_dotenv
import os
from pathlib import Path
from google.cloud import texttospeech
from google.oauth2 import service_account

# Load environment variables from .env
load_dotenv()

# Try to get credentials path from .env, with fallback to hardcoded path
raw_path = os.getenv("GOOGLE_TTS_CREDENTIALS")

# If .env fails, use hardcoded path as backup
if not raw_path or '\n' in raw_path:
    print("⚠️  Using hardcoded path due to .env issues")
    credentials_path = Path("C:/Users/padma/Documents/Projects/nitkmodular/nitk-virtual-assistant-1f87354dcd8b.json")
else:
    print(f"✅ Using path from .env: {raw_path}")
    credentials_path = Path(raw_path).expanduser().resolve()

print(f"Looking for credentials at: {credentials_path}")
print(f"File exists: {credentials_path.exists()}")

if not credentials_path.exists():
    print("❌ Credentials file not found!")
    print("Please check if the file exists and the path is correct.")
    
    # Let's check what files are in the directory
    parent_dir = credentials_path.parent
    if parent_dir.exists():
        print(f"\nFiles in {parent_dir}:")
        for file in parent_dir.iterdir():
            if file.suffix == '.json':
                print(f"  📄 {file.name}")
    exit(1)

# Load credentials
try:
    credentials = service_account.Credentials.from_service_account_file(str(credentials_path))
    print("✅ Credentials loaded successfully")
except Exception as e:
    print(f"❌ Error loading credentials: {e}")
    exit(1)

# Initialize the client
client = texttospeech.TextToSpeechClient(credentials=credentials)

# Configuration
PHRASE = "Sorry, that's taking too long to process. Please try asking again."
OUTPUT_FILE = "timeout_error.wav"

# Build request
synthesis_input = texttospeech.SynthesisInput(text=PHRASE)
voice = texttospeech.VoiceSelectionParams(
    language_code="en-IN",
    name="en-IN-Wavenet-B"  # Male Indian voice
    #ssml_gender=texttospeech.SsmlVoiceGender.MALE
)
audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16
)

# Perform the request
try:
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    
    # Write the audio content to file
    with open(OUTPUT_FILE, "wb") as out:
        out.write(response.audio_content)
        print(f"✅ Audio written to: {OUTPUT_FILE}")
        
except Exception as e:
    print(f"❌ Error during TTS synthesis: {e}")