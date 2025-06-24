"""Image processing and optimization utilities"""

from PIL import Image, ImageOps
from io import BytesIO
from pathlib import Path
from typing import Tuple
import aiofiles

class ImageProcessor:
    def __init__(self, max_dimension: int = 1600):
        self.max_dimension = max_dimension
    
    async def optimize_for_upload(self, image_path: str) -> Tuple[bytes, str, str]:
        """Optimize image for upload - returns (data, content_type, extension)"""
        try:
            # Read image data
            async with aiofiles.open(image_path, 'rb') as f:
                image_data = await f.read()
            
            with Image.open(BytesIO(image_data)) as img:
                # Handle EXIF orientation
                img = ImageOps.exif_transpose(img)
                
                # Convert to appropriate mode
                if img.mode not in ('RGBA', 'RGB'):
                    if img.mode in ('P', 'LA'):
                        img = img.convert('RGBA')
                    else:
                        img = img.convert('RGB')
                
                # Scale if needed
                width, height = img.size
                if width > self.max_dimension or height > self.max_dimension:
                    ratio = min(self.max_dimension / width, self.max_dimension / height)
                    new_width = int(width * ratio)
                    new_height = int(height * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save as PNG for best quality
                output = BytesIO()
                img.save(output, format='PNG', optimize=True)
                return output.getvalue(), 'image/png', '.png'
                
        except Exception:
            # Return original if optimization fails
            async with aiofiles.open(image_path, 'rb') as f:
                data = await f.read()
            ext = Path(image_path).suffix.lower()
            content_type = 'image/png' if ext == '.png' else 'image/jpeg'
            return data, content_type, ext