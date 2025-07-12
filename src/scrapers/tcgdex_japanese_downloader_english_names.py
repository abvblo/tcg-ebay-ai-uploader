"""Japanese Pokemon Card Downloader using TCGdex SDK with English Names"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

# TCGdex SDK imports
from tcgdexsdk import Language, Query, TCGdex

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TCGdexJapaneseDownloaderEnglish:
    """Download Japanese Pokemon cards using TCGdex SDK with English file names"""

    def __init__(self, download_dir: str = "japanese_cards_english_names"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)

        # Initialize TCGdex SDK for both Japanese and English
        self.tcgdex_ja = TCGdex(Language.JA)
        self.tcgdex_en = TCGdex(Language.EN)

        # Statistics
        self.downloaded_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.rate_limit = 1.0  # 1 second between requests

        # Create metadata file
        self.metadata_file = self.download_dir / "japanese_cards_metadata.json"
        self.metadata = self._load_metadata()

        # Cache for English card lookups
        self.english_name_cache = {}

    def _load_metadata(self) -> Dict[str, Any]:
        """Load existing metadata"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metadata: {e}")

        return {"sets": {}, "cards": {}, "download_history": [], "last_updated": None}

    def _save_metadata(self):
        """Save metadata to file"""
        try:
            self.metadata["last_updated"] = datetime.now().isoformat()
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    async def get_english_card_info(self, japanese_card, set_id: str) -> Tuple[str, str]:
        """Get English card name and set code from Japanese card data"""
        try:
            # For CardResume objects, we need to use the passed set_id
            card_set_id = set_id if not hasattr(japanese_card, "set") else japanese_card.set.id
            card_number = japanese_card.localId

            # Check cache first
            cache_key = f"{card_set_id}_{card_number}"
            if cache_key in self.english_name_cache:
                return self.english_name_cache[cache_key]

            # Try to find the English equivalent
            # First, get the English set
            english_set = await self.tcgdex_en.set.get(card_set_id)
            if not english_set:
                # If no direct match, use the Japanese set ID
                logger.debug(f"No English set found for {card_set_id}")
                return (self._clean_card_name(japanese_card.name), card_set_id)

            # Get English cards from the set
            english_cards = await self.tcgdex_en.card.list(Query().equal("set.id", english_set.id))

            # Find matching card by number
            english_card = None
            for card in english_cards:
                if card.localId == card_number:
                    english_card = card
                    break

            if english_card:
                result = (english_card.name, english_set.id)
            else:
                # Fallback to Japanese name transliterated
                result = (self._clean_card_name(japanese_card.name), english_set.id)

            # Cache the result
            self.english_name_cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"Error getting English card info: {e}")
            return (self._clean_card_name(japanese_card.name), card_set_id)

    def _clean_card_name(self, name: str) -> str:
        """Clean card name for use in filename"""
        # Remove special characters and replace with underscores
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"[-\s]+", "_", name)
        return name

    async def download_all_japanese_cards(self):
        """Download all Japanese Pokemon cards with English names"""
        logger.info("Starting Japanese Pokemon card download with English naming...")

        try:
            # Get all Japanese sets
            sets = await self.tcgdex_ja.set.list()

            if not sets:
                logger.error("No sets found from TCGdex API")
                return

            logger.info(f"Found {len(sets)} Japanese sets to download")

            # Process each set
            for set_data in sets:
                await self.download_set_cards(set_data)

                # Rate limiting between sets
                await asyncio.sleep(self.rate_limit)

            # Save final metadata
            self._save_metadata()

            logger.info(
                f"Download complete! Downloaded: {self.downloaded_count}, Failed: {self.failed_count}, Skipped: {self.skipped_count}"
            )

        except Exception as e:
            logger.error(f"Error during download: {e}")
            self._save_metadata()

    async def download_set_cards(self, set_data):
        """Download all cards for a specific set"""
        try:
            set_id = set_data.id
            set_name = set_data.name

            logger.info(f"Processing Japanese set: {set_name} ({set_id})")

            # Get all cards for this set
            cards = await self.tcgdex_ja.card.list(Query().equal("set.id", set_id))

            if not cards:
                logger.debug(f"No cards found for set {set_id}")
                return

            logger.info(f"  Found {len(cards)} cards in {set_name}")

            # Store set metadata
            self.metadata["sets"][set_id] = {
                "name": set_name,
                "id": set_id,
                "processed_at": datetime.now().isoformat(),
                "card_count": len(cards),
                "downloaded_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
            }

            # Download each card
            for card in cards:
                success = await self.download_card_image(card, set_id)

                if success == "downloaded":
                    self.metadata["sets"][set_id]["downloaded_count"] += 1
                    self.downloaded_count += 1
                elif success == "skipped":
                    self.metadata["sets"][set_id]["skipped_count"] += 1
                    self.skipped_count += 1
                else:
                    self.metadata["sets"][set_id]["failed_count"] += 1
                    self.failed_count += 1

                # Rate limiting between cards
                await asyncio.sleep(0.5)

            # Save progress after each set
            self._save_metadata()

        except Exception as e:
            logger.error(f"Error processing set {set_data.id}: {e}")

    async def download_card_image(self, card, set_id: str) -> str:
        """Download a single card image with English naming"""
        try:
            # Handle both Card and CardResume objects
            if hasattr(card, "id"):
                card_id = card.id
            else:
                # For CardResume, create a unique ID
                card_id = f"{set_id}_{card.localId}"

            # Get the full card details if this is a CardResume
            if not hasattr(card, "name"):
                # Fetch full card details
                full_card = await self.tcgdex_ja.card.get(card_id)
                if full_card:
                    card = full_card
                else:
                    logger.error(f"Could not fetch full details for card {card_id}")
                    return "failed"

            japanese_name = card.name
            card_number = card.localId

            # Get English card info
            english_name, english_set_code = await self.get_english_card_info(card, set_id)

            # Create set directory using English set code
            set_dir = self.download_dir / english_set_code
            set_dir.mkdir(exist_ok=True)

            # Generate filename following the convention: Number_EnglishCardName.png
            filename = f"{card_number}_{english_name}.png"
            file_path = set_dir / filename

            # Store card metadata
            self.metadata["cards"][card_id] = {
                "id": card_id,
                "japanese_name": japanese_name,
                "english_name": english_name,
                "number": card_number,
                "set_code": english_set_code,
                "filename": filename,
                "file_path": str(file_path),
                "downloaded_at": datetime.now().isoformat(),
                "rarity": getattr(card, "rarity", None),
                "hp": getattr(card, "hp", None),
                "types": getattr(card, "types", []),
                "artist": getattr(card, "illustrator", None),
            }

            # Skip if already downloaded
            if file_path.exists():
                logger.debug(f"  Skipping {filename} (already exists)")
                return "skipped"

            # Get the best image URL
            image_url = self._get_best_image_url(card)
            if not image_url:
                logger.warning(f"  No image URL for {english_name}")
                return "failed"

            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(file_path, "wb") as f:
                            f.write(content)

                        logger.info(f"  Downloaded: {english_set_code}/{filename}")
                        return "downloaded"
                    else:
                        # Try low quality as fallback
                        if "/high.png" in image_url:
                            fallback_url = image_url.replace("/high.png", "/low.png")
                            logger.debug(f"  Trying low quality fallback: {fallback_url}")

                            async with session.get(fallback_url) as fallback_response:
                                if fallback_response.status == 200:
                                    content = await fallback_response.read()
                                    with open(file_path, "wb") as f:
                                        f.write(content)

                                    logger.info(
                                        f"  Downloaded (low quality): {english_set_code}/{filename}"
                                    )
                                    return "downloaded"

                        logger.warning(f"  Failed to download {filename}: {response.status}")
                        return "failed"

        except Exception as e:
            logger.error(f"Error downloading card {card.name}: {e}")
            return "failed"

    def _get_best_image_url(self, card) -> Optional[str]:
        """Get the best quality image URL for a card"""
        try:
            # TCGdex provides base URLs that need quality and format appended
            if hasattr(card, "image") and card.image:
                base_url = card.image if isinstance(card.image, str) else str(card.image)
                # Return high quality PNG URL
                return f"{base_url}/high.png"

            return None

        except Exception as e:
            logger.error(f"Error getting image URL for card: {e}")
            return None

    async def download_specific_set(self, set_id: str):
        """Download cards from a specific set only"""
        logger.info(f"Downloading specific Japanese set with English names: {set_id}")

        try:
            # Get set info
            set_data = await self.tcgdex_ja.set.get(set_id)
            if not set_data:
                logger.error(f"Set {set_id} not found")
                return

            # Download cards for this set
            await self.download_set_cards(set_data)

        except Exception as e:
            logger.error(f"Error downloading set {set_id}: {e}")

    def get_download_stats(self) -> Dict[str, int]:
        """Get download statistics"""
        return {
            "downloaded": self.downloaded_count,
            "failed": self.failed_count,
            "skipped": self.skipped_count,
            "total_attempted": self.downloaded_count + self.failed_count + self.skipped_count,
        }

    def print_final_stats(self):
        """Print final download statistics"""
        print("\n" + "=" * 60)
        print("JAPANESE POKEMON CARD DOWNLOAD COMPLETE (English Names)")
        print("=" * 60)
        print(f"Cards Downloaded: {self.downloaded_count}")
        print(f"Cards Failed: {self.failed_count}")
        print(f"Cards Skipped: {self.skipped_count}")
        print(f"Total Cards: {self.downloaded_count + self.failed_count + self.skipped_count}")

        if self.downloaded_count + self.failed_count > 0:
            success_rate = (
                self.downloaded_count / (self.downloaded_count + self.failed_count)
            ) * 100
            print(f"Success Rate: {success_rate:.1f}%")

        print(f"Download Directory: {self.download_dir.absolute()}")
        print(f"Metadata File: {self.metadata_file.absolute()}")
        print("=" * 60)


async def main():
    """Main function to run the downloader"""
    logger.info("Starting Japanese Pokemon card download with English naming...")

    downloader = TCGdexJapaneseDownloaderEnglish("japanese_cards_english_names")

    # Download all Japanese cards
    await downloader.download_all_japanese_cards()

    # Print final statistics
    downloader.print_final_stats()


if __name__ == "__main__":
    asyncio.run(main())
