"""
Database connection management for PaperTrail.
Uses SQLite with WAL mode for better concurrency.
"""

import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages SQLite database connection with WAL mode and transactions."""

    def __init__(self, db_path: str):
        """
        Initialize database connection.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None

        # Ensure parent directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        """
        Create and configure database connection.

        Returns:
            Configured SQLite connection
        """
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,  # Allow multi-threaded access
                timeout=30.0  # 30 second timeout for locks
            )

            # Enable foreign keys
            self._connection.execute("PRAGMA foreign_keys = ON")

            # Enable WAL mode for better concurrency
            self._connection.execute("PRAGMA journal_mode = WAL")

            # Use memory-mapped I/O for performance
            self._connection.execute("PRAGMA mmap_size = 268435456")  # 256MB

            # Configure row factory for dict-like access
            self._connection.row_factory = sqlite3.Row

            logger.info(f"Connected to database at {self.db_path}")

        return self._connection

    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a query without returning results.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Cursor object
        """
        conn = self.connect()
        return conn.execute(query, params)

    def executemany(self, query: str, params_list: list) -> sqlite3.Cursor:
        """
        Execute a query multiple times with different parameters.

        Args:
            query: SQL query string
            params_list: List of parameter tuples

        Returns:
            Cursor object
        """
        conn = self.connect()
        return conn.executemany(query, params_list)

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """
        Execute a query and fetch one result.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Single row or None
        """
        cursor = self.execute(query, params)
        return cursor.fetchone()

    def fetch_all(self, query: str, params: tuple = ()) -> list:
        """
        Execute a query and fetch all results.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of rows
        """
        cursor = self.execute(query, params)
        return cursor.fetchall()

    def commit(self):
        """Commit current transaction."""
        if self._connection:
            self._connection.commit()

    def rollback(self):
        """Rollback current transaction."""
        if self._connection:
            self._connection.rollback()

    @contextmanager
    def transaction(self):
        """
        Context manager for transactions.

        Usage:
            with db.transaction():
                db.execute("INSERT ...")
                db.execute("UPDATE ...")
        """
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise

    def vacuum(self):
        """
        Optimize database by reclaiming unused space.
        Should be called periodically.
        """
        self.execute("VACUUM")
        logger.info("Database vacuumed")

    def get_schema_version(self) -> Optional[str]:
        """
        Get current schema version from settings table.

        Returns:
            Schema version string or None if not set
        """
        try:
            row = self.fetch_one(
                "SELECT value FROM settings WHERE key = 'schema_version'"
            )
            return row['value'] if row else None
        except sqlite3.OperationalError:
            # Settings table doesn't exist yet
            return None


# Global database instance (initialized in main.py)
_db_instance: Optional[DatabaseConnection] = None


def initialize_database(db_path: str) -> DatabaseConnection:
    """
    Initialize global database instance.

    Args:
        db_path: Path to database file

    Returns:
        Database connection instance
    """
    global _db_instance
    _db_instance = DatabaseConnection(db_path)
    return _db_instance


def get_database() -> DatabaseConnection:
    """
    Get global database instance.

    Returns:
        Database connection instance

    Raises:
        RuntimeError: If database not initialized
    """
    if _db_instance is None:
        raise RuntimeError("Database not initialized. Call initialize_database() first.")
    return _db_instance


def close_database():
    """Close global database instance."""
    global _db_instance
    if _db_instance:
        _db_instance.close()
        _db_instance = None
