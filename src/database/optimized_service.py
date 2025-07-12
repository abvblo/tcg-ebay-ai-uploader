"""Optimized database service with bulk operations and eager loading"""

import asyncio
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import and_, create_engine, desc, func, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker

from ..utils.logger import logger
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
from .service import DatabaseService


class OptimizedDatabaseService(DatabaseService):
    """Enhanced database service with performance optimizations"""

    def __init__(self, connection_string: str = None, pool_size: int = 30, max_overflow: int = 60):
        """Initialize with larger connection pool for better concurrency"""
        super().__init__(connection_string, pool_size, max_overflow)

        # Cache for types and subtypes to avoid repeated queries
        self._type_cache: Dict[str, Type] = {}
        self._subtype_cache: Dict[str, Subtype] = {}
        self._set_cache: Dict[str, PokemonSet] = {}
        self._cache_loaded = False

    def _load_caches(self, session: Session):
        """Pre-load frequently accessed data into memory"""
        if not self._cache_loaded:
            # Load all types
            for type_obj in session.query(Type).all():
                self._type_cache[type_obj.name] = type_obj

            # Load all subtypes
            for subtype_obj in session.query(Subtype).all():
                self._subtype_cache[subtype_obj.name] = subtype_obj

            # Load all sets
            for set_obj in session.query(PokemonSet).all():
                self._set_cache[set_obj.id] = set_obj

            self._cache_loaded = True
            logger.info(
                f"Loaded caches: {len(self._type_cache)} types, "
                f"{len(self._subtype_cache)} subtypes, {len(self._set_cache)} sets"
            )

    def store_cards_bulk(self, cards_data: List[Dict[str, Any]]) -> List[Optional[str]]:
        """Store multiple cards efficiently in a single transaction"""
        card_ids = []

        try:
            with self.get_session() as session:
                # Pre-load caches
                self._load_caches(session)

                # Prepare bulk data
                sets_to_create = {}
                types_to_create = set()
                subtypes_to_create = set()

                # First pass: collect all unique entities
                for card_data in cards_data:
                    # Collect sets
                    set_data = card_data.get("set", {})
                    set_id = set_data.get("id", f"unknown_{set_data.get('name', 'unknown')}")
                    if set_id not in self._set_cache and set_id not in sets_to_create:
                        sets_to_create[set_id] = set_data

                    # Collect types
                    for type_name in card_data.get("types", []):
                        if type_name not in self._type_cache:
                            types_to_create.add(type_name)

                    # Collect subtypes
                    for subtype_name in card_data.get("subtypes", []):
                        if subtype_name not in self._subtype_cache:
                            subtypes_to_create.add(subtype_name)

                # Bulk create sets
                if sets_to_create:
                    self._bulk_create_sets(session, sets_to_create)

                # Bulk create types
                if types_to_create:
                    self._bulk_create_types(session, types_to_create)

                # Bulk create subtypes
                if subtypes_to_create:
                    self._bulk_create_subtypes(session, subtypes_to_create)

                # Now create/update all cards
                for card_data in cards_data:
                    card_id = self._store_single_card(session, card_data)
                    card_ids.append(card_id)

                session.commit()
                logger.info(f"Successfully stored {len(card_ids)} cards in bulk")

        except Exception as e:
            logger.error(f"Error in bulk card storage: {e}")
            card_ids = [None] * len(cards_data)

        return card_ids

    def _bulk_create_sets(self, session: Session, sets_data: Dict[str, Dict[str, Any]]):
        """Bulk create Pokemon sets"""
        set_objects = []

        for set_id, set_data in sets_data.items():
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
            set_objects.append(set_obj)
            self._set_cache[set_id] = set_obj

        session.bulk_save_objects(set_objects)
        session.flush()

    def _bulk_create_types(self, session: Session, type_names: Set[str]):
        """Bulk create types"""
        type_objects = []

        for type_name in type_names:
            type_obj = Type(name=type_name)
            type_objects.append(type_obj)
            self._type_cache[type_name] = type_obj

        session.bulk_save_objects(type_objects)
        session.flush()

    def _bulk_create_subtypes(self, session: Session, subtype_names: Set[str]):
        """Bulk create subtypes"""
        subtype_objects = []

        for subtype_name in subtype_names:
            subtype_obj = Subtype(name=subtype_name, category="unknown")
            subtype_objects.append(subtype_obj)
            self._subtype_cache[subtype_name] = subtype_obj

        session.bulk_save_objects(subtype_objects)
        session.flush()

    def _store_single_card(self, session: Session, card_data: Dict[str, Any]) -> Optional[str]:
        """Store a single card using cached lookups"""
        try:
            # Get set from cache
            set_data = card_data.get("set", {})
            set_id = set_data.get("id", f"unknown_{set_data.get('name', 'unknown')}")
            set_obj = self._set_cache.get(set_id)

            if not set_obj:
                # Fallback to creating if not in cache
                set_obj = self._get_or_create_set(session, card_data)
                self._set_cache[set_id] = set_obj

            # Check if card exists (using index on api_id)
            api_id = card_data.get("id", card_data.get("api_id"))
            card = session.query(PokemonCard).filter(PokemonCard.api_id == api_id).first()

            if card:
                # Update existing
                self._update_card_data_optimized(session, card, card_data, set_obj)
            else:
                # Create new
                card = self._create_card_data_optimized(session, card_data, set_obj)

            session.flush()
            return str(card.id)

        except Exception as e:
            logger.error(f"Error storing card {card_data.get('name')}: {e}")
            return None

    def _create_card_data_optimized(
        self, session: Session, card_data: Dict[str, Any], set_obj: PokemonSet
    ) -> PokemonCard:
        """Create card with optimized type/subtype assignment"""
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

        # Add types and subtypes using cache
        self._add_card_types_optimized(session, card, card_data.get("types", []))
        self._add_card_subtypes_optimized(session, card, card_data.get("subtypes", []))

        return card

    def _add_card_types_optimized(self, session: Session, card: PokemonCard, types: List[str]):
        """Add types using cache (no N+1 queries)"""
        for type_name in types:
            type_obj = self._type_cache.get(type_name)
            if type_obj and type_obj not in card.types:
                card.types.append(type_obj)

    def _add_card_subtypes_optimized(
        self, session: Session, card: PokemonCard, subtypes: List[str]
    ):
        """Add subtypes using cache (no N+1 queries)"""
        for subtype_name in subtypes:
            subtype_obj = self._subtype_cache.get(subtype_name)
            if subtype_obj and subtype_obj not in card.subtypes:
                card.subtypes.append(subtype_obj)

    def _update_card_data_optimized(
        self, session: Session, card: PokemonCard, card_data: Dict[str, Any], set_obj: PokemonSet
    ):
        """Update card with optimized operations"""
        # Update basic fields
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
        card.artist = card_data.get("artist", card.artist)
        card.regulation_mark = card_data.get("regulationMark", card.regulation_mark)
        card.updated_at = datetime.utcnow()

        # Update types and subtypes efficiently
        self._update_card_types_optimized(session, card, card_data.get("types", []))
        self._update_card_subtypes_optimized(session, card, card_data.get("subtypes", []))

    def _update_card_types_optimized(self, session: Session, card: PokemonCard, types: List[str]):
        """Update types efficiently"""
        # Clear existing
        card.types.clear()

        # Add new using cache
        for type_name in types:
            type_obj = self._type_cache.get(type_name)
            if type_obj:
                card.types.append(type_obj)

    def _update_card_subtypes_optimized(
        self, session: Session, card: PokemonCard, subtypes: List[str]
    ):
        """Update subtypes efficiently"""
        # Clear existing
        card.subtypes.clear()

        # Add new using cache
        for subtype_name in subtypes:
            subtype_obj = self._subtype_cache.get(subtype_name)
            if subtype_obj:
                card.subtypes.append(subtype_obj)

    def get_cards_with_prices_bulk(self, card_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get multiple cards with their latest prices in a single query"""
        results = {}

        try:
            with self.get_session() as session:
                # Eager load related data to avoid N+1 queries
                cards = (
                    session.query(PokemonCard)
                    .options(
                        joinedload(PokemonCard.set),
                        selectinload(PokemonCard.types),
                        selectinload(PokemonCard.subtypes),
                        selectinload(PokemonCard.variations),
                        selectinload(PokemonCard.prices),
                    )
                    .filter(PokemonCard.id.in_(card_ids))
                    .all()
                )

                for card in cards:
                    card_dict = self._card_to_dict(card)

                    # Get latest price from already loaded prices
                    if card.prices:
                        latest_price = max(card.prices, key=lambda p: p.timestamp)
                        card_dict["latest_price"] = {
                            "prices": latest_price.prices,
                            "source": latest_price.source,
                            "condition": latest_price.condition,
                            "timestamp": latest_price.timestamp,
                            "currency": latest_price.currency,
                        }

                    results[str(card.id)] = card_dict

        except Exception as e:
            logger.error(f"Error getting cards with prices: {e}")

        return results

    def store_price_data_bulk(self, price_data_list: List[Dict[str, Any]]) -> int:
        """Store multiple price snapshots efficiently"""
        stored_count = 0

        try:
            with self.get_session() as session:
                price_objects = []

                for price_data in price_data_list:
                    price_snapshot = PriceSnapshot(
                        card_id=price_data["card_id"],
                        variation_id=price_data.get("variation_id"),
                        timestamp=datetime.utcnow(),
                        prices=price_data.get("prices", {}),
                        source=price_data.get("source", "unknown"),
                        condition=price_data.get("condition", "NM"),
                        currency=price_data.get("currency", "USD"),
                        volume=price_data.get("volume"),
                        listings_count=price_data.get("listings_count"),
                    )
                    price_objects.append(price_snapshot)

                session.bulk_save_objects(price_objects)
                session.commit()
                stored_count = len(price_objects)

                logger.info(f"Stored {stored_count} price snapshots in bulk")

        except Exception as e:
            logger.error(f"Error storing price data in bulk: {e}")

        return stored_count

    def search_cards_optimized(
        self, query: str, filters: Dict[str, Any] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Optimized card search with full-text search and eager loading"""
        results = []

        try:
            with self.get_session() as session:
                # Base query with eager loading
                q = session.query(PokemonCard).options(
                    joinedload(PokemonCard.set),
                    selectinload(PokemonCard.types),
                    selectinload(PokemonCard.subtypes),
                )

                # Full-text search if available
                if query:
                    # Use PostgreSQL full-text search
                    q = q.filter(func.to_tsvector("english", PokemonCard.name).match(query))

                # Apply filters
                if filters:
                    if filters.get("set_id"):
                        q = q.filter(PokemonCard.set_id == filters["set_id"])
                    if filters.get("rarity"):
                        q = q.filter(PokemonCard.rarity == filters["rarity"])
                    if filters.get("supertype"):
                        q = q.filter(PokemonCard.supertype == filters["supertype"])
                    if filters.get("hp_min"):
                        q = q.filter(PokemonCard.hp >= filters["hp_min"])
                    if filters.get("hp_max"):
                        q = q.filter(PokemonCard.hp <= filters["hp_max"])

                # Limit results
                cards = q.limit(limit).all()

                # Convert to dicts
                for card in cards:
                    results.append(self._card_to_dict(card))

        except Exception as e:
            logger.error(f"Error in optimized search: {e}")

        return results

    def refresh_caches(self):
        """Refresh in-memory caches"""
        self._cache_loaded = False
        self._type_cache.clear()
        self._subtype_cache.clear()
        self._set_cache.clear()

        with self.get_session() as session:
            self._load_caches(session)
