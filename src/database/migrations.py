"""Database migration utilities for the eBay TCG Batch Uploader"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class MigrationManager:
    """Manages database migrations using Alembic"""

    def __init__(self, alembic_ini_path: str = None):
        """Initialize the migration manager.

        Args:
            alembic_ini_path: Path to alembic.ini file. If None, searches from project root.
        """
        if alembic_ini_path is None:
            # Find alembic.ini from the project root
            project_root = Path(__file__).parent.parent.parent
            alembic_ini_path = project_root / "config" / "alembic.ini"

        if not Path(alembic_ini_path).exists():
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")

        self.alembic_cfg = Config(str(alembic_ini_path))
        self.engine = self._create_engine()

    def _create_engine(self):
        """Create SQLAlchemy engine from environment variables"""
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "password")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "pokemon_cards")

        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        return create_engine(db_url)

    def init_db(self):
        """Initialize the database with Alembic version table"""
        try:
            command.ensure_version(self.alembic_cfg)
            logger.info("Initialized Alembic version table")
        except Exception as e:
            logger.error(f"Failed to initialize Alembic: {e}")
            raise

    def create_migration(self, message: str, autogenerate: bool = True):
        """Create a new migration.

        Args:
            message: Description of the migration
            autogenerate: Whether to auto-generate migration from model changes
        """
        try:
            if autogenerate:
                command.revision(self.alembic_cfg, message=message, autogenerate=True)
                logger.info(f"Generated migration: {message}")
            else:
                command.revision(self.alembic_cfg, message=message)
                logger.info(f"Created empty migration: {message}")
        except Exception as e:
            logger.error(f"Failed to create migration: {e}")
            raise

    def upgrade(self, revision: str = "head"):
        """Upgrade database to a revision.

        Args:
            revision: Target revision (default: "head" for latest)
        """
        try:
            command.upgrade(self.alembic_cfg, revision)
            logger.info(f"Upgraded database to {revision}")
        except Exception as e:
            logger.error(f"Failed to upgrade database: {e}")
            raise

    def downgrade(self, revision: str = "-1"):
        """Downgrade database to a revision.

        Args:
            revision: Target revision (default: "-1" for one step back)
        """
        try:
            command.downgrade(self.alembic_cfg, revision)
            logger.info(f"Downgraded database to {revision}")
        except Exception as e:
            logger.error(f"Failed to downgrade database: {e}")
            raise

    def current_version(self):
        """Get current database revision"""
        try:
            with self.engine.connect() as conn:
                context = conn.execute("SELECT version_num FROM alembic_version")
                result = context.fetchone()
                return result[0] if result else None
        except Exception:
            return None

    def show_history(self):
        """Show migration history"""
        try:
            command.history(self.alembic_cfg)
        except Exception as e:
            logger.error(f"Failed to show history: {e}")
            raise

    def stamp(self, revision: str = "head"):
        """Stamp database with a revision without running migrations.

        Useful for existing databases.

        Args:
            revision: Revision to stamp (default: "head")
        """
        try:
            command.stamp(self.alembic_cfg, revision)
            logger.info(f"Stamped database with revision {revision}")
        except Exception as e:
            logger.error(f"Failed to stamp database: {e}")
            raise

    def check_pending_migrations(self):
        """Check if there are pending migrations"""
        try:
            current = self.current_version()
            if current is None:
                return True  # No version table, migrations needed

            # Get the head revision
            from alembic.script import ScriptDirectory

            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            head = script_dir.get_current_head()

            return current != head
        except Exception as e:
            logger.error(f"Failed to check pending migrations: {e}")
            return True

    def auto_upgrade(self):
        """Automatically run pending migrations"""
        if self.check_pending_migrations():
            logger.info("Pending migrations detected, upgrading...")
            self.upgrade()
        else:
            logger.info("Database is up to date")

    def verify_tables(self):
        """Verify all expected tables exist"""
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()

        expected_tables = [
            "pokemon_cards",
            "pokemon_sets",
            "types",
            "subtypes",
            "card_types",
            "card_subtypes",
            "card_variations",
            "price_snapshots",
            "validation_rules",
            "ximilar_corrections",
            "alembic_version",
        ]

        missing_tables = [t for t in expected_tables if t not in tables]

        if missing_tables:
            logger.warning(f"Missing tables: {missing_tables}")
            return False

        logger.info("All expected tables exist")
        return True


# Convenience functions for use in other modules
def run_migrations():
    """Run all pending migrations"""
    manager = MigrationManager()
    manager.auto_upgrade()


def create_migration(message: str):
    """Create a new auto-generated migration"""
    manager = MigrationManager()
    manager.create_migration(message, autogenerate=True)


def init_migrations():
    """Initialize migrations for a new database"""
    manager = MigrationManager()
    manager.init_db()
    manager.stamp("head")  # Mark current schema as up-to-date


if __name__ == "__main__":
    # CLI interface for migrations
    import argparse

    parser = argparse.ArgumentParser(description="Database migration management")
    parser.add_argument(
        "command",
        choices=["init", "create", "upgrade", "downgrade", "current", "history", "verify"],
    )
    parser.add_argument("-m", "--message", help="Migration message (for create command)")
    parser.add_argument("-r", "--revision", help="Target revision (for upgrade/downgrade)")

    args = parser.parse_args()

    manager = MigrationManager()

    if args.command == "init":
        manager.init_db()
        print("Initialized migration system")
    elif args.command == "create":
        if not args.message:
            print("Error: Message required for create command")
            sys.exit(1)
        manager.create_migration(args.message)
    elif args.command == "upgrade":
        manager.upgrade(args.revision or "head")
    elif args.command == "downgrade":
        manager.downgrade(args.revision or "-1")
    elif args.command == "current":
        version = manager.current_version()
        print(f"Current version: {version}")
    elif args.command == "history":
        manager.show_history()
    elif args.command == "verify":
        if manager.verify_tables():
            print("All tables verified")
        else:
            print("Some tables are missing")
