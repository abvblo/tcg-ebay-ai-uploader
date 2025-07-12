"""Async image processing and optimization utilities with concurrent processing"""

import asyncio
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import aiofiles
from PIL import Image, ImageOps

from ..utils.logger import logger


class AsyncImageProcessor:
    def __init__(self, max_dimension: int = 1600, max_workers: int = 4):
        self.max_dimension = max_dimension
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    async def optimize_for_upload(self, image_path: str) -> Tuple[bytes, str, str]:
        """Optimize image for upload - returns (data, content_type, extension)"""
        try:
            # Check if file exists
            if not Path(image_path).exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")
            
            # Read image data asynchronously
            image_data = await self._read_image_async(image_path)

            # Process image in thread pool (CPU-bound operation)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, self._process_image, image_data, image_path
            )

            return result

        except Exception as e:
            logger.error(f"Error optimizing image {image_path}: {e}")
            # Return original if optimization fails
            if Path(image_path).exists():
                data = await self._read_image_async(image_path)
                ext = Path(image_path).suffix.lower()
                content_type = "image/png" if ext == ".png" else "image/jpeg"
                return data, content_type, ext
            else:
                raise

    async def optimize_batch(self, image_paths: List[str]) -> List[Tuple[bytes, str, str]]:
        """Optimize multiple images concurrently"""
        tasks = [self.optimize_for_upload(path) for path in image_paths]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def get_image_hash_async(self, image_path: str) -> str:
        """Generate unique hash for image asynchronously"""
        hasher = hashlib.sha256()

        try:
            # Get file stats
            loop = asyncio.get_event_loop()
            stat = await loop.run_in_executor(None, Path(image_path).stat)
            hasher.update(f"{stat.st_size}_{stat.st_mtime}".encode())

            # Read file in chunks asynchronously
            async with aiofiles.open(image_path, "rb") as f:
                chunk = await f.read(32768)
                hasher.update(chunk)

            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Error hashing image {image_path}: {e}")
            return hashlib.sha256(image_path.encode()).hexdigest()

    async def get_batch_hashes(self, image_paths: List[str]) -> Dict[str, str]:
        """Get hashes for multiple images concurrently"""
        tasks = []
        for path in image_paths:
            tasks.append(self.get_image_hash_async(path))

        hashes = await asyncio.gather(*tasks, return_exceptions=True)

        result = {}
        for path, hash_val in zip(image_paths, hashes):
            if isinstance(hash_val, Exception):
                logger.error(f"Failed to hash {path}: {hash_val}")
                result[path] = hashlib.sha256(path.encode()).hexdigest()
            else:
                result[path] = hash_val

        return result

    async def process_image_stream(
        self, image_path: str, chunk_size: int = 1024 * 1024
    ) -> AsyncIterator[bytes]:
        """Stream-process large images to reduce memory usage"""
        try:
            # First pass: read and analyze image metadata
            metadata = await self._get_image_metadata(image_path)

            if metadata["size"] < 10 * 1024 * 1024:  # Less than 10MB
                # Small image - process normally
                result = await self.optimize_for_upload(image_path)
                yield result[0]
            else:
                # Large image - stream process
                async for chunk in self._stream_process_large_image(image_path, metadata):
                    yield chunk

        except Exception as e:
            logger.error(f"Error in stream processing {image_path}: {e}")
            # Fallback to reading entire file
            async with aiofiles.open(image_path, "rb") as f:
                data = await f.read()
                yield data

    async def _read_image_async(self, image_path: str) -> bytes:
        """Read image data asynchronously with memory-efficient handling"""
        file_size = os.path.getsize(image_path)
        
        # For large files, read in chunks to avoid memory issues
        if file_size > 50 * 1024 * 1024:  # 50MB
            chunks = []
            async with aiofiles.open(image_path, "rb") as f:
                chunk_size = 8 * 1024 * 1024  # 8MB chunks
                while True:
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    chunks.append(chunk)
            return b''.join(chunks)
        else:
            async with aiofiles.open(image_path, "rb") as f:
                return await f.read()

    def _process_image(self, image_data: bytes, image_path: str) -> Tuple[bytes, str, str]:
        """Process image (CPU-bound operation for thread pool)"""
        with Image.open(BytesIO(image_data)) as img:
            # Handle EXIF orientation
            img = ImageOps.exif_transpose(img)

            # Convert to appropriate mode
            if img.mode not in ("RGBA", "RGB"):
                if img.mode in ("P", "LA"):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")

            # Scale if needed
            width, height = img.size
            if width > self.max_dimension or height > self.max_dimension:
                ratio = min(self.max_dimension / width, self.max_dimension / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Save as PNG for best quality
            output = BytesIO()
            img.save(output, format="PNG", optimize=True)
            return output.getvalue(), "image/png", ".png"

    async def _get_image_metadata(self, image_path: str) -> Dict[str, Any]:
        """Get image metadata without loading full image"""
        loop = asyncio.get_event_loop()

        def get_metadata():
            stat = Path(image_path).stat()
            with Image.open(image_path) as img:
                return {
                    "size": stat.st_size,
                    "width": img.width,
                    "height": img.height,
                    "mode": img.mode,
                    "format": img.format,
                }

        return await loop.run_in_executor(self._executor, get_metadata)

    async def _stream_process_large_image(self, image_path: str, metadata: Dict[str, Any]):
        """Stream process large images in chunks with memory optimization"""
        loop = asyncio.get_event_loop()

        # Process large images with chunked reading to reduce memory usage
        chunk_size = 4 * 1024 * 1024  # 4MB chunks for better efficiency

        # For very large images, use a more memory-efficient approach
        if metadata["size"] > 50 * 1024 * 1024:  # Over 50MB
            # Process with reduced quality to save memory
            result = await loop.run_in_executor(
                self._executor, self._process_large_image_reduced, image_path, metadata
            )
        else:
            # Normal processing for moderately large images
            # Read file in chunks for memory efficiency
            image_data = await self._read_image_async(image_path)
            result = await loop.run_in_executor(
                self._executor,
                self._process_image,
                image_data,
                image_path,
            )

        # Yield processed data in chunks
        data = result[0]
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]
            # Force garbage collection for very large files
            if metadata["size"] > 100 * 1024 * 1024:
                import gc
                gc.collect()

    def _process_large_image_reduced(
        self, image_path: str, metadata: Dict[str, Any]
    ) -> Tuple[bytes, str, str]:
        """Process very large images with reduced memory footprint"""
        from PIL import Image, ImageOps

        with Image.open(image_path) as img:
            # Handle EXIF orientation
            img = ImageOps.exif_transpose(img)

            # More aggressive resizing for very large images
            width, height = img.size
            max_dimension = 1200  # Lower max dimension for huge files

            if width > max_dimension or height > max_dimension:
                ratio = min(max_dimension / width, max_dimension / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Convert to RGB to reduce file size (no alpha channel)
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Save as JPEG with good quality for very large images
            output = BytesIO()
            img.save(output, format="JPEG", quality=85, optimize=True)
            return output.getvalue(), "image/jpeg", ".jpg"

    def __del__(self):
        """Cleanup thread pool executor safely"""
        try:
            if hasattr(self, "_executor") and self._executor:
                self._executor.shutdown(wait=True, cancel_futures=True)
        except Exception as e:
            logger.error(f"Error cleaning up thread pool executor: {e}")


# Backwards compatible wrapper
class ImageProcessor(AsyncImageProcessor):
    """Backwards compatible image processor that wraps async methods"""

    def optimize_for_upload_sync(self, image_path: str) -> Tuple[bytes, str, str]:
        """Synchronous wrapper for optimize_for_upload"""
        try:
            # Try to get the running event loop
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a task
            return asyncio.run_coroutine_threadsafe(
                self.optimize_for_upload(image_path), loop
            ).result()
        except RuntimeError:
            # No running event loop, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.optimize_for_upload(image_path))
            finally:
                loop.close()
                asyncio.set_event_loop(None)

    def get_image_hash(self, image_path: str) -> str:
        """Synchronous wrapper for get_image_hash_async"""
        try:
            # Try to get the running event loop
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a task
            return asyncio.run_coroutine_threadsafe(
                self.get_image_hash_async(image_path), loop
            ).result()
        except RuntimeError:
            # No running event loop, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.get_image_hash_async(image_path))
            finally:
                loop.close()
                asyncio.set_event_loop(None)
