"""
Context panel widget.
Shows details for the selected paper: metadata, ratings, PDF status, notes.
"""

import logging
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QHBoxLayout, QApplication
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from models import Paper
from ui.theme import get_theme_manager, FONT_MONO_STACK
from ui.widgets.rating_widget import RatingWidget
from ui.widgets.note_editor_widget import NoteEditorWidget

logger = logging.getLogger(__name__)


class ContextPanelWidget(QWidget):
    """Right-side panel showing details for the selected paper."""

    # Signals
    view_pdf_requested = Signal(int)   # paper_id
    delete_pdf_requested = Signal(int) # paper_id
    rating_changed = Signal(int, str, str, str)  # paper_id, importance, comprehension, technicality
    note_changed = Signal(int, str)    # paper_id, note_text

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_paper = None
        self._setup_ui()

    def _setup_ui(self):
        theme = get_theme_manager()
        base_font_size = QApplication.instance().font().pointSize() or 11

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {theme.get_color('surface')};
                border-left: 1px solid {theme.get_color('border')};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet("border: none;")
        self.content_layout = QVBoxLayout(container)
        self.content_layout.setContentsMargins(16, 16, 16, 16)
        self.content_layout.setSpacing(0)

        # Empty state
        self.empty_label = QLabel("Select a paper to view details")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"""
            color: {theme.get_color('text_tertiary')};
            padding: 40px 16px;
            border: none;
        """)
        self.content_layout.addWidget(self.empty_label)

        # --- Paper detail sections (hidden until paper selected) ---
        self.detail_widget = QWidget()
        self.detail_widget.setStyleSheet("border: none;")
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(0)

        # Section: Selected Paper
        detail_layout.addWidget(self._make_section_heading("Selected Paper"))

        self.paper_title_label = QLabel()
        self.paper_title_label.setWordWrap(True)
        self.paper_title_label.setFont(theme.get_display_font(size_pt=int(base_font_size * 1.1)))
        self.paper_title_label.setStyleSheet(f"""
            color: {theme.get_color('text_primary')};
            margin-bottom: 8px;
            border: none;
        """)
        detail_layout.addWidget(self.paper_title_label)

        self.paper_meta_label = QLabel()
        self.paper_meta_label.setWordWrap(True)
        self.paper_meta_label.setFont(theme.get_mono_font(size_pt=int(base_font_size * 0.82)))
        self.paper_meta_label.setStyleSheet(f"""
            color: {theme.get_color('text_tertiary')};
            line-height: 1.8;
            margin-bottom: 16px;
            border: none;
        """)
        detail_layout.addWidget(self.paper_meta_label)

        # Section: Rating
        detail_layout.addWidget(self._make_section_heading("Rating"))

        self.rating_widget = RatingWidget()
        self.rating_widget.setStyleSheet("border: none;")
        self.rating_widget.rating_changed.connect(self._on_rating_changed)
        detail_layout.addWidget(self.rating_widget)

        detail_layout.addSpacing(16)

        # Section: PDF
        detail_layout.addWidget(self._make_section_heading("PDF"))

        self.pdf_status_label = QLabel()
        self.pdf_status_label.setStyleSheet(f"border: none; margin-bottom: 8px;")
        detail_layout.addWidget(self.pdf_status_label)

        self.pdf_button = QPushButton("View PDF")
        self.pdf_button.setStyleSheet(theme.get_widget_style('button_primary'))
        self.pdf_button.clicked.connect(self._on_view_pdf)
        detail_layout.addWidget(self.pdf_button)

        self.delete_pdf_button = QPushButton("Delete PDF")
        self.delete_pdf_button.setStyleSheet(theme.get_widget_style('button_secondary'))
        self.delete_pdf_button.clicked.connect(self._on_delete_pdf)
        self.delete_pdf_button.setVisible(False)
        detail_layout.addWidget(self.delete_pdf_button)

        detail_layout.addSpacing(16)

        # Section: Notes
        detail_layout.addWidget(self._make_section_heading("Notes"))

        self.note_editor = NoteEditorWidget()
        self.note_editor.setStyleSheet("border: none;")
        self.note_editor.note_changed.connect(self._on_note_changed)
        detail_layout.addWidget(self.note_editor)

        detail_layout.addStretch()

        self.detail_widget.setVisible(False)
        self.content_layout.addWidget(self.detail_widget)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _make_section_heading(self, text: str) -> QLabel:
        theme = get_theme_manager()
        base_font_size = QApplication.instance().font().pointSize() or 11
        label = QLabel(text.upper())
        label.setFont(theme.get_mono_font(size_pt=max(int(base_font_size * 0.73), 8)))
        label.setStyleSheet(f"""
            color: {theme.get_color('text_tertiary')};
            letter-spacing: 1px;
            padding-bottom: 4px;
            margin-bottom: 8px;
            margin-top: 4px;
            border: none;
            border-bottom: 1px solid {theme.get_color('border')};
        """)
        return label

    def set_paper(self, paper: Paper):
        """Display details for the given paper."""
        self.current_paper = paper
        self.empty_label.setVisible(False)
        self.detail_widget.setVisible(True)

        # Title
        self.paper_title_label.setText(paper.title)

        # Metadata
        categories = ", ".join([c.code for c in paper.categories]) if paper.categories else ""
        meta_lines = [
            f"arXiv:{paper.arxiv_id}",
            categories,
            f"Published: {paper.publication_date}",
        ]
        self.paper_meta_label.setText("\n".join(meta_lines))

        # Ratings
        if paper.ratings:
            self.rating_widget.set_ratings(
                paper.ratings.importance,
                paper.ratings.comprehension,
                paper.ratings.technicality
            )
        else:
            self.rating_widget.set_ratings(None, None, None)

        # PDF status
        theme = get_theme_manager()
        has_pdf = paper.local_pdf_path and os.path.exists(paper.local_pdf_path)
        if has_pdf:
            # Get file size
            try:
                size_mb = os.path.getsize(paper.local_pdf_path) / (1024 * 1024)
                size_str = f"{size_mb:.1f} MB"
            except OSError:
                size_str = ""
            self.pdf_status_label.setText(f"Downloaded {size_str}")
            self.pdf_status_label.setStyleSheet(f"""
                color: {theme.get_color('success')};
                background: {theme.get_color('success_light')};
                padding: 4px 8px;
                border-radius: 2px;
                border: none;
                margin-bottom: 8px;
            """)
            self.pdf_button.setText("Open PDF")
            self.delete_pdf_button.setVisible(True)
        else:
            self.pdf_status_label.setText("Not downloaded")
            self.pdf_status_label.setStyleSheet(f"""
                color: {theme.get_color('text_tertiary')};
                border: none;
                margin-bottom: 8px;
            """)
            self.pdf_button.setText("View PDF")
            self.delete_pdf_button.setVisible(False)

        # Notes
        if paper.notes and paper.notes.note_text:
            self.note_editor.set_note(paper.notes.note_text)
        else:
            self.note_editor.set_note("")

    def clear_selection(self):
        """Clear the panel back to empty state."""
        self.current_paper = None
        self.empty_label.setVisible(True)
        self.detail_widget.setVisible(False)

    def _on_view_pdf(self):
        if self.current_paper:
            self.view_pdf_requested.emit(self.current_paper.id)

    def _on_delete_pdf(self):
        if self.current_paper:
            self.delete_pdf_requested.emit(self.current_paper.id)

    def _on_rating_changed(self, importance, comprehension, technicality):
        if self.current_paper:
            self.rating_changed.emit(self.current_paper.id, importance, comprehension, technicality)

    def _on_note_changed(self, note_text):
        if self.current_paper:
            self.note_changed.emit(self.current_paper.id, note_text)
