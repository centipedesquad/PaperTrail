"""
Guard the paper_authors BEFORE-DELETE FTS trigger against parent-paper deletes.

Deleting (or pruning) a paper that has authors used to fire
papers_fts_update_authors_delete during the ON DELETE CASCADE on paper_authors,
AFTER papers_fts_delete had already removed the paper's contentless papers_fts row
and AFTER the parent papers row was gone. The redundant 'delete' plus phantom
reinsert left the FTS index inconsistent and aborted the statement with
"database disk image is malformed", making prune and per-paper removal unusable for
any real (authored) paper.

The fix adds a `WHEN EXISTS (SELECT 1 FROM papers WHERE id = OLD.paper_id)` guard to
that trigger (see FTS5_TRIGGER_SQL). This migration recreates the papers_fts triggers
from the now-guarded source on existing databases. The on-disk FTS index is not
rebuilt: the corrupting statement always rolled back, so no successful delete ever
persisted an inconsistent index.
"""

name = "fix_fts_author_delete_guard"
description = "Guard papers_fts_update_authors_delete so paper deletes/prunes don't corrupt the FTS index"


def needs_run(conn) -> bool:
    """Run if the author-delete trigger exists without the WHEN-EXISTS parent guard."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' "
        "AND name='papers_fts_update_authors_delete'"
    ).fetchone()
    if row is None:
        # No trigger yet — baseline_schema / fts5_contentless will create the
        # guarded version directly from FTS5_TRIGGER_SQL.
        return False
    sql = (row[0] or "").upper()
    return "WHEN EXISTS" not in sql


def apply(conn) -> None:
    """Drop and recreate all FTS triggers with the guarded author-delete trigger."""
    from database.migrations import FTS5_TRIGGER_SQL

    drop_sql = """
    DROP TRIGGER IF EXISTS papers_fts_insert;
    DROP TRIGGER IF EXISTS papers_fts_delete;
    DROP TRIGGER IF EXISTS papers_fts_update;
    DROP TRIGGER IF EXISTS papers_fts_update_authors_insert;
    DROP TRIGGER IF EXISTS papers_fts_update_authors_delete;
    """
    conn.executescript(drop_sql + FTS5_TRIGGER_SQL)
