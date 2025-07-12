"""Image processing and optimization utilities"""

from io import BytesIO
from pathlib import Path
from typing import Tuple

import aiofiles
from PIL import Image, ImageOps

from .async_image_processor import AsyncImageProcessor


class ImageProcessor(AsyncImageProcessor):
    """Enhanced image processor with async capabilities"""

    def __init__(self, max_dimension: int = 1600):
        # Initialize with more workers for better concurrency
        super().__init__(max_dimension=max_dimension, max_workers=4)

    # The parent class already provides optimize_for_upload as an async method
    # We just inherit it and can use all the enhanced async functionality
