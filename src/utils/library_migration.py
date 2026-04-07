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


def analyze_merge(src_db_path: str, dst_db_path: str) -> dict:
    """
    Compare two databases and return merge analysis.

    Returns:
        dict with total_incoming, non_duplicate_count,
        duplicate_count, duplicate_arxiv_ids
    """
    src_conn = sqlite3.connect(src_db_path)
    dst_conn = sqlite3.connect(dst_db_path)
    try:
        src_ids = set(
            row[0] for row in
            src_conn.execute("SELECT arxiv_id FROM papers").fetchall()
        )
        dst_ids = set(
            row[0] for row in
            dst_conn.execute("SELECT arxiv_id FROM papers").fetchall()
        )
        duplicates = sorted(src_ids & dst_ids)
        return {
            "total_incoming": len(src_ids),
            "non_duplicate_count": len(src_ids - dst_ids),
            "duplicate_count": len(duplicates),
            "duplicate_arxiv_ids": duplicates,
        }
    finally:
        src_conn.close()
        dst_conn.close()


def _find_unique_copy_id(conn: sqlite3.Connection, arxiv_id: str) -> str:
    """Find a unique arxiv_id by appending _copy, _copy2, etc."""
    candidate = f"{arxiv_id}_copy"
    for i in range(2, 100):
        row = conn.execute(
            "SELECT 1 FROM papers WHERE arxiv_id = ?", (candidate,)
        ).fetchone()
        if row is None:
            return candidate
        candidate = f"{arxiv_id}_copy{i}"
    raise ValueError(f"Could not find unique copy ID for {arxiv_id}")


def _insert_paper_with_related(
    dst_conn: sqlite3.Connection,
    src_paper: sqlite3.Row,
    arxiv_id: str,
    src_files_dir: str,
    dst_files_dir: str,
) -> Tuple[int, list]:
    """
    Insert a paper and all related data into the destination database.

    Returns:
        (new_paper_id, [(src_file_path, dst_file_path), ...])
    """
    src_paper_id = src_paper['id']
    files_to_copy = []

    new_pdf_path = None
    new_source_path = None

    if src_paper['local_pdf_path']:
        old_path = src_paper['local_pdf_path']
        try:
            rel = os.path.relpath(old_path, src_files_dir)
            if not rel.startswith('..'):
                new_pdf_path = os.path.join(dst_files_dir, rel)
                files_to_copy.append((old_path, new_pdf_path))
        except ValueError:
            pass

    if src_paper['local_source_path']:
        old_path = src_paper['local_source_path']
        try:
            rel = os.path.relpath(old_path, src_files_dir)
            if not rel.startswith('..'):
                new_source_path = os.path.join(dst_files_dir, rel)
                files_to_copy.append((old_path, new_source_path))
        except ValueError:
            pass

    cursor = dst_conn.execute(
        "INSERT INTO main.papers ("
        "  arxiv_id, title, abstract, publication_date, pdf_url,"
        "  local_pdf_path, local_source_path, origin, version,"
        "  comment, journal_ref, doi, date_added, last_accessed,"
        "  created_at, updated_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            arxiv_id,
            src_paper['title'], src_paper['abstract'],
            src_paper['publication_date'], src_paper['pdf_url'],
            new_pdf_path, new_source_path,
            src_paper['origin'], src_paper['version'],
            src_paper['comment'], src_paper['journal_ref'],
            src_paper['doi'], src_paper['date_added'],
            src_paper['last_accessed'], src_paper['created_at'],
            src_paper['updated_at'],
        )
    )
    new_paper_id = cursor.lastrowid

    # Authors
    src_authors = dst_conn.execute(
        "SELECT a.name, a.normalized_name, pa.author_order "
        "FROM src.paper_authors pa "
        "JOIN src.authors a ON pa.author_id = a.id "
        "WHERE pa.paper_id = ? ORDER BY pa.author_order",
        (src_paper_id,)
    ).fetchall()

    for author_row in src_authors:
        existing = dst_conn.execute(
            "SELECT id FROM main.authors WHERE normalized_name = ?",
            (author_row['normalized_name'],)
        ).fetchone()
        if existing:
            author_id = existing['id']
        else:
            c = dst_conn.execute(
                "INSERT INTO main.authors (name, normalized_name) VALUES (?, ?)",
                (author_row['name'], author_row['normalized_name'])
            )
            author_id = c.lastrowid

        dst_conn.execute(
            "INSERT INTO main.paper_authors (paper_id, author_id, author_order) "
            "VALUES (?, ?, ?)",
            (new_paper_id, author_id, author_row['author_order'])
        )

    # Categories
    src_cats = dst_conn.execute(
        "SELECT c.code, c.name, c.parent_code, pc.is_primary "
        "FROM src.paper_categories pc "
        "JOIN src.categories c ON pc.category_id = c.id "
        "WHERE pc.paper_id = ?",
        (src_paper_id,)
    ).fetchall()

    for cat_row in src_cats:
        existing = dst_conn.execute(
            "SELECT id FROM main.categories WHERE code = ?",
            (cat_row['code'],)
        ).fetchone()
        if existing:
            cat_id = existing['id']
        else:
            c = dst_conn.execute(
                "INSERT INTO main.categories (code, name, parent_code) "
                "VALUES (?, ?, ?)",
                (cat_row['code'], cat_row['name'], cat_row['parent_code'])
            )
            cat_id = c.lastrowid

        dst_conn.execute(
            "INSERT INTO main.paper_categories (paper_id, category_id, is_primary) "
            "VALUES (?, ?, ?)",
            (new_paper_id, cat_id, cat_row['is_primary'])
        )

    # Notes
    try:
        src_note = dst_conn.execute(
            "SELECT note_text FROM src.paper_notes WHERE paper_id = ?",
            (src_paper_id,)
        ).fetchone()
        if src_note and src_note['note_text']:
            dst_conn.execute(
                "INSERT INTO main.paper_notes (paper_id, note_text) VALUES (?, ?)",
                (new_paper_id, src_note['note_text'])
            )
    except sqlite3.OperationalError:
        pass

    # Ratings
    try:
        src_rating = dst_conn.execute(
            "SELECT importance, comprehension, technicality "
            "FROM src.paper_ratings WHERE paper_id = ?",
            (src_paper_id,)
        ).fetchone()
        if src_rating:
            dst_conn.execute(
                "INSERT INTO main.paper_ratings "
                "(paper_id, importance, comprehension, technicality) "
                "VALUES (?, ?, ?, ?)",
                (new_paper_id, src_rating['importance'],
                 src_rating['comprehension'], src_rating['technicality'])
            )
    except sqlite3.OperationalError:
        pass

    return new_paper_id, files_to_copy


