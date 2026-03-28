-- Migration 002: Fix author search in FTS5
-- Recreate FTS table without content= to allow manual author updates

-- Drop ALL FTS-related triggers first (including new ones in case of retry)
DROP TRIGGER IF EXISTS papers_fts_insert;
DROP TRIGGER IF EXISTS papers_fts_delete;
DROP TRIGGER IF EXISTS papers_fts_update;
DROP TRIGGER IF EXISTS papers_fts_update_authors_insert;
DROP TRIGGER IF EXISTS papers_fts_update_authors_delete;

-- Drop old FTS table
DROP TABLE IF EXISTS papers_fts;

-- Create new contentless FTS5 table
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    arxiv_id,
    title,
    abstract,
    authors,
    tokenize='porter'
);

-- Populate FTS table with existing papers
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

-- Trigger to update FTS when papers are inserted
CREATE TRIGGER IF NOT EXISTS papers_fts_insert AFTER INSERT ON papers
BEGIN
    INSERT INTO papers_fts(rowid, arxiv_id, title, abstract, authors)
    VALUES (
        NEW.id,
        NEW.arxiv_id,
        NEW.title,
        NEW.abstract,
        ''
    );
END;

-- Trigger to update FTS when papers are deleted
CREATE TRIGGER IF NOT EXISTS papers_fts_delete AFTER DELETE ON papers
BEGIN
    DELETE FROM papers_fts WHERE rowid = OLD.id;
END;

-- Trigger to update FTS when papers are updated
CREATE TRIGGER IF NOT EXISTS papers_fts_update AFTER UPDATE ON papers
BEGIN
    UPDATE papers_fts
    SET arxiv_id = NEW.arxiv_id,
        title = NEW.title,
        abstract = NEW.abstract
    WHERE rowid = NEW.id;
END;

-- Trigger to update FTS when authors are added to a paper
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

-- Trigger to update FTS when authors are removed from a paper
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
