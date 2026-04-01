"""
PDF service for PaperTrail.
Handles PDF downloading, streaming, and opening.
"""

import os
import logging
import requests
from pathlib import Path
from typing import Optional, Callable

from models import Paper
from utils.filename_utils import FilenameGenerator
from utils.platform_utils import open_pdf_external, ensure_directory_exists

logger = logging.getLogger(__name__)


class PDFService:
    """Service for PDF operations."""

    def __init__(self, config_service, paper_service):
        """
        Initialize PDF service.

        Args:
            config_service: Configuration service instance
            paper_service: Paper service instance
        """
        self.config_service = config_service
        self.paper_service = paper_service

        # Get data directory
        self.data_dir = config_service.get_database_location()
        if not self.data_dir:
            raise ValueError("Database location not configured")

        # Setup directories
        self.pdfs_dir = os.path.join(self.data_dir, "pdfs")
        self.cache_dir = os.path.join(self.data_dir, "cache")
        ensure_directory_exists(self.pdfs_dir)
        ensure_directory_exists(self.cache_dir)

    def get_or_download_pdf(
        self,
        paper: Paper,
        download_mode: str = "ask",
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Optional[str]:
        """
        Get PDF path, downloading if necessary.

        Args:
            paper: Paper object
            download_mode: 'download', 'stream', or 'ask'
            progress_callback: Optional callback(current_bytes, total_bytes)

        Returns:
            Local PDF path or None if failed
        """
        # Check if already have local copy
        if paper.local_pdf_path and os.path.exists(paper.local_pdf_path):
            logger.info(f"PDF already exists: {paper.local_pdf_path}")
            return paper.local_pdf_path

        # Need to download
        if download_mode == "download":
            return self.download_pdf(paper, permanent=True, progress_callback=progress_callback)
        elif download_mode == "stream":
            return self.download_pdf(paper, permanent=False, progress_callback=progress_callback)
        else:
            # Mode 'ask' should be handled by UI
            return None

    def download_pdf(
        self,
        paper: Paper,
        permanent: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Optional[str]:
        """
        Download PDF for a paper.

        Args:
            paper: Paper object
            permanent: If True, save to pdfs dir with custom name; if False, save to cache
            progress_callback: Optional callback(current_bytes, total_bytes)

        Returns:
            Local PDF path or None if failed
        """
        try:
            # Generate filename
            if permanent:
                pattern = self.config_service.get_pdf_naming_pattern()
                generator = FilenameGenerator(pattern)
                filename = generator.generate(paper)
                pdf_path = os.path.join(self.pdfs_dir, filename)
                # Avoid overwriting a different paper's file
                if os.path.exists(pdf_path):
                    base, ext = os.path.splitext(filename)
                    safe_id = paper.arxiv_id.replace('/', '_')
                    filename = f"{base}_{safe_id}{ext}"
                    pdf_path = os.path.join(self.pdfs_dir, filename)
            else:
                # Use sanitized arxiv_id for cache (legacy IDs contain '/')
                safe_id = paper.arxiv_id.replace('/', '_')
                filename = f"{safe_id}.pdf"
                pdf_path = os.path.join(self.cache_dir, filename)

            # Download to temp file, atomic rename on success
            logger.info(f"Downloading PDF from {paper.pdf_url}")
            part_path = pdf_path + '.part'

            try:
                with requests.get(paper.pdf_url, stream=True, timeout=30) as response:
                    response.raise_for_status()

                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0

                    with open(part_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)

                                if progress_callback:
                                    progress_callback(downloaded, total_size)

                os.replace(part_path, pdf_path)
            except BaseException:
                if os.path.exists(part_path):
                    os.remove(part_path)
                raise

            logger.info(f"PDF downloaded to: {pdf_path}")

            # Update database if permanent
            if permanent:
                self.paper_service.update_pdf_path(paper.id, pdf_path)

            return pdf_path

        except requests.RequestException as e:
            logger.error(f"Failed to download PDF: {e}")
            return None
        except Exception as e:
            logger.error(f"Error downloading PDF: {e}")
            return None

    def open_pdf(self, paper: Paper, pdf_path: Optional[str] = None) -> bool:
        """
        Open PDF in external reader.

        Args:
            paper: Paper object
            pdf_path: Optional path to PDF (uses paper.local_pdf_path if not provided)

        Returns:
            True if successful
        """
        if not pdf_path:
            pdf_path = paper.local_pdf_path

        if not pdf_path or not os.path.exists(pdf_path):
            logger.error(f"PDF not found: {pdf_path}")
            return False

        # Get PDF reader path from config
        reader_path = self.config_service.get_pdf_reader_path()

        # Open with external reader first (priority operation)
        success = open_pdf_external(pdf_path, reader_path)

        if success:
            logger.info(f"Opened PDF: {pdf_path}")
            # Update last accessed timestamp after successful open (non-critical operation)
            try:
                self.paper_service.mark_accessed(paper.id)
            except Exception as e:
                # Don't fail the open operation if timestamp update fails
                logger.warning(f"Failed to update last accessed timestamp: {e}")
        else:
            logger.error(f"Failed to open PDF: {pdf_path}")

        return success

    def delete_pdf(self, paper: Paper) -> bool:
        """
        Delete local PDF file.

        Args:
            paper: Paper object

        Returns:
            True if successful
        """
        if not paper.local_pdf_path:
            return True

        try:
            if os.path.exists(paper.local_pdf_path):
                os.remove(paper.local_pdf_path)
                logger.info(f"Deleted PDF: {paper.local_pdf_path}")

            # Update database
            self.paper_service.update_pdf_path(paper.id, None)
            return True

        except Exception as e:
            logger.error(f"Failed to delete PDF: {e}")
            return False

    def has_local_pdf(self, paper: Paper) -> bool:
        """
        Check if paper has local PDF.

        Args:
            paper: Paper object

        Returns:
            True if local PDF exists
        """
        return paper.local_pdf_path and os.path.exists(paper.local_pdf_path)

    def get_cache_size(self) -> int:
        """
        Get total size of cache directory in bytes.

        Returns:
            Cache size in bytes
        """
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(self.cache_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(filepath)
        except Exception as e:
            logger.error(f"Failed to calculate cache size: {e}")

        return total_size

    def cleanup_cache(self) -> int:
        """
        Clean up cache directory.

        Returns:
            Number of files deleted
        """
        deleted = 0
        try:
            for filename in os.listdir(self.cache_dir):
                filepath = os.path.join(self.cache_dir, filename)
                if os.path.isfile(filepath):
                    os.remove(filepath)
                    deleted += 1
                    logger.debug(f"Deleted cached file: {filepath}")

            logger.info(f"Cleaned up {deleted} cached files")

        except Exception as e:
            logger.error(f"Failed to cleanup cache: {e}")

        return deleted
