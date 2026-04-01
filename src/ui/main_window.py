"""
Main window for PaperTrail application.
Three-column layout: nav rail | paper feed | context panel.
"""

import os
import re
import sys
import logging
import subprocess
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
from ui.dialogs.arxiv_search_results_dialog import ArxivSearchResultsDialog
from utils.async_utils import (
    FetchWorker, PDFDownloadWorker, ArxivIdWorker,
    ArxivSearchWorker, SourceDownloadWorker
)
from utils.platform_utils import reveal_in_file_manager
from ui.theme import get_theme_manager, ThemeMode

logger = logging.getLogger(__name__)

# arXiv ID pattern: new format (2301.07041) or old format (hep-th/9901001), optional prefix/version
ARXIV_ID_PATTERN = re.compile(
    r'^(?:arxiv:)?'
    r'(\d{4}\.\d{4,5}'
    r'|[a-z.-]+/\d{7})'
    r'(?:v\d+)?$',
    re.IGNORECASE
)


class MainWindow(QMainWindow):
    """Main application window with three-column layout."""

    def __init__(self, config_service, paper_service, fetch_service, pdf_service,
                 source_service=None):
        super().__init__()
        self.config_service = config_service
        self.paper_service = paper_service
        self.fetch_service = fetch_service
        self.pdf_service = pdf_service
        self.source_service = source_service

        self.setWindowTitle("PaperTrail")
        self.setMinimumSize(1000, 700)
        self.resize(1400, 900)

        self.fetch_worker = None
        self.pdf_worker = None
        self.arxiv_id_worker = None
        self.arxiv_search_worker = None
        self.source_worker = None
        self._cursor_override_count = 0
        self._search_generation = 0  # generation counter for stale arXiv result rejection

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
        self.paper_feed.arxiv_search_requested.connect(self._on_arxiv_search_requested)
        self.paper_feed.import_paper_requested.connect(self._on_import_paper_requested)
        splitter.addWidget(self.paper_feed)

        # Right: Context panel (240px)
        self.context_panel = ContextPanelWidget()
        self.context_panel.setMinimumWidth(280)
        self.context_panel.setMaximumWidth(420)
        self.context_panel.view_pdf_requested.connect(self._on_view_pdf)
        self.context_panel.delete_pdf_requested.connect(self._on_delete_pdf)
        self.context_panel.show_pdf_in_finder_requested.connect(self._on_show_pdf_in_finder)
        self.context_panel.view_source_requested.connect(self._on_view_source)
        self.context_panel.delete_source_requested.connect(self._on_delete_source)
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
                # Thread didn't stop — disconnect signals so it can't mutate UI,
                # but don't deleteLater() a still-running thread.
                logger.warning(f"Worker {worker_attr} did not stop in time, disconnecting signals")
                try:
                    worker.disconnect()
                except RuntimeError:
                    pass
                setattr(self, worker_attr, None)
                return
        if worker:
            worker.deleteLater()
            setattr(self, worker_attr, None)

    def _stop_all_workers(self):
        """Cancel and wait on all active workers."""
        for attr in ['fetch_worker', 'pdf_worker', 'source_worker',
                      'arxiv_id_worker', 'arxiv_search_worker']:
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
            total = self.paper_service.get_total_count()
            imported = self.paper_service.get_imported_count()
            self.filter_panel.set_library_counts(total, imported)
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
                    origin=filters.get('origin'),
                    include_downloaded=filters.get('include_downloaded', False),
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
        """Handle search from the feed search bar with arXiv fallback."""
        # Cancel any in-flight arXiv workers
        self._cancel_arxiv_workers()

        if not search_text:
            # Empty search — preserve filter panel state
            filters = self.filter_panel.get_filters()
            filters['sort_by'] = self.paper_feed.get_sort_key()
            self._load_papers(filters)
            return

        # Check if input is an arXiv ID
        match = ARXIV_ID_PATTERN.match(search_text.strip())
        if match:
            arxiv_id = match.group(1)
            self._search_by_arxiv_id(arxiv_id)
            return

        # General text search — try local first
        filters = self.filter_panel.get_filters()
        filters['search_text'] = search_text
        filters['sort_by'] = self.paper_feed.get_sort_key()

        try:
            papers = self.paper_service.search_papers(
                search_text=filters.get('search_text'),
                categories=filters.get('categories'),
                date_from=filters.get('date_from'),
                date_to=filters.get('date_to'),
                has_pdf=filters.get('has_pdf'),
                has_rating=filters.get('has_rating'),
                origin=filters.get('origin'),
                include_downloaded=filters.get('include_downloaded', False),
                sort_by=filters.get('sort_by', 'date_desc'),
                limit=100
            )

            if papers:
                self.paper_feed.set_papers(papers)
                self.paper_feed.append_arxiv_search_option(search_text)
                self._update_statusbar(f"{len(papers)} papers found")
            else:
                # No local results — check if filters are active
                has_active_filters = any(
                    v for k, v in filters.items()
                    if k not in ('search_text', 'sort_by') and v
                )
                if has_active_filters:
                    self.paper_feed.show_filtered_empty()
                else:
                    self.paper_feed.show_arxiv_fallback(search_text)

        except Exception as e:
            logger.error(f"Search failed: {e}")
            self.paper_feed.show_error_message(f"Search error: {e}")

    def _search_by_arxiv_id(self, arxiv_id: str):
        """Handle arXiv ID search: check local first, then fetch preview from arXiv."""
        # Strip version suffix for local lookup
        base_id = re.sub(r'v\d+$', '', arxiv_id, flags=re.IGNORECASE)

        local_paper = self.paper_service.get_paper_by_arxiv_id(base_id)
        if local_paper:
            # Found locally — show it in feed and select it
            self.paper_feed.set_papers([local_paper])
            self.context_panel.set_paper(local_paper)
            self._update_statusbar(f"Found in library: {base_id}")
            return

        # Not local — fetch preview from arXiv (no DB save)
        self.paper_feed.show_loading("Fetching paper from arXiv...")
        self._update_statusbar(f"Looking up {arxiv_id} on arXiv...")

        self._search_generation += 1
        gen = self._search_generation
        self._cleanup_worker('arxiv_id_worker')
        self.arxiv_id_worker = ArxivIdWorker(
            self.fetch_service.fetch_by_arxiv_id_preview, arxiv_id
        )
        self.arxiv_id_worker.finished.connect(
            lambda data, g=gen: self._on_arxiv_id_result(data, g)
        )
        self.arxiv_id_worker.error.connect(
            lambda err, g=gen: self._on_arxiv_id_error(err, g)
        )
        self.arxiv_id_worker.start()

    def _on_arxiv_id_result(self, paper_data, generation: int):
        """Handle arXiv ID lookup result — show preview card."""
        if generation != self._search_generation:
            return  # stale result from a superseded search
        if paper_data:
            try:
                self.paper_feed.show_arxiv_preview(paper_data)
                self._update_statusbar("Paper found on arXiv", 3000)
            except Exception as e:
                logger.error(f"Failed to display arXiv preview: {e}")
                self.paper_feed.show_error_message(f"Error displaying paper: {e}")
        else:
            self.paper_feed.show_error_message("Paper not found on arXiv")
            self._update_statusbar("Paper not found on arXiv", 3000)

    def _on_arxiv_id_error(self, error: str, generation: int):
        if generation != self._search_generation:
            return  # stale error from a superseded search
        self.paper_feed.show_error_message(f"Could not reach arXiv: {error}")
        self._update_statusbar("arXiv lookup failed", 3000)

    def _on_import_paper_requested(self, paper_data: dict):
        """Handle 'Import to Library' button from preview card."""
        try:
            paper_data['origin'] = 'search'
            paper_id = self.paper_service.create_paper(paper_data)
            if paper_id:
                self._update_statusbar("Paper imported to library", 3000)
                # Reload and show the imported paper
                paper = self.paper_service.get_paper(paper_id)
                if paper:
                    self.paper_feed.set_papers([paper])
                    self.context_panel.set_paper(paper)
                self._load_categories()
            else:
                self._update_statusbar("Paper already in library", 3000)
        except Exception as e:
            logger.error(f"Failed to import paper: {e}")
            QMessageBox.critical(self, "Import Error", f"Failed to import paper:\n\n{str(e)}")

    def _on_arxiv_search_requested(self, query: str):
        """Handle 'Search arXiv' button click from fallback indicator."""
        self._cancel_arxiv_workers()
        self._cleanup_worker('arxiv_search_worker')
        self.paper_feed.show_loading("Searching arXiv...")
        self._update_statusbar(f"Searching arXiv for '{query}'...")

        self._search_generation += 1
        gen = self._search_generation
        self.arxiv_search_worker = ArxivSearchWorker(
            self.fetch_service.search_arxiv, query, 50
        )
        self.arxiv_search_worker.finished.connect(
            lambda results, g=gen: self._on_arxiv_search_results(query, results, g)
        )
        self.arxiv_search_worker.error.connect(
            lambda err, g=gen: self._on_arxiv_search_error(err, g)
        )
        self.arxiv_search_worker.start()

    def _on_arxiv_search_results(self, query: str, results: list, generation: int):
        """Handle arXiv search results — open picker dialog."""
        if generation != self._search_generation:
            return  # stale result
        if not results:
            self.paper_feed.show_error_message(
                f'No papers found on arXiv for "{query}".\nTry different search terms.'
            )
            self._update_statusbar("No arXiv results", 3000)
            return

        dialog = ArxivSearchResultsDialog(query, results, self)
        dialog.import_requested.connect(self._on_batch_import)
        dialog.exec()

    def _on_arxiv_search_error(self, error: str, generation: int):
        if generation != self._search_generation:
            return  # stale error from a superseded search
        self.paper_feed.show_error_message(f"Could not reach arXiv.\n{error}")
        self._update_statusbar("arXiv search failed", 3000)

    def _on_batch_import(self, selected_papers: list):
        """Import selected papers from the picker dialog."""
        try:
            for pd in selected_papers:
                pd['origin'] = 'search'
            result = self.fetch_service.import_papers(selected_papers)
            imported = result['imported']
            duplicates = result['duplicates']
            errors = result.get('errors', 0)
            parts = [f"Imported {imported} papers"]
            if duplicates > 0:
                parts.append(f"{duplicates} duplicates skipped")
            if errors > 0:
                parts.append(f"{errors} errors")
            self._update_statusbar(", ".join(parts), 5000)

            # Refresh feed and categories
            self._load_categories()
            self._load_papers(self._build_current_filters())
            self.context_panel.clear_selection()
        except Exception as e:
            logger.error(f"Batch import failed: {e}")
            QMessageBox.critical(self, "Import Error", f"Failed to import papers:\n\n{str(e)}")

    def _cancel_arxiv_workers(self):
        """Cancel any in-flight arXiv workers."""
        if self.arxiv_id_worker and self.arxiv_id_worker.isRunning():
            self.arxiv_id_worker.cancel()
        if self.arxiv_search_worker and self.arxiv_search_worker.isRunning():
            self.arxiv_search_worker.cancel()

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

    def _on_show_pdf_in_finder(self, paper_id: int):
        """Reveal the downloaded PDF in the system file manager."""
        try:
            paper = self.paper_service.get_paper(paper_id)
            if not paper:
                return

            if not self.pdf_service.has_local_pdf(paper):
                self._update_statusbar("No local PDF to reveal", 3000)
                return

            if not reveal_in_file_manager(paper.local_pdf_path):
                QMessageBox.warning(self, "Error", "Failed to reveal PDF in file manager.")
        except Exception as e:
            logger.error(f"Error revealing PDF: {e}")

    # --- Source file actions ---

    def _on_view_source(self, paper_id: int):
        """Handle 'Download Source' button from context panel."""
        if not self.source_service:
            QMessageBox.warning(self, "Error", "Source service not available.")
            return
        try:
            paper = self.paper_service.get_paper(paper_id)
            if not paper:
                return

            if self.source_service.has_local_source(paper):
                self.source_service.open_source(paper)
                self._update_statusbar("Source folder opened", 3000)
                return

            # Ask download or stream
            dialog = PDFActionDialog(paper.title, self)
            dialog.setWindowTitle("Download Source")
            result = dialog.exec()
            if result != QDialog.Accepted:
                return
            action = dialog.get_action()
            permanent = (action == "download")

            self._start_source_download(paper, permanent)

        except Exception as e:
            logger.error(f"Error viewing source: {e}")
            QMessageBox.critical(self, "Error", f"Failed to view source:\n\n{str(e)}")

    def _start_source_download(self, paper, permanent: bool):
        self._cleanup_worker('source_worker')
        self.source_worker = SourceDownloadWorker(
            self.source_service.download_source, paper, permanent
        )
        self.source_worker.progress.connect(self._on_source_progress)
        paper_id = paper.id
        self.source_worker.finished.connect(
            lambda path, pid=paper_id: self._on_source_finished(pid, path)
        )
        self.source_worker.error.connect(self._on_source_error)
        self.source_worker.start()
        self._push_wait_cursor()
        self._update_statusbar("Downloading source files...")

    def _on_source_progress(self, percentage: int, message: str):
        self._update_statusbar(message)

    def _on_source_finished(self, paper_id: int, source_path: str):
        self._pop_wait_cursor()
        self._update_statusbar("Source files ready", 3000)
        # Open the downloaded path directly (works for both permanent and stream mode)
        try:
            if os.path.exists(source_path):
                if sys.platform == 'darwin':
                    subprocess.Popen(['open', source_path])
                else:
                    subprocess.Popen(['xdg-open', source_path])
            else:
                logger.error(f"Source path not found: {source_path}")
        except Exception as e:
            logger.error(f"Failed to open source directory: {e}")
        # Refresh context panel only if this paper is still selected
        if (self.context_panel.current_paper and
                self.context_panel.current_paper.id == paper_id):
            paper = self.paper_service.get_paper(paper_id)
            if paper:
                self.context_panel.set_paper(paper)

    def _on_source_error(self, error: str):
        self._pop_wait_cursor()
        self._update_statusbar("Source download failed", 5000)
        QMessageBox.critical(self, "Source Error", f"Failed to download source files:\n\n{error}")

    def _on_delete_source(self, paper_id: int):
        if not self.source_service:
            return
        try:
            paper = self.paper_service.get_paper(paper_id)
            if not paper or not self.source_service.has_local_source(paper):
                self._update_statusbar("No local source to delete", 3000)
                return

            reply = QMessageBox.question(
                self, "Delete Source",
                f"Delete the local source files for:\n\n{paper.title}",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            if self.source_service.delete_source(paper):
                self._update_statusbar("Source files deleted", 3000)
                full_paper = self.paper_service.get_paper(paper_id)
                if full_paper:
                    self.context_panel.set_paper(full_paper)
            else:
                QMessageBox.critical(self, "Error", "Failed to delete source files.")
        except Exception as e:
            logger.error(f"Error deleting source: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete source:\n\n{str(e)}")

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
        # Re-fetch to reflect last_accessed update, only if still selected
        if (self.context_panel.current_paper and
                self.context_panel.current_paper.id == paper_id):
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
            "<p>Version 0.7.0</p>"
        )

    def closeEvent(self, event):
        logger.info("Closing main window")
        self._stop_all_workers()
        try:
            deleted = self.pdf_service.cleanup_cache()
            logger.info(f"Cleaned up {deleted} cached PDF files")
        except Exception as e:
            logger.error(f"Failed to cleanup cache: {e}")
        try:
            if self.source_service:
                deleted = self.source_service.cleanup_cache()
                logger.info(f"Cleaned up {deleted} cached source items")
        except Exception as e:
            logger.error(f"Failed to cleanup source cache: {e}")
        event.accept()
