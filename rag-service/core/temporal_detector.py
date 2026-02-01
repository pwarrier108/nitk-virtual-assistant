# Standard library imports
import re
from datetime import datetime
from typing import List

# Local application imports
from .config import Config

class TemporalDetector:
    """Detects queries that need current/recent information beyond knowledge base."""
    
    def __init__(self, config: Config):
        self.config = config
        self.current_year = datetime.now().year
        
        # Compile patterns for efficiency
        self.temporal_pattern = self._build_temporal_pattern()
        self.year_pattern = re.compile(r'\b(20\d{2})\b')  # Match years like 2023, 2024, etc.
        
    def _build_temporal_pattern(self) -> re.Pattern:
        """Build combined regex pattern for temporal keywords."""
        all_keywords = (
            self.config.temporal_keywords + 
            self.config.status_keywords + 
            self.config.relative_time_keywords
        )
        # Create word boundary pattern for all keywords
        pattern = r'\b(?:' + '|'.join(re.escape(keyword) for keyword in all_keywords) + r')\b'
        return re.compile(pattern, re.IGNORECASE)
    
    def needs_current_info(self, query: str) -> bool:
        """
        Determine if query needs current information.
        
        Args:
            query: User's question
            
        Returns:
            True if query likely needs current/recent information
        """
        query_lower = query.lower().strip()
        
        # Check for temporal keywords
        if self._has_temporal_keywords(query_lower):
            return True
            
        # Check for recent years (current year ± range)
        if self._has_recent_years(query):
            return True
            
        return False
    
    def _has_temporal_keywords(self, query: str) -> bool:
        """Check if query contains temporal indicator keywords."""
        return bool(self.temporal_pattern.search(query))
    
    def _has_recent_years(self, query: str) -> bool:
        """Check if query mentions years within current range."""
        years = self.year_pattern.findall(query)
        if not years:
            return False
            
        current_range_start = self.current_year - self.config.current_year_range
        current_range_end = self.current_year + self.config.current_year_range
        
        for year_str in years:
            year = int(year_str)
            if current_range_start <= year <= current_range_end:
                return True
                
        return False
    
    def get_detection_info(self, query: str) -> dict:
        """
        Get detailed information about temporal detection for debugging.
        
        Args:
            query: User's question
            
        Returns:
            Dictionary with detection details
        """
        query_lower = query.lower().strip()
        
        # Find temporal keywords
        temporal_matches = self.temporal_pattern.findall(query_lower)
        
        # Find years and check if recent
        year_matches = self.year_pattern.findall(query)
        recent_years = []
        
        if year_matches:
            current_range_start = self.current_year - self.config.current_year_range
            current_range_end = self.current_year + self.config.current_year_range
            
            for year_str in year_matches:
                year = int(year_str)
                if current_range_start <= year <= current_range_end:
                    recent_years.append(year)
        
        needs_current = self.needs_current_info(query)
        
        return {
            "needs_current_info": needs_current,
            "temporal_keywords_found": temporal_matches,
            "years_found": [int(y) for y in year_matches],
            "recent_years_found": recent_years,
            "current_year": self.current_year,
            "year_range": f"{self.current_year - self.config.current_year_range}-{self.current_year + self.config.current_year_range}"
        }