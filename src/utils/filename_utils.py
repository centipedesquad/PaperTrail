"""
Filename utilities for PaperTrail.
Handles PDF filename pattern parsing and sanitization.
"""

import re
import logging
from typing import Optional
from models import Paper

logger = logging.getLogger(__name__)


class FilenameGenerator:
    """Generates PDF filenames from patterns."""

    def __init__(self, pattern: str = "[{author1}_{author2}][{title}][{arxiv_id}].pdf"):
        """
        Initialize filename generator.

        Args:
            pattern: Filename pattern with variables
        """
        self.pattern = pattern

    def generate(self, paper: Paper) -> str:
        """
        Generate filename from paper and pattern.

        Args:
            paper: Paper object

        Returns:
            Sanitized filename
        """
        # Extract variables
        variables = {
            'arxiv_id': paper.arxiv_id,
            'title': self._truncate_title(paper.title),
            'year': paper.publication_date[:4] if paper.publication_date else '',
            'author1': self._get_author_lastname(paper, 0),
            'author2': self._get_author_lastname(paper, 1),
            'authors_all': self._get_all_authors(paper),
        }

        # Replace variables in pattern
        filename = self.pattern
        for key, value in variables.items():
            filename = filename.replace(f'{{{key}}}', value)

        # Sanitize
        filename = self._sanitize_filename(filename)

        # Ensure .pdf extension
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'

        return filename

    def _get_author_lastname(self, paper: Paper, index: int) -> str:
        """
        Get last name of author at index.

        Args:
            paper: Paper object
            index: Author index

        Returns:
            Author last name or empty string
        """
        if not paper.authors or index >= len(paper.authors):
            return ''

        author_name = paper.authors[index].name
        # Try to extract last name (usually last word)
        parts = author_name.split()
        if parts:
            lastname = parts[-1]
            # Remove any punctuation
            lastname = re.sub(r'[^\w\s-]', '', lastname)
            return lastname
        return ''

    def _get_all_authors(self, paper: Paper) -> str:
        """
        Get all author last names concatenated.

        Args:
            paper: Paper object

        Returns:
            Concatenated author names
        """
        if not paper.authors:
            return 'Unknown'

        # Get first 3 authors
        authors = []
        for i in range(min(3, len(paper.authors))):
            lastname = self._get_author_lastname(paper, i)
            if lastname:
                authors.append(lastname)

        if len(paper.authors) > 3:
            authors.append('etal')

        return '_'.join(authors) if authors else 'Unknown'

    def _truncate_title(self, title: str, max_length: int = 50) -> str:
        """
        Truncate and clean title for filename.

        Args:
            title: Paper title
            max_length: Maximum length

        Returns:
            Cleaned title
        """
        # Remove special characters
        title = re.sub(r'[^\w\s-]', '', title)

        # Replace spaces with underscores
        title = title.replace(' ', '_')

        # Remove multiple underscores
        title = re.sub(r'_+', '_', title)

        # Truncate
        if len(title) > max_length:
            title = title[:max_length]

        # Remove trailing underscore
        title = title.rstrip('_')

        return title

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename by removing invalid characters.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove invalid characters for filenames
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')

        # Remove control characters
        filename = ''.join(char for char in filename if ord(char) >= 32)

        # Replace multiple spaces/underscores
        filename = re.sub(r'[\s_]+', '_', filename)

        # Remove leading/trailing spaces and dots
        filename = filename.strip('. ')

        # Limit length (filesystem limit is usually 255)
        max_length = 200
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        if len(name) > max_length:
            name = name[:max_length]
        filename = f"{name}.{ext}" if ext else name

        return filename


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Standalone function to sanitize any filename.

    Args:
        filename: Original filename
        max_length: Maximum filename length

    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')

    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)

    # Replace multiple spaces with single space
    filename = ' '.join(filename.split())

    # Trim to max length
    if len(filename) > max_length:
        # Keep extension if present
        parts = filename.rsplit('.', 1)
        if len(parts) == 2:
            name, ext = parts
            max_name_length = max_length - len(ext) - 1
            filename = name[:max_name_length] + '.' + ext
        else:
            filename = filename[:max_length]

    return filename.strip()
