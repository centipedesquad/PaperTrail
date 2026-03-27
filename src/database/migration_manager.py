"""
Database migration manager for PaperTrail.
Uses schema introspection to determine which migrations need to run.
"""

import re
import logging

from database.connection import DatabaseConnection
from database.migrations import MIGRATION_REGISTRY

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database schema migrations using introspection."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def needs_migration(self) -> bool:
        """Check if any migration needs to run by introspecting the schema."""
        conn = self.db.connect()
        return any(m.needs_run(conn) for m in MIGRATION_REGISTRY)

    def migrate(self):
        """Apply all pending migrations based on schema introspection."""
        conn = self.db.connect()
        applied = []

        for migration in MIGRATION_REGISTRY:
            if migration.needs_run(conn):
                logger.info(f"Applying migration: {migration.name}")
                try:
                    migration.apply(conn)
                    conn.commit()
                    applied.append(migration.name)
                    logger.info(f"Migration {migration.name} applied successfully")
                except Exception as e:
                    logger.error(f"Failed to apply migration {migration.name}: {e}")
                    raise
            else:
                logger.debug(f"Migration {migration.name}: already applied, skipping")

        if applied:
            # Update informational schema version
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', ?)",
                    (f"{len(MIGRATION_REGISTRY):03d}",)
                )
                conn.commit()
            except Exception:
                pass  # Settings table may not exist yet on error paths

        final_version = self.db.get_schema_version()
        logger.info(f"Schema migration complete. Version: {final_version}, applied: {applied or 'none'}")

    def reset_database(self):
        """
        Drop all tables and reapply migrations.
        WARNING: This will delete all data!
        """
        logger.warning("Resetting database - all data will be lost!")

        conn = self.db.connect()

        # Disable foreign keys to avoid cascade errors during table drops
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.commit()

        # Drop triggers first to prevent FTS triggers from firing during drops
        triggers = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
        for trigger in triggers:
            trigger_name = trigger[0]
            if re.match(r'^[a-zA-Z0-9_]+$', trigger_name):
                conn.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
        conn.commit()

        # Drop all tables
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for table in tables:
            table_name = table[0]
            if re.match(r'^[a-zA-Z0-9_]+$', table_name):
                conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                logger.info(f"Dropped table: {table_name}")
        conn.commit()

        # Re-enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()

        self.migrate()
