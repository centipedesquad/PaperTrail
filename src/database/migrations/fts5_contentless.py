"""
FTS5 contentless upgrade migration.

Upgrades papers_fts from content=papers (or no content clause) to content=''
with correct BEFORE triggers using the special delete syntax.
"""

# NOTE: FTS5_TRIGGER_SQL is imported lazily in apply() to avoid circular import
# (__init__.py imports this module, so we can't import from __init__ at module level).

name = "fts5_contentless"
description = "Upgrade papers_fts to contentless FTS5 with correct delete triggers"

_FTS5_MIGRATION_SQL_BEFORE_TRIGGERS = """
-- Drop ALL FTS-related triggers
DROP TRIGGER IF EXISTS papers_fts_insert;
DROP TRIGGER IF EXISTS papers_fts_delete;
DROP TRIGGER IF EXISTS papers_fts_update;
DROP TRIGGER IF EXISTS papers_fts_update_authors_insert;
DROP TRIGGER IF EXISTS papers_fts_update_authors_delete;

-- Drop and recreate FTS table as explicitly contentless (content='')
DROP TABLE IF EXISTS papers_fts;

CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    arxiv_id,
    title,
    abstract,
    authors,
    content='',
    tokenize='porter'
);

-- Repopulate from existing data
INSERT INTO papers_fts(rowid, arxiv_id, title, abstract, authors)
SELECT
    p.id,
    p.arxiv_id,
    p.title,
    p.abstract,
    COALESCE((
        SELECT GROUP_CONCAT(a.name, ' ')
        FROM paper_authors pa
        JOIN authors a ON pa.author_id = a.id
        WHERE pa.paper_id = p.id
        ORDER BY pa.author_order
    ), '')
FROM papers p;
"""


def needs_run(conn) -> bool:
    """Check if papers_fts exists but is NOT contentless (content='')."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='papers_fts'"
    ).fetchone()
    if row is None:
        return False  # No FTS table — baseline will handle it
    sql = (row[0] or "").lower().replace(" ", "")
    # Handle both single-quote and double-quote variations defensively
    return "content=''" not in sql and 'content=""' not in sql


def apply(conn) -> None:
    """Drop and recreate FTS with content='', repopulate, create triggers."""
    from database.migrations import FTS5_TRIGGER_SQL
    conn.executescript(_FTS5_MIGRATION_SQL_BEFORE_TRIGGERS + FTS5_TRIGGER_SQL)
