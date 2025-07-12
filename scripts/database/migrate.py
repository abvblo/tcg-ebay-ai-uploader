#!/usr/bin/env python3
"""
Simple CLI wrapper for database migrations

Usage:
    python migrate.py              # Show current version and pending migrations
    python migrate.py up           # Apply all pending migrations
    python migrate.py down         # Rollback one migration
    python migrate.py create "message"  # Create new migration
    python migrate.py history      # Show migration history
"""

import sys
import os
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database.migrations import MigrationManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def main():
    manager = MigrationManager()
    
    if len(sys.argv) == 1:
        # No arguments - show status
        print("Database Migration Status")
        print("=" * 50)
        
        current = manager.current_version()
        if current:
            print(f"Current version: {current}")
        else:
            print("Database not initialized")
        
        if manager.check_pending_migrations():
            print("\n⚠️  There are pending migrations!")
            print("Run 'python migrate.py up' to apply them")
        else:
            print("\n✅ Database is up to date")
        
        if manager.verify_tables():
            print("\n✅ All expected tables exist")
        else:
            print("\n❌ Some tables are missing")
            
    elif sys.argv[1] == "up":
        print("Applying migrations...")
        manager.upgrade()
        print("✅ Migrations applied successfully")
        
    elif sys.argv[1] == "down":
        print("Rolling back one migration...")
        manager.downgrade()
        print("✅ Rollback completed")
        
    elif sys.argv[1] == "create" and len(sys.argv) > 2:
        message = " ".join(sys.argv[2:])
        print(f"Creating migration: {message}")
        manager.create_migration(message)
        print("✅ Migration created")
        
    elif sys.argv[1] == "history":
        print("Migration History")
        print("=" * 50)
        manager.show_history()
        
    elif sys.argv[1] == "init":
        print("Initializing migration system...")
        manager.init_db()
        print("✅ Migration system initialized")
        
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)