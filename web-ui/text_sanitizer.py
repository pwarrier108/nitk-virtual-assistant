import re

def sanitize_for_tts(text: str) -> str:
    """
    Clean text for better TTS output by removing markdown formatting
    and translation artifacts.
    
    Args:
        text: Raw text that may contain markdown formatting and translation artifacts
        
    Returns:
        Cleaned text suitable for text-to-speech
    """
    if not text or not text.strip():
        return text
    
    # Remove markdown formatting (handles original and translation artifacts)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # **bold** → bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # *italic* → italic
    text = re.sub(r'`(.*?)`', r'\1', text)        # `code` → code
    
    # Remove headers and leaked markdown symbols
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)  # ### Header → Header
    text = re.sub(r'#+\s+', '', text)  # Handle ### in middle of text
    
    # Clean bullet points (keep the text)
    text = re.sub(r'^[-*•]\s*', '', text, flags=re.MULTILINE)  # - item → item
    text = re.sub(r'^\d+\.\s*', '', text, flags=re.MULTILINE)  # 1. item → item
    
    # Remove stray asterisks that didn't match pairs
    text = re.sub(r'\*+', '', text)  # Remove any remaining asterisks
    
    # Remove stray hash symbols
    text = re.sub(r'#+', '', text)   # Remove any remaining hashes
    
    # Remove links but keep text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # [text](url) → text
    text = re.sub(r'http[s]?://\S+', '', text)  # Remove standalone URLs
    
    # Basic symbol expansion for common cases
    text = re.sub(r'&', ' and ', text)  # & → and
    text = re.sub(r'%', ' percent', text)  # % → percent
    
    # Clean whitespace
    text = re.sub(r'\n+', ' ', text)      # Multiple newlines → single space
    text = re.sub(r'\s+', ' ', text)      # Multiple spaces → single space
    text = text.strip()
    
    return text

