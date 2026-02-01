# Standard library imports
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class WebUICacheManager:
    """
    Cache manager for web-ui client supporting translation and audio caching.
    Optimized for Windows environment with proper path handling.
    """
    
    def __init__(self, config, logger_instance=None):
        self.config = config
        self.logger = logger_instance or logger
        
        # Cache directories
        self.cache_dir = Path(config.cache_dir)
        self.translations_dir = self.cache_dir / "translations"
        self.audio_dir = self.cache_dir / "audio"
        self.metadata_file = self.cache_dir / "metadata.json"
        
        # Cache settings with defaults
        self.translation_ttl_days = getattr(config, 'cache_translation_ttl_days', 7)
        self.audio_ttl_days = getattr(config, 'cache_audio_ttl_days', 7)
        self.max_cache_size_mb = getattr(config, 'cache_max_size_mb', 500)
        self.cleanup_interval_hours = getattr(config, 'cache_cleanup_interval_hours', 24)
        
        # Runtime state
        self.last_cleanup = datetime.now()
        self.cache_stats = {
            'translation_hits': 0,
            'translation_misses': 0,
            'audio_hits': 0,
            'audio_misses': 0,
            'total_size_mb': 0
        }
        
        # Initialize cache
        self._initialize_cache()
        self._load_metadata()
        
    def _initialize_cache(self):
        """Create cache directories if they don't exist."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.translations_dir.mkdir(parents=True, exist_ok=True)
            self.audio_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Cache initialized at: {self.cache_dir}")
        except Exception as e:
            self.logger.error(f"Failed to initialize cache directories: {str(e)}")
            raise
    
    def _load_metadata(self):
        """Load cache metadata and statistics."""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache_stats.update(data.get('stats', {}))
                    last_cleanup_str = data.get('last_cleanup')
                    if last_cleanup_str:
                        self.last_cleanup = datetime.fromisoformat(last_cleanup_str)
        except Exception as e:
            self.logger.warning(f"Failed to load cache metadata: {str(e)}")
    
    def _save_metadata(self):
        """Save cache metadata and statistics."""
        try:
            metadata = {
                'stats': self.cache_stats,
                'last_cleanup': self.last_cleanup.isoformat(),
                'version': '1.0'
            }
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save cache metadata: {str(e)}")
    
    def _generate_cache_key(self, text: str, language: str) -> str:
        """Generate MD5 cache key from text and language."""
        key_string = f"{text}_{language}"
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    def _is_file_expired(self, file_path: Path, ttl_days: int) -> bool:
        """Check if cache file has expired based on TTL."""
        try:
            if not file_path.exists():
                return True
            
            file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
            return file_age > timedelta(days=ttl_days)
        except Exception:
            return True
    
    # ========== TRANSLATION CACHE METHODS ==========
    
    def get_translation_cache(self, text: str, target_language: str) -> Optional[str]:
        """
        Get cached translation if available and not expired.
        
        Args:
            text: Original text to translate
            target_language: Target language name (e.g., "Hindi")
            
        Returns:
            Cached translated text or None if not found/expired
        """
        try:
            cache_key = self._generate_cache_key(text, target_language)
            cache_file = self.translations_dir / f"{cache_key}.json"
            
            if self._is_file_expired(cache_file, self.translation_ttl_days):
                if cache_file.exists():
                    cache_file.unlink(missing_ok=True)
                self.cache_stats['translation_misses'] += 1
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            self.cache_stats['translation_hits'] += 1
            self.logger.debug(f"Translation cache hit for: {text[:50]}...")
            return cache_data['translated_text']
            
        except Exception as e:
            self.logger.warning(f"Error reading translation cache: {str(e)}")
            self.cache_stats['translation_misses'] += 1
            return None
    
    def cache_translation(self, text: str, target_language: str, translated_text: str):
        """
        Cache a translation result.
        
        Args:
            text: Original text
            target_language: Target language name
            translated_text: Translated result
        """
        try:
            cache_key = self._generate_cache_key(text, target_language)
            cache_file = self.translations_dir / f"{cache_key}.json"
            
            cache_data = {
                'original_text': text,
                'target_language': target_language,
                'translated_text': translated_text,
                'timestamp': datetime.now().isoformat(),
                'cache_key': cache_key
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Cached translation for: {text[:50]}...")
            
        except Exception as e:
            self.logger.error(f"Failed to cache translation: {str(e)}")
    
    # ========== AUDIO CACHE METHODS ==========
    
    def get_audio_cache(self, text: str, language: str) -> Optional[Tuple[Path, Optional[float]]]:
        """
        Get cached audio file if available and not expired.
        
        Args:
            text: Text that was converted to speech
            language: Language name (e.g., "Hindi")
            
        Returns:
            Tuple of (audio_file_path, duration) or None if not found/expired
        """
        try:
            cache_key = self._generate_cache_key(text, language)
            audio_file = self.audio_dir / f"{cache_key}.mp3"
            metadata_file = self.audio_dir / f"{cache_key}.json"
            
            if (self._is_file_expired(audio_file, self.audio_ttl_days) or 
                self._is_file_expired(metadata_file, self.audio_ttl_days)):
                
                # Clean up both files if either is expired
                audio_file.unlink(missing_ok=True)
                metadata_file.unlink(missing_ok=True)
                self.cache_stats['audio_misses'] += 1
                return None
            
            # Load metadata
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            duration = metadata.get('duration')
            self.cache_stats['audio_hits'] += 1
            self.logger.debug(f"Audio cache hit for: {text[:50]}...")
            return audio_file, duration
            
        except Exception as e:
            self.logger.warning(f"Error reading audio cache: {str(e)}")
            self.cache_stats['audio_misses'] += 1
            return None
    
    def cache_audio(self, text: str, language: str, audio_path: Path, duration: Optional[float] = None):
        """
        Cache an audio file by copying it to cache directory.
        
        Args:
            text: Text that was converted to speech
            language: Language name
            audio_path: Path to generated audio file
            duration: Audio duration in seconds (optional)
        """
        try:
            import shutil
            
            cache_key = self._generate_cache_key(text, language)
            cached_audio_file = self.audio_dir / f"{cache_key}.mp3"
            metadata_file = self.audio_dir / f"{cache_key}.json"
            
            # Copy audio file to cache
            shutil.copy2(audio_path, cached_audio_file)
            
            # Save metadata
            metadata = {
                'text': text,
                'language': language,
                'duration': duration,
                'timestamp': datetime.now().isoformat(),
                'cache_key': cache_key,
                'file_size': cached_audio_file.stat().st_size
            }
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Cached audio for: {text[:50]}...")
            
        except Exception as e:
            self.logger.error(f"Failed to cache audio: {str(e)}")
    
    # ========== CACHE MANAGEMENT METHODS ==========
    
    def cleanup_expired(self):
        """Remove expired cache files and update statistics."""
        try:
            cleanup_interval = timedelta(hours=self.cleanup_interval_hours)
            if datetime.now() - self.last_cleanup < cleanup_interval:
                return
            
            self.logger.info("Starting cache cleanup...")
            
            # Clean expired translation files
            translation_cleaned = 0
            for cache_file in self.translations_dir.glob("*.json"):
                if self._is_file_expired(cache_file, self.translation_ttl_days):
                    cache_file.unlink(missing_ok=True)
                    translation_cleaned += 1
            
            # Clean expired audio files (both .mp3 and .json)
            audio_cleaned = 0
            for cache_file in self.audio_dir.glob("*.json"):
                if self._is_file_expired(cache_file, self.audio_ttl_days):
                    # Remove both metadata and audio file
                    audio_file = cache_file.with_suffix('.mp3')
                    cache_file.unlink(missing_ok=True)
                    audio_file.unlink(missing_ok=True)
                    audio_cleaned += 1
            
            self.last_cleanup = datetime.now()
            self._save_metadata()
            
            if translation_cleaned > 0 or audio_cleaned > 0:
                self.logger.info(f"Cache cleanup completed: {translation_cleaned} translations, {audio_cleaned} audio files removed")
            
        except Exception as e:
            self.logger.error(f"Cache cleanup failed: {str(e)}")
    
    def check_size_limit(self):
        """Check cache size and remove oldest files if limit exceeded."""
        try:
            total_size = 0
            all_files = []
            
            # Collect all cache files with their sizes and modification times
            for cache_dir in [self.translations_dir, self.audio_dir]:
                for file_path in cache_dir.rglob("*"):
                    if file_path.is_file():
                        stat = file_path.stat()
                        total_size += stat.st_size
                        all_files.append((file_path, stat.st_mtime, stat.st_size))
            
            # Convert to MB
            total_size_mb = total_size / (1024 * 1024)
            self.cache_stats['total_size_mb'] = total_size_mb
            
            if total_size_mb > self.max_cache_size_mb:
                self.logger.info(f"Cache size {total_size_mb:.1f}MB exceeds limit {self.max_cache_size_mb}MB")
                
                # Sort by modification time (oldest first)
                all_files.sort(key=lambda x: x[1])
                
                # Remove oldest files until under limit
                removed_size = 0
                removed_count = 0
                
                for file_path, _, file_size in all_files:
                    try:
                        # For audio files, remove both .mp3 and .json
                        if file_path.suffix == '.mp3':
                            metadata_file = file_path.with_suffix('.json')
                            metadata_file.unlink(missing_ok=True)
                        elif file_path.suffix == '.json' and (file_path.parent == self.audio_dir):
                            audio_file = file_path.with_suffix('.mp3')
                            audio_file.unlink(missing_ok=True)
                        
                        file_path.unlink(missing_ok=True)
                        removed_size += file_size
                        removed_count += 1
                        
                        # Check if we're now under the limit
                        if (total_size_mb - removed_size / (1024 * 1024)) <= self.max_cache_size_mb:
                            break
                            
                    except Exception as e:
                        self.logger.warning(f"Failed to remove cache file {file_path}: {str(e)}")
                
                self.logger.info(f"Removed {removed_count} files ({removed_size / (1024 * 1024):.1f}MB)")
            
        except Exception as e:
            self.logger.error(f"Size limit check failed: {str(e)}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        try:
            # Update size statistics
            self.check_size_limit()
            
            # Calculate hit rates
            total_translation_requests = self.cache_stats['translation_hits'] + self.cache_stats['translation_misses']
            total_audio_requests = self.cache_stats['audio_hits'] + self.cache_stats['audio_misses']
            
            translation_hit_rate = (self.cache_stats['translation_hits'] / total_translation_requests 
                                  if total_translation_requests > 0 else 0)
            audio_hit_rate = (self.cache_stats['audio_hits'] / total_audio_requests 
                            if total_audio_requests > 0 else 0)
            
            # Count files
            translation_files = len(list(self.translations_dir.glob("*.json")))
            audio_files = len(list(self.audio_dir.glob("*.mp3")))
            
            return {
                'translation_hit_rate': translation_hit_rate,
                'audio_hit_rate': audio_hit_rate,
                'total_size_mb': self.cache_stats['total_size_mb'],
                'translation_files': translation_files,
                'audio_files': audio_files,
                'cache_dirs': {
                    'translations': str(self.translations_dir),
                    'audio': str(self.audio_dir)
                },
                'last_cleanup': self.last_cleanup.isoformat(),
                'settings': {
                    'translation_ttl_days': self.translation_ttl_days,
                    'audio_ttl_days': self.audio_ttl_days,
                    'max_size_mb': self.max_cache_size_mb
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {str(e)}")
            return {'error': str(e)}
    
    def clear_cache(self, cache_type: str = "all"):
        """
        Clear cache files.
        
        Args:
            cache_type: "all", "translations", or "audio"
        """
        try:
            cleared_count = 0
            
            if cache_type in ["all", "translations"]:
                for file_path in self.translations_dir.glob("*.json"):
                    file_path.unlink(missing_ok=True)
                    cleared_count += 1
                self.cache_stats['translation_hits'] = 0
                self.cache_stats['translation_misses'] = 0
            
            if cache_type in ["all", "audio"]:
                for file_path in self.audio_dir.glob("*"):
                    file_path.unlink(missing_ok=True)
                    cleared_count += 1
                self.cache_stats['audio_hits'] = 0
                self.cache_stats['audio_misses'] = 0
            
            self._save_metadata()
            self.logger.info(f"Cleared {cleared_count} cache files ({cache_type})")
            
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {str(e)}")
    
    def __del__(self):
        """Cleanup on destruction."""
        try:
            self._save_metadata()
        except:
            pass