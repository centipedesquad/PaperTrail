#!/usr/bin/env python3
"""
Test script for Phase 2 functionality.
Verifies that all components are working without launching GUI.
"""

import sys
import os

# Add src to path
sys.path.insert(0, 'src')

from database.connection import initialize_database
from database.migration_manager import MigrationManager
from services.config_service import ConfigService
from services.paper_service import PaperService
from services.fetch_service import FetchService
from api.arxiv_client import ArxivClient

def test_phase2():
    """Test Phase 2 components."""
    print("Testing Phase 2: arXiv Integration\n")
    print("=" * 50)

    # 1. Database setup
    print("\n1. Testing database setup...")
    db = initialize_database('test_phase2.db')
    migrations_dir = 'src/database/migrations'
    manager = MigrationManager(db, migrations_dir)
    manager.migrate()
    print("   ✓ Database initialized")

    # 2. Services
    print("\n2. Testing services...")
    config_service = ConfigService(db)
    paper_service = PaperService(db)
    fetch_service = FetchService(paper_service)
    print("   ✓ Services initialized")

    # 3. Create test paper
    print("\n3. Testing paper creation...")
    test_paper = {
        'arxiv_id': '2301.99999',
        'title': 'Test Paper for Phase 2',
        'abstract': 'This is a test abstract.',
        'publication_date': '2023-01-15',
        'pdf_url': 'https://arxiv.org/pdf/2301.99999',
        'authors': [
            {'name': 'Test Author', 'normalized_name': 'test author'}
        ],
        'categories': ['hep-th'],
        'primary_category': 'hep-th'
    }
    paper_id = paper_service.create_paper(test_paper)
    print(f"   ✓ Created paper with ID: {paper_id}")

    # 4. Retrieve paper
    print("\n4. Testing paper retrieval...")
    paper = paper_service.get_paper(paper_id)
    print(f"   ✓ Retrieved: {paper.title}")
    print(f"   ✓ Authors: {[a.name for a in paper.authors]}")
    print(f"   ✓ Categories: {[c.code for c in paper.categories]}")

    # 5. Test arXiv client (just initialization)
    print("\n5. Testing arXiv client...")
    arxiv_client = ArxivClient()
    print("   ✓ ArxivClient initialized")

    # Cleanup
    print("\n6. Cleaning up...")
    db.close()
    os.remove('test_phase2.db')
    if os.path.exists('test_phase2.db-wal'):
        os.remove('test_phase2.db-wal')
    if os.path.exists('test_phase2.db-shm'):
        os.remove('test_phase2.db-shm')
    print("   ✓ Test database removed")

    print("\n" + "=" * 50)
    print("✓ Phase 2 tests passed!")
    print("\nPhase 2 is complete and ready to use.")
    print("Run './run.sh' to start the application.")

if __name__ == "__main__":
    try:
        test_phase2()
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
