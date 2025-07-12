"""Scrape Base Set Unlimited images from TCGPlayer"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import aiohttp
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import DatabaseConfig, PokemonCard, PokemonSet, get_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UnlimitedImageScraper:
    """Scrape unlimited edition images for Base Set cards"""

    def __init__(self):
        self.base_url = "https://www.tcgplayer.com/product"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

        # Base Set Unlimited TCGPlayer product IDs (manually gathered)
        # Format: card_number: tcgplayer_product_id
        self.unlimited_product_ids = {
            "1": "42375",  # Alakazam
            "2": "42376",  # Blastoise
            "3": "42377",  # Chansey
            "4": "42378",  # Charizard
            "5": "42379",  # Clefairy
            "6": "42380",  # Gyarados
            "7": "42381",  # Hitmonchan
            "8": "42382",  # Machamp
            "9": "42383",  # Magneton
            "10": "42384",  # Mewtwo
            "11": "42385",  # Nidoking
            "12": "42386",  # Ninetales
            "13": "42387",  # Poliwrath
            "14": "42388",  # Raichu
            "15": "42389",  # Venusaur
            "16": "42390",  # Zapdos
            # Add more as needed - these are examples
        }

    async def search_tcgplayer_for_card(
        self, session: aiohttp.ClientSession, card_name: str, card_number: str
    ):
        """Search TCGPlayer for a specific Base Set Unlimited card"""
        search_query = f"{card_name} Base Set Unlimited {card_number}"
        search_url = f"https://www.tcgplayer.com/search/pokemon/base-set?q={quote(search_query)}"

        try:
            async with session.get(search_url, headers=self.headers) as response:
                if response.status == 200:
                    html = await response.text()
                    # Extract product ID from search results
                    # This would need HTML parsing
                    logger.info(f"Searched for: {search_query}")
                    return None
        except Exception as e:
            logger.error(f"Search failed for {card_name}: {e}")
            return None

    async def download_from_tcgplayer(
        self, session: aiohttp.ClientSession, card: PokemonCard, output_dir: Path
    ):
        """Download unlimited edition image from TCGPlayer"""

        card_number = card.number
        if card_number not in self.unlimited_product_ids:
            # Try to search for it
            product_id = await self.search_tcgplayer_for_card(session, card.name, card_number)
            if not product_id:
                return False
        else:
            product_id = self.unlimited_product_ids[card_number]

        # TCGPlayer image URL pattern
        image_url = f"https://product-images.tcgplayer.com/fit-in/400x558/{product_id}.jpg"

        output_path = output_dir / f"{card_number}.png"

        try:
            async with session.get(image_url, headers=self.headers) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(output_path, "wb") as f:
                        f.write(content)
                    logger.info(f"✓ Downloaded unlimited: {card.name} #{card_number}")
                    return True
                else:
                    logger.warning(f"Failed to download {card.name}: HTTP {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error downloading {card.name}: {e}")
            return False

    async def scrape_unlimited_images(self):
        """Main scraping function"""

        # Database connection
        connection_string = DatabaseConfig.get_connection_string(
            host="localhost", database="pokemon_tcg", username="mateoallen", password=""
        )

        engine = create_engine(connection_string)
        session = get_session(engine)

        try:
            # Setup directories
            project_root = Path(__file__).parent.parent.parent
            unlimited_dir = (
                project_root / "assets" / "images" / "pokemon" / "english" / "base-unlimited"
            )
            unlimited_dir.mkdir(parents=True, exist_ok=True)

            # Get Base Set cards
            base_set = session.query(PokemonSet).filter_by(name="Base Set").first()
            if not base_set:
                logger.error("Base Set not found in database!")
                return

            cards = (
                session.query(PokemonCard)
                .filter_by(set_id=base_set.id)
                .order_by(PokemonCard.number.cast(Integer))
                .all()
            )

            logger.info(f"Found {len(cards)} Base Set cards to process")

            downloaded = 0
            failed = []

            async with aiohttp.ClientSession() as http_session:
                for card in cards:
                    success = await self.download_from_tcgplayer(http_session, card, unlimited_dir)
                    if success:
                        downloaded += 1
                    else:
                        failed.append(f"{card.name} #{card.number}")

                    # Rate limiting
                    await asyncio.sleep(1)

            logger.info(f"\n=== UNLIMITED SCRAPING COMPLETE ===")
            logger.info(f"Downloaded: {downloaded} images")
            logger.info(f"Failed: {len(failed)} images")

            if failed:
                logger.info("Failed cards:")
                for card in failed[:10]:
                    logger.info(f"  - {card}")

            # Create mapping file
            mapping = {
                "source": "TCGPlayer",
                "timestamp": datetime.now().isoformat(),
                "edition": "unlimited",
                "cards_downloaded": downloaded,
                "product_ids": self.unlimited_product_ids,
            }

            with open(unlimited_dir / "mapping.json", "w") as f:
                json.dump(mapping, f, indent=2)

        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            raise
        finally:
            session.close()


# Alternative approach using a card image repository
async def download_from_repository():
    """Alternative: Download from a community repository of card scans"""

    # Some collectors share high-quality scans on:
    # 1. Archive.org collections
    # 2. Google Drive shares
    # 3. Discord communities
    # 4. Reddit communities (r/pkmntcgcollections)

    # Example: Using archive.org Pokemon card scans
    archive_urls = {
        "base_set_unlimited": "https://archive.org/download/pokemon-base-set-unlimited-scans",
        # This is a hypothetical URL - you'd need to find actual archives
    }

    logger.info("Note: Community repositories often have the highest quality scans")
    logger.info("Check Pokemon collector forums and Discord servers for scan collections")


if __name__ == "__main__":
    scraper = UnlimitedImageScraper()

    print("\n=== Base Set Unlimited Image Scraper ===")
    print("\nThis script will attempt to download Base Set Unlimited images.")
    print("Note: TCGPlayer rate limits requests, so this will be slow.")
    print("\nAlternative sources to consider:")
    print("1. Bulbapedia - Has individual card pages with edition variants")
    print("2. Pokemon collector Discord servers - Often share high-quality scans")
    print("3. Archive.org - May have complete scan collections")
    print("4. eBay listings - Often show actual unlimited edition cards")

    choice = input("\nProceed with TCGPlayer scraping? (y/n): ")
    if choice.lower() == "y":
        asyncio.run(scraper.scrape_unlimited_images())
    else:
        print("\nConsider manually downloading from collector communities for best results.")
