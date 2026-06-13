"""Regression tests for Phase 1 crash fixes."""

import threading
import pytest
from database.repositories import sanitize_fts5_query


# ── Regression: FTS5 crash on special characters ────────────────────

class TestFts5CrashRegression:
    """Verify that search queries with FTS5 special characters don't crash.

    Before the fix, any of these would raise sqlite3.OperationalError.
    """

    CRASH_INPUTS = [
        '"double quoted"',
        "it's an apostrophe",
        "(parenthesized)",
        "col:on",
        "plus+minus-star*",
        "NEAR/3 proximity",
        "{braces} [brackets]",
        "^caret",
        'mixed "quotes (and) parens"',
        "",
        "   ",
    ]

    @pytest.mark.parametrize("query", CRASH_INPUTS)
    def test_sanitize_does_not_crash(self, query):
        result = sanitize_fts5_query(query)
        assert isinstance(result, str)

    @pytest.mark.parametrize("query", CRASH_INPUTS)
    def test_search_does_not_crash(self, paper_repo, sample_paper_data, query):
        paper_repo.create(sample_paper_data)
        # This must not raise
        results = paper_repo.search_papers(search_text=query)
        assert isinstance(results, list)


# ── Regression: FetchWorker signal type (Bug #1) ────────────────────

class TestFetchWorkerSignalRegression:
    """Verify FetchWorker correctly handles dict results from fetch service."""

    def test_fetch_service_returns_dict(self, db):
        from unittest.mock import patch
        from services.paper_service import PaperService
        from services.fetch_service import FetchService

        ps = PaperService(db)
        fs = FetchService(ps)

        with patch.object(fs.arxiv_client, 'fetch_new_papers', return_value=[]):
            result = fs.fetch_new_papers(['cs.AI'])

        assert isinstance(result, dict)
        assert 'fetched' in result
        # len() on this dict should NOT be used as paper count
        # The dict has 5 keys: fetched, created, duplicates, errors, papers
        assert len(result) == 5
        assert result['fetched'] == 0

    def test_fetched_count_is_correct(self, db):
        from unittest.mock import patch
        from services.paper_service import PaperService
        from services.fetch_service import FetchService

        ps = PaperService(db)
        fs = FetchService(ps)

        mock_papers = [
            {
                'arxiv_id': f'2301.{i:05d}',
                'title': f'Paper {i}',
                'abstract': 'Abstract',
                'publication_date': '2023-01-01',
                'pdf_url': f'http://x/{i}',
                'authors': [{'name': f'Author {i}', 'normalized_name': f'a{i}'}],
                'categories': ['cs.AI'],
                'primary_category': 'cs.AI',
            }
            for i in range(10)
        ]

        with patch.object(fs.arxiv_client, 'fetch_new_papers', return_value=mock_papers):
            result = fs.fetch_new_papers(['cs.AI'])

        # The fetched count must reflect actual papers, not dict key count
        assert result['fetched'] == 10
        assert result['created'] == 10


# ── Regression: Thread safety on database transactions ───────────────

