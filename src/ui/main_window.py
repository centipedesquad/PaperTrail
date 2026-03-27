"""
Main window for PaperTrail application.
Three-column layout: nav rail | paper feed | context panel.
"""

import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QStatusBar, QMessageBox, QSplitter, QLabel, QDialog, QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QCursor

from ui.widgets.paper_feed_widget import PaperFeedWidget
from ui.widgets.filter_panel_widget import FilterPanelWidget
from ui.widgets.context_panel_widget import ContextPanelWidget
from ui.dialogs.fetch_papers_dialog import FetchPapersDialog
from ui.dialogs.pdf_action_dialog import PDFActionDialog
from utils.async_utils import FetchWorker, PDFDownloadWorker
from ui.theme import get_theme_manager, ThemeMode

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window with three-column layout."""

    def __init__(self, config_service, paper_service, fetch_service, pdf_service):
        super().__init__()
        self.config_service = config_service
        self.paper_service = paper_service
        self.fetch_service = fetch_service
        self.pdf_service = pdf_service

        self.setWindowTitle("PaperTrail")
        self.setMinimumSize(1000, 700)
        self.resize(1400, 900)

        self.fetch_worker = None
        self.pdf_worker = None
        self._cursor_override_count = 0

        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()
        self._setup_shortcuts()

        # Subscribe to theme changes so apply_to_app fires for programmatic changes
        theme = get_theme_manager()
        theme.add_theme_listener(self._on_theme_changed)

        # Load initial data
        self._load_categories()
        self._load_papers()

        logger.info("Main window initialized")

    def _setup_ui(self):
        """Setup three-column layout: nav rail | feed | context panel."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        # Left: Nav rail (180px)
        self.filter_panel = FilterPanelWidget()
        self.filter_panel.setMinimumWidth(200)
        self.filter_panel.setMaximumWidth(300)
        self.filter_panel.filters_changed.connect(self._on_filters_changed)
        splitter.addWidget(self.filter_panel)

        # Center: Paper feed (flexible)
        self.paper_feed = PaperFeedWidget()
        self.paper_feed.paper_selected.connect(self._on_paper_selected)
        self.paper_feed.search_requested.connect(self._on_search_requested)
        self.paper_feed.sort_changed.connect(self._on_sort_changed)
        splitter.addWidget(self.paper_feed)

        # Right: Context panel (240px)
        self.context_panel = ContextPanelWidget()
        self.context_panel.setMinimumWidth(280)
        self.context_panel.setMaximumWidth(420)
        self.context_panel.view_pdf_requested.connect(self._on_view_pdf)
        self.context_panel.delete_pdf_requested.connect(self._on_delete_pdf)
        self.context_panel.rating_changed.connect(self._on_rating_changed)
        self.context_panel.note_changed.connect(self._on_note_changed)
        splitter.addWidget(self.context_panel)

        # Splitter proportions
        splitter.setStretchFactor(0, 0)  # Nav rail: fixed
        splitter.setStretchFactor(1, 1)  # Feed: stretches
        splitter.setStretchFactor(2, 0)  # Context: fixed
        splitter.setSizes([230, 840, 330])
        splitter.setHandleWidth(3)

        main_layout.addWidget(splitter)
        self.splitter = splitter

    def _setup_menubar(self):
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

        # View menu
        view_menu = menubar.addMenu("&View")

        toggle_theme_action = QAction("Toggle &Theme (Light/Dark)", self)
        toggle_theme_action.setShortcut(QKeySequence("Ctrl+T"))
        toggle_theme_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(toggle_theme_action)

        # Papers menu
        papers_menu = menubar.addMenu("&Papers")

        fetch_action = QAction("&Fetch Papers", self)
        fetch_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        fetch_action.triggered.connect(self._fetch_papers)
        papers_menu.addAction(fetch_action)

        search_action = QAction("&Search", self)
        search_action.setShortcut(QKeySequence("Ctrl+F"))
        search_action.triggered.connect(lambda: self.paper_feed.search_input.setFocus())
        papers_menu.addAction(search_action)

        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut(QKeySequence.Refresh)
        refresh_action.triggered.connect(self._refresh_papers)
        papers_menu.addAction(refresh_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self._update_statusbar("Ready")

    def _setup_shortcuts(self):
        pass

    def _update_statusbar(self, message: str, timeout: int = 0):
        self.statusbar.showMessage(message, timeout)

    def _toggle_theme(self):
        theme_manager = get_theme_manager()

        if theme_manager.current_mode == ThemeMode.LIGHT:
            new_mode = ThemeMode.DARK
            theme_name = 'dark'
        else:
            new_mode = ThemeMode.LIGHT
            theme_name = 'light'

        theme_manager.set_theme(new_mode)
        theme_manager.apply_to_app(QApplication.instance())

        self.config_service.set_theme(theme_name)
        self._update_statusbar(f"Switched to {theme_name} theme", 2000)
        logger.info(f"Theme toggled to: {theme_name}")

    def _on_theme_changed(self):
        """Handle theme change — reapply global stylesheet."""
        theme_manager = get_theme_manager()
        theme_manager.apply_to_app(QApplication.instance())

    # --- Worker lifecycle helpers ---

    def _cleanup_worker(self, worker_attr: str):
        """Cancel and clean up a worker before replacing it."""
        worker = getattr(self, worker_attr, None)
        if worker and worker.isRunning():
            worker.cancel()
            if not worker.wait(2000):
                # Thread didn't stop — don't destroy it, let it finish naturally
                logger.warning(f"Worker {worker_attr} did not stop in time, skipping cleanup")
                return
        if worker:
            worker.deleteLater()
            setattr(self, worker_attr, None)

    def _stop_all_workers(self):
        """Cancel and wait on all active workers."""
        for attr in ['fetch_worker', 'pdf_worker']:
            worker = getattr(self, attr, None)
            if worker and worker.isRunning():
                worker.cancel()
                worker.wait(3000)

    def _push_wait_cursor(self):
        """Push a wait cursor (nestable)."""
        self._cursor_override_count += 1
        if self._cursor_override_count == 1:
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

    def _pop_wait_cursor(self):
        """Pop a wait cursor (nestable)."""
        if self._cursor_override_count > 0:
            self._cursor_override_count -= 1
            if self._cursor_override_count == 0:
                QApplication.restoreOverrideCursor()

    def _build_current_filters(self) -> dict:
        """Build complete filter dict from filter panel + search bar state."""
        filters = self.filter_panel.get_filters()
        search_text = self.paper_feed.get_search_text()
        if search_text:
            filters['search_text'] = search_text
        filters['sort_by'] = self.paper_feed.get_sort_key()
        return filters

    # --- Data loading ---

    def _load_categories(self):
        try:
            categories = self.paper_service.get_all_categories()
            category_counts = self.paper_service.get_category_counts()
            self.filter_panel.set_categories(categories, category_counts)
            logger.info(f"Loaded {len(categories)} categories with counts")
        except Exception as e:
            logger.error(f"Failed to load categories: {e}")

    def _load_papers(self, filters: dict = None):
        try:
            if filters:
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
                papers = self.paper_service.get_all_papers(limit=100)

            self.paper_feed.set_papers(papers)

            count = len(papers)
            if filters and any(v for k, v in filters.items() if k != 'sort_by'):
                self._update_statusbar(f"{count} papers found")
            else:
                self._update_statusbar(f"{count} papers loaded")

        except Exception as e:
            logger.error(f"Failed to load papers: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load papers:\n\n{str(e)}")

    # --- Signal handlers ---

    def _on_filters_changed(self, filters: dict):
        """Handle nav rail filter changes."""
        # Check for action items
        action = filters.get("_action")
        if action == "action_fetch":
            self._fetch_papers()
            return
        elif action == "action_prefs":
            self._show_preferences()
            return

        # Update feed title
        label = self.filter_panel.get_active_label()
        self.paper_feed.set_feed_title(label)

        # Merge with search text if present
        search_text = self.paper_feed.get_search_text()
        if search_text:
            filters['search_text'] = search_text

        # Merge sort
        filters['sort_by'] = self.paper_feed.get_sort_key()

        self._load_papers(filters)
        self.context_panel.clear_selection()

    def _on_paper_selected(self, paper):
        """Handle paper selection in the feed."""
        # Reload full paper data (with ratings, notes)
        full_paper = self.paper_service.get_paper(paper.id)
        if full_paper:
            self.context_panel.set_paper(full_paper)

    def _on_search_requested(self, search_text: str):
        """Handle search from the feed search bar."""
        filters = self.filter_panel.get_filters()
        if search_text:
            filters['search_text'] = search_text
        filters['sort_by'] = self.paper_feed.get_sort_key()
        self._load_papers(filters)

    def _on_sort_changed(self, sort_key: str):
        """Handle sort change from the feed."""
        filters = self.filter_panel.get_filters()
        search_text = self.paper_feed.get_search_text()
        if search_text:
            filters['search_text'] = search_text
        filters['sort_by'] = sort_key
        self._load_papers(filters)

    # --- Paper actions (from context panel) ---

    def _on_view_pdf(self, paper_id: int):
        try:
            paper = self.paper_service.get_paper(paper_id)
            if not paper:
                QMessageBox.warning(self, "Error", "Paper not found")
                return

            if self.pdf_service.has_local_pdf(paper):
                self._update_statusbar("Opening PDF...")
                success = self.pdf_service.open_pdf(paper)
                if success:
                    self._update_statusbar("PDF opened", 3000)
                else:
                    QMessageBox.critical(self, "Error", "Failed to open PDF. Check that your PDF reader is installed.")
                return

            download_preference = self.config_service.get_download_preference()

            if download_preference == "ask":
                dialog = PDFActionDialog(paper.title, self)
                result = dialog.exec()
                if result != QDialog.Accepted:
                    return
                action = dialog.get_action()
                if dialog.should_remember():
                    self.config_service.set_download_preference(action)
            else:
                action = download_preference

            self._start_pdf_download(paper, action)

        except Exception as e:
            logger.error(f"Error viewing PDF: {e}")
            QMessageBox.critical(self, "Error", f"Failed to view PDF:\n\n{str(e)}")

    def _on_delete_pdf(self, paper_id: int):
        try:
            paper = self.paper_service.get_paper(paper_id)
            if not paper:
                return

            if not self.pdf_service.has_local_pdf(paper):
                self._update_statusbar("No local PDF to delete", 3000)
                return

            reply = QMessageBox.question(
                self, "Delete PDF",
                f"Delete the local PDF for:\n\n{paper.title}\n\nThe paper entry will be kept.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            success = self.pdf_service.delete_pdf(paper)
            if success:
                self._update_statusbar("PDF deleted", 3000)
                # Refresh context panel
                full_paper = self.paper_service.get_paper(paper_id)
                if full_paper:
                    self.context_panel.set_paper(full_paper)
            else:
                QMessageBox.critical(self, "Error", "Failed to delete PDF.")

        except Exception as e:
            logger.error(f"Error deleting PDF: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete PDF:\n\n{str(e)}")

    def _on_rating_changed(self, paper_id: int, importance: str, comprehension: str, technicality: str):
        try:
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
            QMessageBox.critical(self, "Error", f"Failed to save rating:\n\n{str(e)}")

    def _on_note_changed(self, paper_id: int, note_text: str):
        try:
            if note_text:
                self.paper_service.save_note(paper_id, note_text)
                logger.info(f"Saved note for paper {paper_id}")
            else:
                self.paper_service.save_note(paper_id, "")
        except Exception as e:
            logger.error(f"Failed to save note: {e}")
            self._update_statusbar("Failed to save note", 3000)

    # --- Fetch / Download ---

    def _fetch_papers(self):
        self.fetch_dialog = FetchPapersDialog(config_service=self.config_service, parent=self)
        self.fetch_dialog.fetch_requested.connect(self._start_fetch)
        self.fetch_dialog.exec()

    def _start_fetch(self, mode: str, categories: list, max_results: int, days: int):
        self._cleanup_worker('fetch_worker')

        if mode == "new":
            fetch_func = lambda: self.fetch_service.fetch_new_papers(categories, max_results)
        else:
            fetch_func = lambda: self.fetch_service.fetch_recent_papers(categories, days, max_results)

        self.fetch_worker = FetchWorker(fetch_func)
        self.fetch_worker.progress.connect(self._on_fetch_progress)
        self.fetch_worker.finished.connect(self._on_fetch_finished)
        self.fetch_worker.error.connect(self._on_fetch_error)
        self.fetch_worker.start()

        self._push_wait_cursor()
        self._update_statusbar("Fetching papers...")

    def _on_fetch_progress(self, percentage: int, message: str):
        self._update_statusbar(message)
        if hasattr(self, 'fetch_dialog') and self.fetch_dialog:
            self.fetch_dialog.set_progress(percentage, message)

    def _on_fetch_finished(self, result: dict):
        self._pop_wait_cursor()
        errors = result.get('errors', 0)
        msg = f"Fetched {result['created']} new papers ({result['duplicates']} duplicates)"
        if errors:
            msg += f", {errors} errors"
        self._update_statusbar(msg, 5000)

        if hasattr(self, 'fetch_dialog') and self.fetch_dialog:
            self.fetch_dialog.fetch_complete(result)

        self._load_categories()
        self._load_papers(self._build_current_filters())
        self.context_panel.clear_selection()

    def _on_fetch_error(self, error: str):
        self._pop_wait_cursor()
        self._update_statusbar("Fetch failed", 5000)

        if hasattr(self, 'fetch_dialog') and self.fetch_dialog:
            self.fetch_dialog.fetch_failed(error)
        else:
            QMessageBox.critical(self, "Fetch Error", f"Failed to fetch papers:\n\n{error}")

    def _refresh_papers(self):
        self._load_papers(self._build_current_filters())
        self.context_panel.clear_selection()
        self._update_statusbar("Papers refreshed", 2000)

    def _start_pdf_download(self, paper, action: str):
        self._cleanup_worker('pdf_worker')
        permanent = (action == "download")

        def download_func(progress_callback):
            return self.pdf_service.download_pdf(paper, permanent=permanent, progress_callback=progress_callback)

        self.pdf_worker = PDFDownloadWorker(download_func)
        self.pdf_worker.progress.connect(self._on_pdf_progress)
        paper_id = paper.id
        self.pdf_worker.finished.connect(lambda path, pid=paper_id: self._on_pdf_finished(pid, path))
        self.pdf_worker.error.connect(self._on_pdf_error)
        self.pdf_worker.start()
        self._push_wait_cursor()
        self._update_statusbar("Downloading PDF...")

    def _on_pdf_progress(self, percentage: int, message: str):
        self._update_statusbar(message)

    def _on_pdf_finished(self, paper_id: int, pdf_path: str):
        self._pop_wait_cursor()
        self._update_statusbar("Download complete, opening PDF...", 2000)
        paper = self.paper_service.get_paper(paper_id)
        if not paper:
            QMessageBox.critical(self, "Error", "Paper not found after download.")
            return
        success = self.pdf_service.open_pdf(paper, pdf_path)
        if not success:
            QMessageBox.critical(self, "Error", "PDF downloaded but failed to open.")
        # Re-fetch to reflect last_accessed update from open_pdf
        paper = self.paper_service.get_paper(paper_id)
        if paper:
            self.context_panel.set_paper(paper)

    def _on_pdf_error(self, error: str):
        self._pop_wait_cursor()
        self._update_statusbar("PDF download failed", 5000)
        QMessageBox.critical(self, "Download Error", f"Failed to download PDF:\n\n{error}")

    # --- Dialogs ---

    def _show_preferences(self):
        from ui.dialogs.preferences_dialog import PreferencesDialog
        dialog = PreferencesDialog(self.config_service, self)
        if dialog.exec() == QDialog.Accepted:
            self._update_statusbar("Preferences saved", 2000)

    def _show_about(self):
        QMessageBox.about(
            self, "About PaperTrail",
            "<h3>PaperTrail</h3>"
            "<p>arXiv Paper Management Application</p>"
            "<p>Version 0.6.2</p>"
        )

    def closeEvent(self, event):
        logger.info("Closing main window")
        self._stop_all_workers()
        try:
            deleted = self.pdf_service.cleanup_cache()
            logger.info(f"Cleaned up {deleted} cached PDF files")
        except Exception as e:
            logger.error(f"Failed to cleanup cache: {e}")
        event.accept()