def merge_library(
    src_db_dir: str,
    dst_db_dir: str,
    src_files_dir: str,
    dst_files_dir: str,
    duplicate_strategy: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
) -> bool:
    """
    Merge incoming (source) library into destination library.

    Args:
        src_db_dir: Current (source) database directory
        dst_db_dir: Destination database directory
        src_files_dir: Current files directory
        dst_files_dir: Destination files directory
        duplicate_strategy: "keep_incoming", "keep_existing", or "keep_both"
        progress_callback: Optional callback(current, total, status)
        cancelled: Optional callable returning True if cancelled

    Returns:
        True if successful
    """
    src_db_path = os.path.join(src_db_dir, "papertrail.db")
    dst_db_path = os.path.join(dst_db_dir, "papertrail.db")

    dst_conn = sqlite3.connect(dst_db_path)
    dst_conn.row_factory = sqlite3.Row
    dst_conn.execute("PRAGMA foreign_keys = ON")

    try:
        dst_conn.execute("ATTACH DATABASE ? AS src", (src_db_path,))

        src_papers = dst_conn.execute(
            "SELECT * FROM src.papers ORDER BY id"
        ).fetchall()

        dst_arxiv_ids = set(
            row[0] for row in
            dst_conn.execute("SELECT arxiv_id FROM main.papers").fetchall()
        )

        total_papers = len(src_papers)
        if total_papers == 0:
            logger.info("No papers to merge")
            return True

        files_to_copy = []
        processed = 0

        dst_conn.execute("BEGIN")
        try:
            for src_paper in src_papers:
                if cancelled and cancelled():
                    dst_conn.execute("ROLLBACK")
                    return False

                arxiv_id = src_paper['arxiv_id']
                is_duplicate = arxiv_id in dst_arxiv_ids

                if not is_duplicate:
                    _, files = _insert_paper_with_related(
                        dst_conn, src_paper, arxiv_id,
                        src_files_dir, dst_files_dir
                    )
                    files_to_copy.extend(files)

                elif duplicate_strategy == "keep_existing":
                    pass

                elif duplicate_strategy == "keep_incoming":
                    dst_conn.execute(
                        "DELETE FROM main.papers WHERE arxiv_id = ?",
                        (arxiv_id,)
                    )
                    _, files = _insert_paper_with_related(
                        dst_conn, src_paper, arxiv_id,
                        src_files_dir, dst_files_dir
                    )
                    files_to_copy.extend(files)

                elif duplicate_strategy == "keep_both":
                    new_arxiv_id = _find_unique_copy_id(dst_conn, arxiv_id)
                    _, files = _insert_paper_with_related(
                        dst_conn, src_paper, new_arxiv_id,
                        src_files_dir, dst_files_dir
                    )
                    files_to_copy.extend(files)

                processed += 1
                if progress_callback:
                    pct = int((processed / total_papers) * 50)
                    progress_callback(
                        pct, 100,
                        f"Merging paper {processed}/{total_papers}"
                    )

            dst_conn.execute("COMMIT")
        except Exception:
            dst_conn.execute("ROLLBACK")
            raise

        # Phase 3: Copy files
        total_files = len(files_to_copy)
        for i, (src_path, dst_path) in enumerate(files_to_copy):
            if cancelled and cancelled():
                return False

            if src_path and os.path.exists(src_path):
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(src_path, dst_path)

            if progress_callback and total_files > 0:
                pct = 50 + int(((i + 1) / total_files) * 50)
                progress_callback(pct, 100, os.path.basename(str(dst_path)))

        # Phase 4: Update config
        write_config(dst_db_dir, dst_files_dir, src_db_dir, src_files_dir)

        logger.info(f"Library merge completed: {processed} papers processed, "
                     f"{total_files} files copied")
        return True

    except Exception as e:
        logger.error(f"Library merge failed: {e}")
        raise
    finally:
        try:
            dst_conn.execute("DETACH DATABASE src")
        except Exception:
            pass
        dst_conn.close()
