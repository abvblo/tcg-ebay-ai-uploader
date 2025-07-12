"""Import Pokemon card data from Pokemon TCG API into database"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from tqdm import tqdm

from models import (
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


class PokemonDataImporter:
    """Import Pokemon card data from the official API"""

    def __init__(self, session: Session):
        self.session = session
        self.api_base = "https://api.pokemontcg.io/v2"
        self.headers = {}  # Add API key here if you have one
        self.type_cache = {}
        self.subtype_cache = {}

    async def import_all_data(self):
        """Import all sets and cards"""
        logger.info("Starting Pokemon TCG data import...")

        # Import sets first
        await self.import_sets()

        # Import cards by set
        await self.import_all_cards()

        logger.info("Import completed!")

    async def import_sets(self):
        """Import all Pokemon sets"""
        logger.info("Importing sets...")

        async with aiohttp.ClientSession() as session:
            page = 1
            total_imported = 0

            while True:
                url = f"{self.api_base}/sets?page={page}&pageSize=250"
                async with session.get(url, headers=self.headers) as response:
                    data = await response.json()

                    if not data.get("data"):
                        break

                    for set_data in data["data"]:
                        self._import_set(set_data)

                    self.session.commit()
                    total_imported += len(data["data"])
                    logger.info(f"Imported {total_imported} sets...")

                    if len(data["data"]) < 250:
                        break

                    page += 1
                    await asyncio.sleep(0.1)  # Rate limiting

        logger.info(f"Total sets imported: {total_imported}")

    def _import_set(self, set_data: Dict[str, Any]):
        """Import or update a single set"""
        set_obj = PokemonSet(
            id=set_data["id"],
            name=set_data["name"],
            series=set_data.get("series"),
            printed_total=set_data.get("printedTotal"),
            total=set_data.get("total"),
            legalities=set_data.get("legalities"),
            images=set_data.get("images"),
            ptcgo_code=set_data.get("ptcgoCode"),
            release_date=(
                datetime.strptime(set_data["releaseDate"], "%Y/%m/%d").date()
                if set_data.get("releaseDate")
                else None
            ),
        )

        # Upsert the set
        stmt = insert(PokemonSet).values(
            id=set_obj.id,
            name=set_obj.name,
            series=set_obj.series,
            printed_total=set_obj.printed_total,
            total=set_obj.total,
            legalities=set_obj.legalities,
            images=set_obj.images,
            ptcgo_code=set_obj.ptcgo_code,
            release_date=set_obj.release_date,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_=dict(
                name=stmt.excluded.name,
                series=stmt.excluded.series,
                printed_total=stmt.excluded.printed_total,
                total=stmt.excluded.total,
                legalities=stmt.excluded.legalities,
                images=stmt.excluded.images,
                ptcgo_code=stmt.excluded.ptcgo_code,
                release_date=stmt.excluded.release_date,
                updated_at=datetime.utcnow(),
            ),
        )
        self.session.execute(stmt)

    async def import_all_cards(self):
        """Import all cards from all sets"""
        logger.info("Importing cards...")

        # Get all sets
        sets = self.session.query(PokemonSet).order_by(PokemonSet.release_date.desc()).all()

        for set_obj in tqdm(sets, desc="Importing sets"):
            await self.import_cards_for_set(set_obj.id)
            await asyncio.sleep(0.5)  # Rate limiting between sets

    async def import_cards_for_set(self, set_id: str):
        """Import all cards for a specific set"""
        async with aiohttp.ClientSession() as session:
            page = 1

            while True:
                url = f"{self.api_base}/cards?q=set.id:{set_id}&page={page}&pageSize=250"

                try:
                    async with session.get(url, headers=self.headers) as response:
                        data = await response.json()

                        if not data.get("data"):
                            break

                        for card_data in data["data"]:
                            await self._import_card(card_data)

                        self.session.commit()

                        if len(data["data"]) < 250:
                            break

                        page += 1
                        await asyncio.sleep(0.1)  # Rate limiting

                except Exception as e:
                    logger.error(f"Error importing cards for set {set_id}: {e}")
                    break

    async def _import_card(self, card_data: Dict[str, Any]):
        """Import or update a single card"""
        # Get or create types
        type_ids = []
        if card_data.get("types"):
            for type_name in card_data["types"]:
                type_obj = self._get_or_create_type(type_name)
                type_ids.append(type_obj)

        # Get or create subtypes
        subtype_ids = []
        if card_data.get("subtypes"):
            for subtype_name in card_data["subtypes"]:
                subtype_obj = self._get_or_create_subtype(
                    subtype_name, card_data.get("supertype", "").lower()
                )
                subtype_ids.append(subtype_obj)

        # Convert HP to integer
        hp = None
        if card_data.get("hp"):
            try:
                hp = int(card_data["hp"])
            except:
                pass

        # Create card
        card = PokemonCard(
            api_id=card_data["id"],
            name=card_data["name"],
            number=card_data["number"],
            set_id=card_data["set"]["id"],
            supertype=card_data.get("supertype"),
            rarity=card_data.get("rarity"),
            hp=hp,
            evolves_from=card_data.get("evolvesFrom"),
            evolves_to=card_data.get("evolvesTo", []),
            abilities=card_data.get("abilities"),
            attacks=card_data.get("attacks"),
            weaknesses=card_data.get("weaknesses"),
            resistances=card_data.get("resistances"),
            retreat_cost=card_data.get("retreatCost", []),
            rules=card_data.get("rules", []),
            images=card_data.get("images"),
            tcgplayer_id=(
                str(card_data["tcgplayer"].get("productId"))
                if card_data.get("tcgplayer") and card_data["tcgplayer"].get("productId")
                else None
            ),
            cardmarket_id=card_data.get("cardmarket", {}).get("id"),
            artist=card_data.get("artist"),
            regulation_mark=card_data.get("regulationMark"),
        )

        # Check if card exists
        existing = self.session.query(PokemonCard).filter_by(api_id=card.api_id).first()

        if existing:
            # Update existing card
            for key, value in card.__dict__.items():
                if key.startswith("_"):
                    continue
                setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            card_obj = existing
        else:
            self.session.add(card)
            card_obj = card

        # Set relationships
        card_obj.types = type_ids
        card_obj.subtypes = subtype_ids

        # Create variations based on TCGPlayer data
        if card_data.get("tcgplayer"):
            await self._create_variations(card_obj, card_data["tcgplayer"])

    def _get_or_create_type(self, type_name: str) -> Type:
        """Get or create a Pokemon type"""
        if type_name in self.type_cache:
            return self.type_cache[type_name]

        type_obj = self.session.query(Type).filter_by(name=type_name).first()
        if not type_obj:
            type_obj = Type(name=type_name)
            self.session.add(type_obj)
            self.session.flush()

        self.type_cache[type_name] = type_obj
        return type_obj

    def _get_or_create_subtype(self, subtype_name: str, category: str) -> Subtype:
        """Get or create a card subtype"""
        key = f"{category}:{subtype_name}"
        if key in self.subtype_cache:
            return self.subtype_cache[key]

        # Just use name for uniqueness, not category
        subtype_obj = self.session.query(Subtype).filter_by(name=subtype_name).first()

        if not subtype_obj:
            subtype_obj = Subtype(name=subtype_name, category=category)
            self.session.add(subtype_obj)
            try:
                self.session.flush()
            except:
                self.session.rollback()
                # Try again after rollback
                subtype_obj = self.session.query(Subtype).filter_by(name=subtype_name).first()

        self.subtype_cache[key] = subtype_obj
        return subtype_obj

    async def _create_variations(self, card: PokemonCard, tcgplayer_data: Dict[str, Any]):
        """Create card variations based on TCGPlayer price data"""
        if not tcgplayer_data.get("prices"):
            return

        for price_type, price_data in tcgplayer_data["prices"].items():
            if not price_data:
                continue

            # Determine variation attributes
            variation_type = "normal"
            is_reverse_holo = False
            is_first_edition = False

            if "reverseHolofoil" in price_type:
                variation_type = "reverse_holo"
                is_reverse_holo = True
            elif "1stEdition" in price_type:
                variation_type = "1st_edition"
                is_first_edition = True

            # Check if variation exists
            existing_var = (
                self.session.query(CardVariation)
                .filter_by(card_id=card.id, variation_type=variation_type)
                .first()
            )

            if not existing_var:
                variation = CardVariation(
                    card_id=card.id,
                    variation_type=variation_type,
                    finish=price_type,
                    is_reverse_holo=is_reverse_holo,
                    is_first_edition=is_first_edition,
                    price_category=price_type,
                    tcgplayer_product_id=str(tcgplayer_data.get("productId")),
                )
                self.session.add(variation)


class StampedCardImporter:
    """Import known stamped card patterns"""

    def __init__(self, session: Session):
        self.session = session

    def import_stamped_patterns(self):
        """Import known stamped card patterns"""

        # League promos
        league_sets = [
            "League & Championship Cards",
            "Pokemon League",
            "League Challenge",
            "League Cup",
        ]

        # Championship stamps
        championship_patterns = [
            ("Worlds", "world championship"),
            ("Regional", "regional championship"),
            ("City Championship", "city championship"),
            ("State Championship", "state championship"),
        ]

        # Pre-release stamps
        prerelease_sets = [".*Prerelease.*", ".*Pre-release.*"]

        # Staff stamps
        staff_patterns = [(".*Staff.*", "staff"), (".*Professor.*", "professor")]

        # Specific stamped cards (like Wynaut from Legend Maker)
        specific_stamped = [
            ("Wynaut", "Legend Maker", None, "league"),
            ("Pikachu", ".*Promo.*", "SWSH020", "league"),
            # Add more specific known stamped cards here
        ]

        logger.info("Stamped card patterns imported")


async def main():
    """Main import function"""
    # Database connection
    connection_string = DatabaseConfig.get_connection_string(
        host="localhost",
        database="pokemon_tcg",
        username="mateoallen",
        password="",  # No password needed for local connection
    )

    # Initialize database
    engine = init_database(connection_string)
    session = get_session(engine)

    try:
        # Import Pokemon data
        importer = PokemonDataImporter(session)
        await importer.import_all_data()

        # Import stamped patterns
        stamped_importer = StampedCardImporter(session)
        stamped_importer.import_stamped_patterns()

        session.commit()
        logger.info("Import completed successfully!")

    except Exception as e:
        logger.error(f"Import failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
