"""Japanese Pokemon Card Manager with metadata and database integration"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Import database models
from ..database.models import (
    CardVariation,
    DatabaseConfig,
    PokemonCard,
    PokemonSet,
    Subtype,
    Type,
    get_session,
    init_database,
)

logger = logging.getLogger(__name__)


class JapaneseCardManager:
    """Manage Japanese Pokemon cards with database integration"""

    def __init__(self, download_dir: str = None, db_session: Session = None):
        self.base_url = "https://api.tcgdx.net/v2/ja"
        if download_dir is None:
            download_dir = Path(__file__).parent.parent.parent / "assets/images/pokemon/japanese"
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True, parents=True)
        self.db_session = db_session
        self.session = None
        self.metadata_file = self.download_dir / "japanese_cards_metadata.json"

        # Load existing metadata
        self.metadata = self._load_metadata()

        # Statistics
        self.stats = {"downloaded": 0, "failed": 0, "skipped": 0, "sets_processed": 0}

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        self._save_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        """Load existing metadata from file"""
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

    async def sync_japanese_sets_to_database(self):
        """Sync Japanese sets to the database"""
        if not self.db_session:
            logger.warning("No database session provided, skipping database sync")
            return

        logger.info("Syncing Japanese sets to database...")

        sets = await self.get_all_sets()
        synced_count = 0

        for set_data in sets:
            try:
                set_id = f"jp_{set_data.get('id', '')}"  # Prefix with 'jp_'

                # Check if set already exists
                existing = self.db_session.query(PokemonSet).filter_by(id=set_id).first()
                if existing:
                    continue

                # Create new Japanese set
                release_date = None
                if set_data.get("releaseDate"):
                    try:
                        release_date = datetime.fromisoformat(set_data["releaseDate"]).date()
                    except:
                        pass

                jp_set = PokemonSet(
                    id=set_id,
                    name=f"{set_data.get('name', '')} (Japanese)",
                    series=set_data.get("serie", {}).get("name", ""),
                    printed_total=set_data.get("cardCount", {}).get("total"),
                    total=set_data.get("cardCount", {}).get("total"),
                    release_date=release_date,
                    images=set_data.get("logo", {}),
                    legalities={},
                )

                self.db_session.add(jp_set)
                synced_count += 1

            except Exception as e:
                logger.error(f"Failed to sync set {set_data.get('id', 'unknown')}: {e}")

        if synced_count > 0:
            self.db_session.commit()
            logger.info(f"Synced {synced_count} Japanese sets to database")

    async def download_and_catalog_all_sets(self):
        """Download all Japanese cards and catalog them"""
        logger.info("Starting comprehensive Japanese card download and cataloging...")

        sets = await self.get_all_sets()
        if not sets:
            logger.error("Failed to fetch sets from TCGdx API")
            return

        logger.info(f"Found {len(sets)} Japanese sets to process")

        # Process each set
        for set_data in sets:
            await self.process_set(set_data)
            self.stats["sets_processed"] += 1

            # Save progress periodically
            if self.stats["sets_processed"] % 5 == 0:
                self._save_metadata()

            # Rate limiting
            await asyncio.sleep(1.0)

        # Final save
        self._save_metadata()

        logger.info("Japanese card download and cataloging complete!")
        self.print_final_stats()

    async def process_set(self, set_data: Dict[str, Any]):
        """Process a single set - download cards and catalog metadata"""
        set_id = set_data.get("id")
        set_name = set_data.get("name", "Unknown")

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
        }

        # Get cards for this set
        cards = await self.get_set_cards(set_id)
        if not cards:
            logger.warning(f"No cards found for set {set_id}")
            return

        self.metadata["sets"][set_id]["card_count"] = len(cards)

        # Process each card
        for card in cards:
            success = await self.process_card(card, set_dir, set_name)
            if success:
                self.metadata["sets"][set_id]["downloaded_count"] += 1
                self.stats["downloaded"] += 1
            else:
                self.metadata["sets"][set_id]["failed_count"] += 1
                self.stats["failed"] += 1

            # Rate limiting
            await asyncio.sleep(0.5)

    async def process_card(self, card: Dict[str, Any], set_dir: Path, set_name: str) -> bool:
        """Process a single card - download image and store metadata"""
        try:
            card_id = card.get("id")
            card_name = card.get("name", "Unknown")
            card_number = card.get("localId", card.get("id", "Unknown"))

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
                "metadata": card,
            }

            # Skip if already downloaded
            if file_path.exists():
                logger.debug(f"  Skipping {filename} (already exists)")
                self.stats["skipped"] += 1
                return True

            # Download image
            image_url = self._get_best_image_url(card)
            if not image_url:
                logger.warning(f"  No image URL for {card_name}")
                return False

            async with self.session.get(image_url) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(file_path, "wb") as f:
                        f.write(content)

                    logger.info(f"  Downloaded: {filename}")
                    return True
                else:
                    logger.warning(f"  Failed to download {filename}: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error processing card {card.get('name', 'Unknown')}: {e}")
            return False

    async def get_all_sets(self) -> List[Dict[str, Any]]:
        """Get all sets from TCGdx API"""
        try:
            url = f"{self.base_url}/sets"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data if isinstance(data, list) else []
                else:
                    logger.error(f"Failed to fetch sets: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching sets: {e}")
            return []

    async def get_set_cards(self, set_id: str) -> List[Dict[str, Any]]:
        """Get all cards for a specific set"""
        try:
            url = f"{self.base_url}/sets/{set_id}/cards"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data if isinstance(data, list) else []
                else:
                    logger.error(f"Failed to fetch cards for set {set_id}: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching cards for set {set_id}: {e}")
            return []

    def _get_best_image_url(self, card: Dict[str, Any]) -> Optional[str]:
        """Get the best quality image URL for a card"""
        image_data = card.get("image")
        if not image_data:
            return None

        # Try high quality first, then low quality
        if isinstance(image_data, dict):
            for quality in ["high", "low"]:
                if quality in image_data:
                    quality_data = image_data[quality]
                    # Try PNG first, then JPG
                    for format in ["png", "jpg", "webp"]:
                        if format in quality_data:
                            return quality_data[format]

        # Fallback to string URL
        if isinstance(image_data, str):
            return image_data

        return None

    def _generate_filename(self, card_name: str, card_number: str, set_name: str) -> str:
        """Generate consistent filename"""
        clean_name = self._sanitize_filename(card_name)
        clean_number = str(card_number).replace("/", "_")
        clean_set = self._sanitize_filename(set_name)

        filename = f"{clean_name}_{clean_number}_{clean_set}_JP.png"

        # Ensure filename isn't too long
        if len(filename) > 255:
            max_name_length = 255 - len(f"_{clean_number}_{clean_set}_JP.png")
            clean_name = clean_name[:max_name_length]
            filename = f"{clean_name}_{clean_number}_{clean_set}_JP.png"

        return filename

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for cross-platform compatibility"""
        import re

        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        filename = filename.replace(" ", "_")
        filename = re.sub(r"_+", "_", filename)
        return filename.strip("_")

    def print_final_stats(self):
        """Print final download statistics"""
        print("\n" + "=" * 50)
        print("JAPANESE CARD DOWNLOAD COMPLETE")
        print("=" * 50)
        print(f"Sets Processed: {self.stats['sets_processed']}")
        print(f"Cards Downloaded: {self.stats['downloaded']}")
        print(f"Cards Failed: {self.stats['failed']}")
        print(f"Cards Skipped: {self.stats['skipped']}")
        print(
            f"Total Cards: {self.stats['downloaded'] + self.stats['failed'] + self.stats['skipped']}"
        )

        if self.stats["downloaded"] + self.stats["failed"] > 0:
            success_rate = (
                self.stats["downloaded"] / (self.stats["downloaded"] + self.stats["failed"])
            ) * 100
            print(f"Success Rate: {success_rate:.1f}%")

        print(f"Download Directory: {self.download_dir.absolute()}")
        print(f"Metadata File: {self.metadata_file.absolute()}")
        print("=" * 50)


async def main():
    """Main function to run the Japanese card manager"""
    # Set up database connection (optional)
    db_session = None
    try:
        # Use same database config as existing system
        db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "pokemon_cards",
            "username": "mateo",
            "password": "pokemon",
        }

        connection_string = DatabaseConfig.get_connection_string(**db_config)
        engine = create_engine(connection_string)
        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=engine)
        db_session = Session()

        print("✅ Database connection established")
    except Exception as e:
        print(f"⚠️ Database connection failed: {e}")
        print("Continuing without database integration...")

    # Run the manager
    async with JapaneseCardManager(db_session=db_session) as manager:
        # Sync sets to database first (if connected)
        if db_session:
            await manager.sync_japanese_sets_to_database()

        # Download and catalog all cards
        await manager.download_and_catalog_all_sets()

    # Clean up database session
    if db_session:
        db_session.close()


if __name__ == "__main__":
    asyncio.run(main())
