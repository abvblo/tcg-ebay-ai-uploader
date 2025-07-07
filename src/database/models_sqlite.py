"""SQLite version of database models for Pokemon card reference data"""

from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Date, Text, ForeignKey, Index, UniqueConstraint, Table, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import uuid
import json

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

# Association tables for many-to-many relationships
card_subtypes = Table('card_subtypes', Base.metadata,
    Column('card_id', String(36), ForeignKey('pokemon_cards.id')),
    Column('subtype_id', Integer, ForeignKey('subtypes.id')),
    UniqueConstraint('card_id', 'subtype_id')
)

card_types = Table('card_types', Base.metadata,
    Column('card_id', String(36), ForeignKey('pokemon_cards.id')),
    Column('type_id', Integer, ForeignKey('types.id')),
    UniqueConstraint('card_id', 'type_id')
)

class PokemonSet(Base):
    """Pokemon TCG Set information"""
    __tablename__ = 'pokemon_sets'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False, index=True)
    series = Column(String(100), index=True)
    printed_total = Column(Integer)
    total = Column(Integer)
    
    # JSON fields for SQLite
    legalities = Column(Text)  # JSON string
    images = Column(Text)  # JSON string
    
    ptcgo_code = Column(String(20))
    release_date = Column(Date, index=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    cards = relationship("PokemonCard", back_populates="set", cascade="all, delete-orphan")
    
    def get_legalities(self):
        return json.loads(self.legalities) if self.legalities else {}
    
    def set_legalities(self, value):
        self.legalities = json.dumps(value) if value else None
    
    def get_images(self):
        return json.loads(self.images) if self.images else {}
    
    def set_images(self, value):
        self.images = json.dumps(value) if value else None

class PokemonCard(Base):
    """Individual Pokemon card data"""
    __tablename__ = 'pokemon_cards'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    api_id = Column(String(50), unique=True, nullable=False, index=True)
    
    # Core identification
    name = Column(String(200), nullable=False, index=True)
    number = Column(String(20), nullable=False)
    set_id = Column(String(50), ForeignKey('pokemon_sets.id'), nullable=False)
    
    # Enumerated values
    supertype = Column(String(50), index=True)
    rarity = Column(String(50), index=True)
    
    # Pokemon-specific attributes
    hp = Column(Integer)
    evolves_from = Column(String(100))
    evolves_to = Column(Text)  # JSON array
    
    # JSON fields
    abilities = Column(Text)
    attacks = Column(Text)
    weaknesses = Column(Text)
    resistances = Column(Text)
    retreat_cost = Column(Text)
    rules = Column(Text)
    images = Column(Text)
    
    # Market identifiers
    tcgplayer_id = Column(String(50), index=True)
    cardmarket_id = Column(String(50))
    
    # Artist and regulation
    artist = Column(String(200))
    regulation_mark = Column(String(10))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    set = relationship("PokemonSet", back_populates="cards")
    subtypes = relationship("Subtype", secondary=card_subtypes, back_populates="cards")
    types = relationship("Type", secondary=card_types, back_populates="cards")
    variations = relationship("CardVariation", back_populates="card", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('set_id', 'number', name='uq_set_number'),
        Index('idx_card_hp', 'hp'),
        Index('idx_card_evolves', 'evolves_from'),
    )
    
    # Helper methods for JSON fields
    def get_json_field(self, field_name):
        value = getattr(self, field_name)
        return json.loads(value) if value else None
    
    def set_json_field(self, field_name, value):
        setattr(self, field_name, json.dumps(value) if value else None)

class Type(Base):
    """Pokemon types (normalized)"""
    __tablename__ = 'types'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    
    cards = relationship("PokemonCard", secondary=card_types, back_populates="types")

class Subtype(Base):
    """Card subtypes (normalized)"""
    __tablename__ = 'subtypes'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String(50))
    
    cards = relationship("PokemonCard", secondary=card_subtypes, back_populates="subtypes")

class CardVariation(Base):
    """Different printings/variations of cards"""
    __tablename__ = 'card_variations'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    card_id = Column(String(36), ForeignKey('pokemon_cards.id'), nullable=False)
    
    # Variation details
    variation_type = Column(String(50), nullable=False)
    finish = Column(String(50))
    
    # Special characteristics
    is_reverse_holo = Column(Boolean, default=False, index=True)
    is_first_edition = Column(Boolean, default=False, index=True)
    is_shadowless = Column(Boolean, default=False, index=True)
    is_stamped = Column(Boolean, default=False, index=True)
    is_promo = Column(Boolean, default=False, index=True)
    
    # Stamp details
    stamp_type = Column(String(100))
    stamp_text = Column(String(200))
    
    # Market identifiers
    tcgplayer_sku = Column(String(50), unique=True)
    tcgplayer_product_id = Column(String(50))
    price_category = Column(String(100))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    card = relationship("PokemonCard", back_populates="variations")
    
    __table_args__ = (
        UniqueConstraint('card_id', 'variation_type', 'stamp_type', name='uq_card_variation'),
        Index('idx_variation_stamps', 'is_stamped', 'stamp_type'),
    )

# Database configuration
class DatabaseConfig:
    """Database configuration for SQLite"""
    
    @staticmethod
    def get_connection_string(db_path='pokemon_tcg.db'):
        return f'sqlite:///{db_path}'
    
    @staticmethod
    def get_engine(connection_string, **kwargs):
        """Create engine for SQLite"""
        return create_engine(
            connection_string,
            echo=False,
            **kwargs
        )

def init_database(connection_string):
    """Initialize the database with all tables"""
    engine = DatabaseConfig.get_engine(connection_string)
    Base.metadata.create_all(engine)
    return engine

def get_session(engine):
    """Get a database session"""
    Session = sessionmaker(bind=engine)
    return Session()