"""Tests for service layer."""

import pytest
from unittest.mock import patch, MagicMock
from services.paper_service import PaperService
from services.config_service import ConfigService


# ── PaperService ────────────────────────────────────────────────────

class TestPaperService:
    def test_create_paper(self, paper_service, sample_paper_data):
        paper_id = paper_service.create_paper(sample_paper_data)
        assert paper_id is not None

    def test_get_paper(self, paper_service, sample_paper_data):
        paper_id = paper_service.create_paper(sample_paper_data)
        paper = paper_service.get_paper(paper_id)
        assert paper is not None
        assert paper.arxiv_id == '2301.12345'

    def test_get_paper_nonexistent(self, paper_service):
        paper = paper_service.get_paper(99999)
        assert paper is None

    def test_get_paper_by_arxiv_id(self, paper_service, sample_paper_data):
        paper_service.create_paper(sample_paper_data)
        paper = paper_service.get_paper_by_arxiv_id('2301.12345')
        assert paper is not None

    def test_get_all_papers(self, paper_service, sample_paper_data, sample_paper_data_2):
        paper_service.create_paper(sample_paper_data)
        paper_service.create_paper(sample_paper_data_2)
        papers = paper_service.get_all_papers()
        assert len(papers) == 2

    def test_create_papers_batch(self, paper_service, sample_paper_data, sample_paper_data_2):
        count = paper_service.create_papers_batch([sample_paper_data, sample_paper_data_2])
        assert count == 2

    def test_create_papers_batch_with_duplicates(self, paper_service, sample_paper_data):
        paper_service.create_paper(sample_paper_data)
        count = paper_service.create_papers_batch([sample_paper_data])
        assert count == 0

    def test_create_papers_batch_empty(self, paper_service):
        count = paper_service.create_papers_batch([])
        assert count == 0

    def test_search_papers(self, paper_service, sample_paper_data):
        paper_service.create_paper(sample_paper_data)
        results = paper_service.search_papers(search_text="Attention")
        assert len(results) >= 1


# ── ConfigService ───────────────────────────────────────────────────

class TestConfigService:
    def test_get_default(self, config_service):
        value = config_service.get("nonexistent_key", "default_val")
        assert value == "default_val"

    def test_get_none_default(self, config_service):
        value = config_service.get("nonexistent_key")
        assert value is None

    def test_set_and_get(self, config_service):
        config_service.set("test_key", "test_value")
        value = config_service.get("test_key")
        assert value == "test_value"

    def test_set_overwrite(self, config_service):
        config_service.set("key", "value1")
        config_service.set("key", "value2")
        assert config_service.get("key") == "value2"

    def test_get_all(self, config_service):
        config_service.set("k1", "v1")
        config_service.set("k2", "v2")
        all_settings = config_service.get_all()
        assert "k1" in all_settings
        assert all_settings["k1"] == "v1"

    def test_delete(self, config_service):
        config_service.set("to_delete", "value")
        config_service.delete("to_delete")
        assert config_service.get("to_delete") is None

    def test_get_theme_default(self, config_service):
        assert config_service.get_theme() == "light"

    def test_set_theme(self, config_service):
        config_service.set_theme("dark")
        assert config_service.get_theme() == "dark"

    def test_get_font_size_default(self, config_service):
        assert config_service.get_font_size() == 11

    def test_set_font_size(self, config_service):
        config_service.set_font_size(14)
        assert config_service.get_font_size() == 14

    def test_get_download_preference_default(self, config_service):
        assert config_service.get_download_preference() == "ask"

    def test_set_download_preference_valid(self, config_service):
        config_service.set_download_preference("download")
        assert config_service.get_download_preference() == "download"

    def test_set_download_preference_invalid(self, config_service):
        with pytest.raises(ValueError):
            config_service.set_download_preference("invalid")

    def test_get_pdf_naming_pattern_default(self, config_service):
        pattern = config_service.get_pdf_naming_pattern()
        assert "{arxiv_id}" in pattern

    def test_get_max_fetch_results_default(self, config_service):
        assert config_service.get_max_fetch_results() == 50

    def test_set_fetch_mode_valid(self, config_service):
        config_service.set_fetch_mode("recent")
        assert config_service.get_fetch_mode() == "recent"

    def test_set_fetch_mode_invalid(self, config_service):
        with pytest.raises(ValueError):
            config_service.set_fetch_mode("invalid")

    def test_get_recent_days_default(self, config_service):
        assert config_service.get_recent_days() == 7


# ── FetchService (with mocked ArxivClient) ──────────────────────────

class TestFetchService:
    def test_fetch_new_papers(self, db):
        from services.fetch_service import FetchService
        paper_service = PaperService(db)
        fetch_service = FetchService(paper_service)

        mock_papers = [
            {
                'arxiv_id': '2301.00001',
                'title': 'Mock Paper 1',
                'abstract': 'Mock abstract',
                'publication_date': '2023-01-01',
                'pdf_url': 'http://x/1',
                'authors': [{'name': 'Author A', 'normalized_name': 'a_a'}],
                'categories': ['cs.AI'],
                'primary_category': 'cs.AI',
            }
        ]

        with patch.object(fetch_service.arxiv_client, 'fetch_new_papers', return_value=mock_papers):
            result = fetch_service.fetch_new_papers(['cs.AI'], max_results=10)

        assert result['fetched'] == 1
        assert result['created'] == 1
        assert result['duplicates'] == 0

    def test_fetch_new_papers_with_duplicates(self, db):
        from services.fetch_service import FetchService
        paper_service = PaperService(db)
        fetch_service = FetchService(paper_service)

        mock_paper = {
            'arxiv_id': '2301.00002',
            'title': 'Dup Paper',
            'abstract': 'Abstract',
            'publication_date': '2023-01-02',
            'pdf_url': 'http://x/2',
            'authors': [{'name': 'B', 'normalized_name': 'b'}],
            'categories': ['cs.AI'],
            'primary_category': 'cs.AI',
        }

        # Create paper first
        paper_service.create_paper(mock_paper)

        with patch.object(fetch_service.arxiv_client, 'fetch_new_papers', return_value=[mock_paper]):
            result = fetch_service.fetch_new_papers(['cs.AI'])

        assert result['fetched'] == 1
        assert result['created'] == 0
        assert result['duplicates'] == 1

    def test_fetch_returns_dict(self, db):
        from services.fetch_service import FetchService
        paper_service = PaperService(db)
        fetch_service = FetchService(paper_service)

        with patch.object(fetch_service.arxiv_client, 'fetch_new_papers', return_value=[]):
            result = fetch_service.fetch_new_papers(['cs.AI'])

        assert isinstance(result, dict)
        assert 'fetched' in result
        assert 'created' in result
        assert 'duplicates' in result
        assert 'papers' in result

    def test_fetch_propagates_api_error(self, db):
        from services.fetch_service import FetchService
        paper_service = PaperService(db)
        fetch_service = FetchService(paper_service)

        with patch.object(
            fetch_service.arxiv_client, 'fetch_new_papers',
            side_effect=ConnectionError("Network down")
        ):
            with pytest.raises(ConnectionError):
                fetch_service.fetch_new_papers(['cs.AI'])
