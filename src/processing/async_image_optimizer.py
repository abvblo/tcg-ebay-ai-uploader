"""
Async automatic image optimization for trading card images
Optimizes images concurrently for optimal eBay performance
"""

import asyncio
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
from PIL import Image

from ..utils.logger import logger


class AsyncImageOptimizer:
    """Handles automatic image optimization for trading card images with async/concurrent processing"""

    def __init__(
        self,
        max_size: int = 1600,
        quality: int = 85,
        format_type: str = "JPEG",
        max_workers: int = 4,
    ):
        """
        Initialize async image optimizer with optimal settings for eBay

        Args:
            max_size: Maximum size in pixels on longest side (default: 1600 - optimal for eBay)
            quality: JPEG quality 1-100 (default: 85 - good balance of quality/size)
            format_type: Output format 'JPEG' or 'PNG' (default: JPEG for smaller files)
            max_workers: Maximum concurrent workers for CPU-bound operations
        """
        self.max_size = max_size
        self.quality = quality
        self.format_type = format_type
        self.max_workers = max_workers
        self.optimized_count = 0
        self.total_size_saved = 0
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = asyncio.Lock()  # For thread-safe counter updates

    async def should_optimize_image(self, image_path: Path) -> bool:
        """Check if image needs optimization (async version)"""
        try:
            # Get file stats asynchronously
            loop = asyncio.get_event_loop()
            stat = await loop.run_in_executor(None, image_path.stat)
            file_size = stat.st_size

            if file_size < 2 * 1024 * 1024:  # Less than 2MB
                return False

            # Check image dimensions in thread pool
            needs_opt = await loop.run_in_executor(
                self._executor, self._check_image_dimensions, image_path, file_size
            )

            return needs_opt

        except Exception as e:
            logger.debug(f"Could not check optimization need for {image_path}: {e}")
            return False

    def _check_image_dimensions(self, image_path: Path, file_size: int) -> bool:
        """Check image dimensions (CPU-bound operation for thread pool)"""
        with Image.open(image_path) as img:
            width, height = img.size
            max_dimension = max(width, height)

            # Optimize if larger than target size or if it's a large PNG
            needs_resize = max_dimension > self.max_size
            is_large_png = (
                image_path.suffix.lower() == ".png" and file_size > 1024 * 1024
            )  # > 1MB PNG

            return needs_resize or is_large_png

    async def optimize_image_inplace(self, image_path: Path, create_backup: bool = True) -> bool:
        """
        Optimize image in-place, replacing the original file (async version)

        Args:
            image_path: Path to image file to optimize
            create_backup: Whether to create a backup of original (default: True)

        Returns:
            bool: True if optimization was successful, False otherwise
        """
        try:
            should_optimize = await self.should_optimize_image(image_path)
            if not should_optimize:
                return True  # No optimization needed

            loop = asyncio.get_event_loop()
            original_size = (await loop.run_in_executor(None, image_path.stat)).st_size
            backup_path = None

            # Create backup if requested
            if create_backup:
                backup_path = image_path.parent / f"{image_path.stem}_original{image_path.suffix}"
                if not await self._path_exists_async(backup_path):
                    await self._copy_file_async(image_path, backup_path)

            # Optimize image in thread pool
            result = await loop.run_in_executor(
                self._executor, self._optimize_image_sync, image_path, original_size
            )

            if result:
                optimized_path, new_size, size_saved = result

                # Update counters thread-safely
                async with self._lock:
                    self.optimized_count += 1
                    self.total_size_saved += size_saved

                compression_ratio = (size_saved / original_size) * 100
                logger.info(
                    f"   📷 Optimized: {image_path.name} → {optimized_path.name} "
                    f"({original_size/(1024*1024):.1f}MB → {new_size/(1024*1024):.1f}MB, "
                    f"{compression_ratio:.1f}% smaller)"
                )

                return True
            else:
                # Restore backup if optimization failed
                if backup_path and await self._path_exists_async(backup_path):
                    await self._copy_file_async(backup_path, image_path)
                    await self._remove_file_async(backup_path)

                return False

        except Exception as e:
            logger.error(f"   ❌ Failed to optimize {image_path}: {e}")
            return False

    def _optimize_image_sync(
        self, image_path: Path, original_size: int
    ) -> Optional[Tuple[Path, int, int]]:
        """Synchronous image optimization for thread pool execution"""
        try:
            with Image.open(image_path) as img:
                # Calculate new dimensions maintaining aspect ratio
                img.thumbnail((self.max_size, self.max_size), Image.Resampling.LANCZOS)

                # Convert to RGB if saving as JPEG and image has transparency
                if self.format_type == "JPEG" and img.mode in ("RGBA", "LA"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                    img = background

                # Determine output filename
                if self.format_type == "JPEG" and image_path.suffix.lower() == ".png":
                    # Convert PNG to JPEG
                    new_path = image_path.with_suffix(".jpg")
                    img.save(new_path, format="JPEG", quality=self.quality, optimize=True)

                    # Remove original PNG
                    image_path.unlink()

                    # Update the path reference
                    optimized_path = new_path
                else:
                    # Save in same format/location
                    if self.format_type == "JPEG":
                        img.save(image_path, format="JPEG", quality=self.quality, optimize=True)
                    else:
                        img.save(image_path, format="PNG", optimize=True)

                    optimized_path = image_path

            # Calculate savings
            new_size = optimized_path.stat().st_size
            size_saved = original_size - new_size

            return optimized_path, new_size, size_saved

        except Exception:
            return None

    async def optimize_image_list(
        self, image_paths: List[Path], create_backup: bool = True
    ) -> List[Path]:
        """
        Optimize a list of images concurrently

        Args:
            image_paths: List of image paths to optimize
            create_backup: Whether to create backups of originals

        Returns:
            List[Path]: Updated paths (may have changed if format converted)
        """
        if not image_paths:
            return image_paths

        logger.info(f"🔧 Optimizing {len(image_paths)} images for eBay performance (concurrent)...")

        # Create optimization tasks
        tasks = []
        for image_path in image_paths:
            task = self.optimize_image_inplace(image_path, create_backup)
            tasks.append(task)

        # Run optimizations concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        optimized_paths = []
        for i, (original_path, result) in enumerate(zip(image_paths, results)):
            if isinstance(result, Exception):
                logger.error(f"Failed to optimize {original_path}: {result}")
                optimized_paths.append(original_path)
            elif result:
                # Check if path changed (PNG -> JPEG conversion)
                if self.format_type == "JPEG" and original_path.suffix.lower() == ".png":
                    new_path = original_path.with_suffix(".jpg")
                    if await self._path_exists_async(new_path):
                        optimized_paths.append(new_path)
                    else:
                        optimized_paths.append(original_path)
                else:
                    optimized_paths.append(original_path)
            else:
                # Keep original path if optimization failed
                optimized_paths.append(original_path)

        if self.optimized_count > 0:
            logger.info(
                f"✅ Optimized {self.optimized_count} images, "
                f"saved {self.total_size_saved/(1024*1024):.1f}MB total"
            )

        return optimized_paths

    async def _path_exists_async(self, path: Path) -> bool:
        """Check if path exists asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, path.exists)

    async def _copy_file_async(self, src: Path, dst: Path):
        """Copy file asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, shutil.copy2, src, dst)

    async def _remove_file_async(self, path: Path):
        """Remove file asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, path.unlink)

    def get_optimization_stats(self) -> dict:
        """Get optimization statistics"""
        return {
            "optimized_count": self.optimized_count,
            "total_size_saved_mb": self.total_size_saved / (1024 * 1024),
            "avg_size_saved_mb": (
                (self.total_size_saved / self.optimized_count / (1024 * 1024))
                if self.optimized_count > 0
                else 0
            ),
        }

    def __del__(self):
        """Cleanup thread pool executor"""
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=False)
