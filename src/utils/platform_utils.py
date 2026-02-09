"""
Platform-specific utilities for myArXiv.
Handles differences between macOS and Linux.
"""

import os
import platform
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_platform() -> str:
    """
    Get current platform.

    Returns:
        'macos', 'linux', or 'windows'
    """
    system = platform.system().lower()
    if system == 'darwin':
        return 'macos'
    return system


def get_default_data_dir() -> str:
    """
    Get platform-specific default data directory.

    Returns:
        Default data directory path
    """
    system = get_platform()
    home = Path.home()

    if system == 'macos':
        return str(home / "Library" / "Application Support" / "myArXiv")
    elif system == 'linux':
        return str(home / ".local" / "share" / "myArXiv")
    else:  # windows
        return str(home / "AppData" / "Local" / "myArXiv")


def get_default_pdf_reader() -> Optional[str]:
    """
    Auto-detect installed PDF readers.

    Returns:
        Path to PDF reader or None if not found
    """
    system = get_platform()

    if system == 'macos':
        # Check for Skim first, then Preview
        skim_path = "/Applications/Skim.app"
        if os.path.exists(skim_path):
            return skim_path

        # Preview is always available on Mac
        return "/System/Applications/Preview.app"

    elif system == 'linux':
        # Check for common Linux PDF readers
        readers = ['evince', 'okular', 'xpdf', 'atril', 'mupdf']
        for reader in readers:
            reader_path = shutil.which(reader)
            if reader_path:
                return reader_path

    return None


def open_pdf_external(pdf_path: str, reader_path: Optional[str] = None) -> bool:
    """
    Open PDF in external reader.

    Args:
        pdf_path: Path to PDF file
        reader_path: Optional path to PDF reader (auto-detect if None)

    Returns:
        True if successful, False otherwise
    """
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        return False

    system = get_platform()

    try:
        if system == 'macos':
            if reader_path and reader_path.endswith('.app'):
                # Use open command with specific app
                subprocess.Popen(['open', '-a', reader_path, pdf_path])
            else:
                # Use default app
                subprocess.Popen(['open', pdf_path])

        elif system == 'linux':
            if reader_path:
                subprocess.Popen([reader_path, pdf_path])
            else:
                # Try xdg-open as fallback
                subprocess.Popen(['xdg-open', pdf_path])

        else:  # windows
            os.startfile(pdf_path)

        logger.info(f"Opened PDF: {pdf_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to open PDF: {e}")
        return False


def cleanup_cache_dir(cache_dir: str):
    """
    Clean up cache directory by removing all files.

    Args:
        cache_dir: Path to cache directory
    """
    cache_path = Path(cache_dir)

    if not cache_path.exists():
        return

    try:
        file_count = 0
        for file in cache_path.glob("*"):
            if file.is_file():
                file.unlink()
                file_count += 1

        logger.info(f"Cleaned up {file_count} cached files from {cache_dir}")

    except Exception as e:
        logger.error(f"Failed to cleanup cache directory: {e}")


def ensure_directory_exists(directory: str):
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        directory: Path to directory
    """
    Path(directory).mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitize filename by removing invalid characters.

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


def get_home_directory() -> str:
    """
    Get user's home directory.

    Returns:
        Home directory path
    """
    return str(Path.home())


def browse_for_directory(title: str = "Select Directory") -> Optional[str]:
    """
    Open directory browser dialog.
    Note: This requires Qt integration, placeholder for now.

    Args:
        title: Dialog title

    Returns:
        Selected directory path or None if cancelled
    """
    # This will be implemented in UI layer with Qt
    pass
