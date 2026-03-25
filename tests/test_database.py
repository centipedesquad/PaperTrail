"""Tests for database connection and repository layers."""

import threading
import pytest
from database.connection import DatabaseConnection
from database.repositories import (
    PaperRepository, NotesRepository, RatingsRepository, sanitize_fts5_query
)


# ── sanitize_fts5_query ────────────────────────────────────────────

class TestSanitizeFts5Query:
    def test_normal_input(self):
        assert sanitize_fts5_query("hello world") == '"hello" "world"'

    def test_empty_string(self):
        assert sanitize_fts5_query("") == ""

    def test_whitespace_only(self):
        assert sanitize_fts5_query("   ") == ""

    def test_none(self):
        assert sanitize_fts5_query(None) == ""

    def test_strips_quotes(self):
        result = sanitize_fts5_query('test "quoted" value')
        assert '"' not in result.replace('"test"', '').replace('"quoted"', '').replace('"value"', '')

    def test_strips_parentheses(self):
        result = sanitize_fts5_query("(test) OR (value)")
        assert "(" not in result
        assert ")" not in result

    def test_strips_boolean_treated_as_tokens(self):
        result = sanitize_fts5_query("machine AND learning")
        assert result == '"machine" "AND" "learning"'

    def test_strips_special_chars(self):
        result = sanitize_fts5_query("test+value-other*wild")
        assert "+" not in result
        assert "*" not in result

    def test_single_word(self):
        assert sanitize_fts5_query("quantum") == '"quantum"'


# ── DatabaseConnection ──────────────────────────────────────────────

class TestDatabaseConnection:
    def test_connect(self, db):
        conn = db.connect()
        assert conn is not None

    def test_double_connect_returns_same(self, db):
        conn1 = db.connect()
        conn2 = db.connect()
        assert conn1 is conn2

    def test_execute_and_fetch(self, db):
        rows = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [r['name'] for r in rows]
        assert 'papers' in table_names
        assert 'authors' in table_names
        assert 'categories' in table_names

    def test_transaction_commit(self, db):
        with db.transaction():
            db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                ("test_key", "test_value")
            )
        row = db.fetch_one("SELECT value FROM settings WHERE key = ?", ("test_key",))
        assert row['value'] == "test_value"

    def test_transaction_rollback_on_error(self, db):
        with pytest.raises(Exception):
            with db.transaction():
                db.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)",
                    ("rollback_key", "rollback_value")
                )
                raise ValueError("Intentional error")

        row = db.fetch_one("SELECT value FROM settings WHERE key = ?", ("rollback_key",))
        assert row is None

    def test_has_rlock(self, db):
        assert hasattr(db, '_lock')
        assert isinstance(db._lock, type(threading.RLock()))

    def test_close(self, db):
        db.close()
        assert db._connection is None


# ── PaperRepository ─────────────────────────────────────────────────

