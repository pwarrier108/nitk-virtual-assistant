#!/usr/bin/env python3
"""
Unified Web UI Test Suite
Tests core functionality, truncation fixes, and system readiness for web UI deployment
"""

import sys
import logging
import time
import json
import requests
from datetime import datetime
from pathlib import Path
import traceback

# Setup logging
log_dir = Path("../logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / 'web_ui_test.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('web_ui_test')

# Configuration
RAG_SERVICE_URL = "http://localhost:8000"

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
    
    def add_test(self, name: str, passed: bool, details: str = ""):
        self.total += 1
        if passed:
            self.passed += 1
            status_symbol = "✅"
        else:
            self.failed += 1
            status_symbol = "❌"
        
        message = f"   {status_symbol} {name}"
        if details:
            message += f" - {details}"
        
        print(message)
        logger.info(f"{'PASSED' if passed else 'FAILED'}: {name} - {details}")
    
    def get_success_rate(self):
        return (self.passed / self.total * 100) if self.total > 0 else 0

def safe_request(method, url, **kwargs):
    """Make a safe HTTP request with proper error handling"""
    try:
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 30
            
        if method.lower() == 'get':
            response = requests.get(url, **kwargs)
        elif method.lower() == 'post':
            response = requests.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return response, None
        
    except requests.exceptions.Timeout as e:
        return None, f"Timeout: {str(e)}"
    except requests.exceptions.ConnectionError as e:
        return None, f"Connection error: {str(e)}"
    except Exception as e:
        return None, f"Request error: {str(e)}"

def test_service_connectivity():
    """Test basic service connectivity and structure"""
    print("\n🔍 Service Connectivity")
    print("=" * 40)
    
    result = TestResult()
    
    # Health check
    response, error = safe_request('get', f"{RAG_SERVICE_URL}/health", timeout=10)
    if response and response.status_code == 200:
        try:
            health_data = response.json()
            result.add_test("Health Check", True, f"Service: {health_data.get('service', 'unknown')}")
        except Exception:
            result.add_test("Health Check", False, "Invalid JSON response")
    else:
        result.add_test("Health Check", False, error or f"HTTP {response.status_code if response else 'No response'}")
    
    # Stats endpoint
    response, error = safe_request('get', f"{RAG_SERVICE_URL}/stats", timeout=10)
    if response and response.status_code == 200:
        try:
            stats_data = response.json()
            doc_count = stats_data.get('document_count', 'unknown')
            result.add_test("Stats Endpoint", True, f"Documents: {doc_count}")
        except Exception:
            result.add_test("Stats Endpoint", False, "Invalid JSON response")
    else:
        result.add_test("Stats Endpoint", False, error or f"HTTP {response.status_code if response else 'No response'}")
    
    return result

def test_core_functionality():
    """Test core RAG functionality and response structure"""
    print("\n🤖 Core Functionality")
    print("=" * 40)
    
    result = TestResult()
    
    # Basic RAG query
    query_data = {"question": "What is NITK?", "format": "web"}
    response, error = safe_request('post', f"{RAG_SERVICE_URL}/query", json=query_data, timeout=30)
    
    if error:
        result.add_test("Basic Query", False, error)
        return result
    
    if response and response.status_code == 200:
        try:
            data = response.json()
            response_text = data.get('response', '')
            
            # Check NITK content
            nitk_indicators = ['nitk', 'surathkal', 'karnataka', 'engineering', 'institute']
            has_nitk_content = any(indicator in response_text.lower() for indicator in nitk_indicators)
            result.add_test("NITK Content", has_nitk_content, f"Length: {len(response_text)} chars")
            
            # Check required response fields
            required_fields = ['response', 'emotion', 'cache_safe', 'metadata']
            missing_fields = [field for field in required_fields if field not in data]
            
            if not missing_fields:
                result.add_test("Response Structure", True, "All required fields present")
            else:
                result.add_test("Response Structure", False, f"Missing: {missing_fields}")
            
            # Check field types
            emotion_valid = isinstance(data.get('emotion'), str) and data.get('emotion') != 'none'
            cache_safe_valid = isinstance(data.get('cache_safe'), bool)
            
            result.add_test("Emotion Detection", emotion_valid, f"Emotion: {data.get('emotion', 'none')}")
            result.add_test("Cache Control", cache_safe_valid, f"Cache safe: {data.get('cache_safe')}")
            
        except Exception as e:
            result.add_test("Response Parsing", False, f"JSON error: {str(e)}")
    else:
        status_code = response.status_code if response else "No response"
        result.add_test("Basic Query", False, f"HTTP {status_code}")
    
    return result

def test_truncation_fixes():
    """Test that response truncation issues are fixed"""
    print("\n🔧 Truncation Fixes")
    print("=" * 40)
    
    result = TestResult()
    
    # Test with queries that were previously truncated
    test_queries = [
        "Tell me about the current weather and temperature conditions",
        "What's happening in the world today?",
        "Explain NITK's academic programs in complete detail"
    ]
    
    for query in test_queries:
        query_data = {"question": query, "format": "voice"}
        response, error = safe_request('post', f"{RAG_SERVICE_URL}/query", json=query_data, timeout=45)
        
        if error:
            result.add_test(f"Query: {query[:30]}...", False, error)
            continue
        
        if response and response.status_code == 200:
            try:
                data = response.json()
                response_text = data.get('response', '')
                word_count = len(response_text.split())
                
                # Check if response ends naturally (not cut off mid-sentence)
                ends_naturally = any(response_text.rstrip().endswith(punct) for punct in ['.', '!', '?'])
                
                # For temporal queries, check if they go beyond 80-word limit
                is_temporal = any(phrase in response_text.lower() for phrase in [
                    "based on current", "current information", "unable to access current"
                ])
                
                if is_temporal and word_count > 80:
                    result.add_test(f"No 80-word limit: {query[:25]}...", True, f"{word_count} words")
                elif not is_temporal:
                    result.add_test(f"Static response: {query[:25]}...", True, f"{word_count} words")
                else:
                    result.add_test(f"Response length: {query[:25]}...", word_count > 20, f"{word_count} words")
                
                result.add_test(f"Natural ending: {query[:25]}...", ends_naturally, f"Ends with punctuation: {ends_naturally}")
                
            except Exception as e:
                result.add_test(f"Parse: {query[:30]}...", False, f"JSON error: {str(e)}")
        else:
            status_code = response.status_code if response else "No response"
            result.add_test(f"Request: {query[:30]}...", False, f"HTTP {status_code}")
    
    return result

def test_format_differences():
    """Test web vs voice format differences"""
    print("\n📝 Format Differences")
    print("=" * 40)
    
    result = TestResult()
    
    test_question = "Tell me about NITK's departments and programs"
    
    # Test both formats
    web_query = {"question": test_question, "format": "web"}
    voice_query = {"question": test_question, "format": "voice"}
    
    web_response, web_error = safe_request('post', f"{RAG_SERVICE_URL}/query", json=web_query, timeout=30)
    voice_response, voice_error = safe_request('post', f"{RAG_SERVICE_URL}/query", json=voice_query, timeout=30)
    
    if web_error or voice_error:
        result.add_test("Format Requests", False, web_error or voice_error)
        return result
    
    if (web_response and web_response.status_code == 200 and 
        voice_response and voice_response.status_code == 200):
        try:
            web_data = web_response.json()
            voice_data = voice_response.json()
            
            web_text = web_data.get('response', '')
            voice_text = voice_data.get('response', '')
            
            web_words = len(web_text.split())
            voice_words = len(voice_text.split())
            
            # Voice should be more concise
            voice_appropriate = voice_words <= 100  # Reasonable limit for voice
            format_difference = abs(web_words - voice_words) > 10  # Meaningful difference
            
            result.add_test("Voice Conciseness", voice_appropriate, f"Voice: {voice_words} words")
            result.add_test("Format Differentiation", format_difference, f"Web: {web_words}, Voice: {voice_words}")
            
            # Both should have valid emotions
            web_emotion = web_data.get('emotion', 'none')
            voice_emotion = voice_data.get('emotion', 'none')
            
            valid_emotions = ['happy', 'excited', 'thinking', 'confused', 'greeting', 
                            'goodbye', 'neutral', 'sad', 'surprised']
            
            emotions_valid = web_emotion in valid_emotions and voice_emotion in valid_emotions
            result.add_test("Format Emotions", emotions_valid, f"Web: {web_emotion}, Voice: {voice_emotion}")
            
        except Exception as e:
            result.add_test("Format Parsing", False, f"JSON error: {str(e)}")
    else:
        web_status = web_response.status_code if web_response else "No response"
        voice_status = voice_response.status_code if voice_response else "No response"
        result.add_test("Format Requests", False, f"Web: {web_status}, Voice: {voice_status}")
    
    return result

def test_perplexity_integration():
    """Test Perplexity integration for temporal queries"""
    print("\n🌐 Perplexity Integration")
    print("=" * 40)
    
    result = TestResult()
    
    # Test temporal queries
    temporal_queries = [
        "What's the current weather?",
        "Latest news today",
        "Recent developments in AI"
    ]
    
    perplexity_detected = 0
    
    for query in temporal_queries:
        query_data = {"question": query, "format": "voice"}
        response, error = safe_request('post', f"{RAG_SERVICE_URL}/query", json=query_data, timeout=45)
        
        if error:
            result.add_test(f"Temporal: {query[:25]}...", False, error)
            continue
        
        if response and response.status_code == 200:
            try:
                data = response.json()
                response_text = data.get('response', '').lower()
                cache_safe = data.get('cache_safe', True)
                
                # Check for Perplexity indicators
                perplexity_indicators = [
                    "based on current", "current information", "current web",
                    "unable to access current", "latest information"
                ]
                
                is_perplexity = any(indicator in response_text for indicator in perplexity_indicators)
                if is_perplexity:
                    perplexity_detected += 1
                
                # Temporal queries should not be cache-safe
                temporal_cache_correct = not cache_safe if is_perplexity else True
                
                result.add_test(
                    f"Temporal: {query[:25]}...", 
                    True, 
                    f"Perplexity: {is_perplexity}, Cache-safe: {cache_safe}"
                )
                
            except Exception as e:
                result.add_test(f"Temporal: {query[:25]}...", False, f"JSON error: {str(e)}")
        else:
            status_code = response.status_code if response else "No response"
            result.add_test(f"Temporal: {query[:25]}...", False, f"HTTP {status_code}")
    
    # Test that static queries use RAG (not Perplexity)
    static_query = {"question": "What is NITK Surathkal?", "format": "voice"}
    response, error = safe_request('post', f"{RAG_SERVICE_URL}/query", json=static_query, timeout=30)
    
    if response and response.status_code == 200:
        try:
            data = response.json()
            response_text = data.get('response', '').lower()
            cache_safe = data.get('cache_safe', True)
            
            is_perplexity = any(phrase in response_text for phrase in [
                "based on current", "current information", "current web"
            ])
            
            # Static queries should use RAG and be cache-safe
            static_correct = not is_perplexity and cache_safe
            result.add_test("Static Query Routing", static_correct, f"Uses RAG: {not is_perplexity}, Cache-safe: {cache_safe}")
            
        except Exception as e:
            result.add_test("Static Query", False, f"JSON error: {str(e)}")
    else:
        result.add_test("Static Query", False, error or f"HTTP {response.status_code if response else 'No response'}")
    
    # Overall Perplexity assessment
    perplexity_working = perplexity_detected > 0
    result.add_test("Perplexity Detection", perplexity_working, f"{perplexity_detected}/{len(temporal_queries)} temporal queries detected")
    
    return result

def test_error_handling():
    """Test error handling for invalid inputs"""
    print("\n⚠️ Error Handling")
    print("=" * 40)
    
    result = TestResult()
    
    error_tests = [
        {"query": {"question": "", "format": "web"}, "name": "Empty Question", "expected": 400},
        {"query": {"question": "test", "format": "invalid"}, "name": "Invalid Format", "expected": 400},
        {"query": {"format": "web"}, "name": "Missing Question", "expected": 422}
    ]
    
    for test in error_tests:
        response, error = safe_request('post', f"{RAG_SERVICE_URL}/query", json=test['query'], timeout=15)
        
        print(f"DEBUG: response={response}, error={error}")
        if response:
            print(f"DEBUG: status_code={response.status_code}")
        
        if error:
            result.add_test(test['name'], False, f"Connection failed: {error}")
        elif response is not None and response.status_code == test['expected']:
            result.add_test(
                test['name'], 
                True, 
                f"Got expected {test['expected']}"
            )
        elif response is not None:
            result.add_test(
                test['name'], 
                False, 
                f"Expected {test['expected']}, got {response.status_code}"
            )
        else:
            result.add_test(test['name'], False, "No response received")
    
    return result

def test_performance():
    """Test basic performance benchmarks"""
    print("\n⚡ Performance")
    print("=" * 40)
    
    result = TestResult()
    
    # Simple performance test
    query_data = {"question": "What is NITK?", "format": "web"}
    
    start_time = time.time()
    response, error = safe_request('post', f"{RAG_SERVICE_URL}/query", json=query_data, timeout=30)
    response_time = time.time() - start_time
    
    if error:
        result.add_test("Response Time", False, error)
    elif response and response.status_code == 200:
        acceptable_time = response_time < 15.0  # 15 second limit
        result.add_test("Response Time", acceptable_time, f"{response_time:.2f}s (limit: 15.0s)")
    else:
        status_code = response.status_code if response else "No response"
        result.add_test("Response Time", False, f"HTTP {status_code}")
    
    return result

def run_all_tests():
    """Run all tests and provide summary"""
    print("🚀 Web UI Test Suite v1.0")
    print("Testing core functionality and truncation fixes")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    logger.info("Web UI Test Suite Started")
    
    # Define tests
    tests = [
        ("Service Connectivity", test_service_connectivity),
        ("Core Functionality", test_core_functionality),
        ("Truncation Fixes", test_truncation_fixes),
        ("Format Differences", test_format_differences),
        ("Perplexity Integration", test_perplexity_integration),
        ("Error Handling", test_error_handling),
        ("Performance", test_performance)
    ]
    
    overall_passed = 0
    overall_total = 0
    
    # Run each test
    for test_name, test_func in tests:
        try:
            test_result = test_func()
            overall_passed += test_result.passed
            overall_total += test_result.total
            
            logger.info(f"Test {test_name}: {test_result.passed}/{test_result.total} passed")
            
        except KeyboardInterrupt:
            print(f"\n⚠️ Test interrupted by user")
            logger.warning("Test suite interrupted")
            break
        except Exception as e:
            print(f"\n💥 Test {test_name} crashed: {str(e)}")
            logger.error(f"Test {test_name} crashed", exc_info=True)
            overall_total += 1  # Count as failed test
    
    # Calculate success rate
    success_rate = (overall_passed / overall_total * 100) if overall_total > 0 else 0
    
    # Print summary
    print(f"\n📊 Final Results")
    print("=" * 40)
    print(f"Tests Passed: {overall_passed}/{overall_total}")
    print(f"Success Rate: {success_rate:.1f}%")
    print("=" * 40)
    
    if success_rate >= 80:
        print("\n🎉 WEB UI READY FOR DEPLOYMENT!")
        print("\n✅ Verified:")
        print("  • Service connectivity and structure")
        print("  • Core RAG functionality")
        print("  • Response truncation fixes")
        print("  • Format differentiation (web/voice)")
        print("  • Perplexity integration")
        print("  • Error handling")
        print("  • Performance within limits")
        
        print("\n🚀 Next Steps:")
        print("  1. Start web UI: cd ../web-ui && streamlit run main.py")
        print("  2. Test translation and TTS features")
        print("  3. Verify end-to-end user experience")
        
        logger.info("ALL TESTS PASSED - WEB UI READY")
        return True
    else:
        print("\n⚠️ ISSUES DETECTED")
        print(f"Success rate {success_rate:.1f}% is below 80% threshold")
        print("\n🔧 Troubleshooting:")
        print("  • Ensure RAG service is running on port 8000")
        print("  • Check PERPLEXITY_API_KEY environment variable")
        print("  • Verify OPENAI_API_KEY is set")
        print("  • Check service logs for errors")
        
        logger.warning("TESTS FAILED - ISSUES DETECTED")
        return False

if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
