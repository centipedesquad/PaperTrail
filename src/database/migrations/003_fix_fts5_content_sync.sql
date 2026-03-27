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

-- Drop and recreate FTS table as explicitly contentless (content='')
-- The special delete syntax only works on contentless or external-content tables.
-- We use contentless because 'authors' is computed from joins, not a real column.
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

-- Author INSERT trigger: delete old FTS row + reinsert with updated authors
-- (contentless FTS5 does NOT support UPDATE — must use delete-then-reinsert)
CREATE TRIGGER IF NOT EXISTS papers_fts_update_authors_insert AFTER INSERT ON paper_authors
BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, arxiv_id, title, abstract, authors)
    VALUES('delete', NEW.paper_id,
        (SELECT arxiv_id FROM papers WHERE id = NEW.paper_id),
        (SELECT title FROM papers WHERE id = NEW.paper_id),
        (SELECT abstract FROM papers WHERE id = NEW.paper_id),
        '');
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

-- Author DELETE trigger: delete old FTS row + reinsert with updated authors
CREATE TRIGGER IF NOT EXISTS papers_fts_update_authors_delete AFTER DELETE ON paper_authors
BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, arxiv_id, title, abstract, authors)
    VALUES('delete', OLD.paper_id,
        (SELECT arxiv_id FROM papers WHERE id = OLD.paper_id),
        (SELECT title FROM papers WHERE id = OLD.paper_id),
        (SELECT abstract FROM papers WHERE id = OLD.paper_id),
        '');
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
            ORDER BY pa.author_order
        ), ''));
END;

-- Update schema version
INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', '003');
