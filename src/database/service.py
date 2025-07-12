"""Database service layer for card data persistence and retrieval"""

import asyncio
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, create_engine, desc, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

# Using standard logging instead of relative import
logger = logging.getLogger(__name__)
from .models import (
    Base,
    CardVariation,
    DatabaseConfig,
    PokemonCard,
    PokemonSet,
    PriceSnapshot,
    Subtype,
    Type,
    ValidationRule,
    XimilarCorrection,
)


class DatabaseService:
    """Service layer for database operations with connection pooling"""

    def __init__(self, connection_string: str = None, pool_size: int = 20, max_overflow: int = 40):
        """Initialize database service with connection pooling"""
        if not connection_string:
            connection_string = DatabaseConfig.get_connection_string(
                host="localhost",
                port=5432,
                database="pokemon_cards",
                username="mateo",
                password="pokemon",
            )

        self.engine = DatabaseConfig.get_engine(
            connection_string, pool_size=pool_size, max_overflow=max_overflow
        )
        self.Session = sessionmaker(bind=self.engine)

        # Run migrations instead of creating tables directly
        try:
            from .migrations import MigrationManager

            migration_manager = MigrationManager()

            # Check if database needs initialization
            if migration_manager.current_version() is None:
                logger.info("Initializing database with migrations...")
                migration_manager.init_db()

            # Run any pending migrations
            migration_manager.auto_upgrade()

            # Verify tables exist
            if migration_manager.verify_tables():
                logger.info("✅ Database tables initialized and up to date")
            else:
                logger.warning("⚠️ Some database tables may be missing")

        except ImportError:
            # Fallback to direct table creation if migrations not available
            logger.warning("Migration system not available, creating tables directly")
            Base.metadata.create_all(self.engine)
            logger.info("✅ Database tables initialized (direct creation)")
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise

    @contextmanager
    def get_session(self) -> Session:
        """Context manager for database sessions"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def store_card_data(self, card_data: Dict[str, Any]) -> Optional[str]:
        """Store card data from API response in database"""
        try:
            with self.get_session() as session:
                # Get or create set
                set_obj = self._get_or_create_set(session, card_data)

                # Check if card exists
                card = (
                    session.query(PokemonCard)
                    .filter(PokemonCard.api_id == card_data.get("id", card_data.get("api_id")))
                    .first()
                )

                if card:
                    # Update existing card
                    self._update_card_data(session, card, card_data, set_obj)
                    logger.debug(f"Updated existing card: {card.name}")
                else:
                    # Create new card
                    card = self._create_card_data(session, card_data, set_obj)
                    logger.debug(f"Created new card: {card.name}")

                session.flush()
                return str(card.id)

        except Exception as e:
            logger.error(f"Error storing card data: {e}")
            return None

    def store_identification_result(
        self, identification_data: Dict[str, Any], confidence: float, image_hash: str
    ) -> Optional[str]:
        """Store card identification result with confidence tracking"""
        try:
            with self.get_session() as session:
                # Store the actual card data
                card_id = self.store_card_data(identification_data)

                if card_id:
                    # Create variation if needed
                    variation_id = self._create_or_update_variation(
                        session, card_id, identification_data, confidence
                    )

                    # Store identification metadata
                    self._store_identification_metadata(
                        session, card_id, variation_id, confidence, image_hash
                    )

                    return card_id

        except Exception as e:
            logger.error(f"Error storing identification result: {e}")
            return None

    def store_price_data(
        self, card_id: str, price_data: Dict[str, Any], variation_id: str = None
    ) -> bool:
        """Store price data for a card"""
        try:
            with self.get_session() as session:
                price_snapshot = PriceSnapshot(
                    card_id=card_id,
                    variation_id=variation_id,
                    timestamp=datetime.utcnow(),
                    prices=price_data.get("prices", {}),
                    source=price_data.get("source", "unknown"),
                    condition=price_data.get("condition", "NM"),
                    currency=price_data.get("currency", "USD"),
                    volume=price_data.get("volume"),
                    listings_count=price_data.get("listings_count"),
                )

                session.add(price_snapshot)
                session.flush()

                logger.debug(f"Stored price data for card {card_id}")
                return True

        except Exception as e:
            logger.error(f"Error storing price data: {e}")
            return False

    def get_card_by_details(
        self, name: str, set_name: str = None, number: str = None
    ) -> Optional[Dict[str, Any]]:
        """Get card data by identification details"""
        try:
            with self.get_session() as session:
                query = session.query(PokemonCard).join(PokemonSet)

                # Build query based on available parameters
                filters = [PokemonCard.name.ilike(f"%{name}%")]

                if set_name:
                    filters.append(PokemonSet.name.ilike(f"%{set_name}%"))

                if number:
                    filters.append(PokemonCard.number == number)

                card = query.filter(and_(*filters)).first()

                if card:
                    return self._card_to_dict(card)

        except Exception as e:
            logger.error(f"Error retrieving card: {e}")

        return None

    def get_recent_price(
        self, card_id: str, variation_id: str = None, max_age_hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """Get recent price data for a card"""
        try:
            with self.get_session() as session:
                cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

                query = session.query(PriceSnapshot).filter(
                    PriceSnapshot.card_id == card_id, PriceSnapshot.timestamp >= cutoff_time
                )

                if variation_id:
                    query = query.filter(PriceSnapshot.variation_id == variation_id)

                price_snapshot = query.order_by(desc(PriceSnapshot.timestamp)).first()

                if price_snapshot:
                    return {
                        "prices": price_snapshot.prices,
                        "source": price_snapshot.source,
                        "condition": price_snapshot.condition,
                        "timestamp": price_snapshot.timestamp,
                        "currency": price_snapshot.currency,
                    }

        except Exception as e:
            logger.error(f"Error retrieving price data: {e}")

        return None

    def validate_card_identification(self, identification_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate card identification against database and apply corrections"""
        try:
            with self.get_session() as session:
                # Check for known corrections
                correction = self._check_ximilar_corrections(session, identification_data)
                if correction:
                    logger.info(f"Applied known correction for {identification_data.get('name')}")
                    return correction

                # Validate against database
                card = self.get_card_by_details(
                    identification_data.get("name", ""),
                    identification_data.get("set_name", ""),
                    identification_data.get("number", ""),
                )

                if card:
                    # Merge API data with database data
                    validated_data = identification_data.copy()
                    validated_data.update(
                        {
                            "database_validated": True,
                            "database_card_id": card["id"],
                            "set_confirmed": card.get("set_name"),
                            "rarity_confirmed": card.get("rarity"),
                            "number_confirmed": card.get("number"),
                        }
                    )

                    return validated_data

                # Return original data if no database match
                identification_data["database_validated"] = False
                return identification_data

        except Exception as e:
            logger.error(f"Error validating identification: {e}")
            identification_data["database_validated"] = False
            return identification_data

    def store_ximilar_correction(
        self, ximilar_result: Dict[str, Any], correct_card_id: str, notes: str = None
    ) -> bool:
        """Store a correction for Ximilar misidentification"""
        try:
            with self.get_session() as session:
                correction = XimilarCorrection(
                    ximilar_result=ximilar_result,
                    correct_card_id=correct_card_id,
                    confidence_threshold=ximilar_result.get("confidence", 1.0),
                    notes=notes,
                    verified=True,
                )

                session.add(correction)
                session.flush()

                logger.info(f"Stored correction for {ximilar_result.get('name')}")
                return True

        except Exception as e:
            logger.error(f"Error storing correction: {e}")
            return False

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self.get_session() as session:
                stats = {
                    "total_cards": session.query(PokemonCard).count(),
                    "total_sets": session.query(PokemonSet).count(),
                    "total_variations": session.query(CardVariation).count(),
                    "total_price_snapshots": session.query(PriceSnapshot).count(),
                    "corrections_count": session.query(XimilarCorrection).count(),
                    "last_update": session.query(func.max(PokemonCard.updated_at)).scalar(),
                }

                return stats

        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}

    def _get_or_create_set(self, session: Session, card_data: Dict[str, Any]) -> PokemonSet:
        """Get or create a Pokemon set"""
        set_data = card_data.get("set", {})
        set_id = set_data.get("id", f"unknown_{set_data.get('name', 'unknown')}")

        set_obj = session.query(PokemonSet).filter(PokemonSet.id == set_id).first()

        if not set_obj:
            set_obj = PokemonSet(
                id=set_id,
                name=set_data.get("name", "Unknown Set"),
                series=set_data.get("series", ""),
                printed_total=set_data.get("printedTotal"),
                total=set_data.get("total"),
                legalities=set_data.get("legalities", {}),
                images=set_data.get("images", {}),
                ptcgo_code=set_data.get("ptcgoCode"),
                release_date=self._parse_date(set_data.get("releaseDate")),
            )
            session.add(set_obj)
            session.flush()

        return set_obj

    def _create_card_data(
        self, session: Session, card_data: Dict[str, Any], set_obj: PokemonSet
    ) -> PokemonCard:
        """Create a new Pokemon card"""
        card = PokemonCard(
            api_id=card_data.get("id", card_data.get("api_id")),
            name=card_data.get("name", ""),
            number=card_data.get("number", ""),
            set_id=set_obj.id,
            supertype=card_data.get("supertype", ""),
            rarity=card_data.get("rarity", ""),
            hp=self._parse_int(card_data.get("hp")),
            evolves_from=card_data.get("evolvesFrom"),
            evolves_to=card_data.get("evolvesTo", []),
            abilities=card_data.get("abilities", []),
            attacks=card_data.get("attacks", []),
            weaknesses=card_data.get("weaknesses", []),
            resistances=card_data.get("resistances", []),
            retreat_cost=card_data.get("retreatCost", []),
            rules=card_data.get("rules", []),
            images=card_data.get("images", {}),
            tcgplayer_id=card_data.get("tcgplayer", {}).get("productId"),
            cardmarket_id=card_data.get("cardmarket", {}).get("productId"),
            artist=card_data.get("artist"),
            regulation_mark=card_data.get("regulationMark"),
        )

        session.add(card)
        session.flush()

        # Add types and subtypes
        self._add_card_types(session, card, card_data.get("types", []))
        self._add_card_subtypes(session, card, card_data.get("subtypes", []))

        return card

    def _update_card_data(
        self, session: Session, card: PokemonCard, card_data: Dict[str, Any], set_obj: PokemonSet
    ):
        """Update existing card data"""
        card.name = card_data.get("name", card.name)
        card.number = card_data.get("number", card.number)
        card.set_id = set_obj.id
        card.supertype = card_data.get("supertype", card.supertype)
        card.rarity = card_data.get("rarity", card.rarity)
        card.hp = self._parse_int(card_data.get("hp")) or card.hp
        card.evolves_from = card_data.get("evolvesFrom", card.evolves_from)
        card.evolves_to = card_data.get("evolvesTo", card.evolves_to)
        card.abilities = card_data.get("abilities", card.abilities)
        card.attacks = card_data.get("attacks", card.attacks)
        card.weaknesses = card_data.get("weaknesses", card.weaknesses)
        card.resistances = card_data.get("resistances", card.resistances)
        card.retreat_cost = card_data.get("retreatCost", card.retreat_cost)
        card.rules = card_data.get("rules", card.rules)
        card.images = card_data.get("images", card.images)
        card.tcgplayer_id = card_data.get("tcgplayer", {}).get("productId") or card.tcgplayer_id
        card.cardmarket_id = card_data.get("cardmarket", {}).get("productId") or card.cardmarket_id
        card.artist = card_data.get("artist", card.artist)
        card.regulation_mark = card_data.get("regulationMark", card.regulation_mark)
        card.updated_at = datetime.utcnow()

        # Update types and subtypes
        self._update_card_types(session, card, card_data.get("types", []))
        self._update_card_subtypes(session, card, card_data.get("subtypes", []))

    def _create_or_update_variation(
        self, session: Session, card_id: str, identification_data: Dict[str, Any], confidence: float
    ) -> Optional[str]:
        """Create or update card variation"""
        try:
            unique_chars = identification_data.get("unique_characteristics", [])
            finish = identification_data.get("finish", "")

            # Determine variation type
            variation_type = self._determine_variation_type(unique_chars, finish)

            # Check if variation exists
            variation = (
                session.query(CardVariation)
                .filter(
                    CardVariation.card_id == card_id, CardVariation.variation_type == variation_type
                )
                .first()
            )

            if not variation:
                variation = CardVariation(
                    card_id=card_id,
                    variation_type=variation_type,
                    finish=finish,
                    is_reverse_holo="reverse" in " ".join(unique_chars).lower(),
                    is_first_edition="1st edition" in " ".join(unique_chars).lower(),
                    is_shadowless="shadowless" in " ".join(unique_chars).lower(),
                    is_promo="promo" in " ".join(unique_chars).lower(),
                    price_category=identification_data.get("price_category", ""),
                )
                session.add(variation)
                session.flush()

            return str(variation.id)

        except Exception as e:
            logger.error(f"Error creating variation: {e}")
            return None

    def _add_card_types(self, session: Session, card: PokemonCard, types: List[str]):
        """Add types to card"""
        for type_name in types:
            type_obj = session.query(Type).filter(Type.name == type_name).first()
            if not type_obj:
                type_obj = Type(name=type_name)
                session.add(type_obj)
                session.flush()

            if type_obj not in card.types:
                card.types.append(type_obj)

    def _add_card_subtypes(self, session: Session, card: PokemonCard, subtypes: List[str]):
        """Add subtypes to card"""
        for subtype_name in subtypes:
            subtype_obj = session.query(Subtype).filter(Subtype.name == subtype_name).first()
            if not subtype_obj:
                subtype_obj = Subtype(
                    name=subtype_name,
                    category=card.supertype.lower() if card.supertype else "unknown",
                )
                session.add(subtype_obj)
                session.flush()

            if subtype_obj not in card.subtypes:
                card.subtypes.append(subtype_obj)

    def _update_card_types(self, session: Session, card: PokemonCard, types: List[str]):
        """Update card types"""
        # Clear existing types
        card.types.clear()
        # Add new types
        self._add_card_types(session, card, types)

    def _update_card_subtypes(self, session: Session, card: PokemonCard, subtypes: List[str]):
        """Update card subtypes"""
        # Clear existing subtypes
        card.subtypes.clear()
        # Add new subtypes
        self._add_card_subtypes(session, card, subtypes)

    def _check_ximilar_corrections(
        self, session: Session, identification_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check for known Ximilar corrections"""
        try:
            corrections = (
                session.query(XimilarCorrection).filter(XimilarCorrection.verified == True).all()
            )

            for correction in corrections:
                if self._matches_correction_pattern(correction.ximilar_result, identification_data):
                    # Apply correction
                    correction.times_applied += 1
                    correction.last_applied = datetime.utcnow()

                    # Get correct card data
                    correct_card = (
                        session.query(PokemonCard)
                        .filter(PokemonCard.id == correction.correct_card_id)
                        .first()
                    )

                    if correct_card:
                        corrected_data = identification_data.copy()
                        corrected_data.update(
                            {
                                "name": correct_card.name,
                                "set_name": correct_card.set.name,
                                "number": correct_card.number,
                                "rarity": correct_card.rarity,
                                "correction_applied": True,
                                "correction_id": str(correction.id),
                            }
                        )

                        return corrected_data

        except Exception as e:
            logger.error(f"Error checking corrections: {e}")

        return None

    def _matches_correction_pattern(self, pattern: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """Check if identification data matches correction pattern"""
        # Simple matching - can be enhanced with fuzzy matching
        return (
            pattern.get("name", "").lower() == data.get("name", "").lower()
            and pattern.get("set", "").lower() == data.get("set_name", "").lower()
        )

    def _card_to_dict(self, card: PokemonCard) -> Dict[str, Any]:
        """Convert card object to dictionary"""
        return {
            "id": str(card.id),
            "api_id": card.api_id,
            "name": card.name,
            "number": card.number,
            "set_name": card.set.name if card.set else None,
            "set_id": card.set_id,
            "supertype": card.supertype,
            "rarity": card.rarity,
            "hp": card.hp,
            "evolves_from": card.evolves_from,
            "evolves_to": card.evolves_to,
            "abilities": card.abilities,
            "attacks": card.attacks,
            "weaknesses": card.weaknesses,
            "resistances": card.resistances,
            "retreat_cost": card.retreat_cost,
            "rules": card.rules,
            "images": card.images,
            "tcgplayer_id": card.tcgplayer_id,
            "cardmarket_id": card.cardmarket_id,
            "artist": card.artist,
            "regulation_mark": card.regulation_mark,
            "types": [t.name for t in card.types],
            "subtypes": [s.name for s in card.subtypes],
            "created_at": card.created_at,
            "updated_at": card.updated_at,
        }

    def _store_identification_metadata(
        self, session: Session, card_id: str, variation_id: str, confidence: float, image_hash: str
    ):
        """Store identification metadata"""
        # This could be expanded to store identification history
        pass

    def _determine_variation_type(self, unique_chars: List[str], finish: str) -> str:
        """Determine variation type from characteristics"""
        chars_lower = [c.lower() for c in unique_chars]

        if "reverse" in " ".join(chars_lower):
            return "reverse_holo"
        elif "1st edition" in " ".join(chars_lower):
            return "1st_edition"
        elif "shadowless" in " ".join(chars_lower):
            return "shadowless"
        elif "promo" in " ".join(chars_lower):
            return "promo"
        else:
            return "normal"

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None

        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            try:
                return datetime.strptime(date_str, "%Y/%m/%d").date()
            except ValueError:
                return None

    def _parse_int(self, value: Any) -> Optional[int]:
        """Parse value to integer"""
        if value is None:
            return None

        try:
            return int(value)
        except (ValueError, TypeError):
            return None


# Global database service instance
_db_service: Optional[DatabaseService] = None


def get_db_service() -> DatabaseService:
    """Get or create global database service instance"""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service


def initialize_db_service(connection_string: str = None) -> DatabaseService:
    """Initialize database service with custom connection string"""
    global _db_service
    _db_service = DatabaseService(connection_string)
    return _db_service
