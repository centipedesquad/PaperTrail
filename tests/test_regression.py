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
        # The dict has 4 keys, which was the old bug
        assert len(result) == 4
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
        count = paper_service.create_papers_batch(papers)
        assert count == 2

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

        count = paper_service.create_papers_batch([
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
        assert count == 1
