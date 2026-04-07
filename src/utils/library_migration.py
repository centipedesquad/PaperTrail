"""
Library migration utilities for PaperTrail.
Handles relocating the database and files (PDFs, sources) to new directories.
"""

import json
import os
import shutil
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Callable, Tuple

logger = logging.getLogger(__name__)

CONFIG_FILE = Path.home() / ".papertrail_config"


def read_config() -> Tuple[str, str]:
    """
    Read db_dir and files_dir from the config file.
    Backward compatible: old single-line format is treated as both dirs equal.

    Returns:
        (db_dir, files_dir) tuple

    Raises:
        FileNotFoundError: if config file doesn't exist
        ValueError: if config file is empty or invalid
    """
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_FILE}")

    text = CONFIG_FILE.read_text().strip()
    if not text:
        raise ValueError("Config file is empty")

    try:
        data = json.loads(text)
        db_dir = data["db_dir"]
        files_dir = data.get("files_dir", db_dir)
        return db_dir, files_dir
    except (json.JSONDecodeError, KeyError):
        # Old format: single line = both dirs
        return text, text


def write_config(db_dir: str, files_dir: str,
                 previous_db_dir: Optional[str] = None,
                 previous_files_dir: Optional[str] = None):
    """
    Write config file in JSON format.

    Args:
        db_dir: Database directory path
        files_dir: Files (PDFs + sources) directory path
        previous_db_dir: Old DB dir for cleanup info (optional)
        previous_files_dir: Old files dir for cleanup info (optional)
    """
    data = {"db_dir": db_dir, "files_dir": files_dir}
    if previous_db_dir:
        data["previous_db_dir"] = previous_db_dir
    if previous_files_dir:
        data["previous_files_dir"] = previous_files_dir
    CONFIG_FILE.write_text(json.dumps(data, indent=2))
    logger.info(f"Config written: db_dir={db_dir}, files_dir={files_dir}")


def read_previous_paths() -> Tuple[Optional[str], Optional[str]]:
    """
    Read previous library paths from config (set after an Export migration).

    Returns:
        (previous_db_dir, previous_files_dir) — either may be None
    """
    if not CONFIG_FILE.exists():
        return None, None

    text = CONFIG_FILE.read_text().strip()
    try:
        data = json.loads(text)
        return data.get("previous_db_dir"), data.get("previous_files_dir")
    except (json.JSONDecodeError, KeyError):
        return None, None


def dismiss_previous_paths():
    """Remove previous path entries from the config file."""
    if not CONFIG_FILE.exists():
        return

    text = CONFIG_FILE.read_text().strip()
    try:
        data = json.loads(text)
        data.pop("previous_db_dir", None)
        data.pop("previous_files_dir", None)
        CONFIG_FILE.write_text(json.dumps(data, indent=2))
        logger.info("Dismissed previous library paths from config")
    except (json.JSONDecodeError, KeyError):
        pass


def count_files(*directories: str) -> int:
    """Count total files across one or more directories (recursive)."""
    total = 0
    for directory in directories:
        if os.path.isdir(directory):
            for _, _, files in os.walk(directory):
                total += len(files)
    return total


def count_directory_size(*directories: str) -> int:
    """Count total bytes across one or more directories (recursive)."""
    total = 0
    for directory in directories:
        if os.path.isdir(directory):
            for dirpath, _, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total += os.path.getsize(filepath)
                    except OSError:
                        pass
    return total


def copy_directory_with_progress(
    src: str,
    dst: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    start_count: int = 0,
    total_count: int = 0,
    cancelled: Optional[Callable[[], bool]] = None
) -> int:
    """
    Recursively copy a directory with per-file progress.

    Args:
        src: Source directory
        dst: Destination directory
        progress_callback: Optional callback(current, total, filename)
        start_count: Starting file count (for multi-directory progress)
        total_count: Total files expected across all directories
        cancelled: Optional callable that returns True if cancelled

    Returns:
        Number of files copied
    """
    if not os.path.isdir(src):
        return 0

    os.makedirs(dst, exist_ok=True)
    copied = 0

    for dirpath, dirnames, filenames in os.walk(src):
        # Compute relative path and create destination subdirectory
        rel_dir = os.path.relpath(dirpath, src)
        dst_dir = os.path.join(dst, rel_dir) if rel_dir != '.' else dst
        os.makedirs(dst_dir, exist_ok=True)

        for filename in filenames:
            if cancelled and cancelled():
                return copied

            src_file = os.path.join(dirpath, filename)
            dst_file = os.path.join(dst_dir, filename)
            shutil.copy2(src_file, dst_file)
            copied += 1

            if progress_callback:
                progress_callback(start_count + copied, total_count, filename)

    return copied


def update_paths_in_db(db_path: str, old_prefix: str, new_prefix: str):
    """
    Batch update local_pdf_path and local_source_path in a database.

    Args:
        db_path: Path to the SQLite database file
        old_prefix: Old directory prefix to replace
        new_prefix: New directory prefix
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Normalize: ensure prefixes end without trailing separator
        old_prefix = old_prefix.rstrip(os.sep)
        new_prefix = new_prefix.rstrip(os.sep)

        like_pattern = old_prefix + '%'

        cursor.execute(
            "UPDATE papers SET local_pdf_path = REPLACE(local_pdf_path, ?, ?) "
            "WHERE local_pdf_path LIKE ?",
            (old_prefix, new_prefix, like_pattern)
        )
        pdf_count = cursor.rowcount

        cursor.execute(
            "UPDATE papers SET local_source_path = REPLACE(local_source_path, ?, ?) "
            "WHERE local_source_path LIKE ?",
            (old_prefix, new_prefix, like_pattern)
        )
        source_count = cursor.rowcount

        conn.commit()
        logger.info(f"Updated {pdf_count} PDF paths and {source_count} source paths "
                     f"({old_prefix} -> {new_prefix})")
    finally:
        conn.close()


def update_setting_in_db(db_path: str, key: str, value: str):
    """Update a single setting in a database's settings table."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO settings (key, value, updated_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = CURRENT_TIMESTAMP",
            (key, value)
        )
        conn.commit()
    finally:
        conn.close()


