#!/usr/bin/env python3
"""
Test Google Speech-to-Text for Indian languages
"""

import speech_recognition as sr

def test_google_stt():
    r = sr.Recognizer()
    mic = sr.Microphone()

    # Test languages
    languages = {
        "English": "en-IN",  # Indian English
        "Hindi": "hi-IN",
        "Tamil": "ta-IN", 
        "Telugu": "te-IN",
        "Kannada": "kn-IN",
        "Malayalam": "ml-IN"
    }

    test_words = ["Tamil", "Telugu", "Kannada", "Malayalam", "Surathkal", "NITK", "NITKonnect", "Bangalore"]

    print("🎤 Google STT Test")
    print(f"Test words: {', '.join(test_words)}")

    with mic as source:
        r.adjust_for_ambient_noise(source)

    for lang_name, lang_code in languages.items():
        print(f"\n--- Testing {lang_name} ({lang_code}) ---")
        
        while True:
            user_input = input(f"Press Enter to test {lang_name} (or 's' to skip): ")
            if user_input.lower() == 's':
                break

            print("🔴 Listening...")
            try:
                with mic as source:
                    audio = r.listen(source, timeout=5, phrase_time_limit=3)
                
                # Try Google STT
                text = r.recognize_google(audio, language=lang_code)
                
                # Check matches
                matched = any(word.lower() in text.lower() for word in test_words)
                status = "✅" if matched else "📝"
                print(f"{status} Google ({lang_name}): '{text}'")
                
                # Highlight matches
                for word in test_words:
                    if word.lower() in text.lower():
                        print(f"   🎯 Matched: {word}")
                        
            except sr.UnknownValueError:
                print("❌ Google couldn't understand audio")
            except sr.RequestError as e:
                print(f"❌ Google API error: {e}")
            except Exception as e:
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_google_stt()
