"""Caching layer for all API responses"""

import diskcache
import hashlib
from pathlib import Path
from typing import Optional, Any, Dict
from .models import ProcessingConfig

class CacheManager:
    def __init__(self, cache_dir: Path, config: ProcessingConfig):
        self.config = config
        cache_size = config.cache_size_gb * 1024**3 // 4
        
        # Initialize individual caches
        self.image_cache = diskcache.Cache(
            cache_dir / "images",
            size_limit=cache_size,
            eviction_policy='least-recently-used'
        )
        
        self.card_data_cache = diskcache.Cache(
            cache_dir / "card_data",
            size_limit=cache_size,
            eviction_policy='least-recently-used'
        )
        
        self.ebay_cache = diskcache.Cache(
            cache_dir / "ebay_eps",
            size_limit=cache_size,
            eviction_policy='least-recently-used'
        )
        
        self.title_cache = diskcache.Cache(
            cache_dir / "titles",
            size_limit=cache_size,
            eviction_policy='least-recently-used'
        )
    
    def get_image_hash(self, image_path: str) -> str:
        """Generate unique hash for image"""
        hasher = hashlib.sha256()
        
        try:
            stat = Path(image_path).stat()
            hasher.update(f"{stat.st_size}_{stat.st_mtime}".encode())
            
            with open(image_path, 'rb') as f:
                chunk = f.read(32768)
                hasher.update(chunk)
            
            return hasher.hexdigest()
        except Exception:
            return hashlib.sha256(image_path.encode()).hexdigest()
    
    def get_card_data_key(self, card_name: str, set_name: str) -> str:
        """Generate cache key for card data"""
        import re
        normalized_name = re.sub(r'[^\w\s]', '', card_name.lower()).strip()
        normalized_set = re.sub(r'[^\w\s]', '', set_name.lower()).strip()
        return f"{normalized_name}|{normalized_set}"
    
    def get_cached_identification(self, image_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached card identification"""
        return self.image_cache.get(f"ximilar_{image_hash}")
    
    def cache_identification(self, image_hash: str, data: Dict[str, Any]):
        """Cache card identification"""
        ttl = self.config.cache_ttl * 24 * 60 * 60
        self.image_cache.set(f"ximilar_{image_hash}", data, expire=ttl)
    
    def get_cached_card_data(self, card_name: str, set_name: str) -> Optional[Dict[str, Any]]:
        """Get cached card pricing/metadata"""
        key = self.get_card_data_key(card_name, set_name)
        return self.card_data_cache.get(key)
    
    def cache_card_data(self, card_name: str, set_name: str, data: Dict[str, Any]):
        """Cache card pricing/metadata"""
        key = self.get_card_data_key(card_name, set_name)
        ttl = self.config.cache_ttl * 24 * 60 * 60
        self.card_data_cache.set(key, data, expire=ttl)
    
    def get_cached_ebay_url(self, image_hash: str) -> Optional[str]:
        """Get cached eBay EPS URL"""
        return self.ebay_cache.get(f"ebay_eps_{image_hash}")
    
    def cache_ebay_url(self, image_hash: str, url: str):
        """Cache eBay EPS URL"""
        ttl = self.config.cache_ttl * 24 * 60 * 60
        self.ebay_cache.set(f"ebay_eps_{image_hash}", url, expire=ttl)
    
    def close_all(self):
        """Close all cache connections"""
        self.image_cache.close()
        self.card_data_cache.close()
        self.ebay_cache.close()
        self.title_cache.close()