"""
Fetch service for retrieving papers from arXiv.
Orchestrates between arXiv API and database.
"""

import time
import logging
from typing import List, Callable, Optional
from api.arxiv_client import ArxivClient
from services.paper_service import PaperService

logger = logging.getLogger(__name__)

# Transient errors worth retrying
_TRANSIENT_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)


class FetchService:
    """Service for fetching papers from arXiv."""

    def __init__(self, paper_service: PaperService):
        """
        Initialize fetch service.

        Args:
            paper_service: Paper service instance
        """
        self.paper_service = paper_service
        self.arxiv_client = ArxivClient()

    def fetch_new_papers(
        self,
        categories: List[str],
        max_results: int = 50,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> dict:
        """
        Fetch new papers from arXiv.

        Args:
            categories: List of category codes to fetch from
            max_results: Maximum results per category
            progress_callback: Optional callback for progress updates (percentage, message)

        Returns:
            Dictionary with results: {
                'fetched': int,
                'created': int,
                'duplicates': int,
                'papers': List[dict]
            }
        """
        if progress_callback:
            progress_callback(0, "Starting fetch...")

        logger.info(f"Fetching new papers from categories: {categories}")

        # Fetch from arXiv with retry for transient errors
        if progress_callback:
            progress_callback(20, "Fetching from arXiv...")

        papers_data = self._fetch_with_retry(
            lambda: self.arxiv_client.fetch_new_papers(categories, max_results)
        )

        if progress_callback:
            progress_callback(60, f"Fetched {len(papers_data)} papers")

        # Save to database
        if progress_callback:
            progress_callback(70, "Saving to database...")

        batch_result = self.paper_service.create_papers_batch(papers_data)

        if progress_callback:
            progress_callback(100, "Complete")

        result = {
            'fetched': len(papers_data),
            'created': batch_result['created'],
            'duplicates': batch_result['duplicates'],
            'errors': batch_result['errors'],
            'papers': papers_data
        }

        logger.info(f"Fetch complete: {result}")
        return result

    def fetch_recent_papers(
        self,
        categories: List[str],
        days: int = 7,
        max_results: int = 50,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> dict:
        """
        Fetch recent papers from arXiv.

        Args:
            categories: List of category codes to fetch from
            days: Number of days to look back
            max_results: Maximum results per category
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with results
        """
        if progress_callback:
            progress_callback(0, "Starting fetch...")

        logger.info(f"Fetching recent papers from categories: {categories}")

        # Fetch from arXiv with retry for transient errors
        if progress_callback:
            progress_callback(20, f"Fetching papers from last {days} days...")

        papers_data = self._fetch_with_retry(
            lambda: self.arxiv_client.fetch_recent_papers(categories, days, max_results)
        )

        if progress_callback:
            progress_callback(60, f"Fetched {len(papers_data)} papers")

        # Save to database
        if progress_callback:
            progress_callback(70, "Saving to database...")

        batch_result = self.paper_service.create_papers_batch(papers_data)

        if progress_callback:
            progress_callback(100, "Complete")

        result = {
            'fetched': len(papers_data),
            'created': batch_result['created'],
            'duplicates': batch_result['duplicates'],
            'errors': batch_result['errors'],
            'papers': papers_data
        }

        logger.info(f"Fetch complete: {result}")
        return result

    def fetch_by_arxiv_id(self, arxiv_id: str) -> Optional[dict]:
        """
        Fetch a specific paper by arXiv ID.

        Args:
            arxiv_id: arXiv ID

        Returns:
            Paper data dictionary or None
        """
        try:
            paper_data = self.arxiv_client.fetch_by_arxiv_id(arxiv_id)
            if paper_data:
                # Save to database (manual lookup = search origin)
                paper_data['origin'] = 'search'
                paper_id = self.paper_service.create_paper(paper_data)
                if paper_id:
                    logger.info(f"Fetched and saved paper: {arxiv_id}")
                    return paper_data
            return None

        except Exception as e:
            logger.error(f"Failed to fetch paper {arxiv_id}: {e}")
            return None

    def fetch_by_arxiv_id_preview(self, arxiv_id: str) -> Optional[dict]:
        """
        Fetch paper metadata from arXiv by ID WITHOUT saving to database.
        Used for preview-then-import flow.

        Returns:
            Paper data dictionary or None

        Raises:
            Exception: On network/API errors (so worker error signal fires)
        """
        return self.arxiv_client.fetch_by_arxiv_id(arxiv_id)

    def search_arxiv(self, query: str, max_results: int = 50) -> list:
        """
        Search arXiv for papers matching a query string.
        Distinct from PaperService.search_papers() which searches local DB.

        Args:
            query: Search query (supports arXiv query syntax)
            max_results: Maximum number of results

        Returns:
            List of paper data dictionaries

        Raises:
            Exception: On network/API errors (so worker error signal fires)
        """
        results = self._fetch_with_retry(
            lambda: self.arxiv_client.search_papers(query, max_results=max_results)
        )
        logger.info(f"arXiv search for '{query}': {len(results)} results")
        return results

    def import_papers(self, paper_data_list: list) -> dict:
        """
        Import multiple papers into the database.

        Returns:
            dict with 'imported', 'duplicates', and 'errors' counts
        """
        imported = 0
        duplicates = 0
        errors = 0
        for paper_data in paper_data_list:
            try:
                paper_id = self.paper_service.create_paper(paper_data)
                if paper_id:
                    imported += 1
                else:
                    duplicates += 1
            except Exception as e:
                errors += 1
                logger.error(f"Failed to import {paper_data.get('arxiv_id')}: {e}")
        return {'imported': imported, 'duplicates': duplicates, 'errors': errors}

    def _fetch_with_retry(self, fetch_func, max_retries: int = 3, base_delay: float = 1.0):
        """Call fetch_func with exponential backoff retry for transient errors.

        Retries on network errors (ConnectionError, TimeoutError, OSError).
        Non-transient errors are raised immediately.
        """
        last_exception = None
        for attempt in range(max_retries):
            try:
                return fetch_func()
            except _TRANSIENT_EXCEPTIONS as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"Transient error (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Fetch failed after {max_retries} attempts: {e}")
            except Exception as e:
                # Non-transient error — don't retry
                logger.error(f"Fetch failed (non-transient): {e}")
                raise
        raise last_exception
