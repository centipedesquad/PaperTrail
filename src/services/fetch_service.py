"""
Fetch service for retrieving papers from arXiv.
Orchestrates between arXiv API and database.
"""

import logging
from typing import List, Callable, Optional
from api.arxiv_client import ArxivClient
from services.paper_service import PaperService

logger = logging.getLogger(__name__)


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
        try:
            if progress_callback:
                progress_callback(0, "Starting fetch...")

            logger.info(f"Fetching new papers from categories: {categories}")

            # Fetch from arXiv
            if progress_callback:
                progress_callback(20, "Fetching from arXiv...")

            papers_data = self.arxiv_client.fetch_new_papers(categories, max_results)

            if progress_callback:
                progress_callback(60, f"Fetched {len(papers_data)} papers")

            # Save to database
            if progress_callback:
                progress_callback(70, "Saving to database...")

            initial_count = len(self.paper_service.get_all_papers(limit=1))
            created_count = self.paper_service.create_papers_batch(papers_data)
            final_count = len(self.paper_service.get_all_papers(limit=1))

            duplicates = len(papers_data) - created_count

            if progress_callback:
                progress_callback(100, "Complete")

            result = {
                'fetched': len(papers_data),
                'created': created_count,
                'duplicates': duplicates,
                'papers': papers_data
            }

            logger.info(f"Fetch complete: {result}")
            return result

        except Exception as e:
            logger.error(f"Fetch failed: {e}")
            raise

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
        try:
            if progress_callback:
                progress_callback(0, "Starting fetch...")

            logger.info(f"Fetching recent papers from categories: {categories}")

            # Fetch from arXiv
            if progress_callback:
                progress_callback(20, f"Fetching papers from last {days} days...")

            papers_data = self.arxiv_client.fetch_recent_papers(
                categories, days, max_results
            )

            if progress_callback:
                progress_callback(60, f"Fetched {len(papers_data)} papers")

            # Save to database
            if progress_callback:
                progress_callback(70, "Saving to database...")

            created_count = self.paper_service.create_papers_batch(papers_data)
            duplicates = len(papers_data) - created_count

            if progress_callback:
                progress_callback(100, "Complete")

            result = {
                'fetched': len(papers_data),
                'created': created_count,
                'duplicates': duplicates,
                'papers': papers_data
            }

            logger.info(f"Fetch complete: {result}")
            return result

        except Exception as e:
            logger.error(f"Fetch failed: {e}")
            raise

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
                # Save to database
                paper_id = self.paper_service.create_paper(paper_data)
                if paper_id:
                    logger.info(f"Fetched and saved paper: {arxiv_id}")
                    return paper_data
            return None

        except Exception as e:
            logger.error(f"Failed to fetch paper {arxiv_id}: {e}")
            return None
