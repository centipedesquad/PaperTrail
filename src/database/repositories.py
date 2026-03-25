"""
Repository layer for database operations.
Implements CRUD operations for all entities.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime

from database.connection import DatabaseConnection
from models import (
    Paper, Author, Category, PaperNote, PaperRating,
    Setting, Tag, AuthorMetrics, Annotation
)

logger = logging.getLogger(__name__)


def sanitize_fts5_query(query: str) -> str:
    """Sanitize user input for safe use in FTS5 MATCH queries.

    FTS5 has its own query syntax where characters like quotes, parentheses,
    and boolean operators (AND/OR/NOT/NEAR) cause OperationalError if used
    as raw input. This function escapes the input by wrapping each token
    in double quotes to force literal matching.
    """
    if not query or not query.strip():
        return ""
    # Strip control characters and FTS5 special characters
    cleaned = re.sub(r'[\x00-\x1f\x7f]', ' ', query)
    cleaned = re.sub(r'["\(\)\{\}\[\]:^+\-*]', ' ', cleaned)
    # Split into tokens and wrap each in double quotes for literal matching
    tokens = cleaned.split()
    if not tokens:
        return ""
    return ' '.join(f'"{token}"' for token in tokens)


class PaperRepository:
    """Repository for paper operations."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def create(self, paper_data: dict) -> Optional[int]:
        """
        Create a new paper with authors and categories.

        Args:
            paper_data: Dictionary with paper data (including authors and categories)

        Returns:
            Paper ID if successful, None otherwise
        """
        try:
            with self.db.transaction():
                return self._create_inner(paper_data)
        except Exception as e:
            logger.error(f"Failed to create paper: {e}")
            return None

    def _create_inner(self, paper_data: dict) -> Optional[int]:
        """
        Create a paper without managing its own transaction.
        Caller must wrap this in a transaction.
        """
        # Check if paper already exists
        existing = self.db.fetch_one(
            "SELECT id FROM papers WHERE arxiv_id = ?",
            (paper_data['arxiv_id'],)
        )
        if existing:
            logger.info(f"Paper already exists: {paper_data['arxiv_id']}")
            return None

        # Insert paper
        cursor = self.db.execute(
            """
            INSERT INTO papers (
                arxiv_id, title, abstract, publication_date, pdf_url,
                version, comment, journal_ref, doi
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper_data['arxiv_id'],
                paper_data['title'],
                paper_data['abstract'],
                paper_data['publication_date'],
                paper_data['pdf_url'],
                paper_data.get('version'),
                paper_data.get('comment'),
                paper_data.get('journal_ref'),
                paper_data.get('doi')
            )
        )
        paper_id = cursor.lastrowid

        # Add authors
        if 'authors' in paper_data:
            for i, author_data in enumerate(paper_data['authors']):
                author_id = self._get_or_create_author(
                    author_data['name'],
                    author_data['normalized_name']
                )
                self.db.execute(
                    """
                    INSERT INTO paper_authors (paper_id, author_id, author_order)
                    VALUES (?, ?, ?)
                    """,
                    (paper_id, author_id, i)
                )

        # Add categories
        if 'categories' in paper_data:
            primary_category = paper_data.get('primary_category')
            for category_code in paper_data['categories']:
                category_id = self._get_or_create_category(category_code)
                is_primary = (category_code == primary_category)
                self.db.execute(
                    """
                    INSERT INTO paper_categories (paper_id, category_id, is_primary)
                    VALUES (?, ?, ?)
                    """,
                    (paper_id, category_id, is_primary)
                )

        logger.info(f"Created paper: {paper_data['arxiv_id']} (ID: {paper_id})")
        return paper_id

    def get_by_id(self, paper_id: int) -> Optional[Paper]:
        """Get paper by ID with all related data."""
        row = self.db.fetch_one("SELECT * FROM papers WHERE id = ?", (paper_id,))
        if not row:
            return None

        paper = self._row_to_paper(row)
        self._load_related_data(paper)
        return paper

    def get_by_arxiv_id(self, arxiv_id: str) -> Optional[Paper]:
        """Get paper by arXiv ID."""
        row = self.db.fetch_one("SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,))
        if not row:
            return None

        paper = self._row_to_paper(row)
        self._load_related_data(paper)
        return paper

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Paper]:
        """Get all papers with pagination."""
        rows = self.db.fetch_all(
            """
            SELECT * FROM papers
            ORDER BY publication_date DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )

        papers = [self._row_to_paper(row) for row in rows]
        self._load_related_data_batch(papers)
        return papers

    def update_local_pdf_path(self, paper_id: int, pdf_path: str):
        """Update local PDF path for a paper."""
        self.db.execute(
            "UPDATE papers SET local_pdf_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (pdf_path, paper_id)
        )
        self.db.commit()

    def update_last_accessed(self, paper_id: int):
        """Update last accessed timestamp."""
        self.db.execute(
            "UPDATE papers SET last_accessed = CURRENT_TIMESTAMP WHERE id = ?",
            (paper_id,)
        )
        self.db.commit()

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
            date_from: Filter by publication date (YYYY-MM-DD)
            date_to: Filter by publication date (YYYY-MM-DD)
            has_pdf: Filter by local PDF existence
            has_rating: Filter by rating existence
            sort_by: Sort order (date_desc, date_asc, title_asc, title_desc)
            limit: Maximum results

        Returns:
            List of matching papers
        """
        # Build query dynamically
        where_clauses = []
        params = []

        if search_text:
            # Use FTS5 for full-text search (sanitize input to prevent crashes)
            sanitized = sanitize_fts5_query(search_text)
            if sanitized:
                where_clauses.append(
                    "id IN (SELECT rowid FROM papers_fts WHERE papers_fts MATCH ?)"
                )
                params.append(sanitized)

        if categories:
            placeholders = ','.join('?' * len(categories))
            where_clauses.append(
                f"""id IN (
                    SELECT pc.paper_id FROM paper_categories pc
                    JOIN categories c ON pc.category_id = c.id
                    WHERE c.code IN ({placeholders})
                )"""
            )
            params.extend(categories)

        if date_from:
            where_clauses.append("publication_date >= ?")
            params.append(date_from)

        if date_to:
            where_clauses.append("publication_date <= ?")
            params.append(date_to)

        if has_pdf is not None:
            if has_pdf:
                where_clauses.append("local_pdf_path IS NOT NULL")
            else:
                where_clauses.append("local_pdf_path IS NULL")

        if has_rating is not None:
            if has_rating:
                where_clauses.append("id IN (SELECT paper_id FROM paper_ratings)")
            else:
                where_clauses.append("id NOT IN (SELECT paper_id FROM paper_ratings)")

        # Determine ORDER BY clause
        order_clauses = {
            "date_desc": "publication_date DESC, id DESC",
            "date_asc": "publication_date ASC, id ASC",
            "title_asc": "title ASC",
            "title_desc": "title DESC",
        }
        order_by = order_clauses.get(sort_by, "publication_date DESC, id DESC")

        # Build final query
        query = "SELECT * FROM papers"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += f" ORDER BY {order_by} LIMIT ?"
        params.append(limit)

        rows = self.db.fetch_all(query, tuple(params))

        papers = [self._row_to_paper(row) for row in rows]
        self._load_related_data_batch(papers)
        return papers

    def get_all_categories(self) -> List[tuple]:
        """
        Get all categories in database.

        Returns:
            List of (code, name) tuples
        """
        rows = self.db.fetch_all(
            "SELECT code, name FROM categories ORDER BY code"
        )
        return [(row['code'], row['name']) for row in rows]

    def get_category_counts(self) -> dict:
        """
        Get paper counts for each category.

        Returns:
            Dictionary of {category_code: paper_count}
        """
        rows = self.db.fetch_all(
            """
            SELECT c.code, COUNT(DISTINCT pc.paper_id) as count
            FROM categories c
            LEFT JOIN paper_categories pc ON c.id = pc.category_id
            GROUP BY c.code
            HAVING count > 0
            ORDER BY count DESC
            """
        )
        return {row['code']: row['count'] for row in rows}

    def _get_or_create_author(self, name: str, normalized_name: str) -> int:
        """Get or create author, return author ID."""
        row = self.db.fetch_one(
            "SELECT id FROM authors WHERE normalized_name = ?",
            (normalized_name,)
        )
        if row:
            return row['id']

        cursor = self.db.execute(
            "INSERT INTO authors (name, normalized_name) VALUES (?, ?)",
            (name, normalized_name)
        )
        return cursor.lastrowid

    def _get_or_create_category(self, code: str) -> int:
        """Get or create category, return category ID."""
        row = self.db.fetch_one(
            "SELECT id FROM categories WHERE code = ?",
            (code,)
        )
        if row:
            return row['id']

        # Generate name from code (e.g., "hep-th" -> "High Energy Physics - Theory")
        name = self._category_code_to_name(code)

        cursor = self.db.execute(
            "INSERT INTO categories (code, name) VALUES (?, ?)",
            (code, name)
        )
        return cursor.lastrowid

    def _category_code_to_name(self, code: str) -> str:
        """Convert category code to human-readable name."""
        # Simple mapping for common categories
        category_names = {
            'hep-th': 'High Energy Physics - Theory',
            'hep-ph': 'High Energy Physics - Phenomenology',
            'gr-qc': 'General Relativity and Quantum Cosmology',
            'astro-ph': 'Astrophysics',
            'cs.AI': 'Computer Science - Artificial Intelligence',
            'cs.LG': 'Computer Science - Machine Learning',
            'math.DG': 'Mathematics - Differential Geometry',
            'quant-ph': 'Quantum Physics',
        }
        return category_names.get(code, code)

    def _row_to_paper(self, row) -> Paper:
        """Convert database row to Paper object."""
        return Paper(
            id=row['id'],
            arxiv_id=row['arxiv_id'],
            title=row['title'],
            abstract=row['abstract'],
            publication_date=row['publication_date'],
            pdf_url=row['pdf_url'],
            local_pdf_path=row['local_pdf_path'],
            version=row['version'],
            comment=row['comment'],
            journal_ref=row['journal_ref'],
            doi=row['doi'],
            date_added=row['date_added'],
            last_accessed=row['last_accessed'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def _load_related_data(self, paper: Paper):
        """Load authors, categories, notes, and ratings for a single paper."""
        self._load_related_data_batch([paper])

    def _load_related_data_batch(self, papers: List[Paper]):
        """Batch-load related data for multiple papers in 4 queries total."""
        if not papers:
            return

        paper_ids = [p.id for p in papers]
        paper_map = {p.id: p for p in papers}
        placeholders = ','.join('?' * len(paper_ids))

        # Load authors (1 query)
        author_rows = self.db.fetch_all(
            f"""
            SELECT a.*, pa.author_order, pa.paper_id
            FROM authors a
            JOIN paper_authors pa ON a.id = pa.author_id
            WHERE pa.paper_id IN ({placeholders})
            ORDER BY pa.paper_id, pa.author_order
            """,
            tuple(paper_ids)
        )
        # Group by paper_id
        authors_by_paper: Dict[int, list] = {pid: [] for pid in paper_ids}
        for row in author_rows:
            authors_by_paper[row['paper_id']].append(
                Author(
                    id=row['id'],
                    name=row['name'],
                    normalized_name=row['normalized_name'],
                    created_at=row['created_at'],
                    author_order=row['author_order']
                )
            )
        for paper in papers:
            paper.authors = authors_by_paper.get(paper.id, [])

        # Load categories (1 query)
        category_rows = self.db.fetch_all(
            f"""
            SELECT c.*, pc.is_primary, pc.paper_id
            FROM categories c
            JOIN paper_categories pc ON c.id = pc.category_id
            WHERE pc.paper_id IN ({placeholders})
            """,
            tuple(paper_ids)
        )
        cats_by_paper: Dict[int, list] = {pid: [] for pid in paper_ids}
        for row in category_rows:
            cats_by_paper[row['paper_id']].append(
                Category(
                    id=row['id'],
                    code=row['code'],
                    name=row['name'],
                    parent_code=row['parent_code'],
                    created_at=row['created_at'],
                    is_primary=bool(row['is_primary'])
                )
            )
        for paper in papers:
            paper.categories = cats_by_paper.get(paper.id, [])

        # Load notes (1 query)
        note_rows = self.db.fetch_all(
            f"SELECT * FROM paper_notes WHERE paper_id IN ({placeholders})",
            tuple(paper_ids)
        )
        for row in note_rows:
            paper = paper_map.get(row['paper_id'])
            if paper:
                paper.notes = PaperNote(
                    id=row['id'],
                    paper_id=row['paper_id'],
                    note_text=row['note_text'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )

        # Load ratings (1 query)
        rating_rows = self.db.fetch_all(
            f"SELECT * FROM paper_ratings WHERE paper_id IN ({placeholders})",
            tuple(paper_ids)
        )
        for row in rating_rows:
            paper = paper_map.get(row['paper_id'])
            if paper:
                paper.ratings = PaperRating(
                    id=row['id'],
                    paper_id=row['paper_id'],
                    importance=row['importance'],
                    comprehension=row['comprehension'],
                    technicality=row['technicality'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )


class NotesRepository:
    """Repository for paper notes operations."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def create_or_update(self, paper_id: int, note_text: str) -> int:
        """Create or update note for a paper."""
        with self.db.transaction():
            cursor = self.db.execute(
                """
                INSERT INTO paper_notes (paper_id, note_text, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(paper_id) DO UPDATE SET
                    note_text = excluded.note_text,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (paper_id, note_text)
            )
            return cursor.lastrowid

    def get_by_paper_id(self, paper_id: int) -> Optional[PaperNote]:
        """Get note for a paper."""
        row = self.db.fetch_one(
            "SELECT * FROM paper_notes WHERE paper_id = ?",
            (paper_id,)
        )
        if not row:
            return None

        return PaperNote(
            id=row['id'],
            paper_id=row['paper_id'],
            note_text=row['note_text'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def delete(self, paper_id: int):
        """Delete note for a paper."""
        self.db.execute("DELETE FROM paper_notes WHERE paper_id = ?", (paper_id,))
        self.db.commit()


class RatingsRepository:
    """Repository for paper ratings operations."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def create_or_update(
        self,
        paper_id: int,
        importance: Optional[str] = None,
        comprehension: Optional[str] = None,
        technicality: Optional[str] = None
    ) -> int:
        """Create or update rating for a paper."""
        with self.db.transaction():
            cursor = self.db.execute(
                """
                INSERT INTO paper_ratings (paper_id, importance, comprehension, technicality, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(paper_id) DO UPDATE SET
                    importance = COALESCE(excluded.importance, paper_ratings.importance),
                    comprehension = COALESCE(excluded.comprehension, paper_ratings.comprehension),
                    technicality = COALESCE(excluded.technicality, paper_ratings.technicality),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (paper_id, importance, comprehension, technicality)
            )
            return cursor.lastrowid

    def get_by_paper_id(self, paper_id: int) -> Optional[PaperRating]:
        """Get rating for a paper."""
        row = self.db.fetch_one(
            "SELECT * FROM paper_ratings WHERE paper_id = ?",
            (paper_id,)
        )
        if not row:
            return None

        return PaperRating(
            id=row['id'],
            paper_id=row['paper_id'],
            importance=row['importance'],
            comprehension=row['comprehension'],
            technicality=row['technicality'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def delete(self, paper_id: int):
        """Delete rating for a paper."""
        self.db.execute("DELETE FROM paper_ratings WHERE paper_id = ?", (paper_id,))
        self.db.commit()
