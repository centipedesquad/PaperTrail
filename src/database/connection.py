"""
Database connection management for PaperTrail.
Uses SQLite with WAL mode for better concurrency.
"""

import sqlite3
import os
import shutil
import threading
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
        self._lock = threading.RLock()
        self._in_transaction = False
        self._recovering = False

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

            # Run integrity check on existing databases
            if os.path.getsize(self.db_path) > 0:
                if not self._check_integrity():
                    self._handle_corrupt_database()

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

    def _check_integrity(self) -> bool:
        """Run PRAGMA integrity_check on the database.

        Returns:
            True if database is healthy, False if corrupt.
        """
        try:
            result = self._connection.execute("PRAGMA integrity_check").fetchone()
            if result and result[0] == 'ok':
                return True
            logger.error(f"Database integrity check failed: {result}")
            return False
        except Exception as e:
            logger.error(f"Database integrity check error: {e}")
            return False

    def _handle_corrupt_database(self):
        """Back up the corrupt database and create a fresh connection."""
        if self._recovering:
            raise RuntimeError("Database recovery already in progress — cannot recurse")
        self._recovering = True
        try:
            backup_path = self.db_path + '.corrupt'
            logger.warning(
                f"Database is corrupt. Backing up to {backup_path} and creating fresh database."
            )
            # Close the connection to the corrupt file
            if self._connection:
                try:
                    self._connection.close()
                except Exception:
                    pass
                self._connection = None

            # Back up corrupt file
            try:
                shutil.copy2(self.db_path, backup_path)
                os.remove(self.db_path)
            except OSError as e:
                logger.error(f"Failed to back up corrupt database: {e}")
                raise RuntimeError(
                    f"Cannot recover corrupt database — failed to remove {self.db_path}: {e}"
                ) from e

            # Don't reconnect here — the fresh DB has no tables and migrations
            # can't run from inside connect(). Raise so the app restarts cleanly.
            raise RuntimeError(
                "Database was corrupt and has been backed up. "
                "Please restart the application."
            )
        finally:
            self._recovering = False

    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a query. Auto-commits when not inside a transaction() block.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Cursor object
        """
        with self._lock:
            conn = self.connect()
            cursor = conn.execute(query, params)
            if not self._in_transaction:
                conn.commit()
            return cursor

    def executemany(self, query: str, params_list: list) -> sqlite3.Cursor:
        """
        Execute a query multiple times with different parameters.

        Args:
            query: SQL query string
            params_list: List of parameter tuples

        Returns:
            Cursor object
        """
        with self._lock:
            conn = self.connect()
            cursor = conn.executemany(query, params_list)
            if not self._in_transaction:
                conn.commit()
            return cursor

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """
        Execute a query and fetch one result.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Single row or None
        """
        with self._lock:
            conn = self.connect()
            cursor = conn.execute(query, params)
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
        with self._lock:
            conn = self.connect()
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def commit(self):
        """Commit current transaction."""
        with self._lock:
            if self._connection:
                self._connection.commit()

    def rollback(self):
        """Rollback current transaction."""
        with self._lock:
            if self._connection:
                self._connection.rollback()

    @contextmanager
    def transaction(self):
        """
        Context manager for transactions.
        Thread-safe: holds the lock for the entire transaction to prevent
        interleaving of operations from different threads.

        Usage:
            with db.transaction():
                db.execute("INSERT ...")
                db.execute("UPDATE ...")
        """
        with self._lock:
            conn = self.connect()
            self._in_transaction = True
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Transaction failed: {e}")
                raise
            finally:
                self._in_transaction = False

    def vacuum(self):
        """
        Optimize database by reclaiming unused space.
        VACUUM requires autocommit mode — execute directly on the connection.
        """
        with self._lock:
            conn = self.connect()
            conn.execute("VACUUM")
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
