"""Async image grouping and sequential pair detection with concurrent processing"""

import asyncio
import glob
import re
from pathlib import Path
from typing import Dict, List

from ..config import Config
from ..models import ImageGroup
from ..utils.logger import logger
from .async_image_optimizer import AsyncImageOptimizer


class AsyncImageGroupDetector:
    def __init__(self, config: Config):
        self.config = config
        self.scans_folder = config.scans_folder

        # Initialize automatic image optimizer with config settings
        self.image_optimizer = AsyncImageOptimizer(
            max_size=config.processing.optimization_max_size,
            quality=config.processing.optimization_quality,
            format_type=config.processing.optimization_format,
            max_workers=4,  # Use concurrent workers
        )

        # Compile regex patterns
        self.regex_patterns = {
            "sequential": re.compile(r"^(.*?)(\d+)\.(jpg|jpeg|png|webp|bmp|tiff)$", re.IGNORECASE),
            "underscore": re.compile(
                r"^(.*?)[\_\-\s](\d+)\.(jpg|jpeg|png|webp|bmp|tiff)$", re.IGNORECASE
            ),
            "parentheses": re.compile(
                r"^(.*?)\s*\((\d+)\)\.(jpg|jpeg|png|webp|bmp|tiff)$", re.IGNORECASE
            ),
            "hyphen": re.compile(
                r"^(.*?)\s*-\s*(\d+)\.(jpg|jpeg|png|webp|bmp|tiff)$", re.IGNORECASE
            ),
            "brackets": re.compile(
                r"^(.*?)\s*\[\s*(\d+)\s*\]\.(jpg|jpeg|png|webp|bmp|tiff)$", re.IGNORECASE
            ),
        }

    async def find_groups(self) -> List[ImageGroup]:
        """Find and group images with sequential pair detection using async processing"""
        all_files = await self._scan_for_images()

        if not all_files:
            return []

        # Automatically optimize images for eBay performance (if enabled)
        if self.config.processing.auto_optimize_images:
            logger.info(
                "🔧 Automatically optimizing images for optimal eBay performance (concurrent)..."
            )
            optimized_files = await self._optimize_images_async(all_files)
        else:
            logger.info("⚠️ Automatic image optimization is disabled")
            optimized_files = all_files

        # Sort files
        all_files = sorted(optimized_files)

        # Group images concurrently
        groups = []
        processed_files = set()

        # Process sequential pairs and remaining files concurrently
        sequential_task = asyncio.create_task(
            self._detect_sequential_pairs_async(all_files, processed_files)
        )

        # Wait for sequential processing to complete
        sequential_groups = await sequential_task
        groups.extend(sequential_groups)

        # Handle remaining files
        remaining_groups = await self._group_remaining_files_async(all_files, processed_files)
        groups.extend(remaining_groups)

        total_images = sum(len(g.paths) for g in groups)
        logger.info(f"✅ Found {len(groups)} groups containing {total_images} total images")

        # Log sequential pairs
        sequential_count = sum(1 for g in groups if g.is_sequential_pair)
        if sequential_count:
            logger.info(f"🎴 Detected {sequential_count} sequential pairs from scanner")

        return groups

    async def _scan_for_images(self) -> List[str]:
        """Scan for all image files concurrently"""
        patterns = ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.tiff"]
        all_files = []

        loop = asyncio.get_event_loop()

        def scan_pattern(pattern: str) -> List[str]:
            pattern_path = self.scans_folder / pattern
            files = list(glob.glob(str(pattern_path)))
            files.extend(glob.glob(str(pattern_path.with_name(pattern.upper()))))
            return files

        # Scan all patterns concurrently
        tasks = [loop.run_in_executor(None, scan_pattern, pattern) for pattern in patterns]
        results = await asyncio.gather(*tasks)

        for files in results:
            all_files.extend(files)

        return all_files

    async def _detect_sequential_pairs_async(
        self, all_files: List[str], processed_files: set
    ) -> List[ImageGroup]:
        """Detect sequential pairs (front/back) from scanner using async processing"""
        groups = []
        sequential_files = []

        # Process files in parallel to find sequential patterns
        loop = asyncio.get_event_loop()

        def process_file(img_path: str):
            basename = Path(img_path).name
            match = self.regex_patterns["sequential"].match(basename)
            if match:
                return {
                    "path": img_path,
                    "prefix": match.group(1),
                    "number": int(match.group(2)),
                    "extension": match.group(3),
                    "basename": basename,
                }
            return None

        # Process all files concurrently
        tasks = [loop.run_in_executor(None, process_file, img_path) for img_path in all_files]
        results = await asyncio.gather(*tasks)

        # Filter out None results
        sequential_files = [r for r in results if r is not None]

        # Group by prefix
        prefix_groups = {}
        for file_info in sequential_files:
            prefix = file_info["prefix"]
            if prefix not in prefix_groups:
                prefix_groups[prefix] = []
            prefix_groups[prefix].append(file_info)

        # Process each prefix group
        for prefix, files in prefix_groups.items():
            files.sort(key=lambda x: x["number"])

            # Check for sequential pairs
            for i in range(0, len(files) - 1, 2):
                if i + 1 < len(files):
                    front = files[i]
                    back = files[i + 1]

                    # Verify consecutive numbers
                    if back["number"] == front["number"] + 1:
                        group_key = f"Card_{str(front['number']).zfill(3)}"

                        group = ImageGroup(
                            key=group_key,
                            paths=[front["path"], back["path"]],
                            is_sequential_pair=True,
                            front_idx=0,
                            back_idx=1,
                        )

                        groups.append(group)
                        processed_files.add(front["path"])
                        processed_files.add(back["path"])

        return groups

    async def _group_remaining_files_async(
        self, all_files: List[str], processed_files: set
    ) -> List[ImageGroup]:
        """Group remaining files using various patterns with async processing"""
        groups = []
        remaining_files = [f for f in all_files if f not in processed_files]

        if not remaining_files:
            return groups

        loop = asyncio.get_event_loop()

        def process_remaining_file(img_path: str):
            basename = Path(img_path).name
            group_key = None

            # Try each pattern
            for pattern_name, pattern in self.regex_patterns.items():
                if pattern_name == "sequential":  # Already processed
                    continue
                match = pattern.match(basename)
                if match:
                    group_key = match.group(1).strip()
                    break

            # Fallback to stem
            if not group_key:
                group_key = Path(basename).stem

            return img_path, group_key

        # Process all remaining files concurrently
        tasks = [
            loop.run_in_executor(None, process_remaining_file, img_path)
            for img_path in remaining_files
        ]
        results = await asyncio.gather(*tasks)

        # Group files by key
        groups_dict = {}
        for img_path, group_key in results:
            if group_key not in groups_dict:
                groups_dict[group_key] = []
            groups_dict[group_key].append(img_path)

        # Create ImageGroup objects
        for group_key, paths in groups_dict.items():
            groups.append(ImageGroup(key=group_key, paths=paths, is_sequential_pair=False))

        return groups

    async def _optimize_images_async(self, image_files: List[str]) -> List[str]:
        """Optimize images asynchronously for eBay performance"""
        if not image_files:
            return image_files

        # Convert string paths to Path objects
        image_paths = [Path(file_path) for file_path in image_files]

        # Optimize images concurrently
        optimized_paths = await self.image_optimizer.optimize_image_list(
            image_paths, create_backup=False
        )

        # Log optimization results
        stats = self.image_optimizer.get_optimization_stats()
        if stats["optimized_count"] > 0:
            logger.info(
                f"✅ Automatically optimized {stats['optimized_count']} images, "
                f"saved {stats['total_size_saved_mb']:.1f}MB total"
            )
            logger.info("   💡 Images are now optimized for fast eBay upload and processing")

        # Convert back to string paths
        return [str(path) for path in optimized_paths]
