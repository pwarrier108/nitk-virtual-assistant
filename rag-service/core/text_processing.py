# Standard library imports
import re
from typing import List

class TextProcessor:
    def __init__(self):
        self.stop_words = set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'])
    
    def extract_search_terms(self, text: str) -> List[str]:
        """Extract meaningful search terms from query text."""
        terms = []
        for term in text.lower().split():
            term = re.sub(r'[^\w\s]', '', term)
            if term and term not in self.stop_words:
                terms.append(term)
        return terms

    def calculate_term_overlap(self, query_terms: List[str], document: str) -> float:
        """Calculate what fraction of query terms appear in document."""
        doc_lower = document.lower()
        doc_terms = set(self.extract_search_terms(document))
        matches = sum(1 for term in query_terms if term in doc_terms)
        return matches / len(query_terms) if query_terms else 0.0
