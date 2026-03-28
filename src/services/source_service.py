"""
Source file service for PaperTrail.
Handles downloading, extracting, opening, and deleting arXiv source files.
"""

import os
import gzip
import shutil
import tarfile
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Callable

from models import Paper
from utils.download_utils import download_file
from utils.platform_utils import ensure_directory_exists

logger = logging.getLogger(__name__)

# arXiv e-print URL pattern
EPRINT_URL_TEMPLATE = "https://arxiv.org/e-print/{arxiv_id}"


class SourceService:
    """Service for source file operations (download, extract, open, delete)."""

    def __init__(self, config_service, paper_service):
        self.config_service = config_service
        self.paper_service = paper_service

        self.data_dir = config_service.get_database_location()
        if not self.data_dir:
            raise ValueError("Database location not configured")

        self.sources_dir = os.path.join(self.data_dir, "sources")
        self.cache_dir = os.path.join(self.data_dir, "cache", "sources")
        ensure_directory_exists(self.sources_dir)
        ensure_directory_exists(self.cache_dir)

    def get_source_url(self, paper: Paper) -> str:
        """Construct the arXiv e-print URL for a paper."""
        return EPRINT_URL_TEMPLATE.format(arxiv_id=paper.arxiv_id)

    def download_source(
        self,
        paper: Paper,
        permanent: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Optional[str]:
        """
        Download and extract source files for a paper.

        Args:
            paper: Paper object
            permanent: If True, save to sources_dir; if False, save to cache
            progress_callback: Optional callback(current_bytes, total_bytes)

        Returns:
            Path to extracted source directory, or None on failure
        """
        try:
            url = self.get_source_url(paper)
            dest_dir = self.sources_dir if permanent else self.cache_dir
            extract_dir = os.path.join(dest_dir, paper.arxiv_id)

            # Download to a temp file first
            with tempfile.NamedTemporaryFile(
                dir=dest_dir, suffix=".download", delete=False
            ) as tmp:
                tmp_path = tmp.name

            try:
                download_file(url, tmp_path, progress_callback)
                extracted = self._extract_archive(tmp_path, extract_dir, paper.arxiv_id)
            finally:
                # Clean up temp download file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

            if extracted and permanent:
                self.paper_service.update_source_path(paper.id, extract_dir)

            return extracted

        except Exception as e:
            logger.error(f"Failed to download source for {paper.arxiv_id}: {e}")
            return None

    def _extract_archive(self, archive_path: str, extract_dir: str, arxiv_id: str) -> Optional[str]:
        """
        Extract archive detecting format via magic bytes.
        Handles: tar.gz, gzip-only, single file, PDF-as-source.

        Returns path to extracted directory, or None on failure.
        """
        # Use a temp directory for extraction, then atomic move
        tmp_extract = extract_dir + ".tmp"
        if os.path.exists(tmp_extract):
            shutil.rmtree(tmp_extract)
        os.makedirs(tmp_extract, exist_ok=True)

        try:
            with open(archive_path, 'rb') as f:
                magic = f.read(4)

            if magic[:2] == b'\x1f\x8b':
                # Gzip magic bytes — try tar.gz first, fall back to gzip-only
                try:
                    with tarfile.open(archive_path, 'r:gz') as tar:
                        # Path traversal protection
                        for member in tar.getmembers():
                            member_path = os.path.normpath(member.name)
                            if member_path.startswith('..') or os.path.isabs(member_path):
                                logger.warning(f"Skipping unsafe path in archive: {member.name}")
                                continue
                            if member.issym() or member.islnk():
                                logger.warning(f"Skipping symlink in archive: {member.name}")
                                continue
                            tar.extract(member, tmp_extract)
                    logger.info(f"Extracted tar.gz archive for {arxiv_id}")
                except tarfile.TarError:
                    # Not a tar — try plain gzip
                    output_path = os.path.join(tmp_extract, f"{arxiv_id}.tex")
                    with gzip.open(archive_path, 'rb') as gz:
                        with open(output_path, 'wb') as out:
                            shutil.copyfileobj(gz, out)
                    logger.info(f"Extracted gzip file for {arxiv_id}")
            elif magic[:4] == b'%PDF':
                # PDF as source — just copy it
                shutil.copy2(archive_path, os.path.join(tmp_extract, f"{arxiv_id}.pdf"))
                logger.info(f"Source is PDF for {arxiv_id}")
            else:
                # Single file (bare tex or other)
                shutil.copy2(archive_path, os.path.join(tmp_extract, f"{arxiv_id}.tex"))
                logger.info(f"Source is single file for {arxiv_id}")

            # Atomic move: tmp → final
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            os.rename(tmp_extract, extract_dir)
            return extract_dir

        except Exception as e:
            logger.error(f"Failed to extract source for {arxiv_id}: {e}")
            # Clean up partial extraction
            if os.path.exists(tmp_extract):
                shutil.rmtree(tmp_extract)
            return None

    def open_source(self, paper: Paper) -> bool:
        """Open source directory in Finder (macOS) or file manager (Linux)."""
        source_path = paper.local_source_path
        if not source_path or not os.path.exists(source_path):
            logger.error(f"Source not found: {source_path}")
            return False

        try:
            import sys
            if sys.platform == 'darwin':
                subprocess.Popen(['open', source_path])
            else:
                subprocess.Popen(['xdg-open', source_path])
            logger.info(f"Opened source directory: {source_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to open source directory: {e}")
            return False

    def has_local_source(self, paper: Paper) -> bool:
        """Check if paper has local source files."""
        return bool(paper.local_source_path) and os.path.exists(paper.local_source_path)

    def delete_source(self, paper: Paper) -> bool:
        """Delete local source directory for a paper."""
        if not paper.local_source_path:
            return True

        try:
            if os.path.exists(paper.local_source_path):
                shutil.rmtree(paper.local_source_path)
                logger.info(f"Deleted source: {paper.local_source_path}")

            self.paper_service.update_source_path(paper.id, None)
            return True
        except Exception as e:
            logger.error(f"Failed to delete source: {e}")
            return False

    def cleanup_cache(self) -> int:
        """Clean up source cache directory. Returns number of items deleted."""
        deleted = 0
        try:
            for name in os.listdir(self.cache_dir):
                path = os.path.join(self.cache_dir, name)
                if os.path.isdir(path):
                    shutil.rmtree(path)
                elif os.path.isfile(path):
                    os.remove(path)
                deleted += 1
            logger.info(f"Cleaned up {deleted} cached source items")
        except Exception as e:
            logger.error(f"Failed to cleanup source cache: {e}")
        return deleted
