"""
Asynchronous utilities for PaperTrail.
QThread workers for non-blocking operations.
"""

import logging
from typing import List, Optional, Callable
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class FetchWorker(QThread):
    """Background worker for fetching papers from arXiv."""

    # Signals
    progress = Signal(int, str)  # (percentage, status_message)
    finished = Signal(object)  # Result dict from fetch service
    error = Signal(str)  # Error message

    def __init__(self, fetch_func: Callable, *args, **kwargs):
        """
        Initialize fetch worker.

        Args:
            fetch_func: Function to call for fetching (returns result dict)
            *args, **kwargs: Arguments to pass to fetch_func
        """
        super().__init__()
        self.fetch_func = fetch_func
        self.args = args
        self.kwargs = kwargs
        self._is_cancelled = False

    def run(self):
        """Execute fetch operation in background thread."""
        try:
            self.progress.emit(0, "Starting fetch...")

            # Call fetch function — returns dict with 'fetched', 'created', 'duplicates', 'papers'
            result = self.fetch_func(*self.args, **self.kwargs)

            if self._is_cancelled:
                self.progress.emit(100, "Cancelled")
                return

            fetched_count = result.get('fetched', 0) if isinstance(result, dict) else len(result)
            self.progress.emit(100, f"Fetched {fetched_count} papers")
            self.finished.emit(result)

        except Exception as e:
            logger.error(f"Fetch worker error: {e}")
            self.error.emit(str(e))

    def cancel(self):
        """Cancel the fetch operation."""
        self._is_cancelled = True


class PDFDownloadWorker(QThread):
    """Background worker for downloading PDFs."""

    # Signals
    progress = Signal(int, str)  # (percentage, status_message)
    finished = Signal(str)  # Local file path
    error = Signal(str)  # Error message

    def __init__(self, download_func: Callable):
        """
        Initialize PDF download worker.

        Args:
            download_func: Callable(progress_callback) -> str path
        """
        super().__init__()
        self.download_func = download_func
        self._is_cancelled = False

    def run(self):
        """Execute download in background thread."""
        try:
            self.progress.emit(0, "Starting download...")

            # Call download function with progress callback
            def progress_callback(current: int, total: int):
                if self._is_cancelled:
                    raise InterruptedError("Download cancelled")

                if total > 0:
                    percentage = int((current / total) * 100)
                    self.progress.emit(percentage, f"Downloading: {current}/{total} bytes")
                else:
                    self.progress.emit(-1, f"Downloading: {current} bytes")

            result_path = self.download_func(progress_callback)

            if self._is_cancelled:
                self.progress.emit(100, "Cancelled")
                return

            if not result_path:
                self.error.emit("Download failed")
                return

            self.progress.emit(100, "Download complete")
            self.finished.emit(result_path)

        except InterruptedError:
            logger.info("Download cancelled by user")
            self.error.emit("Download cancelled")
        except Exception as e:
            logger.error(f"Download worker error: {e}")
            self.error.emit(str(e))

    def cancel(self):
        """Cancel the download operation."""
        self._is_cancelled = True


class BatchOperationWorker(QThread):
    """Generic worker for batch operations."""

    # Signals
    progress = Signal(int, str)  # (percentage, status_message)
    item_processed = Signal(int, object)  # (index, result)
    finished = Signal(list)  # List of results
    error = Signal(str)  # Error message

    def __init__(self, operation_func: Callable, items: list):
        """
        Initialize batch operation worker.

        Args:
            operation_func: Function to call for each item
            items: List of items to process
        """
        super().__init__()
        self.operation_func = operation_func
        self.items = items
        self._is_cancelled = False

    def run(self):
        """Execute batch operation in background thread."""
        try:
            results = []
            total = len(self.items)

            self.progress.emit(0, f"Processing 0/{total} items")

            for i, item in enumerate(self.items):
                if self._is_cancelled:
                    self.progress.emit(100, "Cancelled")
                    return

                # Process item
                result = self.operation_func(item)
                results.append(result)

                # Emit progress
                percentage = int(((i + 1) / total) * 100)
                self.progress.emit(percentage, f"Processing {i + 1}/{total} items")
                self.item_processed.emit(i, result)

            self.progress.emit(100, f"Completed {total} items")
            self.finished.emit(results)

        except Exception as e:
            logger.error(f"Batch operation worker error: {e}")
            self.error.emit(str(e))

    def cancel(self):
        """Cancel the batch operation."""
        self._is_cancelled = True


