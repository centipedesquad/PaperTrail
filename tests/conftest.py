"""Shared test fixtures for PaperTrail tests."""

import os
import sys
import tempfile
import pytest

# Add src/ to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.connection import DatabaseConnection
from database.migration_manager import MigrationManager
from database.repositories import PaperRepository, NotesRepository, RatingsRepository
from services.config_service import ConfigService
from services.paper_service import PaperService


@pytest.fixture
def db():
    """Create a fresh in-memory database with migrations applied."""
    db_path = tempfile.mktemp(suffix='.db')
    db_conn = DatabaseConnection(db_path)
    db_conn.connect()

    migrations_dir = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'database', 'migrations'
    )
    mm = MigrationManager(db_conn, migrations_dir)
    mm.migrate()

    yield db_conn

    db_conn.close()
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def paper_repo(db):
    """PaperRepository backed by test database."""
    return PaperRepository(db)


@pytest.fixture
def notes_repo(db):
    """NotesRepository backed by test database."""
    return NotesRepository(db)


@pytest.fixture
def ratings_repo(db):
    """RatingsRepository backed by test database."""
    return RatingsRepository(db)


@pytest.fixture
def config_service(db):
    """ConfigService backed by test database."""
    return ConfigService(db)


@pytest.fixture
def paper_service(db):
    """PaperService backed by test database."""
    return PaperService(db)


@pytest.fixture
def sample_paper_data():
    """Sample paper data dict for creation."""
    return {
        'arxiv_id': '2301.12345',
        'title': 'Attention Is All You Need',
        'abstract': 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.',
        'publication_date': '2023-01-15',
        'pdf_url': 'https://arxiv.org/pdf/2301.12345',
        'version': 'v1',
        'comment': 'Published at NeurIPS',
        'journal_ref': None,
        'doi': None,
        'authors': [
            {'name': 'Ashish Vaswani', 'normalized_name': 'vaswani_a'},
            {'name': 'Noam Shazeer', 'normalized_name': 'shazeer_n'},
        ],
        'categories': ['cs.CL', 'cs.AI'],
        'primary_category': 'cs.CL',
    }


@pytest.fixture
def sample_paper_data_2():
    """Second sample paper data dict."""
    return {
        'arxiv_id': '2301.99999',
        'title': 'Deep Residual Learning for Image Recognition',
        'abstract': 'Deeper neural networks are more difficult to train.',
        'publication_date': '2023-01-20',
        'pdf_url': 'https://arxiv.org/pdf/2301.99999',
        'authors': [
            {'name': 'Kaiming He', 'normalized_name': 'he_k'},
        ],
        'categories': ['cs.CV'],
        'primary_category': 'cs.CV',
    }


@pytest.fixture
def created_paper(paper_repo, sample_paper_data):
    """A paper that has already been created in the database. Returns paper_id."""
    paper_id = paper_repo.create(sample_paper_data)
    return paper_id
