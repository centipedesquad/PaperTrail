"""
Data models for PaperTrail application using dataclasses.
These provide type safety and clean interfaces for database entities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class Paper:
    """Represents an arXiv paper with metadata."""
    id: Optional[int] = None
    arxiv_id: str = ""
    title: str = ""
    abstract: str = ""
    publication_date: str = ""
    pdf_url: str = ""
    local_pdf_path: Optional[str] = None
    version: Optional[str] = None
    comment: Optional[str] = None
    journal_ref: Optional[str] = None
    doi: Optional[str] = None
    date_added: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Related data (loaded separately)
    authors: List['Author'] = field(default_factory=list)
    categories: List['Category'] = field(default_factory=list)
    notes: Optional['PaperNote'] = None
    ratings: Optional['PaperRating'] = None


@dataclass
class Author:
    """Represents a paper author."""
    id: Optional[int] = None
    name: str = ""
    normalized_name: str = ""
    created_at: Optional[datetime] = None

    # For paper_authors join
    author_order: Optional[int] = None


@dataclass
class Category:
    """Represents an arXiv category."""
    id: Optional[int] = None
    code: str = ""
    name: str = ""
    parent_code: Optional[str] = None
    created_at: Optional[datetime] = None

    # For paper_categories join
    is_primary: bool = False


@dataclass
class PaperNote:
    """Represents user notes for a paper."""
    id: Optional[int] = None
    paper_id: int = 0
    note_text: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PaperRating:
    """Represents user ratings for a paper."""
    id: Optional[int] = None
    paper_id: int = 0
    importance: Optional[str] = None  # path-breaking, good, routine, passable, meh, trash
    comprehension: Optional[str] = None  # understood, partially understood, not understood
    technicality: Optional[str] = None  # tough, not tough, doesnt make sense
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Setting:
    """Represents an application setting."""
    key: str = ""
    value: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Tag:
    """Represents a tag (user or AI-generated)."""
    id: Optional[int] = None
    name: str = ""
    source: str = "user"  # user or ai
    created_at: Optional[datetime] = None


@dataclass
class AuthorMetrics:
    """Represents author citation metrics."""
    id: Optional[int] = None
    author_id: int = 0
    citation_count: int = 0
    h_index: int = 0
    paper_count: int = 0
    last_updated: Optional[datetime] = None


@dataclass
class Annotation:
    """Represents a PDF annotation."""
    id: Optional[int] = None
    paper_id: int = 0
    annotation_type: str = "highlight"  # highlight, note, underline, strikethrough
    page_number: Optional[int] = None
    content: Optional[str] = None
    color: Optional[str] = None
    created_at: Optional[datetime] = None


# Enums for rating values
class ImportanceLevel:
    PATH_BREAKING = "path-breaking"
    GOOD = "good"
    ROUTINE = "routine"
    PASSABLE = "passable"
    MEH = "meh"
    TRASH = "trash"

    @classmethod
    def all(cls) -> List[str]:
        return [cls.PATH_BREAKING, cls.GOOD, cls.ROUTINE, cls.PASSABLE, cls.MEH, cls.TRASH]


class ComprehensionLevel:
    UNDERSTOOD = "understood"
    PARTIALLY_UNDERSTOOD = "partially understood"
    NOT_UNDERSTOOD = "not understood"

    @classmethod
    def all(cls) -> List[str]:
        return [cls.UNDERSTOOD, cls.PARTIALLY_UNDERSTOOD, cls.NOT_UNDERSTOOD]


class TechnicalityLevel:
    TOUGH = "tough"
    NOT_TOUGH = "not tough"
    DOESNT_MAKE_SENSE = "doesnt make sense"

    @classmethod
    def all(cls) -> List[str]:
        return [cls.TOUGH, cls.NOT_TOUGH, cls.DOESNT_MAKE_SENSE]
