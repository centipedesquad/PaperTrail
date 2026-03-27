-- Migration 003: Fix FTS5 delete/update sync
-- The contentless FTS5 table from migration 002 requires special delete syntax.
-- Plain DELETE/UPDATE silently fail on contentless FTS tables.
-- We stay contentless (authors is a computed column, not on papers table)
-- but use the correct FTS5 delete command in triggers.

-- Drop ALL FTS-related triggers
DROP TRIGGER IF EXISTS papers_fts_insert;
DROP TRIGGER IF EXISTS papers_fts_delete;
DROP TRIGGER IF EXISTS papers_fts_update;
DROP TRIGGER IF EXISTS papers_fts_update_authors_insert;
DROP TRIGGER IF EXISTS papers_fts_update_authors_delete;

-- Drop and recreate FTS table (contentless — no content= clause)
DROP TABLE IF EXISTS papers_fts;

CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    arxiv_id,
    title,
    abstract,
    authors,
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

-- INSERT trigger: standard insert (works on contentless)
CREATE TRIGGER IF NOT EXISTS papers_fts_insert AFTER INSERT ON papers
BEGIN
    INSERT INTO papers_fts(rowid, arxiv_id, title, abstract, authors)
    VALUES (NEW.id, NEW.arxiv_id, NEW.title, NEW.abstract, '');
END;

-- DELETE trigger: use FTS5 delete command (required for contentless)
CREATE TRIGGER IF NOT EXISTS papers_fts_delete AFTER DELETE ON papers
BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, arxiv_id, title, abstract, authors)
    VALUES('delete', OLD.id, OLD.arxiv_id, OLD.title, OLD.abstract, '');
END;

-- UPDATE trigger: delete old entry + insert new (required for contentless)
CREATE TRIGGER IF NOT EXISTS papers_fts_update AFTER UPDATE ON papers
BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, arxiv_id, title, abstract, authors)
    VALUES('delete', OLD.id, OLD.arxiv_id, OLD.title, OLD.abstract, '');
    INSERT INTO papers_fts(rowid, arxiv_id, title, abstract, authors)
    VALUES(NEW.id, NEW.arxiv_id, NEW.title, NEW.abstract, '');
END;

-- Author INSERT trigger: update authors field via UPDATE (works on contentless for existing rows)
CREATE TRIGGER IF NOT EXISTS papers_fts_update_authors_insert AFTER INSERT ON paper_authors
BEGIN
    UPDATE papers_fts
    SET authors = (
        SELECT GROUP_CONCAT(a.name, ' ')
        FROM paper_authors pa
        JOIN authors a ON pa.author_id = a.id
        WHERE pa.paper_id = NEW.paper_id
        ORDER BY pa.author_order
    )
    WHERE rowid = NEW.paper_id;
END;

-- Author DELETE trigger: update authors field
CREATE TRIGGER IF NOT EXISTS papers_fts_update_authors_delete AFTER DELETE ON paper_authors
BEGIN
    UPDATE papers_fts
    SET authors = COALESCE((
        SELECT GROUP_CONCAT(a.name, ' ')
        FROM paper_authors pa
        JOIN authors a ON pa.author_id = a.id
        WHERE pa.paper_id = OLD.paper_id
        ORDER BY pa.author_order
    ), '')
    WHERE rowid = OLD.paper_id;
END;

-- Update schema version
INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', '003');
