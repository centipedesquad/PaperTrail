"""
arXiv API client wrapper.
Uses the official arxiv Python package.
"""

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
        Fetch new papers submitted today from specified categories.

        Args:
            categories: List of arXiv category codes (e.g., ['hep-th', 'gr-qc'])
            max_results: Maximum number of papers to fetch per category

        Returns:
            List of paper dictionaries
        """
        papers = []
        today = datetime.now().date()

        for category in categories:
            try:
                logger.info(f"Fetching new papers from category: {category}")

                # Query for papers in this category, sorted by submission date
                # Fetch more than needed to ensure we get all of today's papers
                search = arxiv.Search(
                    query=f"cat:{category}",
                    max_results=max_results * 3,  # Fetch 3x to ensure we get all of today's papers
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending
                )

                category_papers = []
                for result in search.results():
                    # Only include papers published today
                    paper_date = result.published.date()
                    if paper_date == today:
                        paper = self._convert_result_to_dict(result)
                        category_papers.append(paper)
                    elif paper_date < today:
                        # We've gone past today's papers, stop searching
                        break

                logger.info(f"Found {len(category_papers)} papers from {category} published today")
                papers.extend(category_papers)

            except Exception as e:
                logger.error(f"Failed to fetch papers from {category}: {e}")
                # Continue with other categories

        logger.info(f"Fetched {len(papers)} papers total from today")
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
        cutoff_date = datetime.now() - timedelta(days=days)

        for category in categories:
            try:
                logger.info(f"Fetching recent papers from category: {category}")

                # Query for papers in this category
                search = arxiv.Search(
                    query=f"cat:{category}",
                    max_results=max_results * 2,  # Fetch more to filter by date
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending
                )

                for result in search.results():
                    # Filter by date
                    if result.published.replace(tzinfo=None) >= cutoff_date:
                        paper = self._convert_result_to_dict(result)
                        papers.append(paper)

                    # Stop if we have enough
                    if len(papers) >= max_results:
                        break

            except Exception as e:
                logger.error(f"Failed to fetch papers from {category}: {e}")
                # Continue with other categories

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
        try:
            logger.info(f"Fetching paper: {arxiv_id}")

            search = arxiv.Search(id_list=[arxiv_id])
            result = next(search.results())

            return self._convert_result_to_dict(result)

        except StopIteration:
            logger.warning(f"Paper not found: {arxiv_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch paper {arxiv_id}: {e}")
            return None

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
        try:
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

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _convert_result_to_dict(self, result: arxiv.Result) -> dict:
        """
        Convert arxiv.Result to dictionary format.

        Args:
            result: arxiv.Result object

        Returns:
            Paper dictionary
        """
        # Extract arXiv ID (remove version if present)
        arxiv_id = result.entry_id.split('/')[-1]
        if 'v' in arxiv_id:
            base_id = arxiv_id.split('v')[0]
            version = arxiv_id.split('v')[1]
        else:
            base_id = arxiv_id
            version = None

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
