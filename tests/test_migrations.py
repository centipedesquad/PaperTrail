"""Tests for the schema-introspection migration system."""

import os
import sys
import tempfile
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.connection import DatabaseConnection
from database.migration_manager import MigrationManager


@pytest.fixture
def fresh_db():
    """Create a fresh database with no schema."""
    db_path = tempfile.mktemp(suffix='.db')
    db_conn = DatabaseConnection(db_path)
    db_conn.connect()
    yield db_conn
    db_conn.close()
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def v001_db():
    """Create a database matching the original v001 schema (FTS with content=papers)."""
    db_path = tempfile.mktemp(suffix='.db')
    db_conn = DatabaseConnection(db_path)
    conn = db_conn.connect()

    # Apply the original 001 schema with content=papers FTS
    sql_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'database', 'migrations',
        'archive', '001_initial_schema.sql'
    )
    with open(sql_path) as f:
        conn.executescript(f.read())
    conn.commit()

    yield db_conn
    db_conn.close()
    try:
        os.unlink(db_path)
    except OSError:
        pass


def test_fresh_database_migration(fresh_db):
    """Fresh DB: baseline applies, all tables created correctly."""
    mm = MigrationManager(fresh_db)
    assert mm.needs_migration() is True

    mm.migrate()

    assert mm.needs_migration() is False

    conn = fresh_db.connect()

    # Core tables exist
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()}
    assert 'papers' in tables
    assert 'authors' in tables
    assert 'settings' in tables
    assert 'paper_authors' in tables
    assert 'paper_ratings' in tables

    # FTS table exists and is contentless
    fts_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='papers_fts'"
    ).fetchone()
    assert fts_row is not None
    assert "content=''" in fts_row[0].lower().replace(' ', '')

    # Correct triggers exist
    triggers = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'papers_fts%'"
    ).fetchall()}
    assert triggers == {
        'papers_fts_insert', 'papers_fts_delete', 'papers_fts_update',
        'papers_fts_update_authors_insert', 'papers_fts_update_authors_delete'
    }

    # Delete trigger is BEFORE, not AFTER
    delete_trigger = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='papers_fts_delete'"
    ).fetchone()
    assert 'BEFORE DELETE' in delete_trigger[0]


def test_v001_database_upgrade(v001_db):
    """v001 DB: FTS upgrade detects content=papers and fixes it."""
    mm = MigrationManager(v001_db)

    # Should need migration (FTS is content=papers, not content='')
    assert mm.needs_migration() is True

    mm.migrate()

    assert mm.needs_migration() is False

    conn = v001_db.connect()

    # FTS is now contentless
    fts_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='papers_fts'"
    ).fetchone()
    assert "content=''" in fts_row[0].lower().replace(' ', '')

    # Correct triggers
    delete_trigger = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='papers_fts_delete'"
    ).fetchone()
    assert 'BEFORE DELETE' in delete_trigger[0]


def test_up_to_date_database_noop(fresh_db):
    """Already-migrated DB: second migrate() is a no-op."""
    mm = MigrationManager(fresh_db)
    mm.migrate()

    assert mm.needs_migration() is False

    # Running migrate again should be safe
    mm.migrate()
    assert mm.needs_migration() is False


def test_idempotency(fresh_db):
    """Running migrate() multiple times produces the same result."""
    mm = MigrationManager(fresh_db)
    mm.migrate()
    mm.migrate()
    mm.migrate()

    conn = fresh_db.connect()

    # Still have exactly the right triggers
    triggers = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'papers_fts%'"
    ).fetchall()}
    assert triggers == {
        'papers_fts_insert', 'papers_fts_delete', 'papers_fts_update',
        'papers_fts_update_authors_insert', 'papers_fts_update_authors_delete'
    }


def test_reset_database(fresh_db):
    """reset_database() drops everything and reapplies cleanly."""
    mm = MigrationManager(fresh_db)
    mm.migrate()

    # Insert a paper to verify data is wiped
    conn = fresh_db.connect()
    conn.execute(
        "INSERT INTO papers (arxiv_id, title, abstract, publication_date, pdf_url) "
        "VALUES ('test', 'Test', 'Abstract', '2024-01-01', 'http://test')"
    )
    conn.commit()

    mm.reset_database()

    row = conn.execute("SELECT count(*) FROM papers").fetchone()
    assert row[0] == 0
    assert mm.needs_migration() is False


def test_fresh_db_has_new_columns(fresh_db):
    """Fresh DB gets local_source_path and origin columns from baseline."""
    mm = MigrationManager(fresh_db)
    mm.migrate()

    conn = fresh_db.connect()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
    assert "local_source_path" in columns
    assert "origin" in columns

    # origin has correct default
    conn.execute(
        "INSERT INTO papers (arxiv_id, title, abstract, publication_date, pdf_url) "
        "VALUES ('test', 'Test', 'Abstract', '2024-01-01', 'http://test')"
    )
    conn.commit()
    row = conn.execute("SELECT origin FROM papers WHERE arxiv_id = 'test'").fetchone()
    assert row[0] == "fetch"

    # origin index exists
    indexes = {row[1] for row in conn.execute("PRAGMA index_list(papers)").fetchall()}
    assert "idx_papers_origin" in indexes


def test_v001_upgrade_gets_new_columns(v001_db):
    """v001 DB upgrade adds local_source_path and origin via ALTER TABLE migrations."""
    mm = MigrationManager(v001_db)
    mm.migrate()

    conn = v001_db.connect()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
    assert "local_source_path" in columns
    assert "origin" in columns
    assert mm.needs_migration() is False


def test_new_column_migrations_are_noop_on_fresh_db(fresh_db):
    """On fresh DB, column migrations skip because baseline already has the columns."""
    from database.migrations import add_local_source_path, add_origin_column

    mm = MigrationManager(fresh_db)
    mm.migrate()

    conn = fresh_db.connect()
    assert add_local_source_path.needs_run(conn) is False
    assert add_origin_column.needs_run(conn) is False