def export_library(
    old_db_dir: str,
    new_db_dir: str,
    old_files_dir: str,
    new_files_dir: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None
) -> bool:
    """
    Export library to new locations by copying files and updating paths.

    Args:
        old_db_dir: Current database directory
        new_db_dir: New database directory
        old_files_dir: Current files directory (PDFs + sources)
        new_files_dir: New files directory
        progress_callback: Optional callback(current, total, status)
        cancelled: Optional callable returning True if cancelled

    Returns:
        True if successful
    """
    db_changed = os.path.normpath(old_db_dir) != os.path.normpath(new_db_dir)
    files_changed = os.path.normpath(old_files_dir) != os.path.normpath(new_files_dir)

    old_db_path = os.path.join(old_db_dir, "papertrail.db")
    new_db_path = os.path.join(new_db_dir, "papertrail.db")

    old_pdfs_dir = os.path.join(old_files_dir, "pdfs")
    old_sources_dir = os.path.join(old_files_dir, "sources")
    new_pdfs_dir = os.path.join(new_files_dir, "pdfs")
    new_sources_dir = os.path.join(new_files_dir, "sources")
    new_cache_dir = os.path.join(new_files_dir, "cache")

    try:
        # Phase 1: Copy database if path changed
        if db_changed:
            os.makedirs(new_db_dir, exist_ok=True)
            shutil.copy2(old_db_path, new_db_path)
            # Also copy WAL/SHM if they exist (fallback if checkpoint didn't run)
            for suffix in ['-wal', '-shm']:
                wal_file = old_db_path + suffix
                if os.path.exists(wal_file):
                    shutil.copy2(wal_file, new_db_path + suffix)
            logger.info(f"Copied database to {new_db_path}")

        if cancelled and cancelled():
            return False

        # Phase 2: Copy files if path changed
        if files_changed:
            total = count_files(old_pdfs_dir, old_sources_dir)

            if progress_callback:
                progress_callback(0, total, "Starting file copy...")

            copied = copy_directory_with_progress(
                old_pdfs_dir, new_pdfs_dir,
                progress_callback, 0, total, cancelled
            )

            if cancelled and cancelled():
                return False

            copied += copy_directory_with_progress(
                old_sources_dir, new_sources_dir,
                progress_callback, copied, total, cancelled
            )

            if cancelled and cancelled():
                return False

            # Create empty cache directory
            os.makedirs(new_cache_dir, exist_ok=True)
            os.makedirs(os.path.join(new_cache_dir, "sources"), exist_ok=True)

            logger.info(f"Copied {copied} files to {new_files_dir}")

        # Phase 3: Update paths in the target database
        if files_changed:
            target_db = new_db_path if db_changed else old_db_path
            update_paths_in_db(target_db, old_files_dir, new_files_dir)

        if db_changed:
            update_setting_in_db(new_db_path, "database_location", new_db_dir)

        # Phase 4: Update config file
        prev_db = old_db_dir if db_changed else None
        prev_files = old_files_dir if files_changed else None
        write_config(new_db_dir, new_files_dir, prev_db, prev_files)

        logger.info("Library export completed successfully")
        return True

    except Exception as e:
        logger.error(f"Library export failed: {e}")
        raise


def create_new_library(new_db_dir: str, new_files_dir: str) -> bool:
    """
    Create a new empty library at the specified locations.

    Args:
        new_db_dir: Directory for the new database
        new_files_dir: Directory for files (PDFs + sources)

    Returns:
        True if successful
    """
    from database.connection import DatabaseConnection
    from database.migration_manager import MigrationManager

    try:
        # Create directory structure
        os.makedirs(new_db_dir, exist_ok=True)
        for subdir in ["pdfs", "sources", "cache", os.path.join("cache", "sources")]:
            os.makedirs(os.path.join(new_files_dir, subdir), exist_ok=True)

        # Initialize fresh database
        new_db_path = os.path.join(new_db_dir, "papertrail.db")
        db = DatabaseConnection(new_db_path)
        db.connect()

        migration_manager = MigrationManager(db)
        migration_manager.migrate()

        # Set database_location in the fresh DB
        db.execute(
            "INSERT INTO settings (key, value, updated_at) "
            "VALUES ('database_location', ?, CURRENT_TIMESTAMP)",
            (new_db_dir,)
        )

        db.close()

        # Update config file (no previous paths for Create New)
        write_config(new_db_dir, new_files_dir)

        logger.info(f"New library created at db={new_db_dir}, files={new_files_dir}")
        return True

    except Exception as e:
        logger.error(f"Failed to create new library: {e}")
        raise


def null_file_paths_in_db(db_path: str):
    """
    Set all local_pdf_path and local_source_path to NULL.
    Used when creating a new files directory without exporting.

    Args:
        db_path: Path to the SQLite database file
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE papers SET local_pdf_path = NULL "
            "WHERE local_pdf_path IS NOT NULL"
        )
        conn.execute(
            "UPDATE papers SET local_source_path = NULL "
            "WHERE local_source_path IS NOT NULL"
        )
        conn.commit()
        logger.info("Nulled all local file paths in database")
    finally:
        conn.close()
