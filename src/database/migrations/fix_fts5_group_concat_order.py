"""
Fix GROUP_CONCAT ordering in FTS5 triggers.

SQLite's GROUP_CONCAT does not guarantee ORDER BY in the same SELECT.
Wrapping in a subquery ensures deterministic author ordering, which is
required for FTS5 contentless delete operations (exact value match).
"""

name = "fix_fts5_group_concat_order"
description = "Recreate FTS5 triggers with correct GROUP_CONCAT ordering via subqueries"


def needs_run(conn) -> bool:
    """Check if any FTS trigger still uses the old non-subquery GROUP_CONCAT pattern."""
    triggers = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'papers_fts%'"
    ).fetchall()
    if not triggers:
        return False  # No triggers yet — baseline or fts5_contentless will create them
    for row in triggers:
        sql = row[0] or ""
        # Old pattern: GROUP_CONCAT directly with ORDER BY (no subquery wrapper)
        # New pattern: GROUP_CONCAT(name, ' ') FROM (SELECT ... ORDER BY ...)
        if "GROUP_CONCAT" in sql and "FROM (" not in sql:
            return True
    return False


def apply(conn) -> None:
    """Drop and recreate all FTS triggers with fixed GROUP_CONCAT subqueries."""
    from database.migrations import FTS5_TRIGGER_SQL

    drop_sql = """
    DROP TRIGGER IF EXISTS papers_fts_insert;
    DROP TRIGGER IF EXISTS papers_fts_delete;
    DROP TRIGGER IF EXISTS papers_fts_update;
    DROP TRIGGER IF EXISTS papers_fts_update_authors_insert;
    DROP TRIGGER IF EXISTS papers_fts_update_authors_delete;
    """
    conn.executescript(drop_sql + FTS5_TRIGGER_SQL)
