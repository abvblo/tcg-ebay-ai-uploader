"""Image grouping and sequential pair detection"""

import asyncio
import glob
from pathlib import Path
from typing import List, Dict
import re
from ..models import ImageGroup
from ..config import Config
from ..utils.logger import logger
from .image_optimizer import ImageOptimizer

class ImageGroupDetector:
    def __init__(self, config: Config):
        self.config = config
        self.scans_folder = config.scans_folder
        
        # Initialize automatic image optimizer with config settings
        self.image_optimizer = ImageOptimizer(
            max_size=config.processing.optimization_max_size,
            quality=config.processing.optimization_quality,
            format_type=config.processing.optimization_format
        )
        
        # Compile regex patterns
        self.regex_patterns = {
            'sequential': re.compile(r'^(.*?)(\d+)\.(jpg|jpeg|png|webp|bmp|tiff)$', re.IGNORECASE),
            'underscore': re.compile(r'^(.*?)[\_\-\s](\d+)\.(jpg|jpeg|png|webp|bmp|tiff)$', re.IGNORECASE),
            'parentheses': re.compile(r'^(.*?)\s*\((\d+)\)\.(jpg|jpeg|png|webp|bmp|tiff)$', re.IGNORECASE),
            'hyphen': re.compile(r'^(.*?)\s*-\s*(\d+)\.(jpg|jpeg|png|webp|bmp|tiff)$', re.IGNORECASE),
            'brackets': re.compile(r'^(.*?)\s*\[\s*(\d+)\s*\]\.(jpg|jpeg|png|webp|bmp|tiff)$', re.IGNORECASE),
        }
    
    async def find_groups(self) -> List[ImageGroup]:
        """Find and group images with sequential pair detection"""
        all_files = await self._scan_for_images()
        
        if not all_files:
            return []
        
        # Automatically optimize images for eBay performance (if enabled)
        if self.config.processing.auto_optimize_images:
            logger.info("🔧 Automatically optimizing images for optimal eBay performance...")
            optimized_files = self._optimize_images_inplace(all_files)
        else:
            logger.info("⚠️ Automatic image optimization is disabled")
            optimized_files = all_files
        
        # Sort files
        all_files = sorted(optimized_files)
        
        # Group images
        groups = []
        processed_files = set()
        
        # First, detect sequential pairs
        sequential_groups = self._detect_sequential_pairs(all_files, processed_files)
        groups.extend(sequential_groups)
        
        # Handle remaining files
        remaining_groups = self._group_remaining_files(all_files, processed_files)
        groups.extend(remaining_groups)
        
        total_images = sum(len(g.paths) for g in groups)
        logger.info(f"✅ Found {len(groups)} groups containing {total_images} total images")
        
        # Log sequential pairs
        sequential_count = sum(1 for g in groups if g.is_sequential_pair)
        if sequential_count:
            logger.info(f"🎴 Detected {sequential_count} sequential pairs from scanner")
        
        return groups
    
    async def _scan_for_images(self) -> List[str]:
        """Scan for all image files"""
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
    
    def _detect_sequential_pairs(self, all_files: List[str], processed_files: set) -> List[ImageGroup]:
        """Detect sequential pairs (front/back) from scanner"""
        groups = []
        sequential_files = []
        
        # Find files matching sequential pattern
        for img_path in all_files:
            basename = Path(img_path).name
            match = self.regex_patterns['sequential'].match(basename)
            if match:
                sequential_files.append({
                    'path': img_path,
                    'prefix': match.group(1),
                    'number': int(match.group(2)),
                    'extension': match.group(3),
                    'basename': basename
                })
        
        # Group by prefix
        prefix_groups = {}
        for file_info in sequential_files:
            prefix = file_info['prefix']
            if prefix not in prefix_groups:
                prefix_groups[prefix] = []
            prefix_groups[prefix].append(file_info)
        
        # Process each prefix group
        for prefix, files in prefix_groups.items():
            files.sort(key=lambda x: x['number'])
            
            # Check for sequential pairs
            for i in range(0, len(files) - 1, 2):
                if i + 1 < len(files):
                    front = files[i]
                    back = files[i + 1]
                    
                    # Verify consecutive numbers
                    if back['number'] == front['number'] + 1:
                        group_key = f"Card_{str(front['number']).zfill(3)}"
                        
                        group = ImageGroup(
                            key=group_key,
                            paths=[front['path'], back['path']],
                            is_sequential_pair=True,
                            front_idx=0,
                            back_idx=1
                        )
                        
                        groups.append(group)
                        processed_files.add(front['path'])
                        processed_files.add(back['path'])
        
        return groups
    
    def _group_remaining_files(self, all_files: List[str], processed_files: set) -> List[ImageGroup]:
        """Group remaining files using various patterns"""
        groups = []
        remaining_files = [f for f in all_files if f not in processed_files]
        
        for img_path in remaining_files:
            basename = Path(img_path).name
            group_key = None
            
            # Try each pattern
            for pattern_name, pattern in self.regex_patterns.items():
                if pattern_name == 'sequential':  # Already processed
                    continue
                match = pattern.match(basename)
                if match:
                    group_key = match.group(1).strip()
                    break
            
            # Fallback to stem
            if not group_key:
                group_key = Path(basename).stem
            
            # Find or create group
            existing_group = next((g for g in groups if g.key == group_key and not g.is_sequential_pair), None)
            if existing_group:
                existing_group.paths.append(img_path)
            else:
                groups.append(ImageGroup(
                    key=group_key,
                    paths=[img_path],
                    is_sequential_pair=False
                ))
        
        return groups
    
    def _optimize_images_inplace(self, image_files: List[str]) -> List[str]:
        """Optimize images in-place for eBay performance"""
        if not image_files:
            return image_files
        
        # Convert string paths to Path objects
        image_paths = [Path(file_path) for file_path in image_files]
        
        # Optimize images (this modifies files in-place)
        optimized_paths = self.image_optimizer.optimize_image_list(image_paths, create_backup=False)
        
        # Log optimization results
        stats = self.image_optimizer.get_optimization_stats()
        if stats['optimized_count'] > 0:
            logger.info(f"✅ Automatically optimized {stats['optimized_count']} images, "
                       f"saved {stats['total_size_saved_mb']:.1f}MB total")
            logger.info("   💡 Images are now optimized for fast eBay upload and processing")
        
        # Convert back to string paths
        return [str(path) for path in optimized_paths]