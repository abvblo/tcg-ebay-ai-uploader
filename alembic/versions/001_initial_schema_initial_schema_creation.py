"""Initial schema creation

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-07-10T20:49:16.636860

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply database schema changes.
    
    Changes in this migration:
    - Create all initial tables for Pokemon TCG database
    - Set up association tables for many-to-many relationships
    - Create indexes for performance optimization
    - Add full-text search support with tsvector columns
    """
    
    # Create pokemon_sets table
    op.create_table('pokemon_sets',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('series', sa.String(length=100), nullable=True),
        sa.Column('printed_total', sa.Integer(), nullable=True),
        sa.Column('total', sa.Integer(), nullable=True),
        sa.Column('legalities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('images', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ptcgo_code', sa.String(length=20), nullable=True),
        sa.Column('release_date', sa.Date(), nullable=True),
        sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_set_search', 'pokemon_sets', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_pokemon_sets_name'), 'pokemon_sets', ['name'], unique=False)
    op.create_index(op.f('ix_pokemon_sets_release_date'), 'pokemon_sets', ['release_date'], unique=False)
    op.create_index(op.f('ix_pokemon_sets_series'), 'pokemon_sets', ['series'], unique=False)

    # Create types table
    op.create_table('types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create subtypes table
    op.create_table('subtypes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create validation_rules table
    op.create_table('validation_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rule_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create pokemon_cards table
    op.create_table('pokemon_cards',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('api_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('number', sa.String(length=20), nullable=False),
        sa.Column('set_id', sa.String(length=50), nullable=False),
        sa.Column('supertype', sa.String(length=50), nullable=True),
        sa.Column('rarity', sa.String(length=50), nullable=True),
        sa.Column('hp', sa.Integer(), nullable=True),
        sa.Column('evolves_from', sa.String(length=100), nullable=True),
        sa.Column('evolves_to', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('abilities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('attacks', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('weaknesses', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('resistances', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('retreat_cost', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('rules', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('images', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tcgplayer_id', sa.String(length=50), nullable=True),
        sa.Column('cardmarket_id', sa.String(length=50), nullable=True),
        sa.Column('artist', sa.String(length=200), nullable=True),
        sa.Column('regulation_mark', sa.String(length=10), nullable=True),
        sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['set_id'], ['pokemon_sets.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('api_id'),
        sa.UniqueConstraint('set_id', 'number', name='uq_set_number')
    )
    op.create_index('idx_card_evolves', 'pokemon_cards', ['evolves_from'], unique=False)
    op.create_index('idx_card_hp', 'pokemon_cards', ['hp'], unique=False)
    op.create_index('idx_card_search', 'pokemon_cards', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_pokemon_cards_api_id'), 'pokemon_cards', ['api_id'], unique=False)
    op.create_index(op.f('ix_pokemon_cards_cardmarket_id'), 'pokemon_cards', ['cardmarket_id'], unique=False)
    op.create_index(op.f('ix_pokemon_cards_name'), 'pokemon_cards', ['name'], unique=False)
    op.create_index(op.f('ix_pokemon_cards_rarity'), 'pokemon_cards', ['rarity'], unique=False)
    op.create_index(op.f('ix_pokemon_cards_supertype'), 'pokemon_cards', ['supertype'], unique=False)
    op.create_index(op.f('ix_pokemon_cards_tcgplayer_id'), 'pokemon_cards', ['tcgplayer_id'], unique=False)

    # Create card_variations table
    op.create_table('card_variations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('card_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('variation_type', sa.String(length=50), nullable=False),
        sa.Column('finish', sa.String(length=50), nullable=True),
        sa.Column('is_reverse_holo', sa.Boolean(), nullable=True),
        sa.Column('is_first_edition', sa.Boolean(), nullable=True),
        sa.Column('is_shadowless', sa.Boolean(), nullable=True),
        sa.Column('is_stamped', sa.Boolean(), nullable=True),
        sa.Column('is_promo', sa.Boolean(), nullable=True),
        sa.Column('stamp_type', sa.String(length=100), nullable=True),
        sa.Column('stamp_text', sa.String(length=200), nullable=True),
        sa.Column('tcgplayer_sku', sa.String(length=50), nullable=True),
        sa.Column('tcgplayer_product_id', sa.String(length=50), nullable=True),
        sa.Column('price_category', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['card_id'], ['pokemon_cards.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('card_id', 'variation_type', 'stamp_type', name='uq_card_variation'),
        sa.UniqueConstraint('tcgplayer_sku')
    )
    op.create_index('idx_variation_stamps', 'card_variations', ['is_stamped', 'stamp_type'], unique=False)
    op.create_index(op.f('ix_card_variations_is_first_edition'), 'card_variations', ['is_first_edition'], unique=False)
    op.create_index(op.f('ix_card_variations_is_promo'), 'card_variations', ['is_promo'], unique=False)
    op.create_index(op.f('ix_card_variations_is_reverse_holo'), 'card_variations', ['is_reverse_holo'], unique=False)
    op.create_index(op.f('ix_card_variations_is_shadowless'), 'card_variations', ['is_shadowless'], unique=False)
    op.create_index(op.f('ix_card_variations_is_stamped'), 'card_variations', ['is_stamped'], unique=False)

    # Create ximilar_corrections table
    op.create_table('ximilar_corrections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ximilar_result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('correct_card_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('correct_variation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('confidence_threshold', sa.Float(), nullable=True),
        sa.Column('times_applied', sa.Integer(), nullable=True),
        sa.Column('last_applied', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('verified', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['correct_card_id'], ['pokemon_cards.id'], ),
        sa.ForeignKeyConstraint(['correct_variation_id'], ['card_variations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_correction_ximilar', 'ximilar_corrections', ['ximilar_result'], unique=False, postgresql_using='gin')

    # Create association tables
    op.create_table('card_subtypes',
        sa.Column('card_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('subtype_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['card_id'], ['pokemon_cards.id'], ),
        sa.ForeignKeyConstraint(['subtype_id'], ['subtypes.id'], ),
        sa.UniqueConstraint('card_id', 'subtype_id')
    )

    op.create_table('card_types',
        sa.Column('card_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('type_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['card_id'], ['pokemon_cards.id'], ),
        sa.ForeignKeyConstraint(['type_id'], ['types.id'], ),
        sa.UniqueConstraint('card_id', 'type_id')
    )

    # Create price_snapshots table
    op.create_table('price_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('card_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('variation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('prices', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('condition', sa.String(length=50), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('volume', sa.Integer(), nullable=True),
        sa.Column('listings_count', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['card_id'], ['pokemon_cards.id'], ),
        sa.ForeignKeyConstraint(['variation_id'], ['card_variations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_price_card_time', 'price_snapshots', ['card_id', 'timestamp'], unique=False)
    op.create_index('idx_price_timestamp', 'price_snapshots', ['timestamp'], unique=False)
    op.create_index('idx_price_variation_time', 'price_snapshots', ['variation_id', 'timestamp'], unique=False)


def downgrade() -> None:
    """Revert database schema changes.
    
    This migration reverses:
    - Removes all tables in reverse dependency order
    - Drops all indexes
    """
    # Drop tables in reverse order of creation (to handle foreign key dependencies)
    op.drop_table('price_snapshots')
    op.drop_table('card_types')
    op.drop_table('card_subtypes')
    op.drop_index('idx_correction_ximilar', table_name='ximilar_corrections', postgresql_using='gin')
    op.drop_table('ximilar_corrections')
    
    op.drop_index(op.f('ix_card_variations_is_stamped'), table_name='card_variations')
    op.drop_index(op.f('ix_card_variations_is_shadowless'), table_name='card_variations')
    op.drop_index(op.f('ix_card_variations_is_reverse_holo'), table_name='card_variations')
    op.drop_index(op.f('ix_card_variations_is_promo'), table_name='card_variations')
    op.drop_index(op.f('ix_card_variations_is_first_edition'), table_name='card_variations')
    op.drop_index('idx_variation_stamps', table_name='card_variations')
    op.drop_table('card_variations')
    
    op.drop_index(op.f('ix_pokemon_cards_tcgplayer_id'), table_name='pokemon_cards')
    op.drop_index(op.f('ix_pokemon_cards_supertype'), table_name='pokemon_cards')
    op.drop_index(op.f('ix_pokemon_cards_rarity'), table_name='pokemon_cards')
    op.drop_index(op.f('ix_pokemon_cards_name'), table_name='pokemon_cards')
    op.drop_index(op.f('ix_pokemon_cards_cardmarket_id'), table_name='pokemon_cards')
    op.drop_index(op.f('ix_pokemon_cards_api_id'), table_name='pokemon_cards')
    op.drop_index('idx_card_search', table_name='pokemon_cards', postgresql_using='gin')
    op.drop_index('idx_card_hp', table_name='pokemon_cards')
    op.drop_index('idx_card_evolves', table_name='pokemon_cards')
    op.drop_table('pokemon_cards')
    
    op.drop_table('validation_rules')
    op.drop_table('subtypes')
    op.drop_table('types')
    
    op.drop_index(op.f('ix_pokemon_sets_series'), table_name='pokemon_sets')
    op.drop_index(op.f('ix_pokemon_sets_release_date'), table_name='pokemon_sets')
    op.drop_index(op.f('ix_pokemon_sets_name'), table_name='pokemon_sets')
    op.drop_index('idx_set_search', table_name='pokemon_sets', postgresql_using='gin')
    op.drop_table('pokemon_sets')
