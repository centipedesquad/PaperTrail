"""
Fix notes_fts triggers for external-content FTS5 table.

External-content FTS5 tables (content=tablename) do NOT support plain
DELETE or UPDATE. Must use the special 'delete' command and reinsert
pattern, same as papers_fts.
"""

name = "fix_notes_fts_triggers"
description = "Recreate notes_fts triggers with proper FTS5 external-content delete/update syntax"


def needs_run(conn) -> bool:
    """Check if notes_fts_delete trigger uses plain DELETE instead of the 'delete' command."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='notes_fts_delete'"
    ).fetchone()
    if not row:
        return False  # No trigger yet — baseline will create it correctly
    sql = row[0] or ""
    # Old pattern: "DELETE FROM notes_fts"
    # New pattern: "INSERT INTO notes_fts(notes_fts"
    return "DELETE FROM notes_fts" in sql


def apply(conn) -> None:
    """Drop and recreate notes_fts triggers, then rebuild the index."""
    conn.executescript("""
    DROP TRIGGER IF EXISTS notes_fts_insert;
    DROP TRIGGER IF EXISTS notes_fts_delete;
    DROP TRIGGER IF EXISTS notes_fts_update;

    CREATE TRIGGER IF NOT EXISTS notes_fts_insert AFTER INSERT ON paper_notes BEGIN
        INSERT INTO notes_fts(rowid, note_text) VALUES (NEW.id, NEW.note_text);
    END;

    CREATE TRIGGER IF NOT EXISTS notes_fts_delete AFTER DELETE ON paper_notes BEGIN
        INSERT INTO notes_fts(notes_fts, rowid, note_text)
        VALUES('delete', OLD.id, OLD.note_text);
    END;

    CREATE TRIGGER IF NOT EXISTS notes_fts_update AFTER UPDATE ON paper_notes BEGIN
        INSERT INTO notes_fts(notes_fts, rowid, note_text)
        VALUES('delete', OLD.id, OLD.note_text);
        INSERT INTO notes_fts(rowid, note_text) VALUES (NEW.id, NEW.note_text);
    END;

    -- Rebuild index to clear stale tokens from old triggers
    INSERT INTO notes_fts(notes_fts) VALUES('rebuild');
    """)
