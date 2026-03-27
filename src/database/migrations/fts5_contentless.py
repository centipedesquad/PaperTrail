"""
FTS5 contentless upgrade migration.

Upgrades papers_fts from content=papers (or no content clause) to content=''
with correct BEFORE triggers using the special delete syntax.
"""

name = "fts5_contentless"
description = "Upgrade papers_fts to contentless FTS5 with correct delete triggers"

FTS5_MIGRATION_SQL = """
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

-- INSERT trigger: new paper gets empty authors (author triggers update later)
CREATE TRIGGER IF NOT EXISTS papers_fts_insert AFTER INSERT ON papers
BEGIN
    INSERT INTO papers_fts(rowid, arxiv_id, title, abstract, authors)
    VALUES (NEW.id, NEW.arxiv_id, NEW.title, NEW.abstract, '');
END;

-- DELETE trigger: BEFORE DELETE so paper_authors rows still exist for lookup.
CREATE TRIGGER IF NOT EXISTS papers_fts_delete BEFORE DELETE ON papers
BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, arxiv_id, title, abstract, authors)
    VALUES('delete', OLD.id, OLD.arxiv_id, OLD.title, OLD.abstract,
        COALESCE((
            SELECT GROUP_CONCAT(a.name, ' ')
            FROM paper_authors pa
            JOIN authors a ON pa.author_id = a.id
            WHERE pa.paper_id = OLD.id
            ORDER BY pa.author_order
        ), ''));
END;

-- UPDATE trigger on papers: delete with current authors, reinsert with new fields.
CREATE TRIGGER IF NOT EXISTS papers_fts_update BEFORE UPDATE ON papers
BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, arxiv_id, title, abstract, authors)
    VALUES('delete', OLD.id, OLD.arxiv_id, OLD.title, OLD.abstract,
        COALESCE((
            SELECT GROUP_CONCAT(a.name, ' ')
            FROM paper_authors pa
            JOIN authors a ON pa.author_id = a.id
            WHERE pa.paper_id = OLD.id
            ORDER BY pa.author_order
        ), ''));
    INSERT INTO papers_fts(rowid, arxiv_id, title, abstract, authors)
    VALUES(NEW.id, NEW.arxiv_id, NEW.title, NEW.abstract,
        COALESCE((
            SELECT GROUP_CONCAT(a.name, ' ')
            FROM paper_authors pa
            JOIN authors a ON pa.author_id = a.id
            WHERE pa.paper_id = NEW.id
            ORDER BY pa.author_order
        ), ''));
END;

-- Author INSERT trigger: AFTER INSERT on paper_authors.
CREATE TRIGGER IF NOT EXISTS papers_fts_update_authors_insert AFTER INSERT ON paper_authors
BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, arxiv_id, title, abstract, authors)
    VALUES('delete', NEW.paper_id,
        (SELECT arxiv_id FROM papers WHERE id = NEW.paper_id),
        (SELECT title FROM papers WHERE id = NEW.paper_id),
        (SELECT abstract FROM papers WHERE id = NEW.paper_id),
        COALESCE((
            SELECT GROUP_CONCAT(a.name, ' ')
            FROM paper_authors pa
            JOIN authors a ON pa.author_id = a.id
            WHERE pa.paper_id = NEW.paper_id
            AND pa.rowid != NEW.rowid
            ORDER BY pa.author_order
        ), ''));
    INSERT INTO papers_fts(rowid, arxiv_id, title, abstract, authors)
    VALUES(NEW.paper_id,
        (SELECT arxiv_id FROM papers WHERE id = NEW.paper_id),
        (SELECT title FROM papers WHERE id = NEW.paper_id),
        (SELECT abstract FROM papers WHERE id = NEW.paper_id),
        COALESCE((
            SELECT GROUP_CONCAT(a.name, ' ')
            FROM paper_authors pa
            JOIN authors a ON pa.author_id = a.id
            WHERE pa.paper_id = NEW.paper_id
            ORDER BY pa.author_order
        ), ''));
END;

-- Author DELETE trigger: BEFORE DELETE on paper_authors.
CREATE TRIGGER IF NOT EXISTS papers_fts_update_authors_delete BEFORE DELETE ON paper_authors
BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, arxiv_id, title, abstract, authors)
    VALUES('delete', OLD.paper_id,
        (SELECT arxiv_id FROM papers WHERE id = OLD.paper_id),
        (SELECT title FROM papers WHERE id = OLD.paper_id),
        (SELECT abstract FROM papers WHERE id = OLD.paper_id),
        COALESCE((
            SELECT GROUP_CONCAT(a.name, ' ')
            FROM paper_authors pa
            JOIN authors a ON pa.author_id = a.id
            WHERE pa.paper_id = OLD.paper_id
            ORDER BY pa.author_order
        ), ''));
    INSERT INTO papers_fts(rowid, arxiv_id, title, abstract, authors)
    VALUES(OLD.paper_id,
        (SELECT arxiv_id FROM papers WHERE id = OLD.paper_id),
        (SELECT title FROM papers WHERE id = OLD.paper_id),
        (SELECT abstract FROM papers WHERE id = OLD.paper_id),
        COALESCE((
            SELECT GROUP_CONCAT(a.name, ' ')
            FROM paper_authors pa
            JOIN authors a ON pa.author_id = a.id
            WHERE pa.paper_id = OLD.paper_id
            AND pa.rowid != OLD.rowid
            ORDER BY pa.author_order
        ), ''));
END;
"""


def needs_run(conn) -> bool:
    """Check if papers_fts exists but is NOT contentless (content='')."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='papers_fts'"
    ).fetchone()
    if row is None:
        return False  # No FTS table — baseline will handle it
    sql = (row[0] or "").lower().replace(" ", "")
    # Contentless FTS has content='' in the CREATE statement
    return "content=''" not in sql


def apply(conn) -> None:
    """Drop and recreate FTS with content='', repopulate, create triggers."""
    conn.executescript(FTS5_MIGRATION_SQL)
