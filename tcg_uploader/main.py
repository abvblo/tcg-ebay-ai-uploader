#!/usr/bin/env python3
"""TCG eBay Batch Uploader - Main Entry Point"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from .config import Config
from .cache import CacheManager
from .processing.group_detector import ImageGroupDetector
from .processing.card_identifier import CardIdentifier
from .output.excel_generator import ExcelGenerator
from .utils.logger import logger
from .utils.metrics import MetricsTracker

class TCGUploader:
    def __init__(self, config_path: str = "config.json"):
        """Initialize the uploader"""
        self.config = Config(config_path)
        self.cache = CacheManager(self.config.cache_folder, self.config.processing)
        self.metrics = MetricsTracker()
        
        # Initialize components
        self.group_detector = ImageGroupDetector(self.config)
        self.card_identifier = CardIdentifier(self.config, self.cache, self.metrics)
        self.excel_generator = ExcelGenerator(self.config)
    
    async def run(self):
        """Main processing loop"""
        logger.info("🚀 TCG Batch Uploader Starting...")
        logger.info("=" * 50)
        
        self.metrics.start_processing()
        
        try:
            # Find and group images
            image_groups = await self.group_detector.find_groups()
            if not image_groups:
                logger.error("❌ No images found in Scans folder.")
                return
            
            logger.info(f"📁 Found {len(image_groups)} cards to process")
            
            # Process cards
            results = await self.card_identifier.process_groups(image_groups)
            
            if not results:
                logger.error("❌ No cards were successfully processed.")
                return
            
            # Generate output
            logger.info("\n📄 Generating Excel file...")
            output_path = await self.excel_generator.create_excel(results)
            
            # Print summary
            self.metrics.print_summary(len(results))
            logger.info(f"📄 Output saved to: {output_path}")
            
        finally:
            # Cleanup
            self.cache.close_all()
    
    async def cleanup(self):
        """Cleanup resources"""
        self.cache.close_all()
        logger.info("✅ Cleanup completed")

async def main():
    """Main entry point"""
    uploader = None
    
    try:
        uploader = TCGUploader()
        await uploader.run()
    except KeyboardInterrupt:
        logger.info("\n🛑 Processing interrupted by user")
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if uploader:
            await uploader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())