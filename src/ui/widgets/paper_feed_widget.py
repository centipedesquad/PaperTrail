"""
Paper feed widget.
Scrollable list of paper cards with search bar and feed header.
"""

import logging
from typing import List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QLineEdit, QComboBox, QPushButton, QApplication
)
from PySide6.QtCore import Qt, Signal
from models import Paper
from ui.widgets.paper_cell_widget import PaperCellWidget
from ui.theme import get_theme_manager

logger = logging.getLogger(__name__)


class PaperFeedWidget(QWidget):
    """Paper feed with search bar, header, and selectable paper cards."""

    # Signals
    paper_selected = Signal(object)  # Paper object
    search_requested = Signal(str)   # search text
    sort_changed = Signal(str)       # sort key
    arxiv_search_requested = Signal(str)  # search text for arXiv fallback
    import_paper_requested = Signal(dict)  # paper data dict to import

    def __init__(self, parent=None):
        super().__init__(parent)
        self.paper_cells = []
        self.selected_cell = None
        self._current_filter_label = "All Papers"
        self._setup_ui()

    def _setup_ui(self):
        theme = get_theme_manager()
        base_font_size = QApplication.instance().font().pointSize() or 11

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Feed header ---
        header_widget = QWidget()
        header_widget.setStyleSheet(f"""
            background-color: {theme.get_color('background')};
            border-bottom: 1px solid {theme.get_color('border')};
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 16, 20, 12)
        header_layout.setSpacing(12)

        # Title row
        title_row = QHBoxLayout()
        self.feed_title = QLabel("All Papers")
        self.feed_title.setFont(theme.get_display_font(size_pt=int(base_font_size * 1.6)))
        self.feed_title.setStyleSheet(f"color: {theme.get_color('text_primary')}; border: none;")
        title_row.addWidget(self.feed_title)

        self.feed_meta = QLabel("")
        self.feed_meta.setFont(theme.get_mono_font(size_pt=int(base_font_size * 0.82)))
        self.feed_meta.setStyleSheet(f"color: {theme.get_color('text_tertiary')}; border: none;")
        title_row.addWidget(self.feed_meta)
        title_row.addStretch()

        header_layout.addLayout(title_row)

        # Search + sort row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search titles, authors, abstracts...")
        self.search_input.returnPressed.connect(self._on_search)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.get_color('surface')};
                border: 1px solid {theme.get_color('border')};
                border-radius: 2px;
                padding: 8px 12px;
                color: {theme.get_color('text_primary')};
            }}
            QLineEdit:focus {{
                border-color: {theme.get_color('primary')};
            }}
        """)
        search_row.addWidget(self.search_input, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Newest", "date_desc")
        self.sort_combo.addItem("Oldest", "date_asc")
        self.sort_combo.addItem("Title A-Z", "title_asc")
        self.sort_combo.addItem("Title Z-A", "title_desc")
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        search_row.addWidget(self.sort_combo)

        header_layout.addLayout(search_row)

        main_layout.addWidget(header_widget)

        # --- Scroll area for paper cards ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.container_widget = QWidget()
        self.container_layout = QVBoxLayout(self.container_widget)
        self.container_layout.setContentsMargins(16, 0, 16, 16)
        self.container_layout.setSpacing(0)
        self.container_layout.setAlignment(Qt.AlignTop)

        # Empty state
        self.empty_label = QLabel("No papers to display.\n\nClick 'Fetch Papers' to get started.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.get_color('text_tertiary')};
                font-size: 14pt;
                padding: 50px;
            }}
        """)
        self.container_layout.addWidget(self.empty_label)

        scroll_area.setWidget(self.container_widget)
        main_layout.addWidget(scroll_area)

    def set_feed_title(self, title: str):
        """Set the feed header title (e.g., 'All Papers', 'cs.LG')."""
        self._current_filter_label = title
        self.feed_title.setText(title)

    def set_papers(self, papers: List[Paper]):
        """Display papers in the feed."""
        self.clear_papers()

        if not papers:
            self.empty_label.setVisible(True)
            self.feed_meta.setText("")
            return

        self.empty_label.setVisible(False)
        sort_text = self.sort_combo.currentText().lower()
        self.feed_meta.setText(f"{len(papers)} papers \u00b7 sorted by {sort_text}")

        for paper in papers:
            cell = PaperCellWidget(paper)
            cell.clicked.connect(self._on_cell_clicked)
            self.container_layout.addWidget(cell)
            self.paper_cells.append(cell)

        logger.info(f"Displaying {len(papers)} papers in feed")

    def clear_papers(self):
        """Clear all papers from the feed."""
        self.selected_cell = None
        for cell in self.paper_cells:
            cell.deleteLater()
        self.paper_cells.clear()

    def get_paper_count(self) -> int:
        return len(self.paper_cells)

    def get_search_text(self) -> str:
        return self.search_input.text().strip()

    def get_sort_key(self) -> str:
        return self.sort_combo.currentData() or "date_desc"

    def _on_cell_clicked(self, paper: Paper):
        """Handle paper card click — select it."""
        # Deselect previous
        if self.selected_cell:
            self.selected_cell.set_selected(False)

        # Find and select the clicked cell
        for cell in self.paper_cells:
            if cell.paper.id == paper.id:
                cell.set_selected(True)
                self.selected_cell = cell
                break

        self.paper_selected.emit(paper)

    def _on_search(self):
        self.search_requested.emit(self.search_input.text().strip())

    def _on_sort_changed(self):
        self.sort_changed.emit(self.sort_combo.currentData() or "date_desc")

    # --- arXiv fallback and preview ---

    def show_arxiv_fallback(self, query: str):
        """Show 'No local matches' with a 'Search arXiv' button."""
        self.clear_papers()
        self.empty_label.setVisible(False)

        theme = get_theme_manager()

        fallback_widget = QWidget()
        fallback_widget.setObjectName("arxiv_fallback")
        fallback_layout = QVBoxLayout(fallback_widget)
        fallback_layout.setAlignment(Qt.AlignCenter)
        fallback_layout.setContentsMargins(50, 50, 50, 50)
        fallback_layout.setSpacing(16)

        msg = QLabel(f'No papers match "{query}"\nin your library.')
        msg.setAlignment(Qt.AlignCenter)
        msg.setFont(theme.get_body_font(size_pt=13))
        msg.setStyleSheet(f"color: {theme.get_color('text_primary')};")
        fallback_layout.addWidget(msg)

        btn = QPushButton("Search arXiv")
        btn.setFont(theme.get_body_font(size_pt=11))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {theme.get_color('primary')};
                color: {theme.get_color('primary')};
                background: transparent;
                border-radius: 2px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_light')};
            }}
        """)
        btn.clicked.connect(lambda: self.arxiv_search_requested.emit(query))
        fallback_layout.addWidget(btn, alignment=Qt.AlignCenter)

        self.container_layout.addWidget(fallback_widget)
        self.paper_cells.append(fallback_widget)  # track for cleanup
        self.feed_meta.setText("")

    def append_arxiv_search_option(self, query: str):
        """Append a 'Search arXiv' button at the end of the current results."""
        theme = get_theme_manager()

        divider = QWidget()
        divider_layout = QVBoxLayout(divider)
        divider_layout.setAlignment(Qt.AlignCenter)
        divider_layout.setContentsMargins(20, 16, 20, 16)
        divider_layout.setSpacing(8)

        hint = QLabel("Not finding what you need?")
        hint.setAlignment(Qt.AlignCenter)
        hint.setFont(theme.get_body_font(size_pt=11))
        hint.setStyleSheet(f"color: {theme.get_color('text_tertiary')};")
        divider_layout.addWidget(hint)

        btn = QPushButton("Search arXiv")
        btn.setFont(theme.get_body_font(size_pt=11))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {theme.get_color('primary')};
                color: {theme.get_color('primary')};
                background: transparent;
                border-radius: 2px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_light')};
            }}
        """)
        btn.clicked.connect(lambda: self.arxiv_search_requested.emit(query))
        divider_layout.addWidget(btn, alignment=Qt.AlignCenter)

        self.container_layout.addWidget(divider)
        self.paper_cells.append(divider)  # track for cleanup

    def show_filtered_empty(self):
        """Show 'No results (filters active)' — no arXiv fallback."""
        self.clear_papers()
        self.empty_label.setText("No results (filters active)")
        self.empty_label.setVisible(True)
        self.feed_meta.setText("")

    def show_loading(self, message: str = "Searching..."):
        """Show a loading message in the feed area."""
        self.clear_papers()
        self.empty_label.setText(message)
        self.empty_label.setVisible(True)
        self.feed_meta.setText("")

    def show_arxiv_preview(self, paper_data: dict):
        """Show a preview card for an arXiv paper not yet in the library."""
        self.clear_papers()
        self.empty_label.setVisible(False)
        theme = get_theme_manager()

        card = QWidget()
        card.setObjectName("arxiv_preview")
        card.setStyleSheet(f"""
            QWidget#arxiv_preview {{
                background-color: {theme.get_color('primary_light')};
                border-radius: 4px;
                margin: 16px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(6)

        # Title
        title = QLabel(paper_data.get('title', 'Untitled'))
        title.setFont(theme.get_display_font(size_pt=14))
        title.setWordWrap(True)
        card_layout.addWidget(title)

        # Authors
        authors = paper_data.get('authors', [])
        authors_str = ", ".join(
            a['name'] if isinstance(a, dict) else str(a) for a in authors[:5]
        )
        if len(authors) > 5:
            authors_str += f" +{len(authors) - 5} more"
        authors_label = QLabel(authors_str)
        authors_label.setFont(theme.get_body_font(size_pt=11))
        authors_label.setStyleSheet(f"color: {theme.get_color('text_secondary')};")
        authors_label.setWordWrap(True)
        card_layout.addWidget(authors_label)

        # Metadata: arXiv ID · category · year
        arxiv_id = paper_data.get('arxiv_id', '')
        primary_cat = paper_data.get('primary_category', '')
        pub_date = paper_data.get('publication_date', '')
        year = pub_date[:4] if pub_date else ''
        meta_parts = [s for s in [arxiv_id, primary_cat, year] if s]
        meta_label = QLabel(" \u00b7 ".join(meta_parts))
        meta_label.setFont(theme.get_mono_font(size_pt=9))
        meta_label.setStyleSheet(f"color: {theme.get_color('text_secondary')};")
        card_layout.addWidget(meta_label)

        # Abstract (max 3 lines)
        abstract = paper_data.get('abstract', '')
        if abstract:
            preview_text = abstract[:300].replace('\n', ' ')
            if len(abstract) > 300:
                preview_text += "..."
            abstract_label = QLabel(preview_text)
            abstract_label.setFont(theme.get_body_font(size_pt=12))
            abstract_label.setWordWrap(True)
            abstract_label.setMaximumHeight(80)
            card_layout.addWidget(abstract_label)

        # Import button
        import_btn = QPushButton("Import to Library")
        import_btn.setFont(theme.get_body_font(size_pt=11))
        import_btn.setCursor(Qt.PointingHandCursor)
        import_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('text_primary')};
                border-radius: 2px;
                padding: 8px 20px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
        """)
        import_btn.clicked.connect(lambda: self.import_paper_requested.emit(paper_data))
        card_layout.addWidget(import_btn, alignment=Qt.AlignLeft)

        # Footer hint
        hint = QLabel("This paper is from arXiv \u00b7 not yet in your library")
        hint.setFont(theme.get_body_font(size_pt=10))
        hint.setStyleSheet(f"color: {theme.get_color('text_tertiary')};")
        card_layout.addWidget(hint)

        self.container_layout.addWidget(card)
        self.paper_cells.append(card)  # track for cleanup
        self.feed_meta.setText("")

    def show_error_message(self, message: str):
        """Show an error/info message in the feed area."""
        self.clear_papers()
        self.empty_label.setText(message)
        self.empty_label.setVisible(True)
        self.feed_meta.setText("")
