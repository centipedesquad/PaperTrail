-- Migration 003: Fix FTS5 content sync
-- Recreate FTS table with content=papers so standard triggers work correctly.
-- The contentless table from migration 002 silently fails on DELETE/UPDATE triggers.

-- Drop ALL FTS-related triggers
DROP TRIGGER IF EXISTS papers_fts_insert;
DROP TRIGGER IF EXISTS papers_fts_delete;
DROP TRIGGER IF EXISTS papers_fts_update;
DROP TRIGGER IF EXISTS papers_fts_update_authors_insert;
DROP TRIGGER IF EXISTS papers_fts_update_authors_delete;

-- Drop old FTS table
DROP TABLE IF EXISTS papers_fts;

-- Create content-synced FTS5 table (content=papers keeps FTS in sync with source)
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    arxiv_id,
    title,
    abstract,
    authors,
    content=papers,
    content_rowid=id,
    tokenize='porter'
);

-- Populate FTS table from existing data
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

-- Trigger: insert FTS entry when paper is added
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

-- Trigger: remove FTS entry when paper is deleted
CREATE TRIGGER IF NOT EXISTS papers_fts_delete AFTER DELETE ON papers
BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, arxiv_id, title, abstract, authors)
    VALUES ('delete', OLD.id, OLD.arxiv_id, OLD.title, OLD.abstract, '');
END;

-- Trigger: update FTS entry when paper is modified
CREATE TRIGGER IF NOT EXISTS papers_fts_update AFTER UPDATE ON papers
BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, arxiv_id, title, abstract, authors)
    VALUES ('delete', OLD.id, OLD.arxiv_id, OLD.title, OLD.abstract, '');
    INSERT INTO papers_fts(rowid, arxiv_id, title, abstract, authors)
    VALUES (NEW.id, NEW.arxiv_id, NEW.title, NEW.abstract, '');
END;

-- Trigger: update FTS authors when author is added to a paper
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

-- Trigger: update FTS authors when author is removed from a paper
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
