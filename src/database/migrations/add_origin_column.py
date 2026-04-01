"""Add origin column to papers table to track how papers entered the library."""

name = "add_origin_column"
description = "Add origin column to track how papers entered the library (fetch vs search)"


def needs_run(conn) -> bool:
    """Check if origin column exists on papers table."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
    return "origin" not in columns


def apply(conn) -> None:
    """Add the column and index."""
    conn.execute("ALTER TABLE papers ADD COLUMN origin TEXT NOT NULL DEFAULT 'fetch'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_origin ON papers(origin)")
