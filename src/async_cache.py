"""Async caching layer for all API responses with database synchronization"""

import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import diskcache

from .cache import CacheManager
from .database.service import DatabaseService
from .models import ProcessingConfig


class AsyncCacheManager(CacheManager):
    """Async version of CacheManager with concurrent processing capabilities"""

    def __init__(
        self,
        cache_dir: Path,
        config: ProcessingConfig,
        db_service: DatabaseService = None,
        max_workers: int = 4,
    ):
        super().__init__(cache_dir, config, db_service)
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    async def get_image_hash_async(self, image_path: str) -> str:
        """Generate unique hash for image asynchronously"""
        hasher = hashlib.sha256()

        try:
            # Get file stats asynchronously
            loop = asyncio.get_event_loop()
            stat = await loop.run_in_executor(None, Path(image_path).stat)
            hasher.update(f"{stat.st_size}_{stat.st_mtime}".encode())

            # Read file in chunks asynchronously
            async with aiofiles.open(image_path, "rb") as f:
                # Read first 32KB for hash
                chunk = await f.read(32768)
                hasher.update(chunk)

            return hasher.hexdigest()
        except Exception:
            return hashlib.sha256(image_path.encode()).hexdigest()

    async def get_batch_image_hashes(self, image_paths: List[str]) -> Dict[str, str]:
        """Generate hashes for multiple images concurrently"""
        tasks = [self.get_image_hash_async(path) for path in image_paths]
        hashes = await asyncio.gather(*tasks, return_exceptions=True)

        result = {}
        for path, hash_val in zip(image_paths, hashes):
            if isinstance(hash_val, Exception):
                # Fallback hash on error
                result[path] = hashlib.sha256(path.encode()).hexdigest()
            else:
                result[path] = hash_val

        return result

    async def get_cached_identification_async(self, image_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached card identification asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.image_cache.get, f"ximilar_{image_hash}"
        )

    async def cache_identification_async(self, image_hash: str, data: Dict[str, Any]):
        """Cache card identification asynchronously"""
        loop = asyncio.get_event_loop()
        ttl = self.config.cache_ttl * 24 * 60 * 60
        await loop.run_in_executor(
            self._executor, self.image_cache.set, f"ximilar_{image_hash}", data, ttl
        )

    async def get_batch_cached_identifications(
        self, image_hashes: List[str]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get multiple cached identifications concurrently"""
        tasks = [self.get_cached_identification_async(hash_val) for hash_val in image_hashes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            hash_val: (None if isinstance(result, Exception) else result)
            for hash_val, result in zip(image_hashes, results)
        }

    async def get_cached_card_data_async(
        self, card_name: str, set_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached card pricing/metadata asynchronously"""
        key = self.get_card_data_key(card_name, set_name)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.card_data_cache.get, key)

    async def cache_card_data_async(self, card_name: str, set_name: str, data: Dict[str, Any]):
        """Cache card pricing/metadata asynchronously"""
        key = self.get_card_data_key(card_name, set_name)
        ttl = self.config.cache_ttl * 24 * 60 * 60
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self.card_data_cache.set, key, data, ttl)

    async def get_cached_ebay_url_async(self, image_hash: str) -> Optional[str]:
        """Get cached eBay EPS URL asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.ebay_cache.get, f"ebay_eps_{image_hash}"
        )

    async def cache_ebay_url_async(self, image_hash: str, url: str):
        """Cache eBay EPS URL asynchronously"""
        ttl = self.config.cache_ttl * 24 * 60 * 60
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor, self.ebay_cache.set, f"ebay_eps_{image_hash}", url, ttl
        )

    async def get_batch_cached_ebay_urls(self, image_hashes: List[str]) -> Dict[str, Optional[str]]:
        """Get multiple cached eBay URLs concurrently"""
        tasks = [self.get_cached_ebay_url_async(hash_val) for hash_val in image_hashes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            hash_val: (None if isinstance(result, Exception) else result)
            for hash_val, result in zip(image_hashes, results)
        }

    async def warm_cache_for_images(self, image_paths: List[str]):
        """Pre-compute and cache hashes for a batch of images"""
        # Generate all hashes concurrently
        hashes = await self.get_batch_image_hashes(image_paths)

        # Check which ones are already cached
        cached_data = await self.get_batch_cached_identifications(list(hashes.values()))

        uncached_paths = [
            path for path, hash_val in hashes.items() if cached_data.get(hash_val) is None
        ]

        if uncached_paths:
            print(f"Found {len(uncached_paths)} images without cached identifications")

        return hashes, uncached_paths

    async def sync_with_database_async(self):
        """Asynchronously synchronize cache with database for consistency"""
        loop = asyncio.get_event_loop()

        try:
            # Get database statistics in thread pool
            db_stats = await loop.run_in_executor(
                self._executor, self.db_service.get_database_stats
            )

            # Log synchronization status
            if db_stats:
                print(
                    f"Database sync: {db_stats['total_cards']} cards, {db_stats['total_price_snapshots']} price snapshots"
                )

            # Clear old cache entries periodically
            await self._cleanup_old_cache_entries_async()

        except Exception as e:
            print(f"Cache-database sync failed: {e}")

    async def _cleanup_old_cache_entries_async(self):
        """Clean up old cache entries asynchronously"""
        loop = asyncio.get_event_loop()

        try:
            # Clear entries older than TTL in thread pool
            tasks = [
                loop.run_in_executor(self._executor, cache.expire)
                for cache in [
                    self.image_cache,
                    self.card_data_cache,
                    self.ebay_cache,
                    self.title_cache,
                    self.pricing_cache,
                ]
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"Cache cleanup failed: {e}")

    def __del__(self):
        """Cleanup resources"""
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=False)
        super().close_all()
