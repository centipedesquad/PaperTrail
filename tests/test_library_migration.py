"""Tests for library migration utilities."""

import json
import os
import tempfile
import pytest

import sqlite3

from utils.library_migration import (
    read_config, write_config, read_previous_paths, dismiss_previous_paths,
    update_paths_in_db, export_library, create_new_library,
    null_file_paths_in_db, count_files, count_directory_size,
    copy_directory_with_progress, analyze_merge, merge_library,
)
from services.config_service import ConfigService


def _create_test_db(db_path, papers=None):
    """Create a minimal test database with optional paper data.

    Args:
        db_path: Path for the SQLite database file
        papers: List of dicts with keys: arxiv_id, title, authors (list of str),
                categories (list of str), local_pdf_path, note_text
    """
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS settings "
                 "(key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS papers "
                 "(id INTEGER PRIMARY KEY AUTOINCREMENT, arxiv_id TEXT NOT NULL UNIQUE, "
                 "title TEXT NOT NULL, abstract TEXT NOT NULL, publication_date TEXT NOT NULL, "
                 "pdf_url TEXT NOT NULL, local_pdf_path TEXT, local_source_path TEXT, "
                 "origin TEXT NOT NULL DEFAULT 'fetch', version TEXT, comment TEXT, "
                 "journal_ref TEXT, doi TEXT, date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                 "last_accessed TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                 "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("CREATE TABLE IF NOT EXISTS authors "
                 "(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, "
                 "normalized_name TEXT NOT NULL UNIQUE)")
    conn.execute("CREATE TABLE IF NOT EXISTS categories "
                 "(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, "
                 "name TEXT NOT NULL, parent_code TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS paper_authors "
                 "(id INTEGER PRIMARY KEY AUTOINCREMENT, paper_id INTEGER NOT NULL, "
                 "author_id INTEGER NOT NULL, author_order INTEGER NOT NULL, "
                 "FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE, "
                 "UNIQUE(paper_id, author_id))")
    conn.execute("CREATE TABLE IF NOT EXISTS paper_categories "
                 "(id INTEGER PRIMARY KEY AUTOINCREMENT, paper_id INTEGER NOT NULL, "
                 "category_id INTEGER NOT NULL, is_primary BOOLEAN DEFAULT 0, "
                 "FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE, "
                 "UNIQUE(paper_id, category_id))")
    conn.execute("CREATE TABLE IF NOT EXISTS paper_notes "
                 "(id INTEGER PRIMARY KEY AUTOINCREMENT, paper_id INTEGER NOT NULL UNIQUE, "
                 "note_text TEXT, FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE)")
    conn.execute("CREATE TABLE IF NOT EXISTS paper_ratings "
                 "(id INTEGER PRIMARY KEY AUTOINCREMENT, paper_id INTEGER NOT NULL UNIQUE, "
                 "importance TEXT, comprehension TEXT, technicality TEXT, "
                 "FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE)")
    conn.execute("PRAGMA foreign_keys = ON")

    for p in (papers or []):
        cursor = conn.execute(
            "INSERT INTO papers (arxiv_id, title, abstract, publication_date, pdf_url, "
            "local_pdf_path) VALUES (?, ?, ?, ?, ?, ?)",
            (p['arxiv_id'], p.get('title', 'Test'), 'Abstract',
             '2024-01-01', 'http://x', p.get('local_pdf_path'))
        )
        paper_id = cursor.lastrowid
        for i, author_name in enumerate(p.get('authors', [])):
            normalized = author_name.lower().strip()
            existing = conn.execute(
                "SELECT id FROM authors WHERE normalized_name = ?", (normalized,)
            ).fetchone()
            if existing:
                author_id = existing[0]
            else:
                c = conn.execute(
                    "INSERT INTO authors (name, normalized_name) VALUES (?, ?)",
                    (author_name, normalized)
                )
                author_id = c.lastrowid
            conn.execute(
                "INSERT INTO paper_authors (paper_id, author_id, author_order) "
                "VALUES (?, ?, ?)", (paper_id, author_id, i)
            )
        for code in p.get('categories', []):
            existing = conn.execute(
                "SELECT id FROM categories WHERE code = ?", (code,)
            ).fetchone()
            if existing:
                cat_id = existing[0]
            else:
                c = conn.execute(
                    "INSERT INTO categories (code, name) VALUES (?, ?)",
                    (code, code)
                )
                cat_id = c.lastrowid
            conn.execute(
                "INSERT INTO paper_categories (paper_id, category_id, is_primary) "
                "VALUES (?, ?, ?)", (paper_id, cat_id, 0)
            )
        if p.get('note_text'):
            conn.execute(
                "INSERT INTO paper_notes (paper_id, note_text) VALUES (?, ?)",
                (paper_id, p['note_text'])
            )
    conn.commit()
    conn.close()


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Temporary config file for testing."""
    cfg = tmp_path / ".papertrail_config"
    import utils.library_migration as lm
    monkeypatch.setattr(lm, "CONFIG_FILE", cfg)
    return cfg


@pytest.fixture
def populated_db(db, paper_service, sample_paper_data, sample_paper_data_2):
    """Database with papers that have local_pdf_path set."""
    p1 = paper_service.create_paper(sample_paper_data)
    p2 = paper_service.create_paper(sample_paper_data_2)

    db.execute(
        "UPDATE papers SET local_pdf_path = ? WHERE id = ?",
        ("/old/library/pdfs/paper1.pdf", p1)
    )
    db.execute(
        "UPDATE papers SET local_pdf_path = ? WHERE id = ?",
        ("/old/library/pdfs/paper2.pdf", p2)
    )
    db.execute(
        "UPDATE papers SET local_source_path = ? WHERE id = ?",
        ("/old/library/sources/paper1/", p1)
    )
    return db


# ── Config read/write ───────────────────────────────────────────

class TestReadConfig:
    def test_json_format(self, config_file):
        config_file.write_text(json.dumps({
            "db_dir": "/path/to/db",
            "files_dir": "/path/to/files"
        }))
        db_dir, files_dir = read_config()
        assert db_dir == "/path/to/db"
        assert files_dir == "/path/to/files"

    def test_json_without_files_dir(self, config_file):
        config_file.write_text(json.dumps({"db_dir": "/path/to/both"}))
        db_dir, files_dir = read_config()
        assert db_dir == "/path/to/both"
        assert files_dir == "/path/to/both"

    def test_legacy_single_line(self, config_file):
        config_file.write_text("/legacy/data/dir")
        db_dir, files_dir = read_config()
        assert db_dir == "/legacy/data/dir"
        assert files_dir == "/legacy/data/dir"

    def test_missing_file_raises(self, config_file):
        with pytest.raises(FileNotFoundError):
            read_config()

    def test_empty_file_raises(self, config_file):
        config_file.write_text("")
        with pytest.raises(ValueError):
            read_config()


class TestWriteConfig:
    def test_writes_json(self, config_file):
        write_config("/db", "/files")
        data = json.loads(config_file.read_text())
        assert data["db_dir"] == "/db"
        assert data["files_dir"] == "/files"

    def test_writes_previous_paths(self, config_file):
        write_config("/new/db", "/new/files", "/old/db", "/old/files")
        data = json.loads(config_file.read_text())
        assert data["previous_db_dir"] == "/old/db"
        assert data["previous_files_dir"] == "/old/files"

    def test_omits_previous_when_none(self, config_file):
        write_config("/db", "/files")
        data = json.loads(config_file.read_text())
        assert "previous_db_dir" not in data
        assert "previous_files_dir" not in data


class TestPreviousPaths:
    def test_read_previous_paths(self, config_file):
        write_config("/db", "/files", "/old/db", "/old/files")
        prev_db, prev_files = read_previous_paths()
        assert prev_db == "/old/db"
        assert prev_files == "/old/files"

    def test_read_previous_paths_none(self, config_file):
        write_config("/db", "/files")
        prev_db, prev_files = read_previous_paths()
        assert prev_db is None
        assert prev_files is None

    def test_dismiss_previous_paths(self, config_file):
        write_config("/db", "/files", "/old/db", "/old/files")
        dismiss_previous_paths()
        data = json.loads(config_file.read_text())
        assert "previous_db_dir" not in data
        assert "previous_files_dir" not in data
        assert data["db_dir"] == "/db"


# ── Batch UPDATE correctness ────────────────────────────────────

class TestUpdatePathsInDb:
    def test_replaces_matching_prefix(self, populated_db):
        db_path = populated_db.db_path
        populated_db.close()

        update_paths_in_db(db_path, "/old/library", "/new/location")

        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT local_pdf_path, local_source_path FROM papers").fetchall()
        conn.close()

        pdf_paths = [r["local_pdf_path"] for r in rows if r["local_pdf_path"]]
        source_paths = [r["local_source_path"] for r in rows if r["local_source_path"]]

        for p in pdf_paths:
            assert p.startswith("/new/location/pdfs/")
            assert "/old/library/" not in p

        for s in source_paths:
            assert s.startswith("/new/location/sources/")

    def test_ignores_non_matching(self, populated_db):
        db_path = populated_db.db_path

        # Add a paper with a path that doesn't match the prefix
        populated_db.execute(
            "INSERT INTO papers (arxiv_id, title, abstract, publication_date, pdf_url, local_pdf_path) "
            "VALUES ('9999.00001', 'Other', 'Abstract', '2024-01-01', 'http://x', '/different/path/paper.pdf')"
        )
        populated_db.close()

        update_paths_in_db(db_path, "/old/library", "/new/location")

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT local_pdf_path FROM papers WHERE arxiv_id = '9999.00001'"
        ).fetchone()
        conn.close()
        assert row[0] == "/different/path/paper.pdf"

    def test_ignores_null_paths(self, db):
        """Papers with NULL local_pdf_path stay NULL."""
        db_path = db.db_path
        db.execute(
            "INSERT INTO papers (arxiv_id, title, abstract, publication_date, pdf_url) "
            "VALUES ('0000.00001', 'No PDF', 'Abstract', '2024-01-01', 'http://x')"
        )
        db.close()

        update_paths_in_db(db_path, "/old", "/new")

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT local_pdf_path FROM papers WHERE arxiv_id = '0000.00001'"
        ).fetchone()
        conn.close()
        assert row[0] is None


# ── Export library ───────────────────────────────────────────────

class TestExportLibrary:
    def test_copies_db_file(self, config_file):
        with tempfile.TemporaryDirectory() as old_dir, \
             tempfile.TemporaryDirectory() as new_dir:
            # Create a minimal DB at old location
            old_db = os.path.join(old_dir, "papertrail.db")
            import sqlite3
            conn = sqlite3.connect(old_db)
            conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
            conn.execute("CREATE TABLE papers (id INTEGER PRIMARY KEY, arxiv_id TEXT, title TEXT, "
                         "pdf_url TEXT, local_pdf_path TEXT, local_source_path TEXT)")
            conn.close()

            new_db_dir = os.path.join(new_dir, "db")
            new_files_dir = os.path.join(new_dir, "files")

            export_library(old_dir, new_db_dir, old_dir, new_files_dir)

            assert os.path.exists(os.path.join(new_db_dir, "papertrail.db"))

    def test_copies_pdfs(self, config_file):
        with tempfile.TemporaryDirectory() as old_dir, \
             tempfile.TemporaryDirectory() as new_dir:
            # Setup old structure
            old_db = os.path.join(old_dir, "papertrail.db")
            pdfs_dir = os.path.join(old_dir, "pdfs")
            os.makedirs(pdfs_dir)

            # Create test PDF file
            with open(os.path.join(pdfs_dir, "test.pdf"), 'w') as f:
                f.write("fake pdf")

            # Create minimal DB
            import sqlite3
            conn = sqlite3.connect(old_db)
            conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
            conn.execute("CREATE TABLE papers (id INTEGER PRIMARY KEY, arxiv_id TEXT, title TEXT, "
                         "pdf_url TEXT, local_pdf_path TEXT, local_source_path TEXT)")
            conn.close()

            new_db_dir = os.path.join(new_dir, "db")
            new_files_dir = os.path.join(new_dir, "files")

            export_library(old_dir, new_db_dir, old_dir, new_files_dir)

            assert os.path.exists(os.path.join(new_files_dir, "pdfs", "test.pdf"))

    def test_updates_paths_in_new_db(self, config_file):
        with tempfile.TemporaryDirectory() as old_dir, \
             tempfile.TemporaryDirectory() as new_dir:
            old_db = os.path.join(old_dir, "papertrail.db")
            pdfs_dir = os.path.join(old_dir, "pdfs")
            os.makedirs(pdfs_dir)

            import sqlite3
            conn = sqlite3.connect(old_db)
            conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
            conn.execute("CREATE TABLE papers (id INTEGER PRIMARY KEY, arxiv_id TEXT, title TEXT, "
                         "pdf_url TEXT, local_pdf_path TEXT, local_source_path TEXT)")
            conn.execute("INSERT INTO papers (arxiv_id, title, pdf_url, local_pdf_path) "
                         f"VALUES ('2301.00001', 'Test', 'http://x', '{old_dir}/pdfs/test.pdf')")
            conn.commit()
            conn.close()

            new_db_dir = os.path.join(new_dir, "db")
            new_files_dir = os.path.join(new_dir, "files")

            export_library(old_dir, new_db_dir, old_dir, new_files_dir)

            conn = sqlite3.connect(os.path.join(new_db_dir, "papertrail.db"))
            row = conn.execute("SELECT local_pdf_path FROM papers").fetchone()
            conn.close()
            assert row[0].startswith(new_files_dir)

    def test_preserves_old_library(self, config_file):
        with tempfile.TemporaryDirectory() as old_dir, \
             tempfile.TemporaryDirectory() as new_dir:
            old_db = os.path.join(old_dir, "papertrail.db")
            pdfs_dir = os.path.join(old_dir, "pdfs")
            os.makedirs(pdfs_dir)
            with open(os.path.join(pdfs_dir, "test.pdf"), 'w') as f:
                f.write("fake pdf")

            import sqlite3
            conn = sqlite3.connect(old_db)
            conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
            conn.execute("CREATE TABLE papers (id INTEGER PRIMARY KEY, arxiv_id TEXT, title TEXT, "
                         "pdf_url TEXT, local_pdf_path TEXT, local_source_path TEXT)")
            conn.execute("INSERT INTO papers (arxiv_id, title, pdf_url, local_pdf_path) "
                         f"VALUES ('2301.00001', 'Test', 'http://x', '{old_dir}/pdfs/test.pdf')")
            conn.commit()
            conn.close()

            new_db_dir = os.path.join(new_dir, "db")
            new_files_dir = os.path.join(new_dir, "files")

            export_library(old_dir, new_db_dir, old_dir, new_files_dir)

            # Old files still exist
            assert os.path.exists(old_db)
            assert os.path.exists(os.path.join(pdfs_dir, "test.pdf"))

            # Old DB paths unchanged
            conn = sqlite3.connect(old_db)
            row = conn.execute("SELECT local_pdf_path FROM papers").fetchone()
            conn.close()
            assert row[0].startswith(old_dir)


    def test_cancellation_mid_copy(self, config_file):
        with tempfile.TemporaryDirectory() as old_dir, \
             tempfile.TemporaryDirectory() as new_dir:
            old_db = os.path.join(old_dir, "papertrail.db")
            pdfs_dir = os.path.join(old_dir, "pdfs")
            os.makedirs(pdfs_dir)
            for i in range(5):
                with open(os.path.join(pdfs_dir, f"paper{i}.pdf"), 'w') as f:
                    f.write(f"fake pdf {i}")

            import sqlite3
            conn = sqlite3.connect(old_db)
            conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
            conn.execute("CREATE TABLE papers (id INTEGER PRIMARY KEY, arxiv_id TEXT, title TEXT, "
                         "pdf_url TEXT, local_pdf_path TEXT, local_source_path TEXT)")
            conn.close()

            new_db_dir = os.path.join(new_dir, "db")
            new_files_dir = os.path.join(new_dir, "files")

            result = export_library(
                old_dir, new_db_dir, old_dir, new_files_dir,
                cancelled=lambda: True
            )
            assert result is False

    def test_files_only_move(self, config_file):
        """Export with same db_dir but different files_dir."""
        with tempfile.TemporaryDirectory() as shared_dir, \
             tempfile.TemporaryDirectory() as new_files_dir:
            old_db = os.path.join(shared_dir, "papertrail.db")
            pdfs_dir = os.path.join(shared_dir, "pdfs")
            os.makedirs(pdfs_dir)
            with open(os.path.join(pdfs_dir, "test.pdf"), 'w') as f:
                f.write("fake pdf")

            import sqlite3
            conn = sqlite3.connect(old_db)
            conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
            conn.execute("CREATE TABLE papers (id INTEGER PRIMARY KEY, arxiv_id TEXT, title TEXT, "
                         "pdf_url TEXT, local_pdf_path TEXT, local_source_path TEXT)")
            conn.execute("INSERT INTO papers (arxiv_id, title, pdf_url, local_pdf_path) "
                         f"VALUES ('2301.00001', 'Test', 'http://x', '{shared_dir}/pdfs/test.pdf')")
            conn.commit()
            conn.close()

            # Same db_dir, different files_dir
            export_library(shared_dir, shared_dir, shared_dir, new_files_dir)

            # DB should NOT be copied (stays in shared_dir)
            assert not os.path.exists(os.path.join(new_files_dir, "papertrail.db"))

            # Files should be copied
            assert os.path.exists(os.path.join(new_files_dir, "pdfs", "test.pdf"))

            # Paths in original DB should be updated
            conn = sqlite3.connect(old_db)
            row = conn.execute("SELECT local_pdf_path FROM papers").fetchone()
            conn.close()
            assert row[0].startswith(new_files_dir)


# ── Create new library ──────────────────────────────────────────

class TestCreateNewLibrary:
    def test_initializes_fresh_db(self, config_file):
        with tempfile.TemporaryDirectory() as new_dir:
            new_db_dir = os.path.join(new_dir, "db")
            new_files_dir = os.path.join(new_dir, "files")

            create_new_library(new_db_dir, new_files_dir)

            db_path = os.path.join(new_db_dir, "papertrail.db")
            assert os.path.exists(db_path)

            # Should have schema but no papers
            import sqlite3
            conn = sqlite3.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            conn.close()
            assert count == 0

    def test_creates_directory_structure(self, config_file):
        with tempfile.TemporaryDirectory() as new_dir:
            new_db_dir = os.path.join(new_dir, "db")
            new_files_dir = os.path.join(new_dir, "files")

            create_new_library(new_db_dir, new_files_dir)

            assert os.path.isdir(os.path.join(new_files_dir, "pdfs"))
            assert os.path.isdir(os.path.join(new_files_dir, "sources"))
            assert os.path.isdir(os.path.join(new_files_dir, "cache"))

    def test_writes_config(self, config_file):
        with tempfile.TemporaryDirectory() as new_dir:
            new_db_dir = os.path.join(new_dir, "db")
            new_files_dir = os.path.join(new_dir, "files")

            create_new_library(new_db_dir, new_files_dir)

            data = json.loads(config_file.read_text())
            assert data["db_dir"] == new_db_dir
            assert data["files_dir"] == new_files_dir


# ── Null file paths ─────────────────────────────────────────────

class TestNullFilePaths:
    def test_nulls_all_paths(self, populated_db):
        db_path = populated_db.db_path
        populated_db.close()

        null_file_paths_in_db(db_path)

        import sqlite3
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT local_pdf_path, local_source_path FROM papers"
        ).fetchall()
        conn.close()

        for row in rows:
            assert row[0] is None
            assert row[1] is None


# ── Utility functions ────────────────────────────────────────────

class TestCountFiles:
    def test_counts_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.txt").write_text("b")
        (sub / "c.txt").write_text("c")
        assert count_files(str(tmp_path)) == 3

    def test_empty_dir(self, tmp_path):
        assert count_files(str(tmp_path)) == 0

    def test_nonexistent_dir(self):
        assert count_files("/nonexistent/path") == 0


class TestCopyDirectoryWithProgress:
    def test_copies_files(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        (src / "file.txt").write_text("hello")
        sub = src / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("world")

        copied = copy_directory_with_progress(str(src), str(dst))
        assert copied == 2
        assert (dst / "file.txt").read_text() == "hello"
        assert (dst / "sub" / "nested.txt").read_text() == "world"

    def test_progress_callback(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        (src / "a.txt").write_text("a")
        (src / "b.txt").write_text("b")

        calls = []
        def cb(current, total, name):
            calls.append((current, total, name))

        copy_directory_with_progress(str(src), str(dst), cb, 0, 2)
        assert len(calls) == 2

    def test_cancellation(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        (src / "a.txt").write_text("a")
        (src / "b.txt").write_text("b")

        copied = copy_directory_with_progress(
            str(src), str(dst), cancelled=lambda: True
        )
        assert copied == 0


# ── ConfigService integration ────────────────────────────────────

class TestConfigServiceFilesLocation:
    def test_get_files_location_from_config(self, config_service, config_file):
        write_config("/db/path", "/files/path")
        result = config_service.get_files_location()
        assert result == "/files/path"

    def test_get_files_location_falls_back(self, config_service, config_file):
        """When no config file exists, falls back to database_location."""
        config_service.set_database_location("/fallback")
        result = config_service.get_files_location()
        assert result == "/fallback"

    def test_set_files_location(self, config_service, config_file):
        write_config("/db/path", "/old/files")
        config_service.set_files_location("/new/files")
        data = json.loads(config_file.read_text())
        assert data["db_dir"] == "/db/path"
        assert data["files_dir"] == "/new/files"


# ── count_directory_size ────────────────────────────────────────

class TestCountDirectorySize:
    def test_counts_bytes(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello")  # 5 bytes
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.txt").write_text("world!")  # 6 bytes
        assert count_directory_size(str(tmp_path)) == 11

    def test_empty_dir(self, tmp_path):
        assert count_directory_size(str(tmp_path)) == 0

    def test_nonexistent_dir(self):
        assert count_directory_size("/nonexistent/path") == 0


# ── analyze_merge ──────────────────────────────────────────────

class TestAnalyzeMerge:
    def test_no_duplicates(self, config_file):
        with tempfile.TemporaryDirectory() as d:
            src_db = os.path.join(d, "src.db")
            dst_db = os.path.join(d, "dst.db")
            _create_test_db(src_db, [{"arxiv_id": "2301.00001"}])
            _create_test_db(dst_db, [{"arxiv_id": "2301.00002"}])

            result = analyze_merge(src_db, dst_db)
            assert result["total_incoming"] == 1
            assert result["non_duplicate_count"] == 1
            assert result["duplicate_count"] == 0

    def test_with_duplicates(self, config_file):
        with tempfile.TemporaryDirectory() as d:
            src_db = os.path.join(d, "src.db")
            dst_db = os.path.join(d, "dst.db")
            _create_test_db(src_db, [
                {"arxiv_id": "2301.00001"},
                {"arxiv_id": "2301.00002"},
            ])
            _create_test_db(dst_db, [
                {"arxiv_id": "2301.00001"},
                {"arxiv_id": "2301.00003"},
            ])

            result = analyze_merge(src_db, dst_db)
            assert result["total_incoming"] == 2
            assert result["non_duplicate_count"] == 1
            assert result["duplicate_count"] == 1
            assert "2301.00001" in result["duplicate_arxiv_ids"]

    def test_empty_source(self, config_file):
        with tempfile.TemporaryDirectory() as d:
            src_db = os.path.join(d, "src.db")
            dst_db = os.path.join(d, "dst.db")
            _create_test_db(src_db, [])
            _create_test_db(dst_db, [{"arxiv_id": "2301.00001"}])

            result = analyze_merge(src_db, dst_db)
            assert result["total_incoming"] == 0
            assert result["duplicate_count"] == 0


# ── merge_library ──────────────────────────────────────────────

class TestMergeLibrary:
    def _setup_dirs(self, tmpdir):
        """Create src and dst directory structures with DBs."""
        src_dir = os.path.join(tmpdir, "src")
        dst_dir = os.path.join(tmpdir, "dst")
        os.makedirs(os.path.join(src_dir, "pdfs"))
        os.makedirs(os.path.join(dst_dir, "pdfs"))
        return src_dir, dst_dir

    def test_merge_non_duplicates(self, config_file):
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)
            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "title": "Paper A",
                 "authors": ["Alice", "Bob"], "categories": ["cs.AI"]},
            ])
            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00002", "title": "Paper B"},
            ])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_existing")

            conn = sqlite3.connect(os.path.join(dst_dir, "papertrail.db"))
            papers = conn.execute("SELECT arxiv_id FROM papers ORDER BY arxiv_id").fetchall()
            conn.close()
            ids = [r[0] for r in papers]
            assert "2301.00001" in ids
            assert "2301.00002" in ids

    def test_merge_keep_existing(self, config_file):
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)
            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "title": "Incoming Version"},
            ])
            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "title": "Existing Version"},
            ])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_existing")

            conn = sqlite3.connect(os.path.join(dst_dir, "papertrail.db"))
            row = conn.execute("SELECT title FROM papers WHERE arxiv_id = '2301.00001'").fetchone()
            count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            conn.close()
            assert row[0] == "Existing Version"
            assert count == 1

    def test_merge_keep_incoming(self, config_file):
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)
            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "title": "Incoming Version"},
            ])
            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "title": "Existing Version"},
            ])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_incoming")

            conn = sqlite3.connect(os.path.join(dst_dir, "papertrail.db"))
            row = conn.execute("SELECT title FROM papers WHERE arxiv_id = '2301.00001'").fetchone()
            conn.close()
            assert row[0] == "Incoming Version"

    def test_merge_keep_both(self, config_file):
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)
            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "title": "Incoming"},
            ])
            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "title": "Existing"},
            ])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_both")

            conn = sqlite3.connect(os.path.join(dst_dir, "papertrail.db"))
            papers = conn.execute("SELECT arxiv_id, title FROM papers ORDER BY arxiv_id").fetchall()
            conn.close()
            assert len(papers) == 2
            ids = [r[0] for r in papers]
            assert "2301.00001" in ids
            assert "2301.00001_copy" in ids

    def test_merge_copies_files(self, config_file):
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)
            pdf_path = os.path.join(src_dir, "pdfs", "paper1.pdf")
            with open(pdf_path, 'w') as f:
                f.write("fake pdf")

            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "local_pdf_path": pdf_path},
            ])
            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_existing")

            assert os.path.exists(os.path.join(dst_dir, "pdfs", "paper1.pdf"))

    def test_merge_skips_files_for_keep_existing(self, config_file):
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)
            pdf_path = os.path.join(src_dir, "pdfs", "dup.pdf")
            with open(pdf_path, 'w') as f:
                f.write("incoming pdf")

            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "local_pdf_path": pdf_path},
            ])
            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001"},
            ])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_existing")

            # File should NOT be copied for skipped duplicate
            assert not os.path.exists(os.path.join(dst_dir, "pdfs", "dup.pdf"))

    def test_merge_preserves_settings(self, config_file):
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)
            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001"},
            ])
            dst_db = os.path.join(dst_dir, "papertrail.db")
            _create_test_db(dst_db, [])
            conn = sqlite3.connect(dst_db)
            conn.execute("INSERT INTO settings (key, value) VALUES ('theme', 'dark')")
            conn.commit()
            conn.close()

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_existing")

            conn = sqlite3.connect(dst_db)
            row = conn.execute("SELECT value FROM settings WHERE key = 'theme'").fetchone()
            conn.close()
            assert row[0] == "dark"

    def test_merge_notes_and_ratings(self, config_file):
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)
            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "note_text": "Important paper"},
            ])
            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_existing")

            conn = sqlite3.connect(os.path.join(dst_dir, "papertrail.db"))
            note = conn.execute(
                "SELECT n.note_text FROM paper_notes n "
                "JOIN papers p ON n.paper_id = p.id "
                "WHERE p.arxiv_id = '2301.00001'"
            ).fetchone()
            conn.close()
            assert note[0] == "Important paper"

    def test_merge_authors_shared(self, config_file):
        """Same author in both DBs should not create duplicate author rows."""
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)
            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "authors": ["Alice"]},
            ])
            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00002", "authors": ["Alice"]},
            ])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_existing")

            conn = sqlite3.connect(os.path.join(dst_dir, "papertrail.db"))
            author_count = conn.execute(
                "SELECT COUNT(*) FROM authors WHERE normalized_name = 'alice'"
            ).fetchone()[0]
            conn.close()
            assert author_count == 1

    def test_merge_cancellation(self, config_file):
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)
            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001"},
                {"arxiv_id": "2301.00002"},
            ])
            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [])

            result = merge_library(
                src_dir, dst_dir, src_dir, dst_dir,
                "keep_existing", cancelled=lambda: True
            )
            assert result is False

            # Destination should be unchanged (rollback)
            conn = sqlite3.connect(os.path.join(dst_dir, "papertrail.db"))
            count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            conn.close()
            assert count == 0

    def test_merge_copy_suffix_collision(self, config_file):
        """If _copy already exists, use _copy2."""
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)
            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001"},
            ])
            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001"},
                {"arxiv_id": "2301.00001_copy"},
            ])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_both")

            conn = sqlite3.connect(os.path.join(dst_dir, "papertrail.db"))
            papers = conn.execute("SELECT arxiv_id FROM papers ORDER BY arxiv_id").fetchall()
            conn.close()
            ids = [r[0] for r in papers]
            assert "2301.00001_copy2" in ids

    def test_merge_keep_both_no_file_overwrite(self, config_file):
        """keep_both must not overwrite existing paper's PDF."""
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)

            src_pdf = os.path.join(src_dir, "pdfs", "2301.00001.pdf")
            with open(src_pdf, 'w') as f:
                f.write("incoming content")

            dst_pdf = os.path.join(dst_dir, "pdfs", "2301.00001.pdf")
            with open(dst_pdf, 'w') as f:
                f.write("existing content")

            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "local_pdf_path": src_pdf},
            ])
            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [
                {"arxiv_id": "2301.00001", "local_pdf_path": dst_pdf},
            ])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_both")

            # Existing PDF must be untouched
            with open(dst_pdf) as f:
                assert f.read() == "existing content"

            # Copy should be at a different path
            copy_pdf = os.path.join(dst_dir, "pdfs", "2301.00001_copy.pdf")
            assert os.path.exists(copy_pdf)
            with open(copy_pdf) as f:
                assert f.read() == "incoming content"

    def test_merge_keep_incoming_replaces_notes_and_ratings(self, config_file):
        """keep_incoming should replace existing notes and ratings."""
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)

            src_db = os.path.join(src_dir, "papertrail.db")
            dst_db = os.path.join(dst_dir, "papertrail.db")
            _create_test_db(src_db, [
                {"arxiv_id": "2301.00001", "note_text": "New note"},
            ])
            # Add a rating to src
            conn = sqlite3.connect(src_db)
            paper_id = conn.execute(
                "SELECT id FROM papers WHERE arxiv_id = '2301.00001'"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO paper_ratings (paper_id, importance, comprehension, technicality) "
                "VALUES (?, 'high', 'medium', 'low')", (paper_id,)
            )
            conn.commit()
            conn.close()

            _create_test_db(dst_db, [
                {"arxiv_id": "2301.00001", "note_text": "Old note"},
            ])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_incoming")

            conn = sqlite3.connect(dst_db)
            note = conn.execute(
                "SELECT n.note_text FROM paper_notes n "
                "JOIN papers p ON n.paper_id = p.id "
                "WHERE p.arxiv_id = '2301.00001'"
            ).fetchone()
            rating = conn.execute(
                "SELECT r.importance FROM paper_ratings r "
                "JOIN papers p ON r.paper_id = p.id "
                "WHERE p.arxiv_id = '2301.00001'"
            ).fetchone()
            conn.close()
            assert note[0] == "New note"
            assert rating[0] == "high"

    def test_merge_ratings_values(self, config_file):
        """Verify ratings values are correctly transferred."""
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)

            src_db = os.path.join(src_dir, "papertrail.db")
            _create_test_db(src_db, [{"arxiv_id": "2301.00001"}])
            conn = sqlite3.connect(src_db)
            paper_id = conn.execute(
                "SELECT id FROM papers WHERE arxiv_id = '2301.00001'"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO paper_ratings (paper_id, importance, comprehension, technicality) "
                "VALUES (?, 'high', 'medium', 'low')", (paper_id,)
            )
            conn.commit()
            conn.close()

            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_existing")

            conn = sqlite3.connect(os.path.join(dst_dir, "papertrail.db"))
            rating = conn.execute(
                "SELECT r.importance, r.comprehension, r.technicality "
                "FROM paper_ratings r JOIN papers p ON r.paper_id = p.id "
                "WHERE p.arxiv_id = '2301.00001'"
            ).fetchone()
            conn.close()
            assert rating[0] == "high"
            assert rating[1] == "medium"
            assert rating[2] == "low"

    def test_merge_legacy_arxiv_id_with_slash(self, config_file):
        """Legacy arxiv IDs like hep-th/9901001 should merge without path issues."""
        with tempfile.TemporaryDirectory() as d:
            src_dir, dst_dir = self._setup_dirs(d)

            # Legacy ID with slash — sanitized in filename
            safe_id = "hep-th_9901001"
            pdf_path = os.path.join(src_dir, "pdfs", f"{safe_id}.pdf")
            with open(pdf_path, 'w') as f:
                f.write("legacy paper")

            _create_test_db(os.path.join(src_dir, "papertrail.db"), [
                {"arxiv_id": "hep-th/9901001", "local_pdf_path": pdf_path},
            ])
            _create_test_db(os.path.join(dst_dir, "papertrail.db"), [])

            merge_library(src_dir, dst_dir, src_dir, dst_dir, "keep_existing")

            conn = sqlite3.connect(os.path.join(dst_dir, "papertrail.db"))
            row = conn.execute(
                "SELECT arxiv_id FROM papers WHERE arxiv_id = 'hep-th/9901001'"
            ).fetchone()
            conn.close()
            assert row is not None
            assert os.path.exists(os.path.join(dst_dir, "pdfs", f"{safe_id}.pdf"))
