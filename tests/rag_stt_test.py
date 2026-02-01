#!/usr/bin/env python3
"""
Test Google Speech-to-Text + RAG Service Integration
Records voice queries and gets responses from running RAG service
"""

import speech_recognition as sr
import requests
import json
import time
from datetime import datetime

class RAGSTTTester:
    def __init__(self, rag_host="localhost", rag_port=8000):
        self.rag_url = f"http://{rag_host}:{rag_port}"
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Test languages for STT
        self.languages = {
            "English (India)": "en-IN",
            "Hindi": "hi-IN",
            "Tamil": "ta-IN", 
            "Telugu": "te-IN",
            "Kannada": "kn-IN",
            "Malayalam": "ml-IN"
        }
        
        # Adjust for ambient noise
        print("🔧 Calibrating microphone...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
        print("✅ Microphone ready")
        
    def test_rag_connection(self):
        """Test if RAG service is accessible"""
        try:
            response = requests.get(f"{self.rag_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ RAG Service connected: {data.get('message', 'OK')}")
                return True
            else:
                print(f"❌ RAG Service returned {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to RAG service at {self.rag_url}")
            print("   Make sure your RAG service is running on the specified host:port")
            return False
        except Exception as e:
            print(f"❌ RAG connection error: {e}")
            return False
    
    def query_rag_service(self, question, format_type="web"):
        """Send query to RAG service and get response"""
        try:
            payload = {
                "question": question,
                "format": format_type
            }
            
            print(f"🔄 Querying RAG service ({format_type} format)...")
            response = requests.post(
                f"{self.rag_url}/query", 
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "response": data.get("response", ""),
                    "emotion": data.get("emotion", "neutral"),
                    "cache_safe": data.get("cache_safe", True),
                    "metadata": data.get("metadata", {})
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def listen_and_recognize(self, language_code, timeout=10, phrase_limit=30):
        """Listen to microphone and convert speech to text"""
        try:
            print("🔴 Listening... (speak your question, up to 30 seconds)")
            with self.microphone as source:
                audio = self.recognizer.listen(
                    source, 
                    timeout=timeout, 
                    phrase_time_limit=phrase_limit
                )
            
            print("🔄 Processing speech...")
            text = self.recognizer.recognize_google(audio, language=language_code)
            return {"success": True, "text": text}
            
        except sr.WaitTimeoutError:
            return {"success": False, "error": "No speech detected (timeout)"}
        except sr.UnknownValueError:
            return {"success": False, "error": "Could not understand speech"}
        except sr.RequestError as e:
            return {"success": False, "error": f"Google STT error: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def run_test_session(self):
        """Main test session loop"""
        print("\n" + "="*60)
        print("🎤 RAG Service + Speech-to-Text Test")
        print("="*60)
        
        # Test RAG service connection first
        if not self.test_rag_connection():
            return
        
        print(f"\n📋 Available languages:")
        for i, (name, code) in enumerate(self.languages.items(), 1):
            print(f"   {i}. {name} ({code})")
        
        # Language selection
        while True:
            try:
                choice = input(f"\nSelect language (1-{len(self.languages)}) or 'q' to quit: ")
                if choice.lower() == 'q':
                    return
                
                lang_index = int(choice) - 1
                if 0 <= lang_index < len(self.languages):
                    lang_name, lang_code = list(self.languages.items())[lang_index]
                    break
                else:
                    print(f"Please enter 1-{len(self.languages)}")
            except ValueError:
                print("Please enter a valid number")
        
        print(f"\n🗣️  Selected: {lang_name} ({lang_code})")
        
        # Format selection
        while True:
            format_choice = input("\nResponse format - (w)eb or (v)oice? [w]: ").lower()
            if format_choice in ['', 'w', 'web']:
                response_format = "web"
                break
            elif format_choice in ['v', 'voice']:
                response_format = "voice"
                break
            else:
                print("Please enter 'w' for web or 'v' for voice")
        
        print(f"📱 Response format: {response_format}")
        
        # Query loop
        query_count = 0
        while True:
            print(f"\n{'='*40}")
            print(f"Query #{query_count + 1}")
            print(f"{'='*40}")
            
            user_input = input("Press Enter to speak, 'c' to change language/format, or 'q' to quit: ")
            
            if user_input.lower() == 'q':
                break
            elif user_input.lower() == 'c':
                return self.run_test_session()  # Restart with new selection
            
            # Record and recognize speech
            stt_result = self.listen_and_recognize(lang_code)
            
            if not stt_result["success"]:
                print(f"❌ STT Error: {stt_result['error']}")
                continue
            
            recognized_text = stt_result["text"]
            print(f"🎯 Recognized: '{recognized_text}'")
            
            # Confirm query
            confirm = input("Send this query to RAG service? [Y/n]: ")
            if confirm.lower() in ['n', 'no']:
                continue
            
            # Query RAG service
            start_time = time.time()
            rag_result = self.query_rag_service(recognized_text, response_format)
            query_time = time.time() - start_time
            
            print(f"\n📊 Results:")
            print(f"   Query time: {query_time:.2f}s")
            
            if rag_result["success"]:
                response = rag_result["response"]
                emotion = rag_result["emotion"]
                cache_safe = rag_result["cache_safe"]
                metadata = rag_result["metadata"]
                
                print(f"   Emotion: {emotion}")
                print(f"   Cache safe: {cache_safe}")
                print(f"   Response length: {len(response)} chars")
                
                # Show response
                print(f"\n💬 RAG Response:")
                print("-" * 50)
                print(response)
                print("-" * 50)
                
                # Show query type info if available
                if metadata:
                    query_type = metadata.get("query_type", "unknown")
                    print(f"\n🔍 Query type: {query_type}")
                    if "temporal_detected" in metadata:
                        temporal = metadata["temporal_detected"]
                        print(f"   Temporal query: {temporal}")
                
            else:
                print(f"❌ RAG Error: {rag_result['error']}")
            
            query_count += 1
            
            # Log results
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "query_number": query_count,
                "language": lang_name,
                "language_code": lang_code,
                "response_format": response_format,
                "stt_result": stt_result,
                "rag_result": rag_result,
                "query_time": query_time
            }
            
            # Save to log file
            try:
                with open("rag_stt_test_log.json", "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
            except Exception as e:
                print(f"⚠️  Logging error: {e}")
        
        print(f"\n✅ Test session completed. Total queries: {query_count}")

def main():
    print("🚀 Starting RAG Service STT Integration Test")
    
    # Get RAG service details
    default_host = "localhost"
    default_port = "8000"
    
    print(f"\nRAG Service Configuration:")
    host = input(f"Host [{default_host}]: ") or default_host
    port = input(f"Port [{default_port}]: ") or default_port
    
    try:
        port = int(port)
    except ValueError:
        print("Invalid port number, using default 8000")
        port = 8000
    
    # Create and run tester
    tester = RAGSTTTester(host, port)
    tester.run_test_session()

if __name__ == "__main__":
    main()
