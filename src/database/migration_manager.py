"""
Database migration manager for PaperTrail.
Handles schema versioning and migrations.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional

from database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database schema migrations."""

    def __init__(self, db: DatabaseConnection, migrations_dir: str):
        """
        Initialize migration manager.

        Args:
            db: Database connection
            migrations_dir: Directory containing migration SQL files
        """
        self.db = db
        self.migrations_dir = Path(migrations_dir)

    def get_current_version(self) -> Optional[str]:
        """
        Get current schema version from database.

        Returns:
            Current version string or None if not initialized
        """
        return self.db.get_schema_version()

    def get_available_migrations(self) -> List[str]:
        """
        Get list of available migration files.

        Returns:
            Sorted list of migration filenames
        """
        if not self.migrations_dir.exists():
            return []

        migrations = []
        for file in self.migrations_dir.glob("*.sql"):
            migrations.append(file.name)

        return sorted(migrations)

    def needs_migration(self) -> bool:
        """
        Check if database needs migration.

        Returns:
            True if migration needed, False otherwise
        """
        current = self.get_current_version()
        available = self.get_available_migrations()

        if current is None and available:
            return True

        if current and available:
            # Compare current version with latest available
            latest = available[-1].split('_')[0]  # Extract version number
            return current < latest

        return False

    def apply_migration(self, migration_file: str):
        """
        Apply a single migration file.

        Args:
            migration_file: Name of migration file to apply
        """
        migration_path = self.migrations_dir / migration_file
        logger.info(f"Applying migration: {migration_file}")

        try:
            with open(migration_path, 'r') as f:
                sql = f.read()

            # Use executescript which handles the entire SQL file properly
            conn = self.db.connect()
            conn.executescript(sql)
            conn.commit()

            logger.info(f"Migration {migration_file} applied successfully")

        except Exception as e:
            logger.error(f"Failed to apply migration {migration_file}: {e}")
            raise

    def migrate(self):
        """
        Apply all pending migrations.
        """
        current_version = self.get_current_version()
        available_migrations = self.get_available_migrations()

        if not available_migrations:
            logger.warning("No migrations found")
            return

        if current_version is None:
            # Fresh database, apply all migrations
            logger.info("Initializing new database")
            for migration in available_migrations:
                self.apply_migration(migration)
        else:
            # Apply only newer migrations
            logger.info(f"Current schema version: {current_version}")
            for migration in available_migrations:
                version = migration.split('_')[0]
                if version > current_version:
                    self.apply_migration(migration)

        # Verify final version
        final_version = self.get_current_version()
        logger.info(f"Schema migration complete. Current version: {final_version}")

    def reset_database(self):
        """
        Drop all tables and reapply migrations.
        WARNING: This will delete all data!
        """
        logger.warning("Resetting database - all data will be lost!")

        # Get list of all tables
        tables = self.db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )

        with self.db.transaction():
            # Drop all tables
            for table in tables:
                table_name = table['name']
                self.db.execute(f"DROP TABLE IF EXISTS {table_name}")
                logger.info(f"Dropped table: {table_name}")

        # Reapply migrations
        self.migrate()
