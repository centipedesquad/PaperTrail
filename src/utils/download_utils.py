"""
Shared HTTP download utility for PaperTrail.
Used by PDFService and SourceService for streaming file downloads.
"""

import logging
import requests
from typing import Optional, Callable

logger = logging.getLogger(__name__)


def download_file(
    url: str,
    dest_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    timeout: int = 30
) -> str:
    """
    Stream download a file from URL to disk with progress reporting.

    Args:
        url: URL to download from
        dest_path: Local path to save the file
        progress_callback: Optional callback(current_bytes, total_bytes)
        timeout: Request timeout in seconds

    Returns:
        The dest_path on success

    Raises:
        requests.RequestException: On network errors
    """
    logger.info(f"Downloading from {url}")

    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0

    with open(dest_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_size)

    logger.info(f"Downloaded to: {dest_path}")
    return dest_path