class TestPaperRepository:
    def test_create_paper(self, paper_repo, sample_paper_data):
        paper_id = paper_repo.create(sample_paper_data)
        assert paper_id is not None
        assert isinstance(paper_id, int)

    def test_create_duplicate_returns_none(self, paper_repo, sample_paper_data):
        paper_repo.create(sample_paper_data)
        duplicate_id = paper_repo.create(sample_paper_data)
        assert duplicate_id is None

    def test_get_by_id(self, paper_repo, sample_paper_data):
        paper_id = paper_repo.create(sample_paper_data)
        paper = paper_repo.get_by_id(paper_id)
        assert paper is not None
        assert paper.arxiv_id == '2301.12345'
        assert paper.title == 'Attention Is All You Need'

    def test_get_by_id_nonexistent(self, paper_repo):
        paper = paper_repo.get_by_id(99999)
        assert paper is None

    def test_get_by_arxiv_id(self, paper_repo, sample_paper_data):
        paper_repo.create(sample_paper_data)
        paper = paper_repo.get_by_arxiv_id('2301.12345')
        assert paper is not None
        assert paper.title == 'Attention Is All You Need'

    def test_get_by_arxiv_id_nonexistent(self, paper_repo):
        paper = paper_repo.get_by_arxiv_id('nonexistent')
        assert paper is None

    def test_creates_authors(self, paper_repo, sample_paper_data):
        paper_id = paper_repo.create(sample_paper_data)
        paper = paper_repo.get_by_id(paper_id)
        assert len(paper.authors) == 2
        assert paper.authors[0].name == 'Ashish Vaswani'
        assert paper.authors[1].name == 'Noam Shazeer'

    def test_creates_categories(self, paper_repo, sample_paper_data):
        paper_id = paper_repo.create(sample_paper_data)
        paper = paper_repo.get_by_id(paper_id)
        category_codes = [c.code for c in paper.categories]
        assert 'cs.CL' in category_codes
        assert 'cs.AI' in category_codes

    def test_get_all(self, paper_repo, sample_paper_data, sample_paper_data_2):
        paper_repo.create(sample_paper_data)
        paper_repo.create(sample_paper_data_2)
        papers = paper_repo.get_all()
        assert len(papers) == 2

    def test_get_all_with_limit(self, paper_repo, sample_paper_data, sample_paper_data_2):
        paper_repo.create(sample_paper_data)
        paper_repo.create(sample_paper_data_2)
        papers = paper_repo.get_all(limit=1)
        assert len(papers) == 1

    def test_search_papers_by_title(self, paper_repo, sample_paper_data):
        paper_repo.create(sample_paper_data)
        results = paper_repo.search_papers(search_text="Attention")
        assert len(results) >= 1
        assert results[0].title == 'Attention Is All You Need'

    def test_search_papers_no_results(self, paper_repo, sample_paper_data):
        paper_repo.create(sample_paper_data)
        results = paper_repo.search_papers(search_text="nonexistent_xyz_query")
        assert len(results) == 0

    def test_search_papers_special_chars_no_crash(self, paper_repo, sample_paper_data):
        paper_repo.create(sample_paper_data)
        # These would crash without sanitization
        paper_repo.search_papers(search_text='test AND "quoted"')
        paper_repo.search_papers(search_text="(grouped) OR value")
        paper_repo.search_papers(search_text="NEAR/3 proximity")
        paper_repo.search_papers(search_text="col:umn")

    def test_search_papers_empty_query(self, paper_repo, sample_paper_data):
        paper_repo.create(sample_paper_data)
        results = paper_repo.search_papers(search_text="")
        # Empty search returns all papers (no FTS filter applied)
        assert len(results) >= 1

    def test_create_inner_returns_none_for_duplicate(self, paper_repo, sample_paper_data, db):
        paper_repo.create(sample_paper_data)
        with db.transaction():
            result = paper_repo._create_inner(sample_paper_data)
        assert result is None


# ── NotesRepository ─────────────────────────────────────────────────

class TestNotesRepository:
    def test_create_note(self, notes_repo, created_paper):
        note_id = notes_repo.create_or_update(created_paper, "Great paper!")
        assert note_id is not None

    def test_get_note(self, notes_repo, created_paper):
        notes_repo.create_or_update(created_paper, "Great paper!")
        note = notes_repo.get_by_paper_id(created_paper)
        assert note is not None
        assert note.note_text == "Great paper!"

    def test_update_note(self, notes_repo, created_paper):
        notes_repo.create_or_update(created_paper, "Great paper!")
        notes_repo.create_or_update(created_paper, "Updated note")
        note = notes_repo.get_by_paper_id(created_paper)
        assert note.note_text == "Updated note"

    def test_get_nonexistent_note(self, notes_repo):
        note = notes_repo.get_by_paper_id(99999)
        assert note is None

    def test_delete_note(self, notes_repo, created_paper):
        notes_repo.create_or_update(created_paper, "To be deleted")
        notes_repo.delete(created_paper)
        note = notes_repo.get_by_paper_id(created_paper)
        assert note is None


# ── RatingsRepository ───────────────────────────────────────────────

class TestRatingsRepository:
    def test_create_rating(self, ratings_repo, created_paper):
        rating_id = ratings_repo.create_or_update(
            created_paper, importance="good", comprehension="understood"
        )
        assert rating_id is not None

    def test_get_rating(self, ratings_repo, created_paper):
        ratings_repo.create_or_update(
            created_paper, importance="good", comprehension="understood"
        )
        rating = ratings_repo.get_by_paper_id(created_paper)
        assert rating is not None
        assert rating.importance == "good"
        assert rating.comprehension == "understood"

    def test_update_rating_preserves_unset_fields(self, ratings_repo, created_paper):
        ratings_repo.create_or_update(created_paper, importance="good")
        ratings_repo.create_or_update(created_paper, comprehension="understood")
        rating = ratings_repo.get_by_paper_id(created_paper)
        assert rating.importance == "good"
        assert rating.comprehension == "understood"

    def test_get_nonexistent_rating(self, ratings_repo):
        rating = ratings_repo.get_by_paper_id(99999)
        assert rating is None

    def test_delete_rating(self, ratings_repo, created_paper):
        ratings_repo.create_or_update(created_paper, importance="good")
        ratings_repo.delete(created_paper)
        rating = ratings_repo.get_by_paper_id(created_paper)
        assert rating is None
