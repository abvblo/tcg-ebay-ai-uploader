"""Import ALL English Pokemon cards from the Pokemon TCG API"""

import asyncio
import json
import logging
import os
import urllib.parse
from datetime import datetime

import aiohttp
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from tqdm import tqdm

load_dotenv()  # Load environment variables from .env

from ..api.pokemon_tcg import PokemonTCGClient
from .models import (
    CardVariation,
    DatabaseConfig,
    PokemonCard,
    PokemonSet,
    Subtype,
    Type,
    get_session,
    init_database,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CompletePokemonImporter:
    """Import all English Pokemon cards"""

    def __init__(self, session: Session):
        self.session = session
        self.api_client = PokemonTCGClient(
            api_key=os.getenv("POKEMON_TCG_API_KEY"), rate_limit=0.1  # 10 requests per second
        )
        self.type_cache = {}
        self.subtype_cache = {}
        self.imported_cards = 0
        self.failed_cards = 0
        self.skipped_cards = 0

    async def import_all_english_cards(self):
        """Import all cards from English sets"""
        logger.info("Starting complete English Pokemon card import...")

        # First, import all sets if they don't exist
        await self.import_all_sets()

        # Get all sets, prioritize English sets
        sets = (
            self.session.query(PokemonSet)
            .order_by(PokemonSet.release_date.desc().nullslast())
            .all()
        )

        # Count existing cards
        existing_before = self.session.query(PokemonCard).count()
        logger.info(f"Database currently has {existing_before} cards")

        logger.info(f"Found {len(sets)} sets to process")

        # Process all sets
        async with aiohttp.ClientSession() as session:
            for set_obj in tqdm(sets, desc="Importing sets"):
                # Skip Japanese-only sets (basic filter)
                if set_obj.name and any(jp in set_obj.name.lower() for jp in ["japan", "japanese"]):
                    logger.debug(f"Skipping Japanese set: {set_obj.name}")
                    continue

                await self.import_cards_for_set(set_obj.id, set_obj.name, session)
                try:
                    self.session.commit()  # Commit after each set
                except Exception as e:
                    logger.error(f"Error committing set {set_obj.name}: {e}")
                    self.session.rollback()
                await asyncio.sleep(0.5)  # Rate limiting

        # Final count
        total_cards = self.session.query(PokemonCard).count()

        logger.info(f"\n=== IMPORT COMPLETE ===")
        logger.info(f"Total cards in database: {total_cards}")
        logger.info(f"Cards imported in this run: {self.imported_cards}")
        logger.info(f"Cards that failed: {self.failed_cards}")
        logger.info(f"Cards skipped (already exist): {self.skipped_cards}")
        logger.info(f"Net new cards: {total_cards - existing_before}")

    async def import_all_sets(self):
        """Import all sets from the Pokemon TCG API"""
        logger.info("Importing all sets...")

        async with aiohttp.ClientSession() as session:
            sets_data = await self.api_client.get_all_sets(session)

            if not sets_data:
                logger.error("Failed to fetch sets from API")
                return

            imported_sets = 0
            for set_data in tqdm(sets_data, desc="Importing sets"):
                try:
                    # Check if set already exists
                    existing = self.session.query(PokemonSet).filter_by(id=set_data["id"]).first()

                    if existing:
                        continue

                    # Create new set
                    set_obj = PokemonSet(
                        id=set_data["id"],
                        name=set_data["name"],
                        series=set_data.get("series"),
                        printed_total=set_data.get("printedTotal"),
                        total=set_data.get("total"),
                        ptcgo_code=set_data.get("ptcgoCode"),
                        release_date=(
                            datetime.strptime(set_data["releaseDate"], "%Y/%m/%d").date()
                            if set_data.get("releaseDate")
                            else None
                        ),
                        images=set_data.get("images", {}),
                        legalities=set_data.get("legalities", {}),
                    )

                    self.session.add(set_obj)
                    imported_sets += 1

                except Exception as e:
                    logger.error(f"Failed to import set {set_data.get('id', 'unknown')}: {e}")

            self.session.commit()
            logger.info(f"Imported {imported_sets} new sets")

    async def import_cards_for_set(
        self, set_id: str, set_name: str, session: aiohttp.ClientSession
    ):
        """Import all cards for a specific set"""
        set_card_count = 0
        set_skipped = 0

        cards_data = await self.api_client.get_cards_by_set_id(set_id, session)

        if not cards_data:
            logger.warning(f"No cards found for set {set_id} ({set_name})")
            return

        for card_data in cards_data:
            try:
                # Check if card already exists
                existing = self.session.query(PokemonCard).filter_by(api_id=card_data["id"]).first()

                if existing:
                    set_skipped += 1
                    self.skipped_cards += 1
                    continue

                self._import_single_card(card_data)
                set_card_count += 1
                self.imported_cards += 1

            except Exception as e:
                self.failed_cards += 1
                if "duplicate key value" in str(e):
                    logger.debug(f"Card {card_data.get('id', 'unknown')} already exists")
                else:
                    logger.debug(f"Failed to import card {card_data.get('id', 'unknown')}: {e}")

        if set_card_count > 0 or set_skipped > 0:
            logger.info(
                f"  {set_name}: imported {set_card_count} new cards, skipped {set_skipped} existing"
            )

    def _import_single_card(self, card_data: dict):
        """Import a single card with all data"""
        # Parse HP safely
        hp = None
        if card_data.get("hp"):
            try:
                hp = int(card_data["hp"])
            except:
                pass

        # Create card with all available data
        card = PokemonCard(
            api_id=card_data["id"],
            name=card_data["name"],
            number=card_data["number"],
            set_id=card_data["set"]["id"],
            supertype=card_data.get("supertype"),
            rarity=card_data.get("rarity"),
            hp=hp,
            artist=card_data.get("artist"),
            images=card_data.get("images", {}),
            evolves_from=card_data.get("evolvesFrom"),
            evolves_to=card_data.get("evolvesTo", []),
            retreat_cost=card_data.get("retreatCost", []),
            rules=card_data.get("rules", []),
            attacks=card_data.get("attacks", []),
            abilities=card_data.get("abilities", []),
            weaknesses=card_data.get("weaknesses", []),
            resistances=card_data.get("resistances", []),
            regulation_mark=card_data.get("regulationMark"),
            tcgplayer_id=(
                str(card_data.get("tcgplayer", {}).get("productId"))
                if card_data.get("tcgplayer", {}).get("productId")
                else None
            ),
            cardmarket_id=(
                str(card_data.get("cardmarket", {}).get("id"))
                if card_data.get("cardmarket", {}).get("id")
                else None
            ),
        )

        self.session.add(card)

        # Add types
        if card_data.get("types"):
            for type_name in card_data["types"]:
                type_obj = self._get_or_create_type(type_name)
                if type_obj:
                    card.types.append(type_obj)

        # Add subtypes
        if card_data.get("subtypes"):
            for subtype_name in card_data["subtypes"]:
                subtype_obj = self._get_or_create_subtype(
                    subtype_name, card_data.get("supertype", "").lower()
                )
                if subtype_obj:
                    card.subtypes.append(subtype_obj)

        # Create default variation for the card
        self._create_card_variations(card, card_data)

    def _get_or_create_type(self, type_name: str):
        """Get or create a type"""
        if type_name in self.type_cache:
            return self.type_cache[type_name]

        type_obj = self.session.query(Type).filter_by(name=type_name).first()
        if not type_obj:
            type_obj = Type(name=type_name)
            self.session.add(type_obj)
            self.session.flush()

        self.type_cache[type_name] = type_obj
        return type_obj

    def _get_or_create_subtype(self, subtype_name: str, category: str):
        """Get or create a subtype"""
        key = f"{category}:{subtype_name}"
        if key in self.subtype_cache:
            return self.subtype_cache[key]

        subtype_obj = self.session.query(Subtype).filter_by(name=subtype_name).first()

        if not subtype_obj:
            subtype_obj = Subtype(name=subtype_name, category=category)
            self.session.add(subtype_obj)
            try:
                self.session.flush()
            except:
                self.session.rollback()
                subtype_obj = self.session.query(Subtype).filter_by(name=subtype_name).first()

        self.subtype_cache[key] = subtype_obj
        return subtype_obj

    def _create_card_variations(self, card: PokemonCard, card_data: dict):
        """Create card variations based on available finishes"""
        # Determine if card has special finishes
        rarity = card_data.get("rarity", "").lower()

        # Create normal variation
        normal_variation = CardVariation(
            card=card,
            variation_type="normal",
            finish="normal",
            is_reverse_holo=False,
            is_first_edition=False,
            is_shadowless=False,
            is_stamped=False,
            is_promo="promo" in rarity,
        )
        self.session.add(normal_variation)

        # Create reverse holo variation if card can have it
        if any(term in rarity for term in ["rare", "uncommon", "common"]):
            reverse_variation = CardVariation(
                card=card,
                variation_type="reverse_holo",
                finish="reverse_holo",
                is_reverse_holo=True,
                is_first_edition=False,
                is_shadowless=False,
                is_stamped=False,
                is_promo="promo" in rarity,
            )
            self.session.add(reverse_variation)

        # Create holo variation if card is a holo rare
        if "holo" in rarity or "rare" in rarity:
            holo_variation = CardVariation(
                card=card,
                variation_type="holo",
                finish="holofoil",
                is_reverse_holo=False,
                is_first_edition=False,
                is_shadowless=False,
                is_stamped=False,
                is_promo="promo" in rarity,
            )
            self.session.add(holo_variation)


async def main():
    """Main import function"""
    # Database configuration - use local database as per CLAUDE.md
    db_config = {
        "host": "localhost",
        "port": 5432,
        "database": "pokemon_cards",
        "username": "mateo",
        "password": "pokemon",  # Common password for local dev
    }

    # Try environment variables first, then fallback to local
    if os.getenv("DB_HOST") and os.getenv("DB_HOST") != "db.oetvahhawtqnplwlbjpw.supabase.co":
        db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 5432)),
            "database": os.getenv("DB_NAME", "pokemon_cards"),
            "username": os.getenv("DB_USER", "mateo"),
            "password": os.getenv("DB_PASSWORD", "pokemon"),
        }

    logger.info(
        f"Connecting to database: {db_config['username']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    )

    # Use DatabaseConfig like the web app
    connection_string = DatabaseConfig.get_connection_string(**db_config)

    engine = create_engine(connection_string)
    session = get_session(engine)

    try:
        importer = CompletePokemonImporter(session)

        # Import ALL English cards
        await importer.import_all_english_cards()

        session.commit()

        # Show final statistics
        total_sets = session.query(PokemonSet).count()
        total_cards = session.query(PokemonCard).count()
        cards_with_images = (
            session.query(PokemonCard)
            .filter(PokemonCard.images.isnot(None), PokemonCard.images != "{}")
            .count()
        )

        logger.info(f"\n=== DATABASE STATISTICS ===")
        logger.info(f"Total sets: {total_sets}")
        logger.info(f"Total cards: {total_cards}")
        logger.info(f"Cards with images: {cards_with_images}")
        logger.info(f"Average cards per set: {total_cards / total_sets:.1f}")

    except Exception as e:
        logger.error(f"Import failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
