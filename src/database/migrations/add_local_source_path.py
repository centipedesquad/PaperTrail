"""Add local_source_path column to papers table for tracking downloaded source files."""

name = "add_local_source_path"
description = "Add local_source_path column for tracking downloaded source files"


def needs_run(conn) -> bool:
    """Check if local_source_path column exists on papers table."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
    return "local_source_path" not in columns


def apply(conn) -> None:
    """Add the column."""
    conn.execute("ALTER TABLE papers ADD COLUMN local_source_path TEXT")
