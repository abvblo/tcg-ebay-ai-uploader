"""
Automatic image optimization for trading card images
Optimizes images in-place during processing for optimal eBay performance
"""

import os
import shutil
from pathlib import Path
from PIL import Image
from typing import List, Optional, Tuple
from ..utils.logger import logger

class ImageOptimizer:
    """Handles automatic image optimization for trading card images"""
    
    def __init__(self, max_size: int = 1600, quality: int = 85, format_type: str = 'JPEG'):
        """
        Initialize image optimizer with optimal settings for eBay
        
        Args:
            max_size: Maximum size in pixels on longest side (default: 1600 - optimal for eBay)
            quality: JPEG quality 1-100 (default: 85 - good balance of quality/size)
            format_type: Output format 'JPEG' or 'PNG' (default: JPEG for smaller files)
        """
        self.max_size = max_size
        self.quality = quality
        self.format_type = format_type
        self.optimized_count = 0
        self.total_size_saved = 0
        
    def should_optimize_image(self, image_path: Path) -> bool:
        """Check if image needs optimization"""
        try:
            # Check file size first (if > 2MB, likely needs optimization)
            file_size = image_path.stat().st_size
            if file_size < 2 * 1024 * 1024:  # Less than 2MB
                return False
            
            # Check image dimensions
            with Image.open(image_path) as img:
                width, height = img.size
                max_dimension = max(width, height)
                
                # Optimize if larger than target size or if it's a large PNG
                needs_resize = max_dimension > self.max_size
                is_large_png = image_path.suffix.lower() == '.png' and file_size > 1024 * 1024  # > 1MB PNG
                
                return needs_resize or is_large_png
                
        except Exception as e:
            logger.debug(f"   Could not check optimization need for {image_path}: {e}")
            return False
    
    def optimize_image_inplace(self, image_path: Path, create_backup: bool = True) -> bool:
        """
        Optimize image in-place, replacing the original file
        
        Args:
            image_path: Path to image file to optimize
            create_backup: Whether to create a backup of original (default: True)
            
        Returns:
            bool: True if optimization was successful, False otherwise
        """
        try:
            if not self.should_optimize_image(image_path):
                return True  # No optimization needed
            
            original_size = image_path.stat().st_size
            backup_path = None
            
            # Create backup if requested
            if create_backup:
                backup_path = image_path.parent / f"{image_path.stem}_original{image_path.suffix}"
                if not backup_path.exists():
                    shutil.copy2(image_path, backup_path)
            
            # Open and optimize image
            with Image.open(image_path) as img:
                # Calculate new dimensions maintaining aspect ratio
                img.thumbnail((self.max_size, self.max_size), Image.Resampling.LANCZOS)
                
                # Convert to RGB if saving as JPEG and image has transparency
                if self.format_type == 'JPEG' and img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                
                # Determine output filename
                if self.format_type == 'JPEG' and image_path.suffix.lower() == '.png':
                    # Convert PNG to JPEG
                    new_path = image_path.with_suffix('.jpg')
                    img.save(new_path, format='JPEG', quality=self.quality, optimize=True)
                    
                    # Remove original PNG
                    image_path.unlink()
                    
                    # Update the path reference
                    optimized_path = new_path
                else:
                    # Save in same format/location
                    if self.format_type == 'JPEG':
                        img.save(image_path, format='JPEG', quality=self.quality, optimize=True)
                    else:
                        img.save(image_path, format='PNG', optimize=True)
                    
                    optimized_path = image_path
            
            # Calculate savings
            new_size = optimized_path.stat().st_size
            size_saved = original_size - new_size
            compression_ratio = (size_saved / original_size) * 100
            
            self.optimized_count += 1
            self.total_size_saved += size_saved
            
            logger.info(f"   📷 Optimized: {image_path.name} → {optimized_path.name} "
                       f"({original_size/(1024*1024):.1f}MB → {new_size/(1024*1024):.1f}MB, "
                       f"{compression_ratio:.1f}% smaller)")
            
            return True
            
        except Exception as e:
            logger.error(f"   ❌ Failed to optimize {image_path}: {e}")
            
            # Restore backup if optimization failed
            if backup_path and backup_path.exists():
                try:
                    shutil.copy2(backup_path, image_path)
                    backup_path.unlink()
                except:
                    pass
            
            return False
    
    def optimize_image_list(self, image_paths: List[Path], create_backup: bool = True) -> List[Path]:
        """
        Optimize a list of images in-place
        
        Args:
            image_paths: List of image paths to optimize
            create_backup: Whether to create backups of originals
            
        Returns:
            List[Path]: Updated paths (may have changed if format converted)
        """
        if not image_paths:
            return image_paths
        
        logger.info(f"🔧 Optimizing {len(image_paths)} images for eBay performance...")
        
        optimized_paths = []
        
        for image_path in image_paths:
            original_path = image_path
            
            # Optimize the image
            success = self.optimize_image_inplace(image_path, create_backup)
            
            if success:
                # Check if path changed (PNG -> JPEG conversion)
                if self.format_type == 'JPEG' and original_path.suffix.lower() == '.png':
                    new_path = original_path.with_suffix('.jpg')
                    if new_path.exists():
                        optimized_paths.append(new_path)
                    else:
                        optimized_paths.append(original_path)
                else:
                    optimized_paths.append(original_path)
            else:
                # Keep original path if optimization failed
                optimized_paths.append(original_path)
        
        if self.optimized_count > 0:
            logger.info(f"✅ Optimized {self.optimized_count} images, "
                       f"saved {self.total_size_saved/(1024*1024):.1f}MB total")
        
        return optimized_paths
    
    def get_optimization_stats(self) -> dict:
        """Get optimization statistics"""
        return {
            'optimized_count': self.optimized_count,
            'total_size_saved_mb': self.total_size_saved / (1024 * 1024),
            'avg_size_saved_mb': (self.total_size_saved / self.optimized_count / (1024 * 1024)) if self.optimized_count > 0 else 0
        }