#!/usr/bin/env python3
"""
Database migration script for eBay TCG Batch Uploader
Handles schema updates and data migrations
"""

import logging
import os
import sys
from datetime import datetime

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """Handles database migrations"""

    def __init__(self):
        self.config = Config()
        self.connection = None

    def connect(self):
        """Connect to the database"""
        try:
            # Parse DATABASE_URL if provided
            db_url = os.environ.get("DATABASE_URL")
            if db_url:
                # Parse PostgreSQL URL
                if db_url.startswith("postgresql://"):
                    db_url = db_url.replace("postgresql://", "")

                user_pass, host_db = db_url.split("@")
                user, password = user_pass.split(":")
                host_port, db = host_db.split("/")
                host, port = host_port.split(":")

                self.connection = psycopg2.connect(
                    host=host, port=port, database=db, user=user, password=password
                )
            else:
                # Use config values
                self.connection = psycopg2.connect(
                    host=self.config.DB_HOST,
                    port=self.config.DB_PORT,
                    database=self.config.DB_NAME,
                    user=self.config.DB_USER,
                    password=self.config.DB_PASSWORD,
                )

            self.connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            logger.info("Successfully connected to database")

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()

    def create_migrations_table(self):
        """Create migrations tracking table"""
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id SERIAL PRIMARY KEY,
                    version VARCHAR(255) UNIQUE NOT NULL,
                    description TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            logger.info("Migrations table ready")

    def is_migration_applied(self, version):
        """Check if a migration has been applied"""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,))
            return cursor.fetchone() is not None

    def record_migration(self, version, description):
        """Record that a migration has been applied"""
        with self.connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (%s, %s)",
                (version, description),
            )
            logger.info(f"Recorded migration: {version}")

    def run_migration(self, version, description, sql):
        """Run a single migration"""
        if self.is_migration_applied(version):
            logger.info(f"Migration {version} already applied, skipping")
            return

        logger.info(f"Applying migration {version}: {description}")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql)

            self.record_migration(version, description)
            logger.info(f"Successfully applied migration {version}")

        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            raise

    def run_migrations(self):
        """Run all pending migrations"""
        self.create_migrations_table()

        migrations = [
            {
                "version": "001_initial_schema",
                "description": "Create initial database schema",
                "sql": """
                    -- Already handled by init SQL files
                    SELECT 1;
                """,
            },
            {
                "version": "002_add_japanese_support",
                "description": "Add Japanese card support fields",
                "sql": """
                    -- Add Japanese-specific fields
                    ALTER TABLE pokemon_cards 
                    ADD COLUMN IF NOT EXISTS name_japanese VARCHAR(255),
                    ADD COLUMN IF NOT EXISTS is_japanese BOOLEAN DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en';
                    
                    -- Create index for Japanese cards
                    CREATE INDEX IF NOT EXISTS idx_pokemon_cards_japanese 
                    ON pokemon_cards(is_japanese) WHERE is_japanese = TRUE;
                """,
            },
            {
                "version": "003_add_card_conditions",
                "description": "Add card condition tracking",
                "sql": """
                    -- Add condition field to upload items
                    ALTER TABLE upload_items
                    ADD COLUMN IF NOT EXISTS condition VARCHAR(50) DEFAULT 'Near Mint',
                    ADD COLUMN IF NOT EXISTS condition_notes TEXT;
                    
                    -- Create condition enum type
                    DO $$ BEGIN
                        CREATE TYPE card_condition AS ENUM (
                            'Mint', 'Near Mint', 'Lightly Played', 
                            'Moderately Played', 'Heavily Played', 'Damaged'
                        );
                    EXCEPTION
                        WHEN duplicate_object THEN null;
                    END $$;
                """,
            },
            {
                "version": "004_add_metrics_table",
                "description": "Add metrics tracking table",
                "sql": """
                    CREATE TABLE IF NOT EXISTS processing_metrics (
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        batch_id UUID REFERENCES batch_uploads(id) ON DELETE CASCADE,
                        metric_type VARCHAR(50) NOT NULL,
                        metric_value DECIMAL(10,2),
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_metrics_batch 
                    ON processing_metrics(batch_id);
                    
                    CREATE INDEX IF NOT EXISTS idx_metrics_type 
                    ON processing_metrics(metric_type);
                """,
            },
            {
                "version": "005_add_cache_table",
                "description": "Add cache table for API responses",
                "sql": """
                    CREATE TABLE IF NOT EXISTS api_cache (
                        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        cache_key VARCHAR(255) UNIQUE NOT NULL,
                        cache_value JSONB NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_cache_key 
                    ON api_cache(cache_key);
                    
                    CREATE INDEX IF NOT EXISTS idx_cache_expires 
                    ON api_cache(expires_at);
                """,
            },
        ]

        for migration in migrations:
            self.run_migration(migration["version"], migration["description"], migration["sql"])

        logger.info("All migrations completed successfully")


def main():
    """Main migration runner"""
    migrator = DatabaseMigrator()

    try:
        migrator.connect()
        migrator.run_migrations()

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)

    finally:
        migrator.close()


if __name__ == "__main__":
    main()
