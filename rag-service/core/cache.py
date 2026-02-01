# Standard library imports
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

class CacheManager:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.cache_dir = config.cache_dir
        self.llm_dir = self.cache_dir / "llm"
        self.last_cleanup = datetime.now()
    
    def get_cache_key(self, query: str, response_format: str = "web") -> str:
        """Generate cache key for RAG responses based on query and format."""
        key = f"{query}_{response_format}"
        # Use hash of the key for filename instead of raw text
        filename = hashlib.md5(key.encode()).hexdigest()
        if self.config.debug:
            self.logger.debug(f"Generated cache key: {filename} for query: {query[:50]}... (format: {response_format})")
        return filename

    def get_cached_response(self, key: str) -> dict:
        if not key:
            return None
            
        cache_file = self.llm_dir / f"{key}.json"
        if self.config.debug:
            self.logger.debug(f"Looking for cache file: {cache_file}")
            
        if not cache_file.exists():
            if self.config.debug:
                self.logger.debug(f"Cache miss - file not found: {cache_file}")
            return None
            
        try:
            with open(cache_file, encoding='utf-8') as f:
                cached = json.load(f)
                
            if self.config.debug:
                self.logger.debug(f"Cache hit - loaded file: {cache_file}")
                
            if self._is_expired(cached.get('timestamp')):
                self.logger.debug(f"Cache expired for key {key}")
                return None
                
            return cached
            
        except Exception as e:
            self.logger.error(f"Cache read error for {key}: {str(e)}")
            return None

    def cache_response(self, key: str, response_obj: dict) -> None:
        if not key or not response_obj:
            return
        try:
            response_obj['timestamp'] = datetime.now().timestamp()
            cache_file = self.llm_dir / f"{key}.json"
            
            if self.config.debug:
                self.logger.debug(f"Writing cache file: {cache_file}")
                    
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(response_obj, f, ensure_ascii=False, indent=2)
                
            if self.config.debug:
                self.logger.debug(f"Successfully wrote cache file: {cache_file}")
                
            self.cleanup_cache()
        except Exception as e:
            self.logger.error(f"Cache write error for {key}: {str(e)}")

    def _is_expired(self, timestamp: Any) -> bool:
        if not timestamp:
            return True
        try:
            if isinstance(timestamp, (int, float)):
                cache_time = datetime.fromtimestamp(float(timestamp))
            else:
                cache_time = datetime.fromisoformat(str(timestamp))
            max_age = timedelta(days=self.config.cache_max_age_days)
            is_expired = datetime.now() - cache_time > max_age
            
            if self.config.debug:
                self.logger.debug(f"Cache timestamp: {cache_time}, max age: {max_age}, expired: {is_expired}")
            return is_expired
            
        except Exception as e:
            self.logger.error(f"Error parsing timestamp {timestamp}: {str(e)}")
            return True

    def cleanup_cache(self) -> None:
        cleanup_interval = timedelta(hours=self.config.cache_cleanup_interval_hours)
        if datetime.now() - self.last_cleanup > cleanup_interval:
            if self.config.debug:
                self.logger.debug("Starting cache cleanup")
            try:
                self._remove_old_entries()
                self._check_size_limits()
                self.last_cleanup = datetime.now()
                if self.config.debug:
                    self.logger.debug("Cache cleanup completed successfully")
            except Exception as e:
                self.logger.error(f"Cache cleanup error: {str(e)}")

    def _remove_old_entries(self) -> None:
        if self.config.debug:
            self.logger.debug("Checking for expired cache entries")
            
        for cache_file in self.llm_dir.glob("*.json"):
            try:
                with open(cache_file) as f:
                    cached = json.load(f)
                if self._is_expired(cached.get('timestamp')):
                    if self.config.debug:
                        self.logger.debug(f"Removing expired cache file: {cache_file}")
                    cache_file.unlink(missing_ok=True)
            except Exception as e:
                self.logger.error(f"Error cleaning old entry {cache_file}: {str(e)}")

    def _check_size_limits(self) -> None:
        try:
            total_size = sum(f.stat().st_size for f in self.cache_dir.rglob('*') 
                           if f.is_file())
            max_size = self.config.cache_max_size_gb * 1024 * 1024 * 1024
            
            if self.config.debug:
                self.logger.debug(f"Current cache size: {total_size/1024/1024:.1f}MB, limit: {max_size/1024/1024:.1f}MB")
            
            if total_size > max_size:
                self.logger.info(f"Cache size {total_size/1024/1024:.1f}MB exceeds limit")
                cache_files = sorted(
                    self.llm_dir.glob("*.json"),
                    key=lambda x: x.stat().st_mtime
                )
                
                while total_size > max_size and cache_files:
                    oldest = cache_files.pop(0)
                    try:
                        if self.config.debug:
                            self.logger.debug(f"Removing oldest cache file: {oldest}")
                        total_size -= oldest.stat().st_size
                        oldest.unlink(missing_ok=True)
                    except Exception as e:
                        self.logger.error(f"Error removing file {oldest}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error checking size limits: {str(e)}")