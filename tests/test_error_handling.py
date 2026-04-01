"""Tests for error handling paths."""

import os
import sqlite3
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from database.connection import DatabaseConnection
from database.repositories import PaperRepository, sanitize_fts5_query
from services.config_service import ConfigService
from services.fetch_service import FetchService
from services.paper_service import PaperService


# ── Database integrity check ────────────────────────────────────────

class TestDatabaseIntegrity:
    def test_healthy_database_passes_check(self, db):
        assert db._check_integrity() is True

    def test_corrupt_database_detected(self):
        """Write garbage to a db file and verify corruption raises RuntimeError."""
        db_path = tempfile.mktemp(suffix='.db')
        # Write invalid data that looks like a database but isn't
        with open(db_path, 'wb') as f:
            f.write(b'SQLite format 3\x00' + b'\xff' * 1000)

        db = DatabaseConnection(db_path)
        try:
            with pytest.raises(RuntimeError, match="corrupt"):
                db.connect()
            # Corrupt file should have been backed up
            assert os.path.exists(db_path + '.corrupt')
        finally:
            db.close()
            for f in [db_path, db_path + '.corrupt']:
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def test_integrity_check_returns_false_on_error(self):
        """If integrity check itself throws, return False."""
        db_path = tempfile.mktemp(suffix='.db')
        db = DatabaseConnection(db_path)
        db.connect()
        # Replace the connection with a mock that fails on integrity_check
        real_conn = db._connection
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = sqlite3.DatabaseError("disk I/O error")
        db._connection = mock_conn
        assert db._check_integrity() is False
        # Restore and clean up
        db._connection = real_conn
        db.close()
        try:
            os.unlink(db_path)
        except OSError:
            pass


# ── Config service error splitting ──────────────────────────────────

class TestConfigServiceErrors:
    def test_get_returns_default_for_missing_key(self, config_service):
        result = config_service.get("nonexistent", "fallback")
        assert result == "fallback"

    def test_get_logs_warning_on_db_error(self, config_service):
        """Database errors should be logged, not silently swallowed."""
        with patch.object(config_service.db, 'fetch_one', side_effect=sqlite3.OperationalError("disk error")):
            with patch('services.config_service.logger') as mock_logger:
                result = config_service.get("some_key", "default")
                assert result == "default"
                mock_logger.error.assert_called_once()

    def test_get_all_returns_empty_on_db_error(self, config_service):
        with patch.object(config_service.db, 'fetch_all', side_effect=sqlite3.OperationalError("error")):
            result = config_service.get_all()
            assert result == {}

    def test_set_raises_on_db_error(self, config_service):
        with patch.object(config_service.db, 'transaction', side_effect=sqlite3.OperationalError("error")):
            with pytest.raises(sqlite3.OperationalError):
                config_service.set("key", "value")

    def test_get_int_returns_default_on_invalid(self, config_service):
        config_service.set("bad_int", "not_a_number")
        assert config_service.get_max_fetch_results() == 50  # uses its own default
        # But the bad value is stored
        assert config_service.get("bad_int") == "not_a_number"


# ── Fetch service error handling ────────────────────────────────────

class TestFetchServiceErrors:
    def _make_fetch_service(self, db):
        ps = PaperService(db)
        return FetchService(ps)

    def test_network_error_retries_then_raises(self, db):
        fs = self._make_fetch_service(db)
        mock = MagicMock(side_effect=ConnectionError("No network"))
        with patch.object(fs.arxiv_client, 'fetch_new_papers', mock):
            with patch('services.fetch_service.time.sleep'):  # skip actual sleep
                with pytest.raises(ConnectionError):
                    fs.fetch_new_papers(['cs.AI'])
        # Should have retried 3 times
        assert mock.call_count == 3

    def test_timeout_error_retries(self, db):
        fs = self._make_fetch_service(db)
        mock = MagicMock(side_effect=TimeoutError("Timed out"))
        with patch.object(fs.arxiv_client, 'fetch_new_papers', mock):
            with patch('services.fetch_service.time.sleep'):
                with pytest.raises(TimeoutError):
                    fs.fetch_new_papers(['cs.AI'])
        assert mock.call_count == 3

    def test_non_transient_error_no_retry(self, db):
        fs = self._make_fetch_service(db)
        mock = MagicMock(side_effect=ValueError("Bad input"))
        with patch.object(fs.arxiv_client, 'fetch_new_papers', mock):
            with pytest.raises(ValueError, match="Bad input"):
                fs.fetch_new_papers(['cs.AI'])
        # Should NOT retry non-transient errors
        assert mock.call_count == 1

    def test_retry_succeeds_on_second_attempt(self, db):
        fs = self._make_fetch_service(db)
        mock = MagicMock(side_effect=[ConnectionError("fail"), []])
        with patch.object(fs.arxiv_client, 'fetch_new_papers', mock):
            with patch('services.fetch_service.time.sleep'):
                result = fs.fetch_new_papers(['cs.AI'])
        assert result['fetched'] == 0
        assert mock.call_count == 2

    def test_empty_categories_returns_empty(self, db):
        fs = self._make_fetch_service(db)
        with patch.object(fs.arxiv_client, 'fetch_new_papers', return_value=[]):
            result = fs.fetch_new_papers([])
        assert result['fetched'] == 0

    def test_fetch_by_arxiv_id_returns_none_on_error(self, db):
        fs = self._make_fetch_service(db)
        with patch.object(fs.arxiv_client, 'fetch_by_arxiv_id', side_effect=Exception("API down")):
            result = fs.fetch_by_arxiv_id('2301.12345')
        assert result is None

    def test_fetch_by_arxiv_id_returns_none_for_missing(self, db):
        fs = self._make_fetch_service(db)
        with patch.object(fs.arxiv_client, 'fetch_by_arxiv_id', return_value=None):
            result = fs.fetch_by_arxiv_id('nonexistent')
        assert result is None


