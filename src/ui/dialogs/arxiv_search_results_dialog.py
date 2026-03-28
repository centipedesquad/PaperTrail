"""
arXiv search results picker dialog.
Shows arXiv search results with checkboxes for selecting papers to import.
"""

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from ui.theme import get_theme_manager

logger = logging.getLogger(__name__)


class ArxivSearchResultsDialog(QDialog):
    """Dialog for selecting papers from arXiv search results to import."""

    import_requested = Signal(list)  # List of selected paper data dicts

    def __init__(self, query: str, results: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("arXiv Search Results")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)

        self.query = query
        self.results = results
        self.checkboxes = []

        self._setup_ui()

    def _setup_ui(self):
        theme = get_theme_manager()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title_label = QLabel("arXiv Search Results")
        title_font = theme.get_display_font(size_pt=16)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Subtitle with query and count
        subtitle = QLabel(f'"{self.query}" \u2014 {len(self.results)} results')
        subtitle_font = theme.get_body_font(size_pt=11)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet(f"color: {theme.get_color('text_secondary')};")
        layout.addWidget(subtitle)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {theme.get_color('border')};")
        layout.addWidget(sep)

        # Select All checkbox
        self.select_all_cb = QCheckBox("Select All")
        select_all_font = theme.get_body_font(size_pt=11)
        select_all_font.setWeight(QFont.Weight.Medium)
        self.select_all_cb.setFont(select_all_font)
        self.select_all_cb.stateChanged.connect(self._on_select_all_changed)
        layout.addWidget(self.select_all_cb)

        # Scrollable results list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        self.results_layout = QVBoxLayout(scroll_content)
        self.results_layout.setSpacing(0)
        self.results_layout.setContentsMargins(0, 0, 0, 0)

        for paper_data in self.results:
            row = self._create_result_row(paper_data, theme)
            self.results_layout.addWidget(row)

        self.results_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)  # stretch factor

        # Footer
        footer_layout = QHBoxLayout()

        self.status_label = QLabel("Selected: 0 papers")
        self.status_label.setFont(theme.get_body_font(size_pt=11))
        self.status_label.setStyleSheet(f"color: {theme.get_color('text_secondary')};")
        footer_layout.addWidget(self.status_label)

        footer_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)

        self.import_btn = QPushButton("Import Selected")
        self.import_btn.setEnabled(False)
        self.import_btn.setStyleSheet(
            f"background-color: {theme.get_color('primary')}; "
            f"color: {theme.get_color('text_primary')}; "
            f"border-radius: 2px; padding: 6px 16px;"
        )
        self.import_btn.clicked.connect(self._on_import)
        footer_layout.addWidget(self.import_btn)

        layout.addLayout(footer_layout)

    def _create_result_row(self, paper_data: dict, theme) -> QWidget:
        """Create a single result row with checkbox."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 8, 4, 8)

        cb = QCheckBox()
        cb.stateChanged.connect(self._update_selection_count)
        cb.setProperty("paper_data", paper_data)
        self.checkboxes.append(cb)

        # Accessible name
        authors = paper_data.get('authors', [])
        first_author = authors[0]['name'] if authors and isinstance(authors[0], dict) else (authors[0] if authors else "Unknown")
        cb.setAccessibleName(f"Select {paper_data.get('title', 'Untitled')} by {first_author}")
        row_layout.addWidget(cb, 0)

        # Paper info
        info = QWidget()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        title_label = QLabel(paper_data.get('title', 'Untitled'))
        title_label.setFont(theme.get_body_font(size_pt=12))
        title_label.setWordWrap(True)
        info_layout.addWidget(title_label)

        # Authors + arXiv ID + year
        authors_str = ", ".join(
            a['name'] if isinstance(a, dict) else str(a) for a in authors[:3]
        )
        if len(authors) > 3:
            authors_str += f" +{len(authors) - 3} more"
        arxiv_id = paper_data.get('arxiv_id', '')
        pub_date = paper_data.get('publication_date', '')
        year = pub_date[:4] if pub_date else ''
        primary_cat = paper_data.get('primary_category', '')

        meta_parts = [s for s in [authors_str, arxiv_id, primary_cat, year] if s]
        meta_label = QLabel(" \u00b7 ".join(meta_parts))
        meta_label.setFont(theme.get_body_font(size_pt=10))
        meta_label.setStyleSheet(f"color: {theme.get_color('text_secondary')};")
        meta_label.setWordWrap(True)
        info_layout.addWidget(meta_label)

        # Abstract preview (first line)
        abstract = paper_data.get('abstract', '')
        if abstract:
            preview = abstract[:150].replace('\n', ' ')
            if len(abstract) > 150:
                preview += "..."
            abstract_label = QLabel(preview)
            abstract_label.setFont(theme.get_body_font(size_pt=10))
            abstract_label.setStyleSheet(f"color: {theme.get_color('text_tertiary')};")
            abstract_label.setWordWrap(True)
            info_layout.addWidget(abstract_label)

        row_layout.addWidget(info, 1)

        # Bottom separator
        row.setStyleSheet(f"border-bottom: 1px solid {theme.get_color('border')};")

        return row

    def _on_select_all_changed(self, state):
        checked = state == Qt.CheckState.Checked.value
        for cb in self.checkboxes:
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
        self._update_selection_count()

    def _update_selection_count(self):
        count = sum(1 for cb in self.checkboxes if cb.isChecked())
        self.status_label.setText(f"Selected: {count} papers")
        self.import_btn.setEnabled(count > 0)

    def _on_import(self):
        selected = []
        for cb in self.checkboxes:
            if cb.isChecked():
                selected.append(cb.property("paper_data"))
        if selected:
            self.import_requested.emit(selected)
            self.accept()

    def get_selected_papers(self) -> list:
        """Return list of selected paper data dicts."""
        return [
            cb.property("paper_data")
            for cb in self.checkboxes
            if cb.isChecked()
        ]

    def set_import_progress(self, current: int, total: int):
        """Update status label during import."""
        self.status_label.setText(f"Importing {current}/{total}...")
        self.import_btn.setEnabled(False)

    def set_import_result(self, imported: int, duplicates: int):
        """Show import result."""
        parts = [f"{imported} imported"]
        if duplicates > 0:
            parts.append(f"{duplicates} duplicates skipped")
        self.status_label.setText(", ".join(parts))
