"""Comprehensive CRUD operations for Pokemon TCG database"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, joinedload, selectinload

import logging
logger = logging.getLogger(__name__)
from .models import (
    CardVariation,
    PokemonCard,
    PokemonSet,
    PriceSnapshot,
    Subtype,
    Type,
    ValidationRule,
    XimilarCorrection,
)


@dataclass
class CardSearchFilters:
    """Filters for card search operations"""

    name: Optional[str] = None
    set_name: Optional[str] = None
    set_id: Optional[str] = None
    supertype: Optional[str] = None
    rarity: Optional[str] = None
    hp_min: Optional[int] = None
    hp_max: Optional[int] = None
    types: Optional[List[str]] = None
    subtypes: Optional[List[str]] = None
    artist: Optional[str] = None
    number: Optional[str] = None
    limit: int = 100
    offset: int = 0


class CardCRUD:
    """CRUD operations for Pokemon cards"""

    @staticmethod
    async def create_card(session: AsyncSession, card_data: Dict[str, Any]) -> PokemonCard:
        """Create a new Pokemon card"""
        try:
            # Validate required fields
            required_fields = ["api_id", "name", "number", "set_id"]
            for field in required_fields:
                if field not in card_data:
                    raise ValueError(f"Missing required field: {field}")

            # Check if card already exists
            existing_card = await CardCRUD.get_card_by_api_id(session, card_data["api_id"])
            if existing_card:
                logger.warning(f"Card with API ID {card_data['api_id']} already exists")
                return existing_card

            # Create the card
            card = PokemonCard(
                api_id=card_data["api_id"],
                name=card_data["name"],
                number=card_data["number"],
                set_id=card_data["set_id"],
                supertype=card_data.get("supertype"),
                rarity=card_data.get("rarity"),
                hp=card_data.get("hp"),
                evolves_from=card_data.get("evolves_from"),
                evolves_to=card_data.get("evolves_to", []),
                abilities=card_data.get("abilities", []),
                attacks=card_data.get("attacks", []),
                weaknesses=card_data.get("weaknesses", []),
                resistances=card_data.get("resistances", []),
                retreat_cost=card_data.get("retreat_cost", []),
                rules=card_data.get("rules", []),
                images=card_data.get("images", {}),
                tcgplayer_id=card_data.get("tcgplayer_id"),
                cardmarket_id=card_data.get("cardmarket_id"),
                artist=card_data.get("artist"),
                regulation_mark=card_data.get("regulation_mark"),
            )

            session.add(card)
            await session.commit()
            await session.refresh(card)

            logger.info(f"✅ Created card: {card.name} ({card.api_id})")
            return card

        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Card creation failed - integrity error: {e}")
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Card creation failed: {e}")
            raise

    @staticmethod
    async def get_card_by_id(
        session: AsyncSession, card_id: Union[str, uuid.UUID]
    ) -> Optional[PokemonCard]:
        """Get card by internal UUID"""
        try:
            if isinstance(card_id, str):
                card_id = uuid.UUID(card_id)

            result = await session.execute(
                select(PokemonCard)
                .options(
                    selectinload(PokemonCard.set),
                    selectinload(PokemonCard.types),
                    selectinload(PokemonCard.subtypes),
                    selectinload(PokemonCard.variations),
                    selectinload(PokemonCard.prices),
                )
                .where(PokemonCard.id == card_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting card by ID {card_id}: {e}")
            return None

    @staticmethod
    async def get_card_by_api_id(session: AsyncSession, api_id: str) -> Optional[PokemonCard]:
        """Get card by Pokemon TCG API ID"""
        try:
            result = await session.execute(
                select(PokemonCard)
                .options(
                    selectinload(PokemonCard.set),
                    selectinload(PokemonCard.types),
                    selectinload(PokemonCard.subtypes),
                    selectinload(PokemonCard.variations),
                    selectinload(PokemonCard.prices),
                )
                .where(PokemonCard.api_id == api_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting card by API ID {api_id}: {e}")
            return None

    @staticmethod
    async def get_card_by_name_and_set(
        session: AsyncSession, name: str, set_name: str
    ) -> Optional[PokemonCard]:
        """Get card by name and set name"""
        try:
            result = await session.execute(
                select(PokemonCard)
                .join(PokemonSet)
                .options(
                    selectinload(PokemonCard.set),
                    selectinload(PokemonCard.types),
                    selectinload(PokemonCard.subtypes),
                )
                .where(
                    and_(
                        PokemonCard.name.ilike(f"%{name}%"), PokemonSet.name.ilike(f"%{set_name}%")
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting card by name and set: {e}")
            return None

    @staticmethod
    async def search_cards(session: AsyncSession, filters: CardSearchFilters) -> List[PokemonCard]:
        """Search cards with various filters"""
        try:
            query = select(PokemonCard).options(
                selectinload(PokemonCard.set),
                selectinload(PokemonCard.types),
                selectinload(PokemonCard.subtypes),
            )

            # Apply filters
            conditions = []

            if filters.name:
                conditions.append(PokemonCard.name.ilike(f"%{filters.name}%"))

            if filters.set_name:
                query = query.join(PokemonSet)
                conditions.append(PokemonSet.name.ilike(f"%{filters.set_name}%"))

            if filters.set_id:
                conditions.append(PokemonCard.set_id == filters.set_id)

            if filters.supertype:
                conditions.append(PokemonCard.supertype == filters.supertype)

            if filters.rarity:
                conditions.append(PokemonCard.rarity == filters.rarity)

            if filters.hp_min:
                conditions.append(PokemonCard.hp >= filters.hp_min)

            if filters.hp_max:
                conditions.append(PokemonCard.hp <= filters.hp_max)

            if filters.artist:
                conditions.append(PokemonCard.artist.ilike(f"%{filters.artist}%"))

            if filters.number:
                conditions.append(PokemonCard.number == filters.number)

            if conditions:
                query = query.where(and_(*conditions))

            # Apply pagination
            query = query.offset(filters.offset).limit(filters.limit)

            result = await session.execute(query)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error searching cards: {e}")
            return []

    @staticmethod
    async def update_card_data(
        session: AsyncSession, card_id: Union[str, uuid.UUID], updates: Dict[str, Any]
    ) -> Optional[PokemonCard]:
        """Update card data"""
        try:
            if isinstance(card_id, str):
                card_id = uuid.UUID(card_id)

            # Get the card first
            card = await CardCRUD.get_card_by_id(session, card_id)
            if not card:
                logger.warning(f"Card not found for update: {card_id}")
                return None

            # Update fields
            for field, value in updates.items():
                if hasattr(card, field):
                    setattr(card, field, value)

            card.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(card)

            logger.info(f"✅ Updated card: {card.name} ({card.api_id})")
            return card

        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating card {card_id}: {e}")
            raise

    @staticmethod
    async def delete_card(session: AsyncSession, card_id: Union[str, uuid.UUID]) -> bool:
        """Delete a card"""
        try:
            if isinstance(card_id, str):
                card_id = uuid.UUID(card_id)

            result = await session.execute(delete(PokemonCard).where(PokemonCard.id == card_id))
            await session.commit()

            if result.rowcount > 0:
                logger.info(f"✅ Deleted card: {card_id}")
                return True
            else:
                logger.warning(f"Card not found for deletion: {card_id}")
                return False

        except Exception as e:
            await session.rollback()
            logger.error(f"Error deleting card {card_id}: {e}")
            raise

    @staticmethod
    async def bulk_create_cards(
        session: AsyncSession, cards_data: List[Dict[str, Any]]
    ) -> List[PokemonCard]:
        """Create multiple cards in bulk"""
        try:
            created_cards = []

            for card_data in cards_data:
                try:
                    # Check if card already exists
                    existing_card = await CardCRUD.get_card_by_api_id(session, card_data["api_id"])
                    if existing_card:
                        logger.debug(f"Card already exists: {card_data['api_id']}")
                        created_cards.append(existing_card)
                        continue

                    # Create new card
                    card = PokemonCard(
                        api_id=card_data["api_id"],
                        name=card_data["name"],
                        number=card_data["number"],
                        set_id=card_data["set_id"],
                        supertype=card_data.get("supertype"),
                        rarity=card_data.get("rarity"),
                        hp=card_data.get("hp"),
                        evolves_from=card_data.get("evolves_from"),
                        evolves_to=card_data.get("evolves_to", []),
                        abilities=card_data.get("abilities", []),
                        attacks=card_data.get("attacks", []),
                        weaknesses=card_data.get("weaknesses", []),
                        resistances=card_data.get("resistances", []),
                        retreat_cost=card_data.get("retreat_cost", []),
                        rules=card_data.get("rules", []),
                        images=card_data.get("images", {}),
                        tcgplayer_id=card_data.get("tcgplayer_id"),
                        cardmarket_id=card_data.get("cardmarket_id"),
                        artist=card_data.get("artist"),
                        regulation_mark=card_data.get("regulation_mark"),
                    )

                    session.add(card)
                    created_cards.append(card)

                except Exception as e:
                    logger.error(f"Error creating card {card_data.get('api_id', 'unknown')}: {e}")
                    continue

            await session.commit()
            logger.info(f"✅ Bulk created {len(created_cards)} cards")
            return created_cards

        except Exception as e:
            await session.rollback()
            logger.error(f"Bulk card creation failed: {e}")
            raise


class SetCRUD:
    """CRUD operations for Pokemon sets"""

    @staticmethod
    async def create_set(session: AsyncSession, set_data: Dict[str, Any]) -> PokemonSet:
        """Create a new Pokemon set"""
        try:
            # Check if set already exists
            existing_set = await SetCRUD.get_set_by_id(session, set_data["id"])
            if existing_set:
                logger.warning(f"Set with ID {set_data['id']} already exists")
                return existing_set

            # Parse release date if it's a string
            release_date = set_data.get("release_date")
            if isinstance(release_date, str):
                release_date = datetime.fromisoformat(release_date.replace("Z", "+00:00")).date()

            pokemon_set = PokemonSet(
                id=set_data["id"],
                name=set_data["name"],
                series=set_data.get("series"),
                printed_total=set_data.get("printed_total"),
                total=set_data.get("total"),
                legalities=set_data.get("legalities", {}),
                images=set_data.get("images", {}),
                ptcgo_code=set_data.get("ptcgo_code"),
                release_date=release_date,
            )

            session.add(pokemon_set)
            await session.commit()
            await session.refresh(pokemon_set)

            logger.info(f"✅ Created set: {pokemon_set.name} ({pokemon_set.id})")
            return pokemon_set

        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Set creation failed - integrity error: {e}")
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Set creation failed: {e}")
            raise

    @staticmethod
    async def get_set_by_id(session: AsyncSession, set_id: str) -> Optional[PokemonSet]:
        """Get set by ID"""
        try:
            result = await session.execute(
                select(PokemonSet)
                .options(selectinload(PokemonSet.cards))
                .where(PokemonSet.id == set_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting set by ID {set_id}: {e}")
            return None

    @staticmethod
    async def get_set_by_name(session: AsyncSession, name: str) -> Optional[PokemonSet]:
        """Get set by name"""
        try:
            result = await session.execute(
                select(PokemonSet)
                .options(selectinload(PokemonSet.cards))
                .where(PokemonSet.name.ilike(f"%{name}%"))
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting set by name {name}: {e}")
            return None

    @staticmethod
    async def get_all_sets(session: AsyncSession, limit: int = 100) -> List[PokemonSet]:
        """Get all sets"""
        try:
            result = await session.execute(
                select(PokemonSet).order_by(PokemonSet.release_date.desc()).limit(limit)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting all sets: {e}")
            return []

    @staticmethod
    async def get_set_completion_status(session: AsyncSession, set_id: str) -> Dict[str, Any]:
        """Get completion status for a set"""
        try:
            # Get the set
            pokemon_set = await SetCRUD.get_set_by_id(session, set_id)
            if not pokemon_set:
                return {}

            # Count cards in database
            result = await session.execute(
                select(func.count(PokemonCard.id)).where(PokemonCard.set_id == set_id)
            )
            cards_in_db = result.scalar() or 0

            return {
                "set_name": pokemon_set.name,
                "total_cards": pokemon_set.total or 0,
                "cards_in_database": cards_in_db,
                "completion_percentage": (
                    (cards_in_db / pokemon_set.total * 100) if pokemon_set.total else 0
                ),
            }
        except Exception as e:
            logger.error(f"Error getting set completion status: {e}")
            return {}


class PriceCRUD:
    """CRUD operations for price snapshots"""

    @staticmethod
    async def create_price_snapshot(
        session: AsyncSession, card_id: Union[str, uuid.UUID], price_data: Dict[str, Any]
    ) -> PriceSnapshot:
        """Create a new price snapshot"""
        try:
            if isinstance(card_id, str):
                card_id = uuid.UUID(card_id)

            price_snapshot = PriceSnapshot(
                card_id=card_id,
                variation_id=price_data.get("variation_id"),
                timestamp=price_data.get("timestamp", datetime.utcnow()),
                prices=price_data.get("prices", {}),
                source=price_data.get("source", "unknown"),
                condition=price_data.get("condition", "NM"),
                currency=price_data.get("currency", "USD"),
                volume=price_data.get("volume"),
                listings_count=price_data.get("listings_count"),
            )

            session.add(price_snapshot)
            await session.commit()
            await session.refresh(price_snapshot)

            logger.debug(f"✅ Created price snapshot for card {card_id}")
            return price_snapshot

        except Exception as e:
            await session.rollback()
            logger.error(f"Price snapshot creation failed: {e}")
            raise

    @staticmethod
    async def get_latest_price(
        session: AsyncSession, card_id: Union[str, uuid.UUID]
    ) -> Optional[PriceSnapshot]:
        """Get the latest price for a card"""
        try:
            if isinstance(card_id, str):
                card_id = uuid.UUID(card_id)

            result = await session.execute(
                select(PriceSnapshot)
                .where(PriceSnapshot.card_id == card_id)
                .order_by(PriceSnapshot.timestamp.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting latest price for card {card_id}: {e}")
            return None

    @staticmethod
    async def get_price_history(
        session: AsyncSession, card_id: Union[str, uuid.UUID], days: int = 30
    ) -> List[PriceSnapshot]:
        """Get price history for a card"""
        try:
            if isinstance(card_id, str):
                card_id = uuid.UUID(card_id)

            since_date = datetime.utcnow() - timedelta(days=days)

            result = await session.execute(
                select(PriceSnapshot)
                .where(
                    and_(PriceSnapshot.card_id == card_id, PriceSnapshot.timestamp >= since_date)
                )
                .order_by(PriceSnapshot.timestamp.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting price history for card {card_id}: {e}")
            return []

    @staticmethod
    async def bulk_update_prices(
        session: AsyncSession, price_updates: List[Dict[str, Any]]
    ) -> List[PriceSnapshot]:
        """Update multiple prices in bulk"""
        try:
            created_snapshots = []

            for price_update in price_updates:
                try:
                    snapshot = await PriceCRUD.create_price_snapshot(session, **price_update)
                    created_snapshots.append(snapshot)
                except Exception as e:
                    logger.error(f"Error creating price snapshot: {e}")
                    continue

            logger.info(f"✅ Bulk updated {len(created_snapshots)} price snapshots")
            return created_snapshots

        except Exception as e:
            logger.error(f"Bulk price update failed: {e}")
            raise


class ValidationCRUD:
    """CRUD operations for validation and corrections"""

    @staticmethod
    async def get_validation_rules(
        session: AsyncSession, active_only: bool = True
    ) -> List[ValidationRule]:
        """Get validation rules"""
        try:
            query = select(ValidationRule)
            if active_only:
                query = query.where(ValidationRule.is_active == True)

            result = await session.execute(query.order_by(ValidationRule.priority.desc()))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting validation rules: {e}")
            return []

    @staticmethod
    async def create_ximilar_correction(
        session: AsyncSession, correction_data: Dict[str, Any]
    ) -> XimilarCorrection:
        """Create a new Ximilar correction"""
        try:
            correction = XimilarCorrection(
                ximilar_result=correction_data["ximilar_result"],
                correct_card_id=correction_data.get("correct_card_id"),
                correct_variation_id=correction_data.get("correct_variation_id"),
                confidence_threshold=correction_data.get("confidence_threshold", 1.0),
                notes=correction_data.get("notes"),
            )

            session.add(correction)
            await session.commit()
            await session.refresh(correction)

            logger.info(f"✅ Created Ximilar correction")
            return correction

        except Exception as e:
            await session.rollback()
            logger.error(f"Ximilar correction creation failed: {e}")
            raise


# Convenience functions for common operations
async def get_or_create_card(
    session: AsyncSession, card_data: Dict[str, Any]
) -> Tuple[PokemonCard, bool]:
    """Get existing card or create new one"""
    card = await CardCRUD.get_card_by_api_id(session, card_data["api_id"])
    if card:
        return card, False
    else:
        new_card = await CardCRUD.create_card(session, card_data)
        return new_card, True


async def get_or_create_set(
    session: AsyncSession, set_data: Dict[str, Any]
) -> Tuple[PokemonSet, bool]:
    """Get existing set or create new one"""
    pokemon_set = await SetCRUD.get_set_by_id(session, set_data["id"])
    if pokemon_set:
        return pokemon_set, False
    else:
        new_set = await SetCRUD.create_set(session, set_data)
        return new_set, True


async def persist_api_card_data(
    session: AsyncSession, api_card_data: Dict[str, Any]
) -> PokemonCard:
    """Persist card data from Pokemon TCG API to database"""
    try:
        # Extract set data
        set_data = api_card_data.get("set", {})
        if set_data:
            # Create/get set first
            await get_or_create_set(session, set_data)

        # Extract card data
        card_data = {
            "api_id": api_card_data["id"],
            "name": api_card_data["name"],
            "number": api_card_data["number"],
            "set_id": set_data.get("id"),
            "supertype": api_card_data.get("supertype"),
            "rarity": api_card_data.get("rarity"),
            "hp": api_card_data.get("hp"),
            "evolves_from": api_card_data.get("evolvesFrom"),
            "evolves_to": api_card_data.get("evolvesTo", []),
            "abilities": api_card_data.get("abilities", []),
            "attacks": api_card_data.get("attacks", []),
            "weaknesses": api_card_data.get("weaknesses", []),
            "resistances": api_card_data.get("resistances", []),
            "retreat_cost": api_card_data.get("retreatCost", []),
            "rules": api_card_data.get("rules", []),
            "images": api_card_data.get("images", {}),
            "tcgplayer_id": api_card_data.get("tcgplayer", {}).get("productId"),
            "artist": api_card_data.get("artist"),
            "regulation_mark": api_card_data.get("regulationMark"),
        }

        # Create/get card
        card, created = await get_or_create_card(session, card_data)

        # Create price snapshot if pricing data exists
        tcgplayer_data = api_card_data.get("tcgplayer", {})
        if tcgplayer_data.get("prices"):
            # Find the best price to store
            prices = tcgplayer_data["prices"]
            best_price = None

            # Priority order for price categories
            price_categories = ["normal", "holofoil", "reverseHolofoil", "1stEdition", "unlimited"]
            for category in price_categories:
                if category in prices and prices[category].get("market"):
                    best_price = prices[category]["market"]
                    break

            if best_price:
                price_data = {
                    "prices": {"market": best_price},
                    "source": "pokemon_tcg_api",
                    "condition": "NM",
                    "currency": "USD",
                }
                await PriceCRUD.create_price_snapshot(session, card.id, price_data)

        return card

    except Exception as e:
        logger.error(f"Error persisting API card data: {e}")
        raise
