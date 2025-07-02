"""Main entry point for TCG eBay uploader"""

import asyncio
import sys
import gc
from typing import List, Dict
from collections import defaultdict

from .config import Config
from .cache import CacheManager
from .models import ImageGroup, CardData
from .processing.group_detector import ImageGroupDetector
from .processing.card_identifier import CardIdentifier
from .output.excel_generator import ExcelGenerator
from .output.review_generator import ReviewGenerator
from .utils.logger import logger
from .utils.metrics import MetricsTracker

async def main():
    """Main processing function"""
    try:
        # Initialize
        logger.info("🚀 Initializing TCG eBay Batch Uploader v3.0...")
        
        config = Config()
        cache = CacheManager(config.cache_folder, config.processing)
        metrics = MetricsTracker()
        
        # Verify configuration
        if not config.ximilar_api_key:
            logger.error("❌ Missing Ximilar API key in configuration")
            return
        
        # Start processing
        metrics.start_processing()
        logger.info(f"📁 Scanning for images in: {config.scans_folder}")
        
        # Find image groups
        group_detector = ImageGroupDetector(config)
        image_groups = await group_detector.find_groups()
        
        if not image_groups:
            logger.warning("⚠️ No images found in Scans folder")
            return
        
        # Process cards
        card_identifier = CardIdentifier(config, cache, metrics)
        cards = await card_identifier.process_groups(image_groups)
        
        if not cards:
            logger.error("❌ No cards successfully processed")
            return
        
        # Group duplicate cards into variations
        cards = group_cards_into_variations(cards)
        
        # Generate Excel
        logger.info("\n📊 Generating Excel file...")
        excel_generator = ExcelGenerator(config)
        excel_path = await excel_generator.create_excel(cards)
        
        # Generate review HTML for manual verification
        review_generator = ReviewGenerator(config.output_folder)
        review_path = review_generator.generate_review_html(cards)
        
        # Print summary with variation statistics
        logger.info(f"\n✅ Successfully created: {excel_path}")
        
        # Calculate variation statistics
        single_listings = sum(1 for c in cards if not c.is_variation_parent)
        variation_listings = [c for c in cards if c.is_variation_parent]
        total_cards_in_variations = sum(c.variation_count for c in variation_listings)
        
        logger.info(f"\n📈 Listing Summary:")
        logger.info(f"   • Single listings: {single_listings}")
        logger.info(f"   • Variation listings: {len(variation_listings)}")
        if variation_listings:
            logger.info(f"   • Total cards in variations: {total_cards_in_variations}")
            logger.info(f"   • Average copies per variation: {total_cards_in_variations/len(variation_listings):.1f}")
        logger.info(f"   • Total listings created: {len(cards)}")
        
        # Print metrics summary
        metrics.print_summary(len(cards))
        
        # Cleanup
        logger.info("\n🧹 Cleaning up...")
        cache.close_all()
        gc.collect()
        
    except KeyboardInterrupt:
        logger.info("\n\n🛑 Process interrupted by user")
        raise
    except Exception as e:
        logger.error(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        raise

def group_cards_into_variations(cards: List[CardData]) -> List[CardData]:
    """Group identical cards into variation listings"""
    # Create a dictionary to group cards by their unique identifier
    card_groups = defaultdict(list)
    
    # Group cards by their unique attributes (name, set, number, finish, etc.)
    for card in cards:
        # Create a unique key for grouping identical cards
        # Include all attributes that make a card unique
        key = (
            card.name,
            card.set_name,
            card.number,
            card.rarity,
            card.finish,
            tuple(sorted(card.unique_characteristics)),  # Convert list to sorted tuple
            card.language,
            card.final_price  # Group only cards with same price
        )
        card_groups[key].append(card)
    
    # Process groups and create variation listings
    result_cards = []
    
    for key, group in card_groups.items():
        if len(group) == 1:
            # Single card - no variations needed
            result_cards.append(group[0])
        else:
            # Multiple identical cards - create variation listing
            logger.info(f"🎯 Creating variation listing for {group[0].name} ({len(group)} copies)")
            
            # Use the first card as the parent
            parent_card = group[0]
            parent_card.is_variation_parent = True
            parent_card.variation_count = len(group)
            parent_card.variations = []
            
            # Add each card as a variation
            for idx, card in enumerate(group):
                variation_data = {
                    'custom_label': f"{card.name[:20]}_{card.set_name[:10]}_{idx+1}".replace(' ', '_'),
                    'quantity': 1,
                    'copy_number': idx + 1,
                    'image_urls': card.image_urls,
                    'primary_image_url': card.primary_image_url
                }
                parent_card.variations.append(variation_data)
            
            result_cards.append(parent_card)
    
    logger.info(f"📦 Grouped {len(cards)} cards into {len(result_cards)} listings")
    return result_cards


if __name__ == "__main__":
    asyncio.run(main())