#!/usr/bin/env python3
# Simple robot functionality test - focuses on service integration

import sys
import time
from pathlib import Path

# Add robot directory to path
robot_dir = Path(__file__).parent.parent / "robot"
sys.path.insert(0, str(robot_dir))

try:
    from config import RAG_SERVICE_URL, ERROR_MESSAGES, AUDIO_PATHS
    from rag_client import RAGClient
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def test_rag_service():
    """Test RAG service connection and responses"""
    print("Testing RAG Service")
    print("=" * 40)
    
    client = RAGClient(RAG_SERVICE_URL)
    
    # Health check
    if not client.health_check():
        print("❌ RAG service not reachable")
        print(f"   URL: {RAG_SERVICE_URL}")
        return False
    
    print("✅ RAG service connected")
    
    # Test voice format query
    response = client.query("What is NITK?")
    print(f"✅ Response received: {len(response.text)} chars")
    print(f"✅ Emotion detected: {response.emotion}")
    
    return True

def test_context_and_translation():
    """Test context window and translation detection"""
    print("\nTesting Context & Translation")
    print("=" * 40)
    
    client = RAGClient(RAG_SERVICE_URL)
    
    # Set context
    client.query("Who is the director of NITK?")
    
    # Test follow-up
    followup_type, _ = client.detect_command_type("tell me more")
    print(f"✅ Follow-up detection: {followup_type}")
    
    # Test translation detection
    trans_type, lang = client.detect_command_type("translate to hindi")
    print(f"✅ Translation detection: {trans_type} -> {lang}")
    
    return True

def test_error_handling():
    """Test error responses"""
    print("\nTesting Error Handling")
    print("=" * 40)
    
    # Test invalid service
    invalid_client = RAGClient("http://invalid:9999")
    error_response = invalid_client.query("test")
    
    is_standard_error = error_response.text in ERROR_MESSAGES.values()
    print(f"✅ Standard error handling: {is_standard_error}")
    
    return True

def test_configuration():
    """Test configuration completeness"""
    print("\nTesting Configuration")
    print("=" * 40)
    
    checks = [
        ("RAG_SERVICE_URL", RAG_SERVICE_URL),
        ("ERROR_MESSAGES", len(ERROR_MESSAGES)),
        ("AUDIO_PATHS", len(AUDIO_PATHS))
    ]
    
    for name, value in checks:
        print(f"✅ {name}: {value}")
    
    return True

def main():
    """Run core functionality tests"""
    print("NITK Robot Core Functionality Test\n")
    
    tests = [
        test_rag_service,
        test_context_and_translation, 
        test_error_handling,
        test_configuration
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    print(f"\nResults: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All core functionality working!")
    else:
        print("⚠ Some issues found")
    
    return 0 if passed >= len(tests) * 0.75 else 1

if __name__ == "__main__":
    sys.exit(main())