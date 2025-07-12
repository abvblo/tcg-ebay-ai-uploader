"""Japanese Pokemon Card Downloader using TCGdex SDK"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

# TCGdex SDK imports
from tcgdexsdk import Language, Query, TCGdex

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TCGdexJapaneseDownloader:
    """Download Japanese Pokemon cards using TCGdex SDK"""

    def __init__(self, download_dir: str = None):
        if download_dir is None:
            download_dir = Path(__file__).parent.parent.parent / "assets/images/pokemon/japanese"
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True, parents=True)

        # Initialize TCGdex SDK for Japanese
        self.tcgdex = TCGdex(Language.JA)

        # Statistics
        self.downloaded_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.rate_limit = 1.0  # 1 second between requests

        # Create metadata file
        self.metadata_file = self.download_dir / "japanese_cards_metadata.json"
        self.metadata = self._load_metadata()

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

    async def download_all_japanese_cards(self):
        """Download all Japanese Pokemon cards"""
        logger.info("Starting Japanese Pokemon card download using TCGdex SDK...")

        try:
            # Get all sets in Japanese
            sets = await self.tcgdex.set.list()

            if not sets:
                logger.error("No sets found from TCGdx API")
                return

            logger.info(f"Found {len(sets)} sets to download")

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

            logger.info(f"Processing set: {set_name} ({set_id})")

            # Create set directory
            set_dir = self.download_dir / self._sanitize_filename(set_name)
            set_dir.mkdir(exist_ok=True)

            # Store set metadata
            self.metadata["sets"][set_id] = {
                "name": set_name,
                "id": set_id,
                "directory": str(set_dir),
                "processed_at": datetime.now().isoformat(),
                "card_count": 0,
                "downloaded_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
            }

            # Get all cards for this set
            cards = await self.tcgdex.card.list(Query().equal("set.id", set_id))

            if not cards:
                logger.debug(
                    f"No cards found for set {set_id} (likely older set without card data)"
                )
                return

            self.metadata["sets"][set_id]["card_count"] = len(cards)
            logger.info(f"  Found {len(cards)} cards in {set_name}")

            # Download each card
            for card in cards:
                success = await self.download_card_image(card, set_dir, set_name)

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

    async def download_card_image(self, card, set_dir: Path, set_name: str) -> str:
        """Download a single card image"""
        try:
            card_id = card.id
            card_name = card.name
            card_number = card.localId

            # Generate filename
            filename = self._generate_filename(card_name, card_number, set_name)
            file_path = set_dir / filename

            # Store card metadata
            self.metadata["cards"][card_id] = {
                "id": card_id,
                "name": card_name,
                "number": card_number,
                "set_name": set_name,
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
                logger.warning(f"  No image URL for {card_name}")
                return "failed"

            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(file_path, "wb") as f:
                            f.write(content)

                        logger.info(f"  Downloaded: {filename}")
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

                                    logger.info(f"  Downloaded (low quality): {filename}")
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

    def _generate_filename(self, card_name: str, card_number: str, set_name: str) -> str:
        """Generate consistent filename following existing conventions"""
        # Clean components
        clean_name = self._sanitize_filename(card_name)
        clean_number = str(card_number).replace("/", "_")
        clean_set = self._sanitize_filename(set_name)

        # Follow existing naming pattern: CardName_Number_SetName_JP.png
        filename = f"{clean_name}_{clean_number}_{clean_set}_JP.png"

        # Ensure filename isn't too long
        if len(filename) > 255:
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

        try:
            # Get set info
            set_data = await self.tcgdex.set.get(set_id)
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
        print("JAPANESE POKEMON CARD DOWNLOAD COMPLETE (TCGdex SDK)")
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
    logger.info("Starting Japanese Pokemon card download using TCGdex SDK...")

    downloader = TCGdexJapaneseDownloader()

    # Download all Japanese cards
    await downloader.download_all_japanese_cards()

    # Print final statistics
    downloader.print_final_stats()


if __name__ == "__main__":
    asyncio.run(main())
