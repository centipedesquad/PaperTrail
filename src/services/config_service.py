"""
Configuration service for PaperTrail.
Manages application settings stored in database.
"""

import logging
from typing import Optional, Dict, Any
from database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class ConfigService:
    """Manages application configuration."""

    def __init__(self, db: DatabaseConnection):
        """
        Initialize configuration service.

        Args:
            db: Database connection
        """
        self.db = db

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get configuration value.

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
        try:
            row = self.db.fetch_one(
                "SELECT value FROM settings WHERE key = ?",
                (key,)
            )
            return row['value'] if row else default
        except Exception as e:
            logger.error(f"Failed to get setting {key}: {e}")
            return default

    def set(self, key: str, value: str):
        """
        Set configuration value.

        Args:
            key: Setting key
            value: Setting value
        """
        try:
            with self.db.transaction():
                # Use INSERT OR REPLACE to handle both new and existing keys
                self.db.execute(
                    """
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (key, value)
                )
            logger.debug(f"Set setting {key} = {value}")
        except Exception as e:
            logger.error(f"Failed to set setting {key}: {e}")
            raise

    def get_all(self) -> Dict[str, str]:
        """
        Get all configuration values.

        Returns:
            Dictionary of all settings
        """
        try:
            rows = self.db.fetch_all("SELECT key, value FROM settings")
            return {row['key']: row['value'] for row in rows}
        except Exception as e:
            logger.error(f"Failed to get all settings: {e}")
            return {}

    def delete(self, key: str):
        """
        Delete configuration value.

        Args:
            key: Setting key
        """
        try:
            self.db.execute("DELETE FROM settings WHERE key = ?", (key,))
            self.db.commit()
            logger.debug(f"Deleted setting {key}")
        except Exception as e:
            logger.error(f"Failed to delete setting {key}: {e}")
            raise

    # Convenience methods for common settings

    def get_database_location(self) -> Optional[str]:
        """Get database location setting."""
        return self.get('database_location')

    def set_database_location(self, location: str):
        """Set database location setting."""
        self.set('database_location', location)

    def get_pdf_naming_pattern(self) -> str:
        """Get PDF naming pattern."""
        return self.get('pdf_naming_pattern', '[{author1}_{author2}][{title}][{arxiv_id}].pdf')

    def set_pdf_naming_pattern(self, pattern: str):
        """Set PDF naming pattern."""
        self.set('pdf_naming_pattern', pattern)

    def get_pdf_reader_path(self) -> Optional[str]:
        """Get PDF reader path."""
        return self.get('pdf_reader_path')

    def set_pdf_reader_path(self, path: str):
        """Set PDF reader path."""
        self.set('pdf_reader_path', path)

    def get_download_preference(self) -> str:
        """Get download preference (ask, download, stream)."""
        return self.get('download_preference', 'ask')

    def set_download_preference(self, preference: str):
        """Set download preference."""
        if preference not in ['ask', 'download', 'stream']:
            raise ValueError(f"Invalid download preference: {preference}")
        self.set('download_preference', preference)

    def get_max_fetch_results(self) -> int:
        """Get maximum fetch results."""
        try:
            return int(self.get('max_fetch_results', '50'))
        except ValueError:
            return 50

    def set_max_fetch_results(self, count: int):
        """Set maximum fetch results."""
        self.set('max_fetch_results', str(count))

    def get_fetch_mode(self) -> str:
        """Get fetch mode (new or recent)."""
        return self.get('fetch_mode', 'new')

    def set_fetch_mode(self, mode: str):
        """Set fetch mode."""
        if mode not in ['new', 'recent']:
            raise ValueError(f"Invalid fetch mode: {mode}")
        self.set('fetch_mode', mode)

    def get_recent_days(self) -> int:
        """Get number of recent days for fetching."""
        try:
            return int(self.get('recent_days', '7'))
        except ValueError:
            return 7

    def set_recent_days(self, days: int):
        """Set number of recent days for fetching."""
        self.set('recent_days', str(days))

    def get_theme(self) -> str:
        """Get UI theme."""
        return self.get('theme', 'light')

    def set_theme(self, theme: str):
        """Set UI theme."""
        self.set('theme', theme)

    def get_font_size(self) -> int:
        """Get base font size."""
        try:
            return int(self.get('font_size', '11'))
        except ValueError:
            return 11

    def set_font_size(self, size: int):
        """Set base font size."""
        self.set('font_size', str(size))
