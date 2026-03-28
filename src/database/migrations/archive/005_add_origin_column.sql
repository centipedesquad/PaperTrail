-- Add origin column to track how papers entered the library
-- 'fetch' = category-based auto-fetch, 'search' = manual import via search/ID lookup
-- Version: 005

ALTER TABLE papers ADD COLUMN origin TEXT NOT NULL DEFAULT 'fetch';
CREATE INDEX IF NOT EXISTS idx_papers_origin ON papers(origin);

INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', '005');
