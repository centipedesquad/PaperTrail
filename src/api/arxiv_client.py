"""
arXiv API client wrapper.
Uses the official arxiv Python package.
"""

import re
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import arxiv

logger = logging.getLogger(__name__)


class ArxivClient:
    """Wrapper around arxiv package for fetching papers."""

    def __init__(self):
        """Initialize arXiv client."""
        # The arxiv package handles rate limiting automatically
        pass

    def fetch_new_papers(self, categories: List[str], max_results: int = 50) -> List[dict]:
        """
        Fetch recent papers from specified categories.
        Only fetches papers where the category is the PRIMARY category,
        matching the behavior of arXiv.org/list/category/new "New submissions".

        Args:
            categories: List of arXiv category codes (e.g., ['hep-th', 'gr-qc'])
            max_results: Maximum number of papers to fetch per category

        Returns:
            List of paper dictionaries
        """
        papers = []
        failed_categories = []

        for category in categories:
            try:
                logger.info(f"Fetching new papers from category: {category}")

                search = arxiv.Search(
                    query=f"cat:{category}",
                    max_results=max_results * 2,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending
                )

                category_papers = []
                for result in search.results():
                    if result.primary_category == category:
                        paper = self._convert_result_to_dict(result)
                        category_papers.append(paper)
                        if len(category_papers) >= max_results:
                            break

                logger.info(f"Fetched {len(category_papers)} papers from {category} (primary category only)")
                papers.extend(category_papers)

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Failed to fetch papers from {category}: {error_msg}")
                if "429" in error_msg:
                    raise Exception("arXiv API rate limit reached. Please wait 3-5 minutes before trying again.")
                failed_categories.append((category, e))

        if failed_categories and not papers:
            raise failed_categories[-1][1]

        logger.info(f"Fetched {len(papers)} papers total")
        return papers

    def fetch_recent_papers(
        self,
        categories: List[str],
        days: int = 7,
        max_results: int = 50
    ) -> List[dict]:
        """
        Fetch papers from the last N days from specified categories.

        Args:
            categories: List of arXiv category codes
            days: Number of days to look back
            max_results: Maximum number of papers to fetch per category

        Returns:
            List of paper dictionaries
        """
        papers = []
        failed_categories = []
        cutoff_date = datetime.now() - timedelta(days=days)

        for category in categories:
            try:
                logger.info(f"Fetching recent papers from category: {category}")

                search = arxiv.Search(
                    query=f"cat:{category}",
                    max_results=max_results * 2,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending
                )

                cat_count = 0
                for result in search.results():
                    if result.published.replace(tzinfo=None) >= cutoff_date:
                        if result.primary_category == category:
                            paper = self._convert_result_to_dict(result)
                            papers.append(paper)
                            cat_count += 1
                            if cat_count >= max_results:
                                break

            except Exception as e:
                logger.warning(f"Failed to fetch papers from {category}: {e}")
                failed_categories.append((category, e))

        if failed_categories and not papers:
            raise failed_categories[-1][1]

        logger.info(f"Fetched {len(papers)} recent papers")
        return papers

    def fetch_by_arxiv_id(self, arxiv_id: str) -> Optional[dict]:
        """
        Fetch a specific paper by arXiv ID.

        Args:
            arxiv_id: arXiv ID (e.g., "2301.12345")

        Returns:
            Paper dictionary or None if not found
        """
        logger.info(f"Fetching paper: {arxiv_id}")
        search = arxiv.Search(id_list=[arxiv_id])
        try:
            result = next(search.results())
            return self._convert_result_to_dict(result)
        except StopIteration:
            logger.warning(f"Paper not found: {arxiv_id}")
            return None
        # Other exceptions (network, timeout) propagate to caller

    def search_papers(
        self,
        query: str,
        max_results: int = 50,
        sort_by: str = "relevance"
    ) -> List[dict]:
        """
        Search for papers by query string.

        Args:
            query: Search query (supports arXiv query syntax)
            max_results: Maximum number of results
            sort_by: Sort criterion ('relevance', 'lastUpdatedDate', 'submittedDate')

        Returns:
            List of paper dictionaries
        """
        logger.info(f"Searching papers: {query}")

        # Map sort criterion
        sort_map = {
            'relevance': arxiv.SortCriterion.Relevance,
            'lastUpdatedDate': arxiv.SortCriterion.LastUpdatedDate,
            'submittedDate': arxiv.SortCriterion.SubmittedDate,
        }
        sort_criterion = sort_map.get(sort_by, arxiv.SortCriterion.Relevance)

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=sort_criterion,
            sort_order=arxiv.SortOrder.Descending
        )

        papers = []
        for result in search.results():
            paper = self._convert_result_to_dict(result)
            papers.append(paper)

        logger.info(f"Found {len(papers)} papers")
        return papers

    def _convert_result_to_dict(self, result: arxiv.Result) -> dict:
        """
        Convert arxiv.Result to dictionary format.

        Args:
            result: arxiv.Result object

        Returns:
            Paper dictionary
        """
        # Extract arXiv ID from entry URL, preserving legacy prefixes (e.g. hep-th/9901001)
        raw_id = result.entry_id.rsplit('/abs/', 1)[-1] if '/abs/' in result.entry_id else result.entry_id.split('/')[-1]
        # Split version suffix safely using regex (handles 'v' in legacy prefixes like solv-int/)
        match = re.match(r'^(.+?)(?:v(\d+))?$', raw_id)
        base_id = match.group(1)
        version = match.group(2)

        # Extract authors
        authors = [
            {
                'name': author.name,
                'normalized_name': self._normalize_author_name(author.name)
            }
            for author in result.authors
        ]

        # Extract categories
        categories = [cat for cat in result.categories]

        return {
            'arxiv_id': base_id,
            'version': version,
            'title': result.title,
            'abstract': result.summary,
            'publication_date': result.published.strftime('%Y-%m-%d'),
            'pdf_url': result.pdf_url,
            'comment': result.comment,
            'journal_ref': result.journal_ref,
            'doi': result.doi,
            'authors': authors,
            'categories': categories,
            'primary_category': result.primary_category
        }

    def _normalize_author_name(self, name: str) -> str:
        """
        Normalize author name for matching.

        Args:
            name: Author name

        Returns:
            Normalized name (lowercase, no punctuation)
        """
        # Remove punctuation and convert to lowercase
        normalized = name.lower()
        for char in '.,;:-':
            normalized = normalized.replace(char, '')
        return normalized.strip()
