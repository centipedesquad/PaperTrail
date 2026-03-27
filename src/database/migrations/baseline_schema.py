"""
Baseline schema migration.

Creates all core tables, FTS5 (contentless), triggers, indexes, and default settings.
This is the consolidated final schema from migrations 001 + 003.
"""

# NOTE: FTS5_TRIGGER_SQL is imported lazily in apply() to avoid circular import
# (__init__.py imports this module, so we can't import from __init__ at module level).

name = "baseline_schema"
description = "Create all core tables, FTS5 (contentless), triggers, indexes, and default settings"

_SCHEMA_SQL_BEFORE_TRIGGERS = """
-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Core paper metadata table
CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arxiv_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    abstract TEXT NOT NULL,
    publication_date TEXT NOT NULL,
    pdf_url TEXT NOT NULL,
    local_pdf_path TEXT,
    version TEXT,
    comment TEXT,
    journal_ref TEXT,
    doi TEXT,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id ON papers(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_papers_publication_date ON papers(publication_date);
CREATE INDEX IF NOT EXISTS idx_papers_date_added ON papers(date_added);

-- Authors table with normalized names
CREATE TABLE IF NOT EXISTS authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_authors_normalized_name ON authors(normalized_name);

-- arXiv subject categories
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    parent_code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_code) REFERENCES categories(code)
);

CREATE INDEX IF NOT EXISTS idx_categories_code ON categories(code);

-- Many-to-many: papers to authors
CREATE TABLE IF NOT EXISTS paper_authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    author_order INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE CASCADE,
    UNIQUE(paper_id, author_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_authors_paper_id ON paper_authors(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_authors_author_id ON paper_authors(author_id);

-- Many-to-many: papers to categories
CREATE TABLE IF NOT EXISTS paper_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    UNIQUE(paper_id, category_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_categories_paper_id ON paper_categories(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_categories_category_id ON paper_categories(category_id);

-- User notes for papers
CREATE TABLE IF NOT EXISTS paper_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL UNIQUE,
    note_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_paper_notes_paper_id ON paper_notes(paper_id);

-- User ratings for papers
CREATE TABLE IF NOT EXISTS paper_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL UNIQUE,
    importance TEXT CHECK(importance IN ('path-breaking', 'good', 'routine', 'passable', 'meh', 'trash')),
    comprehension TEXT CHECK(comprehension IN ('understood', 'partially understood', 'not understood')),
    technicality TEXT CHECK(technicality IN ('tough', 'not tough', 'doesnt make sense')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_paper_ratings_paper_id ON paper_ratings(paper_id);

-- Application settings (key-value store)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User's preferred categories for retrieval
CREATE TABLE IF NOT EXISTS preferred_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);

-- Contentless FTS5 for papers (content='' because 'authors' is computed from joins)
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    arxiv_id,
    title,
    abstract,
    authors,
    content='',
    tokenize='porter'
);

"""

_SCHEMA_SQL_AFTER_TRIGGERS = """
-- Full-text search for notes
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    note_text,
    content=paper_notes,
    content_rowid=id,
    tokenize='porter'
);

CREATE TRIGGER IF NOT EXISTS notes_fts_insert AFTER INSERT ON paper_notes BEGIN
    INSERT INTO notes_fts(rowid, note_text) VALUES (NEW.id, NEW.note_text);
END;

CREATE TRIGGER IF NOT EXISTS notes_fts_delete AFTER DELETE ON paper_notes BEGIN
    DELETE FROM notes_fts WHERE rowid = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS notes_fts_update AFTER UPDATE ON paper_notes BEGIN
    UPDATE notes_fts SET note_text = NEW.note_text WHERE rowid = NEW.id;
END;

-- Author metrics from external sources
CREATE TABLE IF NOT EXISTS author_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL UNIQUE,
    citation_count INTEGER DEFAULT 0,
    h_index INTEGER DEFAULT 0,
    paper_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE CASCADE
);

-- Tags (user or AI-generated)
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    source TEXT CHECK(source IN ('user', 'ai')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many: papers to tags
CREATE TABLE IF NOT EXISTS paper_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
    UNIQUE(paper_id, tag_id)
);

-- PDF annotations imported from readers
CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    annotation_type TEXT CHECK(annotation_type IN ('highlight', 'note', 'underline', 'strikethrough')),
    page_number INTEGER,
    content TEXT,
    color TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_annotations_paper_id ON annotations(paper_id);

-- Insert default settings
INSERT INTO settings (key, value) VALUES ('schema_version', 'baseline');
INSERT INTO settings (key, value) VALUES ('pdf_naming_pattern', '[{author1}_{author2}][{title}][{arxiv_id}].pdf');
INSERT INTO settings (key, value) VALUES ('download_preference', 'ask');
INSERT INTO settings (key, value) VALUES ('max_fetch_results', '50');
INSERT INTO settings (key, value) VALUES ('fetch_mode', 'new');
"""


def needs_run(conn) -> bool:
    """Run if the 'papers' table does not exist (fresh database)."""
    row = conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='papers'"
    ).fetchone()
    return row[0] == 0


def apply(conn) -> None:
    """Create the full schema from scratch."""
    from database.migrations import FTS5_TRIGGER_SQL
    conn.executescript(_SCHEMA_SQL_BEFORE_TRIGGERS + FTS5_TRIGGER_SQL + _SCHEMA_SQL_AFTER_TRIGGERS)