# ── PDF service error paths ─────────────────────────────────────────

class TestPDFServiceErrors:
    def _make_paper(self):
        from models import Paper, Author
        return Paper(
            id=1,
            arxiv_id='2301.12345',
            title='Test Paper',
            pdf_url='http://example.com/test.pdf',
            publication_date='2023-01-15',
            authors=[Author(name='Test Author', normalized_name='author_t')],
        )

    def _make_pdf_service(self, db):
        from services.pdf_service import PDFService
        import tempfile
        config = ConfigService(db)
        data_dir = tempfile.mkdtemp()
        config.set_database_location(data_dir)
        ps = PaperService(db)
        return PDFService(config, ps)

    def test_download_returns_none_on_network_error(self, db):
        pdf_service = self._make_pdf_service(db)
        with patch('services.pdf_service.requests.get', side_effect=ConnectionError("No network")):
            result = pdf_service.download_pdf(self._make_paper(), permanent=False)
        assert result is None

    def test_download_returns_none_on_http_error(self, db):
        import requests
        pdf_service = self._make_pdf_service(db)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        # requests.get is used as a context manager — __enter__ must return
        # the same mock so raise_for_status fires inside the with block
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        with patch('services.pdf_service.requests.get', return_value=mock_response):
            result = pdf_service.download_pdf(self._make_paper(), permanent=False)
        assert result is None

    def test_delete_pdf_removes_file_and_clears_path(self, db, paper_service, sample_paper_data):
        import tempfile
        pdf_service = self._make_pdf_service(db)

        # Create a paper and a fake PDF file
        paper_id = paper_service.create_paper(sample_paper_data)
        pdf_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        pdf_file.write(b'%PDF-fake')
        pdf_file.close()

        # Set the local_pdf_path in database
        paper_service.update_pdf_path(paper_id, pdf_file.name)
        paper = paper_service.get_paper(paper_id)
        assert paper.local_pdf_path == pdf_file.name

        # Delete the PDF
        success = pdf_service.delete_pdf(paper)
        assert success is True
        assert not os.path.exists(pdf_file.name)

        # Verify path cleared in database
        paper = paper_service.get_paper(paper_id)
        assert paper.local_pdf_path is None

    def test_delete_pdf_no_local_path(self, db):
        pdf_service = self._make_pdf_service(db)
        paper = self._make_paper()
        paper.local_pdf_path = None
        assert pdf_service.delete_pdf(paper) is True

    def test_has_local_pdf_false_when_no_path(self, db):
        pdf_service = self._make_pdf_service(db)
        paper = self._make_paper()
        paper.local_pdf_path = None
        assert not pdf_service.has_local_pdf(paper)

    def test_has_local_pdf_false_when_file_missing(self, db):
        pdf_service = self._make_pdf_service(db)
        paper = self._make_paper()
        paper.local_pdf_path = '/nonexistent/path.pdf'
        assert not pdf_service.has_local_pdf(paper)


# ── Search input validation ─────────────────────────────────────────

class TestSearchInputValidation:
    """Verify that all kinds of malformed search input are handled safely."""

    @pytest.mark.parametrize("bad_input", [
        None,
        "",
        "   ",
        "a",  # single char
        "'" * 100,  # many quotes
        "DROP TABLE papers;--",  # SQL injection attempt
        "\x00\x01\x02",  # control chars
        "a" * 10000,  # very long input
    ])
    def test_search_handles_bad_input(self, paper_repo, sample_paper_data, bad_input):
        paper_repo.create(sample_paper_data)
        # Must not crash
        if bad_input is None:
            results = paper_repo.search_papers(search_text=None)
        else:
            results = paper_repo.search_papers(search_text=bad_input)
        assert isinstance(results, list)
