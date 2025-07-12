"""Japanese Pokemon Card Downloader using Pokemon TCG API for Japanese sets"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JapaneseCardDownloader:
    """Download Japanese Pokemon cards from Pokemon TCG API"""

    def __init__(self, download_dir: str = "japanese_cards", api_key: str = None):
        self.base_url = "https://api.pokemontcg.io/v2"
        self.api_key = api_key
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.session = None
        self.downloaded_count = 0
        self.failed_count = 0
        self.rate_limit = 1.0  # 1 second between requests

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def download_all_japanese_cards(self):
        """Download all Japanese Pokemon cards organized by set"""
        logger.info("Starting Japanese Pokemon card download...")

        # Get all sets
        sets = await self.get_all_sets()
        if not sets:
            logger.error("Failed to fetch sets from TCGdx API")
            return

        logger.info(f"Found {len(sets)} sets to download")

        # Process each set
        for set_data in sets:
            set_id = set_data.get("id")
            set_name = set_data.get("name")

            if not set_id or not set_name:
                continue

            logger.info(f"Processing set: {set_name} ({set_id})")

            # Create set directory
            set_dir = self.download_dir / self._sanitize_filename(set_name)
            set_dir.mkdir(exist_ok=True)

            # Download cards for this set
            await self.download_set_cards(set_id, set_name, set_dir)

            # Rate limiting between sets
            await asyncio.sleep(self.rate_limit)

        logger.info(
            f"Download complete! Downloaded: {self.downloaded_count}, Failed: {self.failed_count}"
        )

    async def get_all_sets(self) -> List[Dict[str, Any]]:
        """Get all Pokemon sets from Pokemon TCG API, focusing on Japanese sets"""
        try:
            headers = {"X-Api-Key": self.api_key} if self.api_key else {}
            url = f"{self.base_url}/sets"

            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    all_sets = data.get("data", [])

                    # Filter for Japanese sets or sets with Japanese variants
                    japanese_sets = []
                    for set_data in all_sets:
                        set_name = set_data.get("name", "").lower()
                        set_id = set_data.get("id", "")

                        # Look for Japanese indicators in set names or IDs
                        if any(
                            indicator in set_name for indicator in ["japan", "japanese", "jp"]
                        ) or any(indicator in set_id for indicator in ["jp", "japanese"]):
                            japanese_sets.append(set_data)

                    logger.info(
                        f"Found {len(japanese_sets)} Japanese sets out of {len(all_sets)} total sets"
                    )
                    return japanese_sets
                else:
                    logger.error(f"Failed to fetch sets: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching sets: {e}")
            return []

    async def download_set_cards(self, set_id: str, set_name: str, set_dir: Path):
        """Download all cards for a specific set"""
        try:
            # Get all cards for this set
            url = f"{self.base_url}/sets/{set_id}/cards"
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch cards for set {set_id}: {response.status}")
                    return

                cards = await response.json()
                if not isinstance(cards, list):
                    logger.error(f"Invalid response format for set {set_id}")
                    return

                logger.info(f"  Found {len(cards)} cards in {set_name}")

                # Download each card
                for card in cards:
                    await self.download_card_image(card, set_dir, set_name)
                    await asyncio.sleep(self.rate_limit)

        except Exception as e:
            logger.error(f"Error downloading set {set_id}: {e}")

    async def download_card_image(self, card: Dict[str, Any], set_dir: Path, set_name: str):
        """Download a single card image with consistent naming"""
        try:
            card_name = card.get("name", "Unknown")
            card_number = card.get("localId", card.get("id", "Unknown"))

            # Get the image URL
            image_url = self._get_best_image_url(card)
            if not image_url:
                logger.warning(f"  No image URL found for {card_name}")
                self.failed_count += 1
                return

            # Generate filename using consistent naming convention
            filename = self._generate_filename(card_name, card_number, set_name)
            file_path = set_dir / filename

            # Skip if already downloaded
            if file_path.exists():
                logger.debug(f"  Skipping {filename} (already exists)")
                return

            # Download the image
            async with self.session.get(image_url) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(file_path, "wb") as f:
                        f.write(content)

                    logger.info(f"  Downloaded: {filename}")
                    self.downloaded_count += 1
                else:
                    logger.warning(f"  Failed to download {filename}: {response.status}")
                    self.failed_count += 1

        except Exception as e:
            logger.error(f"Error downloading card {card.get('name', 'Unknown')}: {e}")
            self.failed_count += 1

    def _get_best_image_url(self, card: Dict[str, Any]) -> Optional[str]:
        """Get the best quality image URL for a card"""
        image_data = card.get("image")
        if not image_data:
            return None

        # TCGdx provides images in different formats and qualities
        # Priority: high quality PNG > high quality JPG > low quality

        # Check for high quality images first
        if isinstance(image_data, dict):
            # Try different image formats in order of preference
            formats = ["png", "jpg", "webp"]
            qualities = ["high", "low"]

            for quality in qualities:
                for fmt in formats:
                    if quality in image_data and fmt in image_data[quality]:
                        return image_data[quality][fmt]

        # Fallback to any available image
        if isinstance(image_data, str):
            return image_data

        return None

    def _generate_filename(self, card_name: str, card_number: str, set_name: str) -> str:
        """Generate consistent filename following existing conventions"""
        # Clean card name
        clean_name = self._sanitize_filename(card_name)

        # Clean card number
        clean_number = str(card_number).replace("/", "_")

        # Clean set name
        clean_set = self._sanitize_filename(set_name)

        # Follow existing naming pattern: CardName_Number_SetName_JP.png
        filename = f"{clean_name}_{clean_number}_{clean_set}_JP.png"

        # Ensure filename isn't too long
        if len(filename) > 255:
            # Truncate card name if needed
            max_name_length = 255 - len(f"_{clean_number}_{clean_set}_JP.png")
            clean_name = clean_name[:max_name_length]
            filename = f"{clean_name}_{clean_number}_{clean_set}_JP.png"

        return filename

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for cross-platform compatibility"""
        # Remove or replace problematic characters
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

        # Replace spaces with underscores
        filename = filename.replace(" ", "_")

        # Remove multiple consecutive underscores
        filename = re.sub(r"_+", "_", filename)

        # Remove leading/trailing underscores
        filename = filename.strip("_")

        return filename

    async def download_specific_set(self, set_id: str):
        """Download cards from a specific set only"""
        logger.info(f"Downloading specific set: {set_id}")

        # Get set info
        try:
            url = f"{self.base_url}/sets/{set_id}"
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch set {set_id}: {response.status}")
                    return

                set_data = await response.json()
                set_name = set_data.get("name", set_id)

                # Create set directory
                set_dir = self.download_dir / self._sanitize_filename(set_name)
                set_dir.mkdir(exist_ok=True)

                # Download cards
                await self.download_set_cards(set_id, set_name, set_dir)

        except Exception as e:
            logger.error(f"Error downloading set {set_id}: {e}")

    def get_download_stats(self) -> Dict[str, int]:
        """Get download statistics"""
        return {
            "downloaded": self.downloaded_count,
            "failed": self.failed_count,
            "total_attempted": self.downloaded_count + self.failed_count,
        }


async def main():
    """Main function to run the downloader"""
    # Create download directory
    download_dir = "japanese_pokemon_cards"

    logger.info("Starting Japanese Pokemon card download...")

    async with JapaneseCardDownloader(download_dir) as downloader:
        # Download all sets
        await downloader.download_all_japanese_cards()

        # Print final stats
        stats = downloader.get_download_stats()
        logger.info(f"Final Statistics:")
        logger.info(f"  Downloaded: {stats['downloaded']}")
        logger.info(f"  Failed: {stats['failed']}")
        logger.info(f"  Total Attempted: {stats['total_attempted']}")

        if stats["total_attempted"] > 0:
            success_rate = (stats["downloaded"] / stats["total_attempted"]) * 100
            logger.info(f"  Success Rate: {success_rate:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
