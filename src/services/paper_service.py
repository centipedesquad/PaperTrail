"""
Paper service for managing paper operations.
Orchestrates between repositories and business logic.
"""

import logging
from typing import List, Optional
from database.connection import DatabaseConnection
from database.repositories import PaperRepository, NotesRepository, RatingsRepository
from models import Paper

logger = logging.getLogger(__name__)


class PaperService:
    """Service for paper management operations."""

    def __init__(self, db: DatabaseConnection):
        """
        Initialize paper service.

        Args:
            db: Database connection
        """
        self.db = db
        self.paper_repo = PaperRepository(db)
        self.notes_repo = NotesRepository(db)
        self.ratings_repo = RatingsRepository(db)

    def create_paper(self, paper_data: dict) -> Optional[int]:
        """
        Create a new paper.

        Args:
            paper_data: Paper data dictionary

        Returns:
            Paper ID if successful
        """
        return self.paper_repo.create(paper_data)

    def create_papers_batch(self, papers_data: List[dict]) -> int:
        """
        Create multiple papers in a single transaction.

        Args:
            papers_data: List of paper data dictionaries

        Returns:
            Number of papers created
        """
        created_count = 0
        try:
            with self.paper_repo.db.transaction():
                for paper_data in papers_data:
                    paper_id = self.paper_repo._create_inner(paper_data)
                    if paper_id:
                        created_count += 1
        except Exception as e:
            logger.error(f"Batch creation failed: {e}")
            created_count = 0

        logger.info(f"Created {created_count} out of {len(papers_data)} papers")
        return created_count

    def get_paper(self, paper_id: int) -> Optional[Paper]:
        """Get paper by ID."""
        return self.paper_repo.get_by_id(paper_id)

    def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[Paper]:
        """Get paper by arXiv ID."""
        return self.paper_repo.get_by_arxiv_id(arxiv_id)

    def get_all_papers(self, limit: int = 100, offset: int = 0) -> List[Paper]:
        """Get all papers with pagination."""
        return self.paper_repo.get_all(limit, offset)

    def search_papers(
        self,
        search_text: Optional[str] = None,
        categories: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        has_pdf: Optional[bool] = None,
        has_rating: Optional[bool] = None,
        sort_by: str = "date_desc",
        limit: int = 100
    ) -> List[Paper]:
        """
        Search papers with filters.

        Args:
            search_text: Full-text search query
            categories: Filter by category codes
            date_from: Filter by publication date
            date_to: Filter by publication date
            has_pdf: Filter by local PDF existence
            has_rating: Filter by rating existence
            sort_by: Sort order (date_desc, date_asc, title_asc, title_desc)
            limit: Maximum results

        Returns:
            List of matching papers
        """
        return self.paper_repo.search_papers(
            search_text=search_text,
            categories=categories,
            date_from=date_from,
            date_to=date_to,
            has_pdf=has_pdf,
            has_rating=has_rating,
            sort_by=sort_by,
            limit=limit
        )

    def get_all_categories(self) -> List[tuple]:
        """
        Get all categories.

        Returns:
            List of (code, name) tuples
        """
        return self.paper_repo.get_all_categories()

    def get_category_counts(self) -> dict:
        """
        Get paper counts for each category.

        Returns:
            Dictionary of {category_code: paper_count}
        """
        return self.paper_repo.get_category_counts()

    def update_pdf_path(self, paper_id: int, pdf_path: str):
        """Update local PDF path for a paper."""
        self.paper_repo.update_local_pdf_path(paper_id, pdf_path)

    def mark_accessed(self, paper_id: int):
        """Mark paper as accessed (updates last_accessed timestamp)."""
        self.paper_repo.update_last_accessed(paper_id)

    def save_note(self, paper_id: int, note_text: str):
        """Save note for a paper."""
        self.notes_repo.create_or_update(paper_id, note_text)

    def get_note(self, paper_id: int):
        """Get note for a paper."""
        return self.notes_repo.get_by_paper_id(paper_id)

    def delete_note(self, paper_id: int):
        """Delete note for a paper."""
        self.notes_repo.delete(paper_id)

    def save_rating(
        self,
        paper_id: int,
        importance: Optional[str] = None,
        comprehension: Optional[str] = None,
        technicality: Optional[str] = None
    ):
        """Save rating for a paper."""
        self.ratings_repo.create_or_update(
            paper_id,
            importance=importance,
            comprehension=comprehension,
            technicality=technicality
        )

    def get_rating(self, paper_id: int):
        """Get rating for a paper."""
        return self.ratings_repo.get_by_paper_id(paper_id)

    def delete_rating(self, paper_id: int):
        """Delete rating for a paper."""
        self.ratings_repo.delete(paper_id)