class SearchWorker(QThread):
    """Background worker for search operations."""

    # Signals
    finished = Signal(list)  # List of search results
    error = Signal(str)  # Error message

    def __init__(self, search_func: Callable, *args, **kwargs):
        """
        Initialize search worker.

        Args:
            search_func: Function to call for searching
            *args, **kwargs: Arguments to pass to search_func
        """
        super().__init__()
        self.search_func = search_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """Execute search in background thread."""
        try:
            results = self.search_func(*self.args, **self.kwargs)
            self.finished.emit(results)

        except Exception as e:
            logger.error(f"Search worker error: {e}")
            self.error.emit(str(e))


class ArxivIdWorker(QThread):
    """Background worker for fetching a single paper by arXiv ID (preview, no DB save)."""

    finished = Signal(object)  # Paper data dict or None
    error = Signal(str)

    def __init__(self, fetch_func: Callable, arxiv_id: str):
        super().__init__()
        self.fetch_func = fetch_func
        self.arxiv_id = arxiv_id
        self._is_cancelled = False

    def run(self):
        try:
            if self._is_cancelled:
                return
            result = self.fetch_func(self.arxiv_id)
            if not self._is_cancelled:
                self.finished.emit(result)
        except Exception as e:
            logger.error(f"ArxivIdWorker error: {e}")
            if not self._is_cancelled:
                self.error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True


class ArxivSearchWorker(QThread):
    """Background worker for searching arXiv (general query, returns list of dicts)."""

    finished = Signal(list)  # List of paper data dicts
    error = Signal(str)

    def __init__(self, search_func: Callable, query: str, max_results: int = 50):
        super().__init__()
        self.search_func = search_func
        self.query = query
        self.max_results = max_results
        self._is_cancelled = False

    def run(self):
        try:
            if self._is_cancelled:
                return
            results = self.search_func(self.query, self.max_results)
            if not self._is_cancelled:
                self.finished.emit(results)
        except Exception as e:
            logger.error(f"ArxivSearchWorker error: {e}")
            if not self._is_cancelled:
                self.error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True


class SourceDownloadWorker(QThread):
    """Background worker for downloading and extracting source files."""

    progress = Signal(int, str)  # (percentage, status_message)
    finished = Signal(str)  # Path to extracted directory
    error = Signal(str)

    def __init__(self, download_func: Callable, paper, permanent: bool = True):
        super().__init__()
        self.download_func = download_func
        self.paper = paper
        self.permanent = permanent
        self._is_cancelled = False

    def run(self):
        try:
            self.progress.emit(0, "Downloading source files...")

            def progress_callback(current: int, total: int):
                if self._is_cancelled:
                    raise InterruptedError("Download cancelled")
                if total > 0:
                    percentage = min(int((current / total) * 90), 90)
                    self.progress.emit(percentage, f"Downloading: {current}/{total} bytes")

            result_path = self.download_func(
                self.paper,
                permanent=self.permanent,
                progress_callback=progress_callback
            )

            if self._is_cancelled:
                return

            if result_path:
                self.progress.emit(100, "Source files ready")
                self.finished.emit(result_path)
            else:
                self.error.emit("Source files not available for this paper")

        except InterruptedError:
            logger.info("Source download cancelled")
            self.error.emit("Download cancelled")
        except Exception as e:
            logger.error(f"Source download worker error: {e}")
            self.error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True