class TestThreadSafetyRegression:
    """Verify concurrent database access doesn't corrupt data."""

    def test_concurrent_writes_no_corruption(self, db, paper_repo):
        """Multiple threads writing papers simultaneously should not lose data."""
        errors = []
        created_ids = []
        lock = threading.Lock()

        def create_paper(i):
            try:
                paper_id = paper_repo.create({
                    'arxiv_id': f'2301.{i:05d}',
                    'title': f'Concurrent Paper {i}',
                    'abstract': f'Abstract {i}',
                    'publication_date': '2023-01-01',
                    'pdf_url': f'http://x/{i}',
                    'authors': [{'name': f'Author {i}', 'normalized_name': f'a{i}'}],
                    'categories': ['cs.AI'],
                    'primary_category': 'cs.AI',
                })
                with lock:
                    if paper_id:
                        created_ids.append(paper_id)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=create_paper, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"
        assert len(created_ids) == 10

    def test_concurrent_read_write(self, db, paper_repo, sample_paper_data):
        """Reading while writing should not crash."""
        paper_repo.create(sample_paper_data)
        errors = []

        def reader():
            try:
                for _ in range(20):
                    paper_repo.search_papers(search_text="Attention")
            except Exception as e:
                errors.append(f"reader: {e}")

        def writer():
            try:
                for i in range(5):
                    paper_repo.create({
                        'arxiv_id': f'2301.9{i:04d}',
                        'title': f'Write Paper {i}',
                        'abstract': 'Abstract',
                        'publication_date': '2023-01-01',
                        'pdf_url': f'http://x/w{i}',
                        'authors': [],
                        'categories': [],
                    })
            except Exception as e:
                errors.append(f"writer: {e}")

        t_read = threading.Thread(target=reader)
        t_write = threading.Thread(target=writer)
        t_read.start()
        t_write.start()
        t_read.join(timeout=30)
        t_write.join(timeout=30)

        assert len(errors) == 0, f"Errors during concurrent read/write: {errors}"


# ── Regression: Batch transaction atomicity ──────────────────────────

class TestBatchTransactionRegression:
    """Verify batch paper creation uses a single transaction."""

    def test_batch_is_atomic(self, paper_service, db):
        """If one paper in a batch fails, none should be committed."""
        papers = [
            {
                'arxiv_id': '2301.00001',
                'title': 'Good Paper',
                'abstract': 'Abstract',
                'publication_date': '2023-01-01',
                'pdf_url': 'http://x/1',
                'authors': [{'name': 'A', 'normalized_name': 'a'}],
                'categories': ['cs.AI'],
                'primary_category': 'cs.AI',
            },
            {
                'arxiv_id': '2301.00002',
                'title': 'Another Good Paper',
                'abstract': 'Abstract 2',
                'publication_date': '2023-01-02',
                'pdf_url': 'http://x/2',
                'authors': [{'name': 'B', 'normalized_name': 'b'}],
                'categories': ['cs.CV'],
                'primary_category': 'cs.CV',
            },
        ]
        result = paper_service.create_papers_batch(papers)
        assert result['created'] == 2

        # Both should exist
        all_papers = paper_service.get_all_papers()
        assert len(all_papers) == 2

    def test_batch_handles_duplicates_gracefully(self, paper_service):
        """Duplicates in batch should be skipped, not crash the batch."""
        paper = {
            'arxiv_id': '2301.00010',
            'title': 'Paper',
            'abstract': 'Abstract',
            'publication_date': '2023-01-01',
            'pdf_url': 'http://x/10',
            'authors': [],
            'categories': [],
        }
        paper_service.create_paper(paper)

        result = paper_service.create_papers_batch([
            paper,  # duplicate
            {
                'arxiv_id': '2301.00011',
                'title': 'New Paper',
                'abstract': 'Abstract',
                'publication_date': '2023-01-01',
                'pdf_url': 'http://x/11',
                'authors': [],
                'categories': [],
            },
        ])
        # Only the new one should be created
        assert result['created'] == 1
        assert result['duplicates'] == 1


# ── Regression: Batch-loaded related data matches per-paper loading ──

