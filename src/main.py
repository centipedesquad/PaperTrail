"""
PaperTrail - arXiv Paper Management Application
Main entry point.
"""

import sys
import os
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import initialize_database, close_database, get_database
from database.migration_manager import MigrationManager
from services.config_service import ConfigService
from services.paper_service import PaperService
from services.fetch_service import FetchService
from services.pdf_service import PDFService
from services.source_service import SourceService
from utils.platform_utils import get_default_data_dir, cleanup_cache_dir, ensure_directory_exists
from ui.main_window import MainWindow
from ui.theme import get_theme_manager, ThemeMode

# Configure logging
# Use user's home directory for log file (writable location)
log_file = os.path.join(Path.home(), '.papertrail.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)

logger = logging.getLogger(__name__)


def migrate_legacy_names():
    """Migrate from myArXiv naming to PaperTrail naming."""
    home = Path.home()

    # Migrate config file
    old_config = home / ".myarxiv_config"
    new_config = home / ".papertrail_config"
    if old_config.exists() and not new_config.exists():
        old_config.rename(new_config)
        logger.info(f"Migrated config: {old_config} -> {new_config}")

    # Migrate log file
    old_log = home / ".myarxiv.log"
    new_log = home / ".papertrail.log"
    if old_log.exists() and not new_log.exists():
        old_log.rename(new_log)

    # Read config to find data directory, then migrate db within it
    config_file = new_config if new_config.exists() else old_config
    if config_file.exists():
        data_dir = config_file.read_text().strip()
        if os.path.exists(data_dir):
            # Migrate database files
            for suffix in ['', '-wal', '-shm']:
                old_db = os.path.join(data_dir, f"myarxiv.db{suffix}")
                new_db = os.path.join(data_dir, f"papertrail.db{suffix}")
                if os.path.exists(old_db) and not os.path.exists(new_db):
                    os.rename(old_db, new_db)
                    logger.info(f"Migrated database: {old_db} -> {new_db}")

        # Migrate data directory name (myArXiv -> PaperTrail)
        if data_dir.endswith("myArXiv") or data_dir.endswith("myArXiv/"):
            new_data_dir = data_dir.rstrip("/").rsplit("myArXiv", 1)[0] + "PaperTrail"
            if os.path.exists(data_dir) and not os.path.exists(new_data_dir):
                os.rename(data_dir, new_data_dir)
                # Update config file to point to new path
                new_config_path = new_config if new_config.exists() else old_config
                new_config_path.write_text(new_data_dir)
                logger.info(f"Migrated data dir: {data_dir} -> {new_data_dir}")


def get_or_create_data_dir() -> str:
    """
    Get or create data directory.
    On first run, prompts user to choose location.

    Returns:
        Path to data directory
    """
    # Check if we have a saved data directory location
    config_file = Path.home() / ".papertrail_config"

    if config_file.exists():
        with open(config_file, 'r') as f:
            saved_path = f.read().strip()
            if os.path.exists(saved_path):
                return saved_path

    # First run - ask user to choose location
    default_dir = get_default_data_dir()

    msg = QMessageBox()
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle("Welcome to PaperTrail")
    msg.setText("First time setup: Choose where to store your data")
    msg.setInformativeText(
        f"PaperTrail needs a location to store your database and PDF files.\n\n"
        f"Default location: {default_dir}\n\n"
        f"Click OK to use default, or Cancel to choose custom location."
    )
    msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    msg.setDefaultButton(QMessageBox.Ok)

    result = msg.exec()

    if result == QMessageBox.Ok:
        data_dir = default_dir
    else:
        # Let user choose custom location
        data_dir = QFileDialog.getExistingDirectory(
            None,
            "Choose Data Directory",
            str(Path.home()),
            QFileDialog.ShowDirsOnly
        )

        if not data_dir:
            # User cancelled, use default
            data_dir = default_dir
        else:
            # Add PaperTrail subdirectory to chosen location
            data_dir = os.path.join(data_dir, "PaperTrail")

    # Create directory structure
    ensure_directory_exists(data_dir)
    ensure_directory_exists(os.path.join(data_dir, "pdfs"))
    ensure_directory_exists(os.path.join(data_dir, "cache"))

    # Save choice
    with open(config_file, 'w') as f:
        f.write(data_dir)

    logger.info(f"Data directory: {data_dir}")
    return data_dir


def initialize_database_schema(data_dir: str):
    """
    Initialize database schema.

    Args:
        data_dir: Data directory path
    """
    db_path = os.path.join(data_dir, "papertrail.db")
    logger.info(f"Initializing database at {db_path}")

    # Initialize database connection
    db = initialize_database(db_path)

    # Run migrations
    migration_manager = MigrationManager(db)

    if migration_manager.needs_migration():
        logger.info("Running database migrations...")
        migration_manager.migrate()
    else:
        logger.info("Database schema up to date")


def cleanup_on_exit(data_dir: str):
    """
    Cleanup operations on application exit.

    Args:
        data_dir: Data directory path
    """
    logger.info("Running cleanup operations...")

    # Clean cache directory
    cache_dir = os.path.join(data_dir, "cache")
    cleanup_cache_dir(cache_dir)

    # Close database
    close_database()

    logger.info("Cleanup complete")


def main():
    """Main application entry point."""
    logger.info("Starting PaperTrail application")

    # Migrate legacy myArXiv file names
    migrate_legacy_names()

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("PaperTrail")
    app.setOrganizationName("PaperTrail")

    try:
        # Get or create data directory
        data_dir = get_or_create_data_dir()

        # Initialize database
        initialize_database_schema(data_dir)

        # Initialize services
        db = get_database()
        config_service = ConfigService(db)
        config_service.set_database_location(data_dir)
        paper_service = PaperService(db)
        fetch_service = FetchService(paper_service)
        pdf_service = PDFService(config_service, paper_service)
        source_service = SourceService(config_service, paper_service)

        # Apply font size setting
        base_font_size = config_service.get_font_size()
        app_font = app.font()
        app_font.setPointSize(base_font_size)
        app.setFont(app_font)
        logger.info(f"Applied base font size: {base_font_size}pt")

        # Initialize and apply theme
        theme_manager = get_theme_manager()
        theme_preference = config_service.get_theme()
        if theme_preference == 'dark':
            theme_manager.set_theme(ThemeMode.DARK)
        else:
            theme_manager.set_theme(ThemeMode.LIGHT)
        theme_manager.apply_to_app(app)
        logger.info(f"Applied {theme_preference} theme")

        # Create and show main window
        main_window = MainWindow(config_service, paper_service, fetch_service, pdf_service,
                                 source_service=source_service)
        main_window.show()

        # Run application
        result = app.exec()

        # Cleanup on exit
        cleanup_on_exit(data_dir)

        logger.info("Application exited normally")
        return result

    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)

        # Show error dialog
        QMessageBox.critical(
            None,
            "Application Error",
            f"An error occurred:\n\n{str(e)}\n\n"
            f"Check papertrail.log for details."
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
