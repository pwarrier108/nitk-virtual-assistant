#!/usr/bin/env python3
# encoding: utf-8
# Q&A Script Generator for Robot Video Recording
# Generates realistic NITK Q&A with voice-optimized responses

import json
import requests
import time
from datetime import datetime

class QAScriptGenerator:
    """Generates Q&A script for robot video recording"""
    
    def __init__(self, server_url="http://localhost:8000"):
        self.server_url = server_url
        self.script_data = {
            "qa_pairs": []
        }
        
    def test_server_connection(self):
        """Test if RAG server is available"""
        try:
            response = requests.get(f"{self.server_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def query_server(self, question, format_type="voice"):
        """Query the RAG server and return response"""
        try:
            response = requests.post(
                f"{self.server_url}/query",
                json={"question": question, "format": format_type},
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("response", ""), data.get("emotion", "neutral")
            else:
                print(f"Server error {response.status_code}: {response.text}")
                return None, None
        except Exception as e:
            print(f"Query failed: {e}")
            return None, None
    
    def create_greeting(self):
        """Greeting handled by video script - not needed"""
        pass
    
    def create_goodbye(self):
        """Goodbye handled by video script - not needed"""
        pass
    
    def translate_text(self, text, target_language):
        """Simple translation for demonstration (you can enhance this)"""
        # For demo purposes, providing sample translations
        # In production, you'd use proper translation service
        
        if target_language.lower() == "hindi":
            # Sample Hindi translation for director info
            if "director" in text.lower() or "ravi" in text.lower():
                return "प्रोफेसर बी. रवि NITK के वर्तमान निदेशक हैं। वे इंजीनियरिंग शिक्षा में उत्कृष्टता के लिए संस्थान का नेतृत्व कर रहे हैं।"
            else:
                return "यह NITK के बारे में जानकारी है।"
                
        elif target_language.lower() == "kannada":
            # Sample Kannada translation for culture info
            if "culture" in text.lower() or "karnataka" in text.lower():
                return "ಕರ್ನಾಟಕ ಸಂಸ್ಕೃತಿ ಬಹಳ ಸಮೃದ್ಧ ಮತ್ತು ವೈವಿಧ್ಯಮಯವಾಗಿದೆ. ಇಲ್ಲಿ ಸಂಗೀತ, ನೃತ್ಯ ಮತ್ತು ಕಲೆಗಳು ಪ್ರವರ್ಧಮಾನವಾಗಿವೆ."
            else:
                return "ಇದು NITK ಬಗ್ಗೆ ಮಾಹಿತಿಯಾಗಿದೆ."
        
        return text  # Fallback
    
    def create_hardcoded_student_response(self):
        """Create hardcoded proud response about students"""
        return {
            "question": "What do you think about the students of NITK?",
            "answer": "The students of NITK are absolutely exceptional! They're brilliant minds who consistently excel in academics, research, and innovation. I'm really proud of their achievements in engineering and technology.",
            "emotion": "chest"  # Custom emotion for proud chest gesture
        }
    
    def create_temperature_response(self):
        """Query server for current temperature"""
        temp_response, emotion = self.query_server("What is the current temperature at NITK?", "voice")
        if temp_response:
            return {
                "question": "What is the current temperature at NITK?",
                "answer": temp_response,
                "emotion": emotion or "neutral"
            }
        else:
            # Fallback if server fails
            return {
                "question": "What is the current temperature at NITK?",
                "answer": "I'm sorry, I can't get the current temperature right now. Please try again later.",
                "emotion": "confused"
            }
    
    def generate_script(self):
        """Generate the 8 Q&A pairs only"""
        print("🤖 Generating 8 Q&A Pairs for Robot Video...")
        print(f"📡 Server: {self.server_url}")
        
        # Test server connection
        if not self.test_server_connection():
            print("❌ Cannot connect to RAG server. Please ensure it's running on localhost:8000")
            return None
        
        print("✅ Server connection successful")
        
        # Storage for translation context
        director_response = ""
        culture_response = ""
        
        # Question 1: Who is the director of NITK
        print("\n📝 Generating Q1: Director of NITK...")
        director_response, emotion = self.query_server("Who is the current director of NITK?", "voice")
        if director_response:
            self.script_data["qa_pairs"].append({
                "id": 1,
                "question": "Who is the director of NITK?",
                "answer": director_response,
                "emotion": emotion or "explaining"
            })
            print(f"✅ Q1 Complete - Emotion: {emotion}")
        
        # Question 2: Tell me more details (followup)
        print("\n📝 Generating Q2: Follow-up about director...")
        followup_response, emotion = self.query_server("Tell me more details about the director of NITK", "voice")
        if followup_response:
            self.script_data["qa_pairs"].append({
                "id": 2,
                "question": "Tell me more details",
                "answer": followup_response,
                "emotion": emotion or "explaining"
            })
            print(f"✅ Q2 Complete - Emotion: {emotion}")
        
        # Question 3: Translate to Hindi
        print("\n📝 Generating Q3: Hindi translation...")
        if director_response:
            hindi_translation = self.translate_text(director_response, "Hindi")
            self.script_data["qa_pairs"].append({
                "id": 3,
                "question": "Translate to Hindi",
                "answer": hindi_translation,
                "emotion": "neutral"
            })
            print("✅ Q3 Complete - Hindi translation added")
        
        # Question 4: Students of NITK (hardcoded proud response)
        print("\n📝 Generating Q4: Students (hardcoded proud response)...")
        student_qa = self.create_hardcoded_student_response()
        self.script_data["qa_pairs"].append({
            "id": 4,
            "question": student_qa["question"],
            "answer": student_qa["answer"],
            "emotion": student_qa["emotion"]
        })
        print("✅ Q4 Complete - Hardcoded proud response with chest emotion")
        
        # Question 5: Current temperature (server query)
        print("\n📝 Generating Q5: Current temperature (server query)...")
        temp_qa = self.create_temperature_response()
        self.script_data["qa_pairs"].append({
            "id": 5,
            "question": temp_qa["question"],
            "answer": temp_qa["answer"],
            "emotion": temp_qa["emotion"]
        })
        print(f"✅ Q5 Complete - Server response with emotion: {temp_qa['emotion']}")
        
        # Question 6: Beach activities
        print("\n📝 Generating Q6: Beach activities...")
        beach_response, emotion = self.query_server("Tell me about beach activities near NITK Surathkal", "voice")
        if beach_response:
            self.script_data["qa_pairs"].append({
                "id": 6,
                "question": "Tell me about beach activities",
                "answer": beach_response,
                "emotion": emotion or "excited"
            })
            print(f"✅ Q6 Complete - Emotion: {emotion}")
        
        # Question 7: Kannada culture at NITK
        print("\n📝 Generating Q7: Kannada culture at NITK...")
        culture_response, emotion = self.query_server("Tell me about Kannada culture at NITK", "voice")
        if culture_response:
            self.script_data["qa_pairs"].append({
                "id": 7,
                "question": "Tell me about Kannada culture at NITK",
                "answer": culture_response,
                "emotion": emotion or "explaining"
            })
            print(f"✅ Q7 Complete - Emotion: {emotion}")
        
        # Question 8: Translate to Kannada
        print("\n📝 Generating Q8: Kannada translation...")
        if culture_response:
            kannada_translation = self.translate_text(culture_response, "Kannada")
            self.script_data["qa_pairs"].append({
                "id": 8,
                "question": "Translate to Kannada",
                "answer": kannada_translation,
                "emotion": "neutral"
            })
            print("✅ Q8 Complete - Kannada translation added")
        
        return self.script_data
    
    def save_script(self, filename="video_script.json"):
        """Save the generated script to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.script_data, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Script saved to: {filename}")
            return True
        except Exception as e:
            print(f"❌ Error saving script: {e}")
            return False
    
    def preview_script(self):
        """Print a preview of the generated Q&A pairs"""
        print("\n" + "="*60)
        print("📋 GENERATED Q&A PAIRS PREVIEW")
        print("="*60)
        
        # Q&A Pairs only
        for qa in self.script_data.get("qa_pairs", []):
            print(f"\n❓ Q{qa.get('id', '?')}: {qa.get('question', 'N/A')}")
            answer = qa.get('answer', 'N/A')
            print(f"💬 A{qa.get('id', '?')}: {answer[:80]}{'...' if len(answer) > 80 else ''}")
            print(f"   Emotion: {qa.get('emotion', 'N/A')}")
            print(f"   Words: {len(answer.split())} words")
        
        print("="*60)
        print(f"📊 Total Q&A pairs: {len(self.script_data.get('qa_pairs', []))}")
        print("🎬 Ready for video recording!")
        print("ℹ️  Note: Greeting and goodbye handled by video script")

def main():
    """Main function to generate the script"""
    print("🤖 NITK Robot Q&A Script Generator")
    print("="*50)
    
    # Get server URL
    server_url = input("Enter RAG server URL (default: http://localhost:8000): ").strip()
    if not server_url:
        server_url = "http://localhost:8000"
    
    # Create generator
    generator = QAScriptGenerator(server_url)
    
    # Generate script
    print(f"\n🚀 Starting script generation...")
    script_data = generator.generate_script()
    
    if script_data:
        # Preview the script
        generator.preview_script()
        
        # Save to file
        filename = input("\nEnter filename for script (default: video_script.json): ").strip()
        if not filename:
            filename = "video_script.json"
        
        if generator.save_script(filename):
            print(f"\n✅ Q&A pairs generation complete!")
            print(f"📁 File: {filename}")
            print(f"🎬 Ready to use with robot video script!")
            print(f"ℹ️  Contains 8 Q&A pairs (greeting/goodbye handled separately)")
            
            # Offer to show JSON content
            show_json = input("\nShow raw JSON content? (y/n): ").strip().lower()
            if show_json == 'y':
                print("\n📄 JSON Content:")
                print("-" * 40)
                print(json.dumps(script_data, indent=2, ensure_ascii=False))
        else:
            print("❌ Failed to save script")
    else:
        print("❌ Script generation failed")

if __name__ == "__main__":
    main()