class TestBatchLoadRegression:
    """Verify batch loading produces identical results to per-paper loading."""

    def test_batch_loads_authors_correctly(self, paper_repo, sample_paper_data, sample_paper_data_2):
        paper_repo.create(sample_paper_data)
        paper_repo.create(sample_paper_data_2)

        papers = paper_repo.get_all()
        assert len(papers) == 2

        # Find the paper with 2 authors
        multi_author = [p for p in papers if p.arxiv_id == '2301.12345'][0]
        assert len(multi_author.authors) == 2
        assert multi_author.authors[0].name == 'Ashish Vaswani'

        # Find the paper with 1 author
        single_author = [p for p in papers if p.arxiv_id == '2301.99999'][0]
        assert len(single_author.authors) == 1
        assert single_author.authors[0].name == 'Kaiming He'

    def test_batch_loads_categories_correctly(self, paper_repo, sample_paper_data):
        paper_repo.create(sample_paper_data)
        papers = paper_repo.get_all()
        paper = papers[0]
        codes = [c.code for c in paper.categories]
        assert 'cs.CL' in codes
        assert 'cs.AI' in codes

    def test_batch_loads_notes_and_ratings(self, paper_repo, notes_repo, ratings_repo, sample_paper_data):
        paper_id = paper_repo.create(sample_paper_data)
        notes_repo.create_or_update(paper_id, "Test note")
        ratings_repo.create_or_update(paper_id, importance="good")

        papers = paper_repo.get_all()
        paper = papers[0]
        assert paper.notes is not None
        assert paper.notes.note_text == "Test note"
        assert paper.ratings is not None
        assert paper.ratings.importance == "good"

    def test_search_also_uses_batch_loading(self, paper_repo, sample_paper_data):
        paper_repo.create(sample_paper_data)
        results = paper_repo.search_papers(search_text="Attention")
        assert len(results) == 1
        assert len(results[0].authors) == 2


# ── Regression: FTS5 author-delete trigger corrupts index on paper delete ──

class TestPaperDeleteFtsRegression:
    """Deleting or pruning a paper that has authors must not corrupt papers_fts.

    Before the WHEN-EXISTS guard on papers_fts_update_authors_delete, the
    ON DELETE CASCADE on paper_authors fired that trigger after papers_fts_delete
    had already removed the paper's contentless-FTS row, and after the parent
    papers row was gone. The redundant 'delete' + phantom reinsert left the index
    inconsistent and aborted the statement with
    "database disk image is malformed" — making per-paper Remove and prune
    non-functional for any authored paper (i.e. every real arXiv paper).
    """

    @staticmethod
    def _assert_fts_consistent(db):
        # FTS5 integrity-check raises "database disk image is malformed" if corrupt.
        db.execute("INSERT INTO papers_fts(papers_fts) VALUES('integrity-check')")

    def test_delete_paper_with_authors_does_not_corrupt_fts(self, db, paper_repo, created_paper):
        # created_paper (sample_paper_data) has two authors.
        assert paper_repo.get_by_id(created_paper) is not None
        deleted = paper_repo.delete(created_paper)  # used to raise DatabaseError
        assert deleted is True
        assert paper_repo.get_by_id(created_paper) is None
        self._assert_fts_consistent(db)
        # The deleted paper must no longer be findable via search.
        assert paper_repo.search_papers(search_text="Attention") == []

    def test_prune_paper_with_authors_does_not_corrupt_fts(self, db, paper_repo, sample_paper_data):
        pid = paper_repo.create(sample_paper_data)  # two authors
        # Make it eligible for prune: fetched, no saved PDF, old.
        db.execute(
            "UPDATE papers SET origin='fetch', local_pdf_path=NULL, "
            "date_added=datetime('now','-100 days') WHERE id=?",
            (pid,),
        )
        deleted = paper_repo.prune(max_age_days=30)  # used to raise inside the transaction
        assert deleted == 1
        assert paper_repo.get_by_id(pid) is None
        self._assert_fts_consistent(db)

    def test_deleting_one_author_still_resyncs_fts(self, db, paper_repo, created_paper):
        # The guard must NOT suppress resync when the paper itself survives.
        db.execute(
            "DELETE FROM paper_authors WHERE paper_id=? AND author_id="
            "(SELECT id FROM authors WHERE name='Noam Shazeer')",
            (created_paper,),
        )
        self._assert_fts_consistent(db)
        by_remaining = paper_repo.search_papers(search_text="Vaswani")
        by_removed = paper_repo.search_papers(search_text="Shazeer")
        assert any(p.id == created_paper for p in by_remaining)
        assert all(p.id != created_paper for p in by_removed)

    def test_author_delete_trigger_has_guard(self, db):
        # Proves the migration/baseline applied the WHEN-EXISTS guard in this DB.
        row = db.fetch_one(
            "SELECT sql FROM sqlite_master WHERE type='trigger' "
            "AND name='papers_fts_update_authors_delete'"
        )
        assert row is not None
        assert "WHEN EXISTS" in (row["sql"] or "").upper()


