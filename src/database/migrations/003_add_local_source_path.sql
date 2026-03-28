-- Add local_source_path column to papers table for tracking downloaded source files
ALTER TABLE papers ADD COLUMN local_source_path TEXT;
