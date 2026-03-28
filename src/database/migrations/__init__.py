"""
Migration registry for PaperTrail.

Each migration module exposes:
    name: str           - Human-readable name
    description: str    - What this migration does
    needs_run(conn)     - Introspect DB schema, return True if migration should apply
    apply(conn)         - Execute the migration SQL
"""

# Shared FTS5 trigger SQL — single source of truth for both baseline and upgrade migrations.
# These triggers keep papers_fts (contentless, content='') in sync with papers + paper_authors.
FTS5_TRIGGER_SQL = """
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

from database.migrations import (
    baseline_schema,
    fts5_contentless,
    add_local_source_path,
    add_origin_column,
)

# Ordered list of all migrations. Order matters for fresh databases.
MIGRATION_REGISTRY = [
    baseline_schema,
    fts5_contentless,
    add_local_source_path,
    add_origin_column,
]