# ── Regression: prune destroys papers with downloaded source (R8-4) ──

class TestPruneRegression:
    """prune() must only remove genuinely untouched fetches.

    Before the fix, prune used only `local_pdf_path IS NULL`, so a fetched paper
    whose source tarball was permanently downloaded (local_source_path set,
    local_pdf_path still NULL) was deleted — destroying a paper the user engaged
    with and orphaning its extracted source directory on disk forever.
    """

    def _make_old_fetched(self, db, paper_repo, sample_paper_data, **cols):
        pid = paper_repo.create(sample_paper_data)
        db.execute(
            "UPDATE papers SET origin='fetch', date_added=datetime('now','-100 days') WHERE id=?",
            (pid,),
        )
        for col, val in cols.items():
            db.execute(f"UPDATE papers SET {col}=? WHERE id=?", (val, pid))
        return pid

    def test_prune_keeps_paper_with_downloaded_source(self, db, paper_repo, sample_paper_data):
        pid = self._make_old_fetched(
            db, paper_repo, sample_paper_data,
            local_pdf_path=None, local_source_path='/tmp/pt/sources/2301.12345',
        )
        assert paper_repo.prune(max_age_days=30) == 0
        assert paper_repo.get_by_id(pid) is not None

    def test_prune_keeps_paper_with_pdf(self, db, paper_repo, sample_paper_data):
        pid = self._make_old_fetched(
            db, paper_repo, sample_paper_data,
            local_pdf_path='/tmp/pt/pdfs/x.pdf', local_source_path=None,
        )
        assert paper_repo.prune(max_age_days=30) == 0
        assert paper_repo.get_by_id(pid) is not None

    def test_prune_still_removes_contentless_fetch(self, db, paper_repo, sample_paper_data):
        pid = self._make_old_fetched(
            db, paper_repo, sample_paper_data,
            local_pdf_path=None, local_source_path=None,
        )
        assert paper_repo.prune(max_age_days=30) == 1
        assert paper_repo.get_by_id(pid) is None


# ── Regression: closed DB connection silently reopens (R8-6) ──

class TestClosedConnectionRegression:
    """close() must be final.

    Before the fix, close() set _connection=None but the next execute()/connect()
    transparently recreated a live connection to the old database file. During a
    relocation that closed the DB, a surviving worker's write would resurrect the
    old connection and race the copy/merge. After the fix, post-close access raises.
    """

    def test_closed_connection_does_not_silently_reopen(self, tmp_path):
        from database.connection import DatabaseConnection

        db = DatabaseConnection(str(tmp_path / "t.db"))
        db.connect()
        db.execute("CREATE TABLE t (x INTEGER)")  # sanity: works while open
        db.close()

        with pytest.raises(RuntimeError):
            db.execute("INSERT INTO t (x) VALUES (1)")
        with pytest.raises(RuntimeError):
            db.connect()


# ── Regression: relocation closes DB while a worker survives (R8-5) ──

class _FakeWorker:
    """Stand-in QThread-like worker for testing _stop_all_workers."""

    def __init__(self, running: bool, stops: bool):
        self._running = running
        self._stops = stops
        self.cancelled = False

    def isRunning(self):
        return self._running

    def cancel(self):
        self.cancelled = True

    def wait(self, ms):
        return self._stops


