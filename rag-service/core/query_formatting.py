# Standard library imports
from datetime import datetime
from typing import Any, Dict, List

class QueryResultFormatter:
    @staticmethod
    def format_result(raw_result: dict) -> dict:
        metadata = raw_result.get('metadata', {})
        return {
            'document': raw_result['document'],
            'source': {
                'id': metadata.get('source_id'),
                'date': metadata.get('created_date'),
                'author': metadata.get('author'),
                'platform': metadata.get('platform')
            },
            'entities': metadata.get('entities', {}),
            'relevance_score': raw_result.get('relevance_score', 0.0),
            'score_breakdown': raw_result.get('score_breakdown', {})
        }

    @staticmethod
    def format_results(results: list, query: str) -> dict:
        return {
            'query': query,
            'timestamp': datetime.now().isoformat(),
            'results': [QueryResultFormatter.format_result(r) for r in results]
        }
