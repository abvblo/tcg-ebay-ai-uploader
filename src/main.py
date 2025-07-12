"""Main entry point for TCG eBay uploader"""

import asyncio
import gc
import sys
from collections import defaultdict
from typing import Dict, List

# Flexible imports that work both as package and direct execution
try:
    from .cache import CacheManager
    from .config import Config
    from .database.optimized_service import OptimizedDatabaseService
    from .models import CardData, ImageGroup
    from .output.excel_generator import ExcelGenerator
    from .output.review_generator import ReviewGenerator
    from .processing.card_identifier import CardIdentifier
    from .processing.group_detector import ImageGroupDetector
    from .utils.logger import logger
    from .utils.metrics import MetricsTracker
    from .utils.performance_monitor import performance_monitor
except ImportError:
    # Direct execution fallback - run from root directory using src module
    import sys
    from pathlib import Path

    # Add parent directory to path so we can import src module
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from src.cache import CacheManager
    from src.config import Config
    from src.database.optimized_service import OptimizedDatabaseService
    from src.models import CardData, ImageGroup
    from src.output.excel_generator import ExcelGenerator
    from src.output.review_generator import ReviewGenerator
    from src.processing.card_identifier import CardIdentifier
    from src.processing.group_detector import ImageGroupDetector
    from src.utils.logger import logger
    from src.utils.metrics import MetricsTracker
    from src.utils.performance_monitor import performance_monitor


async def main():
    """Main processing function"""
    try:
        # Initialize
        logger.info("🚀 Initializing TCG eBay Batch Uploader v3.0...")

        config = Config()

        # Initialize optimized database service with configuration
        db_service = OptimizedDatabaseService(
            connection_string=config.database_url,
            pool_size=config.database_pool_size,
            max_overflow=config.database_max_overflow,
        )
        logger.info("💾 Database service initialized with configured settings")

        # Initialize cache with database integration
        cache = CacheManager(config.cache_folder, config.processing, db_service)
        metrics = MetricsTracker()

        # Sync cache with database
        cache.sync_with_database()

        # Verify configuration
        if not config.ximilar_api_key:
            logger.error("❌ Missing Ximilar API key in configuration")
            return

        # Start processing timer
        metrics.start_timer("total_processing")
        performance_monitor.start_operation("total_processing")
        logger.info(f"📁 Scanning for images in: {config.scans_folder}")

        # Find image groups
        perf_scan = performance_monitor.start_operation("image_scanning")
        group_detector = ImageGroupDetector(config)
        image_groups = await group_detector.find_groups()
        performance_monitor.end_operation("image_scanning", operations=len(image_groups))

        if not image_groups:
            logger.warning("⚠️ No images found in input folder")
            return

        # Process cards
        perf_cards = performance_monitor.start_operation("card_processing")
        card_identifier = CardIdentifier(config, cache, metrics)
        cards = await card_identifier.process_groups(image_groups)
        performance_monitor.end_operation(
            "card_processing",
            operations=len(cards) if cards else 0,
            errors=len(image_groups) - len(cards) if cards else len(image_groups),
        )

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
            # Add check for empty variation_listings to prevent division by zero
            if len(variation_listings) > 0:
                logger.info(
                    f"   • Average copies per variation: {total_cards_in_variations/len(variation_listings):.1f}"
                )
        logger.info(f"   • Total listings created: {len(cards)}")

        # End processing timer and print metrics summary
        metrics.end_timer("total_processing")
        performance_monitor.end_operation("total_processing", operations=len(cards))
        logger.info(metrics.get_summary())

        # Print performance report
        performance_monitor.print_report()

        # Print database statistics
        db_stats = db_service.get_database_stats()
        if db_stats:
            logger.info(f"\n💾 Database Statistics:")
            logger.info(f"   • Total cards in database: {db_stats['total_cards']}")
            logger.info(f"   • Total sets in database: {db_stats['total_sets']}")
            logger.info(f"   • Total variations: {db_stats['total_variations']}")
            logger.info(f"   • Total price snapshots: {db_stats['total_price_snapshots']}")
            logger.info(f"   • Corrections applied: {db_stats['corrections_count']}")
            if db_stats["last_update"]:
                logger.info(f"   • Last database update: {db_stats['last_update']}")

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
            card.final_price,  # Group only cards with same price
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
                    "custom_label": f"{card.name[:20]}_{card.set_name[:10]}_{idx+1}".replace(
                        " ", "_"
                    ),
                    "quantity": 1,
                    "copy_number": idx + 1,
                    "image_urls": card.image_urls,
                    "primary_image_url": card.primary_image_url,
                }
                parent_card.variations.append(variation_data)

            result_cards.append(parent_card)

    logger.info(f"📦 Grouped {len(cards)} cards into {len(result_cards)} listings")
    return result_cards


if __name__ == "__main__":
    asyncio.run(main())
