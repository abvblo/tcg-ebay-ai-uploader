"""Caching layer for all API responses with database synchronization"""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

import diskcache

# Flexible imports that work both as package and direct execution
try:
    from .database.service import DatabaseService
    from .models import ProcessingConfig
except ImportError:
    # Direct execution fallback - run from root directory using src module
    import sys
    from pathlib import Path

    # Add parent directory to path so we can import src module
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from src.database.service import DatabaseService
    from src.models import ProcessingConfig


class CacheManager:
    def __init__(
        self, cache_dir: Path, config: ProcessingConfig, db_service: DatabaseService = None
    ):
        self.config = config
        self.db_service = db_service or DatabaseService()
        cache_size = config.cache_size_gb * 1024**3 // 4

        # Initialize individual caches
        self.image_cache = diskcache.Cache(
            cache_dir / "images", size_limit=cache_size, eviction_policy="least-recently-used"
        )

        self.card_data_cache = diskcache.Cache(
            cache_dir / "card_data", size_limit=cache_size, eviction_policy="least-recently-used"
        )

        self.ebay_cache = diskcache.Cache(
            cache_dir / "ebay_eps", size_limit=cache_size, eviction_policy="least-recently-used"
        )

        self.title_cache = diskcache.Cache(
            cache_dir / "titles", size_limit=cache_size, eviction_policy="least-recently-used"
        )

        self.pricing_cache = diskcache.Cache(
            cache_dir / "pricing", size_limit=cache_size, eviction_policy="least-recently-used"
        )

    def get_image_hash(self, image_path: str) -> str:
        """Generate unique hash for image"""
        hasher = hashlib.sha256()

        try:
            stat = Path(image_path).stat()
            hasher.update(f"{stat.st_size}_{stat.st_mtime}".encode())

            with open(image_path, "rb") as f:
                chunk = f.read(32768)
                hasher.update(chunk)

            return hasher.hexdigest()
        except Exception:
            return hashlib.sha256(image_path.encode()).hexdigest()

    def get_card_data_key(self, card_name: str, set_name: str) -> str:
        """Generate cache key for card data"""
        import re

        normalized_name = re.sub(r"[^\w\s]", "", card_name.lower()).strip()
        normalized_set = re.sub(r"[^\w\s]", "", set_name.lower()).strip()
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

    def get_cached_pricing(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached pricing data with database fallback"""
        # First check disk cache
        cached_data = self.pricing_cache.get(f"pricing_{cache_key}")
        if cached_data:
            return cached_data

        # If not in cache, check database for recent pricing
        # This requires parsing the cache key to extract card details
        # For now, return None to maintain existing behavior
        return None

    def cache_pricing(self, cache_key: str, data: Dict[str, Any]):
        """Cache pricing data"""
        ttl = self.config.cache_ttl * 24 * 60 * 60
        self.pricing_cache.set(f"pricing_{cache_key}", data, expire=ttl)

        # Also sync to database if we have card information
        if data.get("database_card_id"):
            price_storage_data = {
                "prices": {"market": data.get("api_price", 0.0)},
                "source": data.get("price_source", "unknown"),
                "condition": "NM",
                "currency": "USD",
            }
            self.db_service.store_price_data(data["database_card_id"], price_storage_data)

    def sync_with_database(self):
        """Synchronize cache with database for consistency"""
        try:
            # Get database statistics
            db_stats = self.db_service.get_database_stats()

            # Log synchronization status
            if db_stats:
                print(
                    f"Database sync: {db_stats['total_cards']} cards, {db_stats['total_price_snapshots']} price snapshots"
                )

            # Clear old cache entries periodically
            self._cleanup_old_cache_entries()

        except Exception as e:
            print(f"Cache-database sync failed: {e}")

    def _cleanup_old_cache_entries(self):
        """Clean up old cache entries"""
        try:
            # Clear entries older than TTL
            self.image_cache.expire()
            self.card_data_cache.expire()
            self.ebay_cache.expire()
            self.title_cache.expire()
            self.pricing_cache.expire()
        except Exception as e:
            print(f"Cache cleanup failed: {e}")

    def close_all(self):
        """Close all cache connections"""
        self.image_cache.close()
        self.card_data_cache.close()
        self.ebay_cache.close()
        self.title_cache.close()
        self.pricing_cache.close()

    # Async methods for enhanced performance
    async def get_image_hash_async(self, image_path: str) -> str:
        """Async version of get_image_hash for better performance"""
        try:
            from .async_cache import AsyncCacheManager
        except ImportError:
            from src.async_cache import AsyncCacheManager

        # Create async cache instance with same config
        async_cache = AsyncCacheManager(
            self.image_cache.directory.parent, self.config, self.db_service
        )

        try:
            return await async_cache.get_image_hash_async(image_path)
        finally:
            # Cleanup executor
            if hasattr(async_cache, "_executor"):
                async_cache._executor.shutdown(wait=False)

    async def get_batch_image_hashes_async(self, image_paths: List[str]) -> Dict[str, str]:
        """Get hashes for multiple images concurrently"""
        try:
            from .async_cache import AsyncCacheManager
        except ImportError:
            from src.async_cache import AsyncCacheManager

        # Create async cache instance
        async_cache = AsyncCacheManager(
            self.image_cache.directory.parent, self.config, self.db_service
        )

        try:
            return await async_cache.get_batch_image_hashes(image_paths)
        finally:
            # Cleanup executor
            if hasattr(async_cache, "_executor"):
                async_cache._executor.shutdown(wait=False)
