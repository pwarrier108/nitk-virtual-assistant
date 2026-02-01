# Standard library imports
import json
import logging
import os
import re
from datetime import datetime
from typing import Generator, Optional

# Third-party imports
import pytz
import requests

# Local application imports
from .config import Config

logger = logging.getLogger(__name__)

class PerplexityClient:
    """Client for Perplexity API to handle current information queries."""
    
    def __init__(self, config: Config):
        self.config = config
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        self.base_url = "https://api.perplexity.ai/chat/completions"
        
        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not found in environment variables")
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        })
    
    def is_available(self) -> bool:
        """Check if Perplexity API is available."""
        return bool(self.api_key and self.config.perplexity_enabled)
    
    def query(self, question: str, response_format: str = "web") -> Generator[str, None, None]:
        """
        Query Perplexity API for current information.
        
        Args:
            question: User's question
            response_format: "web" for detailed responses, "voice" for brief responses
            
        Yields:
            Response chunks as strings
        """
        if not self.is_available():
            raise RuntimeError("Perplexity API not available")
        
        try:
            # Format system prompt based on response format
            system_prompt = self._get_system_prompt(response_format)
            
            # Prepare request payload with format-specific limits
            max_tokens = 200 if response_format == "voice" else 800
            
            payload = {
                "model": self.config.perplexity_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                "stream": True,
                "temperature": 0.3,  # Lower temperature for factual responses
                "max_tokens": max_tokens
            }
            
            logger.info(f"Querying Perplexity for {response_format} format: {question[:50]}...")
            
            response = self.session.post(
                self.base_url,
                json=payload,
                stream=True,
                timeout=self.config.perplexity_timeout
            )
            
            if response.status_code != 200:
                error_msg = f"Perplexity API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Stream the response
            for chunk in self._process_stream(response):
                yield chunk
                
        except requests.exceptions.Timeout:
            error_msg = f"Perplexity API timeout after {self.config.perplexity_timeout}s"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Perplexity API request failed: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected Perplexity error: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    def _get_system_prompt(self, response_format: str) -> str:
        """Get appropriate system prompt based on response format."""
        
        # Get current time in multiple relevant timezones
        utc_now = datetime.now(pytz.UTC)
        india_tz = pytz.timezone('Asia/Kolkata')
        us_eastern_tz = pytz.timezone('US/Eastern')
        us_pacific_tz = pytz.timezone('US/Pacific')
        
        # Format times for different zones
        utc_time = utc_now.strftime('%B %d, %Y at %I:%M %p UTC')
        india_time = utc_now.astimezone(india_tz).strftime('%B %d, %Y at %I:%M %p IST')
        us_eastern_time = utc_now.astimezone(us_eastern_tz).strftime('%B %d, %Y at %I:%M %p EST/EDT')
        us_pacific_time = utc_now.astimezone(us_pacific_tz).strftime('%B %d, %Y at %I:%M %p PST/PDT')
        
        base_prompt = f"""You are a helpful assistant providing current information. 

IMPORTANT TIMEZONE CONTEXT:
- Current UTC time: {utc_time}
- Current time in India: {india_time}
- Current time in US Eastern: {us_eastern_time}
- Current time in US Pacific: {us_pacific_time}

GUIDELINES:
- Always specify the timezone when providing timestamps
- For location-specific queries, use the appropriate local timezone
- When uncertain about user location, provide times in UTC and mention major timezones
- Always cite your sources and indicate when information is current/recent"""
        
        if response_format == "voice":
            return f"""{base_prompt}

RESPONSE FORMAT FOR VOICE:
- Keep responses brief and conversational (40-60 words max)
- Use simple, complete sentences suitable for text-to-speech
- Start with "Based on current information..." 
- Provide only the most essential current facts
- Include relevant timestamp with appropriate timezone when discussing current conditions
- For location-specific queries, use the local timezone for that location
- End naturally with complete sentences - do not cut off mid-thought
- Always end with proper punctuation (. ! ?)"""
        
        else:  # web format
            return f"""{base_prompt}

RESPONSE FORMAT FOR WEB:
- Provide structured, informative responses (150-300 words)
- Start with "Based on current web information..."
- Include key current facts, dates, and context with proper timezones
- For location-specific queries, use the appropriate local timezone
- Use bullet points for lists when helpful
- Cite sources when possible
- Be detailed but concise for web reading"""
    
    def _process_stream(self, response) -> Generator[str, None, None]:
        """Process streaming response from Perplexity API."""
        full_response = ""
        
        # Collect full response first
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                
                # Skip non-data lines
                if not line_str.startswith('data: '):
                    continue
                
                # Handle end of stream
                if line_str == 'data: [DONE]':
                    break
                
                try:
                    # Parse JSON data
                    json_str = line_str[6:]  # Remove 'data: ' prefix
                    chunk_data = json.loads(json_str)
                    
                    # Extract content from chunk
                    if 'choices' in chunk_data and chunk_data['choices']:
                        choice = chunk_data['choices'][0]
                        if 'delta' in choice and 'content' in choice['delta']:
                            content = choice['delta']['content']
                            if content:
                                full_response += content
                                
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse Perplexity stream chunk: {json_str[:100]}...")
                    continue
                except KeyError as e:
                    logger.warning(f"Unexpected Perplexity response structure: {e}")
                    continue
        
        # Clean up and ensure proper ending
        full_response = re.sub(r'\[\d+(?:[-,]\d+)*\]', '', full_response)
        full_response = full_response.strip()
        
        # Ensure response ends with punctuation
        if full_response and not full_response[-1] in '.!?':
            full_response += '.'
        
        # Yield word by word
        words = full_response.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
    
    def test_connection(self) -> bool:
        """Test if we can connect to Perplexity API."""
        if not self.is_available():
            return False
            
        try:
            # Simple test query
            payload = {
                "model": self.config.perplexity_model,
                "messages": [
                    {"role": "user", "content": "Hello"}
                ],
                "stream": False,
                "max_tokens": 10
            }
            
            response = self.session.post(
                self.base_url,
                json=payload,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Perplexity connection test failed: {str(e)}")
            return False