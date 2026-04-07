"""Tests for library migration utilities."""

import json
import os
import tempfile
import pytest

from utils.library_migration import (
    read_config, write_config, read_previous_paths, dismiss_previous_paths,
    update_paths_in_db, export_library, create_new_library,
    null_file_paths_in_db, count_files, count_directory_size,
    copy_directory_with_progress,
)
from services.config_service import ConfigService


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
