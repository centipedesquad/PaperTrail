"""Tests for utility modules."""

import pytest
from models import Paper, Author
from utils.filename_utils import FilenameGenerator, sanitize_filename


# ── FilenameGenerator ───────────────────────────────────────────────

class TestFilenameGenerator:
    def _make_paper(self, **kwargs):
        defaults = {
            'arxiv_id': '2301.12345',
            'title': 'Attention Is All You Need',
            'publication_date': '2023-01-15',
            'authors': [
                Author(name='Ashish Vaswani'),
                Author(name='Noam Shazeer'),
            ],
        }
        defaults.update(kwargs)
        return Paper(**defaults)

    def test_default_pattern(self):
        gen = FilenameGenerator()
        paper = self._make_paper()
        filename = gen.generate(paper)
        assert '2301.12345' in filename
        assert filename.endswith('.pdf')

    def test_author_extraction(self):
        gen = FilenameGenerator("[{author1}_{author2}].pdf")
        paper = self._make_paper()
        filename = gen.generate(paper)
        assert 'Vaswani' in filename
        assert 'Shazeer' in filename

    def test_single_author(self):
        gen = FilenameGenerator("[{author1}_{author2}].pdf")
        paper = self._make_paper(authors=[Author(name='Solo Author')])
        filename = gen.generate(paper)
        assert 'Author' in filename

    def test_no_authors(self):
        gen = FilenameGenerator("[{authors_all}].pdf")
        paper = self._make_paper(authors=[])
        filename = gen.generate(paper)
        assert 'Unknown' in filename

    def test_many_authors_truncated(self):
        gen = FilenameGenerator("[{authors_all}].pdf")
        authors = [Author(name=f'Author {i}') for i in range(5)]
        paper = self._make_paper(authors=authors)
        filename = gen.generate(paper)
        assert 'etal' in filename

    def test_title_truncation(self):
        gen = FilenameGenerator("{title}.pdf")
        long_title = "A" * 100 + " " + "B" * 100
        paper = self._make_paper(title=long_title)
        filename = gen.generate(paper)
        # Title should be truncated to 50 chars max
        assert len(filename) < 200

    def test_special_chars_in_title(self):
        gen = FilenameGenerator("{title}.pdf")
        paper = self._make_paper(title='Test: A <Special> "Title" with *chars*')
        filename = gen.generate(paper)
        assert ':' not in filename
        assert '<' not in filename
        assert '>' not in filename
        assert '"' not in filename

    def test_year_extraction(self):
        gen = FilenameGenerator("{year}.pdf")
        paper = self._make_paper(publication_date='2023-01-15')
        filename = gen.generate(paper)
        assert '2023' in filename

    def test_arxiv_id_in_filename(self):
        gen = FilenameGenerator("{arxiv_id}.pdf")
        paper = self._make_paper(arxiv_id='2301.12345')
        filename = gen.generate(paper)
        assert '2301.12345' in filename

    def test_ensures_pdf_extension(self):
        gen = FilenameGenerator("{arxiv_id}")
        paper = self._make_paper()
        filename = gen.generate(paper)
        assert filename.endswith('.pdf')


# ── sanitize_filename ───────────────────────────────────────────────

class TestSanitizeFilename:
    def test_normal_filename(self):
        assert sanitize_filename("paper.pdf") == "paper.pdf"

    def test_removes_invalid_chars(self):
        result = sanitize_filename('test<>:"/\\|?*.pdf')
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result

    def test_truncates_long_filename(self):
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name, max_length=200)
        assert len(result) <= 204  # 200 + .pdf

    def test_preserves_extension_on_truncation(self):
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name, max_length=50)
        assert result.endswith(".pdf")

    def test_strips_whitespace(self):
        result = sanitize_filename("  test.pdf  ")
        assert result == "test.pdf"

    def test_empty_string(self):
        result = sanitize_filename("")
        assert result == ""

    def test_control_characters(self):
        result = sanitize_filename("test\x00\x01\x02.pdf")
        assert "\x00" not in result
