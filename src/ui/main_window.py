"""
Main window for myArXiv application.
Coordinates all UI components.
"""

import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QStatusBar, QMessageBox, QSplitter, QLabel, QDialog, QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence

from ui.widgets.paper_feed_widget import PaperFeedWidget
from ui.widgets.filter_panel_widget import FilterPanelWidget
from ui.dialogs.fetch_papers_dialog import FetchPapersDialog
from ui.dialogs.pdf_action_dialog import PDFActionDialog
from utils.async_utils import FetchWorker, PDFDownloadWorker
from ui.theme import get_theme_manager, ThemeMode

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, config_service, paper_service, fetch_service, pdf_service):
        """
        Initialize main window.

        Args:
            config_service: Configuration service instance
            paper_service: Paper service instance
            fetch_service: Fetch service instance
            pdf_service: PDF service instance
        """
        super().__init__()
        self.config_service = config_service
        self.paper_service = paper_service
        self.fetch_service = fetch_service
        self.pdf_service = pdf_service

        self.setWindowTitle("myArXiv - arXiv Paper Manager")
        self.setMinimumSize(1000, 700)
        self.resize(1400, 900)  # Default size

        # Workers for background operations
        self.fetch_worker = None
        self.pdf_worker = None

        # Initialize UI components
        self._setup_ui()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_shortcuts()

        # Load initial papers and categories
        self._load_categories()
        self._load_papers()

        logger.info("Main window initialized")

    def _setup_ui(self):
        """Setup main UI layout."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)

        # Filter panel (left side)
        self.filter_panel = FilterPanelWidget()
        self.filter_panel.setMinimumWidth(250)
        self.filter_panel.setMaximumWidth(400)
        self.filter_panel.filters_changed.connect(self._on_filters_changed)
        splitter.addWidget(self.filter_panel)

        # Paper feed (right side)
        self.paper_feed = PaperFeedWidget()
        self.paper_feed.view_pdf_requested.connect(self._on_view_pdf)
        self.paper_feed.rating_changed.connect(self._on_rating_changed)
        self.paper_feed.note_changed.connect(self._on_note_changed)
        splitter.addWidget(self.paper_feed)

        # Set splitter proportions (filter panel: 280px, rest: paper feed)
        splitter.setStretchFactor(0, 0)  # Filter panel doesn't stretch
        splitter.setStretchFactor(1, 1)  # Paper feed stretches
        splitter.setSizes([280, 1120])  # Initial sizes

        main_layout.addWidget(splitter)

        # Store reference
        self.splitter = splitter

    def _setup_menubar(self):
        """Setup menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        preferences_action = QAction("&Preferences", self)
        preferences_action.setShortcut(QKeySequence.Preferences)
        preferences_action.triggered.connect(self._show_preferences)
        file_menu.addAction(preferences_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        # TODO: Add edit actions

        # View menu
        view_menu = menubar.addMenu("&View")

        toggle_filter_action = QAction("Toggle &Filter Panel", self)
        toggle_filter_action.setCheckable(True)
        toggle_filter_action.setChecked(True)
        toggle_filter_action.triggered.connect(self._toggle_filter_panel)
        view_menu.addAction(toggle_filter_action)

        view_menu.addSeparator()

        toggle_theme_action = QAction("Toggle &Theme (Light/Dark)", self)
        toggle_theme_action.setShortcut(QKeySequence("Ctrl+T"))
        toggle_theme_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(toggle_theme_action)

        # Papers menu
        papers_menu = menubar.addMenu("&Papers")

        fetch_action = QAction("&Fetch Papers", self)
        fetch_action.setShortcut(QKeySequence("Ctrl+F"))
        fetch_action.triggered.connect(self._fetch_papers)
        papers_menu.addAction(fetch_action)

        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut(QKeySequence.Refresh)
        refresh_action.triggered.connect(self._refresh_papers)
        papers_menu.addAction(refresh_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        """Setup toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Fetch papers button
        fetch_action = QAction("Fetch Papers", self)
        fetch_action.triggered.connect(self._fetch_papers)
        toolbar.addAction(fetch_action)

        # Refresh button
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self._refresh_papers)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        # Settings button
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._show_preferences)
        toolbar.addAction(settings_action)

        # TODO: Add search box to toolbar

    def _setup_statusbar(self):
        """Setup status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self._update_statusbar("Ready")

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Additional shortcuts beyond menu items
        pass

    def _update_statusbar(self, message: str, timeout: int = 0):
        """
        Update status bar message.

        Args:
            message: Status message
            timeout: Timeout in milliseconds (0 for permanent)
        """
        self.statusbar.showMessage(message, timeout)

    def _toggle_filter_panel(self, checked: bool):
        """Toggle filter panel visibility."""
        self.filter_panel.setVisible(checked)

    def _toggle_theme(self):
        """Toggle between light and dark theme."""
        theme_manager = get_theme_manager()

        # Toggle theme
        if theme_manager.current_mode == ThemeMode.LIGHT:
            new_mode = ThemeMode.DARK
            theme_name = 'dark'
        else:
            new_mode = ThemeMode.LIGHT
            theme_name = 'light'

        # Apply new theme
        theme_manager.set_theme(new_mode)
        theme_manager.apply_to_app(QApplication.instance())

        # Save preference
        self.config_service.set_theme(theme_name)

        # Update status bar
        self._update_statusbar(f"Switched to {theme_name} theme", 2000)

        logger.info(f"Theme toggled to: {theme_name}")

    def _fetch_papers(self):
        """Open fetch papers dialog."""
        dialog = FetchPapersDialog(self)
        dialog.fetch_requested.connect(self._start_fetch)

        dialog.exec()

    def _start_fetch(self, mode: str, categories: list, max_results: int, days: int):
        """
        Start fetching papers in background.

        Args:
            mode: Fetch mode ('new' or 'recent')
            categories: List of category codes
            max_results: Maximum results per category
            days: Number of days for recent mode
        """
        # Create fetch function
        if mode == "new":
            fetch_func = lambda: self.fetch_service.fetch_new_papers(
                categories, max_results
            )
        else:
            fetch_func = lambda: self.fetch_service.fetch_recent_papers(
                categories, days, max_results
            )

        # Create worker
        self.fetch_worker = FetchWorker(fetch_func)
        self.fetch_worker.progress.connect(self._on_fetch_progress)
        self.fetch_worker.finished.connect(self._on_fetch_finished)
        self.fetch_worker.error.connect(self._on_fetch_error)

        # Start worker
        self.fetch_worker.start()

        self._update_statusbar("Fetching papers...")

    def _on_fetch_progress(self, percentage: int, message: str):
        """Handle fetch progress updates."""
        self._update_statusbar(message)

    def _on_fetch_finished(self, result: dict):
        """Handle fetch completion."""
        self._update_statusbar(
            f"Fetched {result['created']} new papers ({result['duplicates']} duplicates)",
            5000
        )

        # Reload categories (new categories may have been added)
        self._load_categories()

        # Refresh paper list with current filters
        filters = self.filter_panel.get_filters()
        self._load_papers(filters)

    def _on_fetch_error(self, error: str):
        """Handle fetch error."""
        self._update_statusbar("Fetch failed", 5000)
        QMessageBox.critical(
            self,
            "Fetch Error",
            f"Failed to fetch papers:\n\n{error}"
        )

    def _load_categories(self):
        """Load categories into filter panel."""
        try:
            categories = self.paper_service.get_all_categories()
            self.filter_panel.set_categories(categories)
            logger.info(f"Loaded {len(categories)} categories")
        except Exception as e:
            logger.error(f"Failed to load categories: {e}")

    def _load_papers(self, filters: dict = None):
        """
        Load papers from database and display in feed.

        Args:
            filters: Optional filter dictionary
        """
        try:
            if filters:
                # Apply filters
                papers = self.paper_service.search_papers(
                    search_text=filters.get('search_text'),
                    categories=filters.get('categories'),
                    date_from=filters.get('date_from'),
                    date_to=filters.get('date_to'),
                    has_pdf=filters.get('has_pdf'),
                    has_rating=filters.get('has_rating'),
                    sort_by=filters.get('sort_by', 'date_desc'),
                    limit=100
                )
            else:
                # Load all papers
                papers = self.paper_service.get_all_papers(limit=100)

            self.paper_feed.set_papers(papers)

            # Update status
            count = len(papers)
            if filters and any(filters.values()):
                self._update_statusbar(f"{count} papers found")
            else:
                self._update_statusbar(f"{count} papers loaded")

        except Exception as e:
            logger.error(f"Failed to load papers: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load papers:\n\n{str(e)}"
            )

    def _on_filters_changed(self, filters: dict):
        """Handle filter changes."""
        self._load_papers(filters)

    def _refresh_papers(self):
        """Refresh paper list with current filters."""
        filters = self.filter_panel.get_filters()
        self._load_papers(filters)
        self._update_statusbar("Papers refreshed", 2000)

    def _show_preferences(self):
        """Show preferences dialog."""
        from ui.dialogs.preferences_dialog import PreferencesDialog

        dialog = PreferencesDialog(self.config_service, self)
        if dialog.exec() == QDialog.Accepted:
            # Settings were saved - might need to refresh UI
            self._update_statusbar("Preferences saved", 2000)

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About myArXiv",
            "<h3>myArXiv</h3>"
            "<p>arXiv Paper Management Application</p>"
            "<p>Version 0.5.0</p>"
            "<p>A desktop application for managing arXiv papers with "
            "ratings, notes, PDF organization, and powerful search/filtering.</p>"
        )

    def _on_view_pdf(self, paper_id: int):
        """Handle view PDF request."""
        try:
            # Get paper
            paper = self.paper_service.get_paper(paper_id)
            if not paper:
                QMessageBox.warning(self, "Error", "Paper not found")
                return

            # Check if PDF already exists locally
            if self.pdf_service.has_local_pdf(paper):
                # Open directly
                self._update_statusbar("Opening PDF...")
                success = self.pdf_service.open_pdf(paper)
                if success:
                    self._update_statusbar("PDF opened", 3000)
                else:
                    QMessageBox.critical(
                        self,
                        "Error",
                        "Failed to open PDF. Check that your PDF reader is installed."
                    )
                return

            # Need to download - check user preference
            download_preference = self.config_service.get_download_preference()

            if download_preference == "ask":
                # Show dialog
                dialog = PDFActionDialog(paper.title, self)
                result = dialog.exec()
                if result != QDialog.Accepted:
                    return

                action = dialog.get_action()

                # Save preference if requested
                if dialog.should_remember():
                    self.config_service.set_download_preference(action)

            else:
                action = download_preference

            # Start download in background
            self._start_pdf_download(paper, action)

        except Exception as e:
            logger.error(f"Error viewing PDF: {e}")
            QMessageBox.critical(self, "Error", f"Failed to view PDF:\n\n{str(e)}")

    def _on_rating_changed(self, paper_id: int, importance: str, comprehension: str, technicality: str):
        """
        Handle rating change.

        Args:
            paper_id: Paper ID
            importance: Importance rating
            comprehension: Comprehension rating
            technicality: Technicality rating
        """
        try:
            # Save rating
            self.paper_service.save_rating(
                paper_id,
                importance=importance or None,
                comprehension=comprehension or None,
                technicality=technicality or None
            )

            logger.info(f"Saved rating for paper {paper_id}")
            self._update_statusbar("Rating saved", 2000)

        except Exception as e:
            logger.error(f"Failed to save rating: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save rating:\n\n{str(e)}"
            )

    def _on_note_changed(self, paper_id: int, note_text: str):
        """
        Handle note change.

        Args:
            paper_id: Paper ID
            note_text: Note content
        """
        try:
            # Save note
            if note_text:
                self.paper_service.save_note(paper_id, note_text)
                logger.info(f"Saved note for paper {paper_id}")
            else:
                # Empty note - could delete, but let's just save empty
                self.paper_service.save_note(paper_id, "")

        except Exception as e:
            logger.error(f"Failed to save note: {e}")
            # Don't show error dialog for auto-save failures
            self._update_statusbar("Failed to save note", 3000)

    def _start_pdf_download(self, paper, action: str):
        """
        Start PDF download in background.

        Args:
            paper: Paper object
            action: 'download' or 'stream'
        """
        permanent = (action == "download")

        # Create download function
        def download_func(pdf_url, save_path, progress_callback):
            return self.pdf_service.download_pdf(
                paper,
                permanent=permanent,
                progress_callback=progress_callback
            )

        # Create worker
        self.pdf_worker = PDFDownloadWorker(
            download_func,
            paper.pdf_url,
            ""  # Path determined by service
        )
        self.pdf_worker.progress.connect(self._on_pdf_progress)
        self.pdf_worker.finished.connect(lambda path: self._on_pdf_finished(paper, path))
        self.pdf_worker.error.connect(self._on_pdf_error)

        # Start download
        self.pdf_worker.start()
        self._update_statusbar("Downloading PDF...")

    def _on_pdf_progress(self, percentage: int, message: str):
        """Handle PDF download progress."""
        self._update_statusbar(message)

    def _on_pdf_finished(self, paper, pdf_path: str):
        """Handle PDF download completion."""
        self._update_statusbar("Download complete, opening PDF...", 2000)

        # Open the PDF
        success = self.pdf_service.open_pdf(paper, pdf_path)
        if not success:
            QMessageBox.critical(
                self,
                "Error",
                "PDF downloaded but failed to open. Check that your PDF reader is installed."
            )

    def _on_pdf_error(self, error: str):
        """Handle PDF download error."""
        self._update_statusbar("PDF download failed", 5000)
        QMessageBox.critical(
            self,
            "Download Error",
            f"Failed to download PDF:\n\n{error}"
        )

    def closeEvent(self, event):
        """Handle window close event."""
        logger.info("Closing main window")

        # Cleanup cache directory
        try:
            deleted = self.pdf_service.cleanup_cache()
            logger.info(f"Cleaned up {deleted} cached PDF files")
        except Exception as e:
            logger.error(f"Failed to cleanup cache: {e}")

        event.accept()
