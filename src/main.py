"""
myArXiv - arXiv Paper Management Application
Main entry point.
"""

import sys
import os
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PySide6.QtCore import Qt

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import initialize_database, close_database, get_database
from database.migration_manager import MigrationManager
from services.config_service import ConfigService
from services.paper_service import PaperService
from services.fetch_service import FetchService
from services.pdf_service import PDFService
from utils.platform_utils import get_default_data_dir, cleanup_cache_dir, ensure_directory_exists
from ui.main_window import MainWindow

# Configure logging
# Use user's home directory for log file (writable location)
log_file = os.path.join(Path.home(), '.myarxiv.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)

logger = logging.getLogger(__name__)


def get_or_create_data_dir() -> str:
    """
    Get or create data directory.
    On first run, prompts user to choose location.

    Returns:
        Path to data directory
    """
    # Check if we have a saved data directory location
    config_file = Path.home() / ".myarxiv_config"

    if config_file.exists():
        with open(config_file, 'r') as f:
            saved_path = f.read().strip()
            if os.path.exists(saved_path):
                return saved_path

    # First run - ask user to choose location
    default_dir = get_default_data_dir()

    msg = QMessageBox()
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle("Welcome to myArXiv")
    msg.setText("First time setup: Choose where to store your data")
    msg.setInformativeText(
        f"myArXiv needs a location to store your database and PDF files.\n\n"
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
            # Add myArXiv subdirectory to chosen location
            data_dir = os.path.join(data_dir, "myArXiv")

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
    db_path = os.path.join(data_dir, "myarxiv.db")
    logger.info(f"Initializing database at {db_path}")

    # Initialize database connection
    db = initialize_database(db_path)

    # Run migrations
    migrations_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "database",
        "migrations"
    )

    migration_manager = MigrationManager(db, migrations_dir)

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
    logger.info("Starting myArXiv application")

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("myArXiv")
    app.setOrganizationName("myArXiv")

    try:
        # Get or create data directory
        data_dir = get_or_create_data_dir()

        # Initialize database
        initialize_database_schema(data_dir)

        # Initialize services
        db = get_database()
        config_service = ConfigService(db)
        paper_service = PaperService(db)
        fetch_service = FetchService(paper_service)
        pdf_service = PDFService(config_service, paper_service)

        # Save data directory to settings
        config_service.set_database_location(data_dir)

        # Create and show main window
        main_window = MainWindow(config_service, paper_service, fetch_service, pdf_service)
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
            f"Check myarxiv.log for details."
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
