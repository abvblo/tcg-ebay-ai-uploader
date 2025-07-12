"""Add performance optimization indexes

Revision ID: 002_performance_indexes
Revises: 001_initial_schema
Create Date: 2025-07-11T12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_performance_indexes'
down_revision: Union[str, Sequence[str], None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply database schema changes.
    
    Changes in this migration:
    - Add composite indexes for common query patterns
    - Add partial indexes for filtered queries
    - Add indexes for foreign key lookups
    - Create indexes for price analysis queries
    """
    
    # Composite indexes for common query patterns
    op.create_index(
        'idx_cards_set_rarity', 
        'pokemon_cards', 
        ['set_id', 'rarity'],
        unique=False
    )
    
    op.create_index(
        'idx_cards_name_set', 
        'pokemon_cards', 
        ['name', 'set_id'],
        unique=False
    )
    
    op.create_index(
        'idx_cards_supertype_rarity', 
        'pokemon_cards', 
        ['supertype', 'rarity'],
        unique=False
    )
    
    # Partial indexes for specific card types
    op.create_index(
        'idx_pokemon_cards_only',
        'pokemon_cards',
        ['name', 'hp'],
        unique=False,
        postgresql_where=sa.text("supertype = 'Pokémon'")
    )
    
    op.create_index(
        'idx_rare_cards',
        'pokemon_cards',
        ['set_id', 'name'],
        unique=False,
        postgresql_where=sa.text("rarity IN ('Rare Holo', 'Rare Ultra', 'Rare Secret', 'Rare Holo EX', 'Rare Holo GX', 'Rare Holo V', 'Rare Holo VMAX', 'Rare Holo VSTAR')")
    )
    
    # Indexes for variation queries
    op.create_index(
        'idx_variations_card_type',
        'card_variations',
        ['card_id', 'variation_type'],
        unique=False
    )
    
    op.create_index(
        'idx_first_edition_cards',
        'card_variations',
        ['card_id'],
        unique=False,
        postgresql_where=sa.text("is_first_edition = true")
    )
    
    # Price analysis indexes
    op.create_index(
        'idx_prices_source_condition',
        'price_snapshots',
        ['source', 'condition', 'timestamp'],
        unique=False
    )
    
    op.create_index(
        'idx_recent_prices',
        'price_snapshots',
        ['card_id', 'timestamp'],
        unique=False,
        postgresql_where=sa.text("timestamp > CURRENT_DATE - INTERVAL '30 days'")
    )
    
    # Foreign key performance indexes
    op.create_index(
        'idx_card_subtypes_subtype',
        'card_subtypes',
        ['subtype_id'],
        unique=False
    )
    
    op.create_index(
        'idx_card_types_type',
        'card_types',
        ['type_id'],
        unique=False
    )
    
    # Text search optimization
    op.execute("""
        CREATE INDEX idx_cards_name_trgm ON pokemon_cards 
        USING gin (name gin_trgm_ops);
    """)
    
    op.execute("""
        CREATE INDEX idx_sets_name_trgm ON pokemon_sets 
        USING gin (name gin_trgm_ops);
    """)
    
    # Update statistics for query planner
    op.execute("ANALYZE pokemon_cards;")
    op.execute("ANALYZE pokemon_sets;")
    op.execute("ANALYZE card_variations;")
    op.execute("ANALYZE price_snapshots;")


def downgrade() -> None:
    """Revert database schema changes.
    
    This migration reverses:
    - Removes all performance optimization indexes
    """
    # Drop text search indexes
    op.execute("DROP INDEX IF EXISTS idx_cards_name_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_sets_name_trgm;")
    
    # Drop foreign key indexes
    op.drop_index('idx_card_types_type', table_name='card_types')
    op.drop_index('idx_card_subtypes_subtype', table_name='card_subtypes')
    
    # Drop price analysis indexes
    op.drop_index('idx_recent_prices', table_name='price_snapshots')
    op.drop_index('idx_prices_source_condition', table_name='price_snapshots')
    
    # Drop variation indexes
    op.drop_index('idx_first_edition_cards', table_name='card_variations')
    op.drop_index('idx_variations_card_type', table_name='card_variations')
    
    # Drop partial indexes
    op.drop_index('idx_rare_cards', table_name='pokemon_cards')
    op.drop_index('idx_pokemon_cards_only', table_name='pokemon_cards')
    
    # Drop composite indexes
    op.drop_index('idx_cards_supertype_rarity', table_name='pokemon_cards')
    op.drop_index('idx_cards_name_set', table_name='pokemon_cards')
    op.drop_index('idx_cards_set_rarity', table_name='pokemon_cards')