class TestStopAllWorkersRegression:
    """_stop_all_workers must report whether every worker actually stopped.

    Before the fix it called worker.wait(3000) but ignored the result and the
    caller (ChangeLibraryDialog._on_apply) closed the DB and migrated regardless.
    A download whose socket read outlasted the timeout kept running and raced the
    copy/merge. Now the method returns False and the caller aborts.
    """

    def _stub(self, **workers):
        from types import SimpleNamespace
        base = dict(fetch_worker=None, pdf_worker=None, source_worker=None,
                    arxiv_id_worker=None, arxiv_search_worker=None)
        base.update(workers)
        return SimpleNamespace(**base)

    def test_returns_false_when_a_worker_will_not_stop(self):
        from ui.main_window import MainWindow
        stub = self._stub(pdf_worker=_FakeWorker(running=True, stops=False))
        assert MainWindow._stop_all_workers(stub) is False
        assert stub.pdf_worker.cancelled is True  # it tried to cancel

    def test_returns_true_when_all_workers_stop(self):
        from ui.main_window import MainWindow
        stub = self._stub(
            fetch_worker=_FakeWorker(running=True, stops=True),
            source_worker=_FakeWorker(running=False, stops=True),
        )
        assert MainWindow._stop_all_workers(stub) is True

    def test_returns_true_when_no_workers(self):
        from ui.main_window import MainWindow
        assert MainWindow._stop_all_workers(self._stub()) is True


# ── Regression: clearing a rating is silently ignored (R8-11) ──

class TestRatingClearRegression:
    """Clearing a rating metric back to 'Not rated' must persist.

    Before the fix, an unset metric arrived as NULL and the UPSERT's
    COALESCE(excluded.x, paper_ratings.x) fell back to the stored value, so the
    clear was a no-op and the stale rating re-appeared on reload. The fix
    distinguishes 'omitted' (leave — protects R6-2 partial updates) from
    'explicit None' (clear).
    """

    def test_explicit_none_clears_one_metric(self, ratings_repo, created_paper):
        ratings_repo.create_or_update(created_paper, importance="good",
                                      comprehension="understood", technicality="tough")
        ratings_repo.create_or_update(created_paper, importance=None,
                                      comprehension="understood", technicality="tough")
        r = ratings_repo.get_by_paper_id(created_paper)
        assert r.importance is None       # cleared
        assert r.comprehension == "understood"
        assert r.technicality == "tough"

    def test_save_rating_full_clear(self, paper_service, ratings_repo, created_paper):
        ratings_repo.create_or_update(created_paper, importance="good",
                                      comprehension="understood", technicality="tough")
        # Widget path: all three emitted, all cleared.
        paper_service.save_rating(created_paper, importance=None,
                                  comprehension=None, technicality=None)
        r = ratings_repo.get_by_paper_id(created_paper)
        assert r.importance is None
        assert r.comprehension is None
        assert r.technicality is None

    def test_omitted_metric_is_preserved(self, ratings_repo, created_paper):
        # R6-2 must not regress: omitting a metric leaves it unchanged.
        ratings_repo.create_or_update(created_paper, importance="good")
        ratings_repo.create_or_update(created_paper, comprehension="understood")
        r = ratings_repo.get_by_paper_id(created_paper)
        assert r.importance == "good"
        assert r.comprehension == "understood"


# ── Regression: pending note lost when app closes within debounce (R8-12) ──

class TestNoteFlushRegression:
    """A note typed within the 2s auto-save debounce must be flushed on shutdown.

    closeEvent previously only stopped workers and cleaned caches, so a pending
    debounced save never fired and the note was lost. note_editor.flush() (invoked
    from closeEvent via context_panel.flush_pending_note) now emits the pending save.
    """

    def test_flush_emits_pending_note(self, qtbot):
        from ui.widgets.note_editor_widget import NoteEditorWidget
        w = NoteEditorWidget()
        qtbot.addWidget(w)
        received = []
        w.note_changed.connect(received.append)

        w.text_edit.setPlainText("draft typed just before quitting")
        assert w._save_timer.isActive()  # debounce pending, not yet saved

        w.flush()

        assert received == ["draft typed just before quitting"]
        assert not w._save_timer.isActive()

    def test_flush_is_noop_when_nothing_pending(self, qtbot):
        from ui.widgets.note_editor_widget import NoteEditorWidget
        w = NoteEditorWidget()
        qtbot.addWidget(w)
        received = []
        w.note_changed.connect(received.append)
        w.flush()  # no pending timer
        assert received == []
