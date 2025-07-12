"""Add audit fields and enhancements

Revision ID: 003_audit_enhancements
Revises: 002_performance_indexes
Create Date: 2025-07-11T12:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_audit_enhancements'
down_revision: Union[str, Sequence[str], None] = '002_performance_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply database schema changes.
    
    Changes in this migration:
    - Add audit log table for tracking changes
    - Add user identification table
    - Add batch upload tracking table
    - Add triggers for automatic timestamp updates
    """
    
    # Create audit log table
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('table_name', sa.String(length=50), nullable=False),
        sa.Column('record_id', sa.String(length=100), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),  # INSERT, UPDATE, DELETE
        sa.Column('old_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('changed_by', sa.String(length=100), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_table_record', 'audit_logs', ['table_name', 'record_id'], unique=False)
    op.create_index('idx_audit_changed_at', 'audit_logs', ['changed_at'], unique=False)
    
    # Create user identification results table
    op.create_table('identification_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('image_path', sa.String(length=500), nullable=False),
        sa.Column('image_hash', sa.String(length=64), nullable=True),  # SHA-256 hash
        sa.Column('identified_card_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('identified_variation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('ximilar_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('manual_override', sa.Boolean(), default=False),
        sa.Column('override_reason', sa.Text(), nullable=True),
        sa.Column('identified_at', sa.DateTime(), nullable=False),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['identified_card_id'], ['pokemon_cards.id'], ),
        sa.ForeignKeyConstraint(['identified_variation_id'], ['card_variations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_identification_confidence', 'identification_results', ['confidence_score'], unique=False)
    op.create_index('idx_identification_hash', 'identification_results', ['image_hash'], unique=False)
    
    # Create batch upload tracking table
    op.create_table('batch_uploads',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('batch_name', sa.String(length=200), nullable=False),
        sa.Column('upload_status', sa.String(length=50), nullable=False),  # pending, processing, completed, failed
        sa.Column('total_items', sa.Integer(), nullable=False),
        sa.Column('processed_items', sa.Integer(), default=0),
        sa.Column('successful_items', sa.Integer(), default=0),
        sa.Column('failed_items', sa.Integer(), default=0),
        sa.Column('ebay_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_batch_status', 'batch_uploads', ['upload_status', 'started_at'], unique=False)
    
    # Create batch items table
    op.create_table('batch_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('identification_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('item_status', sa.String(length=50), nullable=False),  # pending, listed, failed
        sa.Column('ebay_item_id', sa.String(length=50), nullable=True),
        sa.Column('listing_price', sa.Float(), nullable=True),
        sa.Column('listing_title', sa.String(length=200), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batch_uploads.id'], ),
        sa.ForeignKeyConstraint(['identification_id'], ['identification_results.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_batch_items_batch', 'batch_items', ['batch_id', 'item_status'], unique=False)
    
    # Create function for updating timestamps
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Create triggers for automatic timestamp updates
    tables_with_updated_at = [
        'pokemon_cards', 'pokemon_sets', 'card_variations', 
        'validation_rules', 'ximilar_corrections'
    ]
    
    for table in tables_with_updated_at:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at 
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """)
    
    # Add check constraints
    op.create_check_constraint(
        'ck_confidence_range',
        'identification_results',
        'confidence_score >= 0 AND confidence_score <= 1'
    )
    
    op.create_check_constraint(
        'ck_batch_counts',
        'batch_uploads',
        'processed_items <= total_items AND successful_items <= processed_items AND failed_items <= processed_items'
    )


def downgrade() -> None:
    """Revert database schema changes.
    
    This migration reverses:
    - Removes audit and tracking tables
    - Removes triggers and functions
    - Removes check constraints
    """
    # Drop check constraints
    op.drop_constraint('ck_batch_counts', 'batch_uploads')
    op.drop_constraint('ck_confidence_range', 'identification_results')
    
    # Drop triggers
    tables_with_updated_at = [
        'pokemon_cards', 'pokemon_sets', 'card_variations', 
        'validation_rules', 'ximilar_corrections'
    ]
    
    for table in tables_with_updated_at:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    
    # Drop tables
    op.drop_index('idx_batch_items_batch', table_name='batch_items')
    op.drop_table('batch_items')
    
    op.drop_index('idx_batch_status', table_name='batch_uploads')
    op.drop_table('batch_uploads')
    
    op.drop_index('idx_identification_hash', table_name='identification_results')
    op.drop_index('idx_identification_confidence', table_name='identification_results')
    op.drop_table('identification_results')
    
    op.drop_index('idx_audit_changed_at', table_name='audit_logs')
    op.drop_index('idx_audit_table_record', table_name='audit_logs')
    op.drop_table('audit_logs')