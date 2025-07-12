"""Database models for Pokemon card reference data using PostgreSQL"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

# Association tables for many-to-many relationships
card_subtypes = Table(
    "card_subtypes",
    Base.metadata,
    Column("card_id", UUID(as_uuid=True), ForeignKey("pokemon_cards.id")),
    Column("subtype_id", Integer, ForeignKey("subtypes.id")),
    UniqueConstraint("card_id", "subtype_id"),
)

card_types = Table(
    "card_types",
    Base.metadata,
    Column("card_id", UUID(as_uuid=True), ForeignKey("pokemon_cards.id")),
    Column("type_id", Integer, ForeignKey("types.id")),
    UniqueConstraint("card_id", "type_id"),
)


class PokemonSet(Base):
    """Pokemon TCG Set information"""

    __tablename__ = "pokemon_sets"

    id = Column(String(50), primary_key=True)  # Official set ID from Pokemon TCG API
    name = Column(String(200), nullable=False, index=True)
    series = Column(String(100), index=True)
    printed_total = Column(Integer)  # Number shown on cards
    total = Column(Integer)  # Actual total including secrets

    # Structured data using JSONB for flexibility
    legalities = Column(JSONB)  # {"standard": "Legal", "expanded": "Legal"}
    images = Column(JSONB)  # {"symbol": "url", "logo": "url"}

    ptcgo_code = Column(String(20))
    release_date = Column(Date, index=True)

    # Full text search
    search_vector = Column(TSVECTOR)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    cards = relationship("PokemonCard", back_populates="set", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_set_search", "search_vector", postgresql_using="gin"),)


class PokemonCard(Base):
    """Individual Pokemon card data with optimized structure"""

    __tablename__ = "pokemon_cards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_id = Column(String(50), unique=True, nullable=False, index=True)  # Original API ID

    # Core identification
    name = Column(String(200), nullable=False, index=True)
    number = Column(String(20), nullable=False)
    set_id = Column(String(50), ForeignKey("pokemon_sets.id"), nullable=False)

    # Enumerated values for better performance
    supertype = Column(String(50), index=True)  # Pokemon, Trainer, Energy
    rarity = Column(String(50), index=True)

    # Pokemon-specific attributes
    hp = Column(Integer)  # Store as integer for better querying
    evolves_from = Column(String(100))

    # Use JSONB for complex nested data
    evolves_to = Column(ARRAY(String))  # PostgreSQL array
    abilities = Column(JSONB)  # [{"name": "...", "text": "...", "type": "..."}]
    attacks = Column(JSONB)  # [{"name": "...", "damage": "...", "cost": [...]}]
    weaknesses = Column(JSONB)  # [{"type": "...", "value": "..."}]
    resistances = Column(JSONB)  # [{"type": "...", "value": "..."}]
    retreat_cost = Column(ARRAY(String))  # ["Colorless", "Colorless"]

    # Rules and special text
    rules = Column(ARRAY(Text))

    # Images with different resolutions
    images = Column(JSONB)  # {"small": "url", "large": "url", "hiRes": "url"}

    # Market identifiers
    tcgplayer_id = Column(String(50), index=True)
    cardmarket_id = Column(String(50))

    # Artist and regulation
    artist = Column(String(200))
    regulation_mark = Column(String(10))

    # Full text search vector
    search_vector = Column(TSVECTOR)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    set = relationship("PokemonSet", back_populates="cards")
    subtypes = relationship("Subtype", secondary=card_subtypes, back_populates="cards")
    types = relationship("Type", secondary=card_types, back_populates="cards")
    variations = relationship("CardVariation", back_populates="card", cascade="all, delete-orphan")
    prices = relationship("PriceSnapshot", back_populates="card", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("set_id", "number", name="uq_set_number"),
        Index("idx_card_search", "search_vector", postgresql_using="gin"),
        Index("idx_card_hp", "hp"),
        Index("idx_card_evolves", "evolves_from"),
    )


class Type(Base):
    """Pokemon types (normalized)"""

    __tablename__ = "types"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

    cards = relationship("PokemonCard", secondary=card_types, back_populates="types")


class Subtype(Base):
    """Card subtypes (normalized)"""

    __tablename__ = "subtypes"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String(50))  # "pokemon", "trainer", "energy"

    cards = relationship("PokemonCard", secondary=card_subtypes, back_populates="subtypes")


class CardVariation(Base):
    """Different printings/variations of cards"""

    __tablename__ = "card_variations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    card_id = Column(UUID(as_uuid=True), ForeignKey("pokemon_cards.id"), nullable=False)

    # Variation details
    variation_type = Column(String(50), nullable=False)  # "normal", "reverse_holo", "1st_edition"
    finish = Column(String(50))  # "holofoil", "normal", etc.

    # Special characteristics as flags
    is_reverse_holo = Column(Boolean, default=False, index=True)
    is_first_edition = Column(Boolean, default=False, index=True)
    is_shadowless = Column(Boolean, default=False, index=True)
    is_stamped = Column(Boolean, default=False, index=True)
    is_promo = Column(Boolean, default=False, index=True)

    # Stamp details if applicable
    stamp_type = Column(String(100))  # "prerelease", "league", "staff", etc.
    stamp_text = Column(String(200))

    # Market identifiers for this specific variation
    tcgplayer_sku = Column(String(50), unique=True)
    tcgplayer_product_id = Column(String(50))
    price_category = Column(String(100))  # TCGPlayer price category

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    card = relationship("PokemonCard", back_populates="variations")
    prices = relationship("PriceSnapshot", back_populates="variation", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("card_id", "variation_type", "stamp_type", name="uq_card_variation"),
        Index("idx_variation_stamps", "is_stamped", "stamp_type"),
    )


class PriceSnapshot(Base):
    """Time-series price data with partitioning support"""

    __tablename__ = "price_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    card_id = Column(UUID(as_uuid=True), ForeignKey("pokemon_cards.id"), nullable=False)
    variation_id = Column(UUID(as_uuid=True), ForeignKey("card_variations.id"))

    # Timestamp for time-series queries
    timestamp = Column(DateTime, nullable=False, index=True)

    # Price data
    prices = Column(JSONB)  # {"market": 10.50, "low": 8.00, "mid": 10.00, "high": 15.00}

    # Context
    source = Column(String(50), nullable=False)  # "tcgplayer", "cardmarket"
    condition = Column(String(50), nullable=False)  # "NM", "LP", etc.
    currency = Column(String(10), default="USD")

    # Volume and availability
    volume = Column(Integer)
    listings_count = Column(Integer)

    # Relationships
    card = relationship("PokemonCard", back_populates="prices")
    variation = relationship("CardVariation", back_populates="prices")

    __table_args__ = (
        Index("idx_price_timestamp", "timestamp"),
        Index("idx_price_card_time", "card_id", "timestamp"),
        Index("idx_price_variation_time", "variation_id", "timestamp"),
        # This table should be partitioned by timestamp in production
    )


class ValidationRule(Base):
    """Rules for validating Ximilar results against database"""

    __tablename__ = "validation_rules"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)

    # Rule definition in JSONB for flexibility
    rule_config = Column(JSONB, nullable=False)
    # Example: {
    #   "type": "era_mismatch",
    #   "conditions": {
    #     "card_patterns": ["V", "VMAX", "VSTAR"],
    #     "invalid_series": ["Base", "Jungle", "Fossil"]
    #   }
    # }

    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class XimilarCorrection(Base):
    """Learned corrections from Ximilar misidentifications"""

    __tablename__ = "ximilar_corrections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # What Ximilar identified
    ximilar_result = Column(JSONB, nullable=False)
    # {"name": "...", "set": "...", "number": "...", "confidence": 0.75}

    # Correct card
    correct_card_id = Column(UUID(as_uuid=True), ForeignKey("pokemon_cards.id"))
    correct_variation_id = Column(UUID(as_uuid=True), ForeignKey("card_variations.id"))

    # Context for when to apply
    confidence_threshold = Column(Float, default=1.0)

    # Usage tracking
    times_applied = Column(Integer, default=0)
    last_applied = Column(DateTime)

    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified = Column(Boolean, default=False)

    # Relationships
    correct_card = relationship("PokemonCard")
    correct_variation = relationship("CardVariation")

    __table_args__ = (Index("idx_correction_ximilar", "ximilar_result", postgresql_using="gin"),)


# Database configuration
class DatabaseConfig:
    """Database configuration for production use"""

    @staticmethod
    def get_connection_string(
        host="localhost",
        port=5432,
        database="pokemon_tcg",
        username="postgres",
        password="password",
    ):
        return f"postgresql://{username}:{password}@{host}:{port}/{database}"

    @staticmethod
    def get_engine(connection_string, **kwargs):
        """Create engine with optimized settings"""
        # Set default values but allow kwargs to override
        engine_kwargs = {
            'pool_size': 20,
            'max_overflow': 40,
            'pool_pre_ping': True,
            'pool_recycle': 3600,
            'echo': False,
        }
        engine_kwargs.update(kwargs)
        return create_engine(connection_string, **engine_kwargs)


def init_database(connection_string):
    """Initialize the database with all tables"""
    engine = DatabaseConfig.get_engine(connection_string)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """Get a database session"""
    Session = sessionmaker(bind=engine)
    return Session()
