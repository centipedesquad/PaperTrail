"""
Collapsible paper cell widget.
Displays paper information in an expandable card.
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QCursor
from models import Paper
from ui.widgets.rating_widget import RatingWidget
from ui.widgets.note_editor_widget import NoteEditorWidget
from ui.theme import get_theme_manager

logger = logging.getLogger(__name__)


class PaperCellWidget(QWidget):
    """Collapsible widget for displaying paper information."""

    # Signals
    view_pdf_clicked = Signal(int)  # paper_id
    rating_changed = Signal(int, str, str, str)  # paper_id, importance, comprehension, technicality
    note_changed = Signal(int, str)  # paper_id, note_text

    def __init__(self, paper: Paper, parent=None):
        """
        Initialize paper cell widget.

        Args:
            paper: Paper object to display
            parent: Parent widget
        """
        super().__init__(parent)
        self.paper = paper
        self.is_expanded = False  # Start collapsed for better scanning
        self.rating_visible = False
        self.notes_visible = False

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 8)  # Bottom margin for spacing between cells
        main_layout.setSpacing(0)

        # Get theme manager and base font size
        theme = get_theme_manager()
        base_font_size = QApplication.instance().font().pointSize()

        # Container frame with border
        self.container = QFrame()
        self.container.setFrameShape(QFrame.Box)
        self.container.setStyleSheet(theme.get_widget_style('paper_cell'))
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(20, 15, 20, 15)  # More breathing room
        container_layout.setSpacing(12)  # More space between elements

        # Header (always visible) - clickable to toggle
        header_widget = QWidget()
        header_widget.setCursor(QCursor(Qt.PointingHandCursor))
        header_widget.mousePressEvent = lambda e: self.toggle_expanded()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Expand/collapse arrow
        self.arrow_label = QLabel("▶")  # Start collapsed
        self.arrow_label.setFixedWidth(25)
        arrow_font = QFont()
        arrow_font.setPointSize(base_font_size)
        self.arrow_label.setFont(arrow_font)
        header_layout.addWidget(self.arrow_label)

        # Title
        title_label = QLabel(self.paper.title)
        title_font = QFont()
        title_font.setPointSize(int(base_font_size * 1.27))  # ~27% larger than base (14pt when base is 11pt)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(
            f"color: {theme.get_color('text_primary')}; "
            f"line-height: 1.4; "
            f"border: none; "
            f"background: transparent;"
        )
        header_layout.addWidget(title_label, 1)

        container_layout.addWidget(header_widget)

        # Content (expandable)
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(25, 10, 0, 0)  # Indent and add top spacing
        content_layout.setSpacing(12)  # More breathing room

        # Authors
        authors_text = ", ".join([a.name for a in self.paper.authors])
        if len(authors_text) > 200:
            authors_text = authors_text[:200] + "..."
        authors_label = QLabel(f"<b>Authors:</b> {authors_text}")
        authors_label.setWordWrap(True)
        authors_font = QFont()
        authors_font.setPointSize(base_font_size)
        authors_label.setFont(authors_font)
        authors_label.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; "
            f"border: none; "
            f"background: transparent;"
        )
        content_layout.addWidget(authors_label)

        # Metadata (arXiv ID, categories, date)
        meta_text = f"<b>arXiv:</b> {self.paper.arxiv_id} | "
        categories = ", ".join([c.code for c in self.paper.categories])
        meta_text += f"<b>Categories:</b> {categories} | "
        meta_text += f"<b>Date:</b> {self.paper.publication_date}"
        meta_label = QLabel(meta_text)
        meta_label.setWordWrap(True)
        meta_font = QFont()
        meta_font.setPointSize(int(base_font_size * 0.91))  # ~9% smaller than base (10pt when base is 11pt)
        meta_label.setFont(meta_font)
        meta_label.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; "
            f"border: none; "
            f"background: transparent;"
        )
        content_layout.addWidget(meta_label)

        # Abstract (truncated with better length)
        abstract_text = self.paper.abstract
        if len(abstract_text) > 600:
            abstract_text = abstract_text[:600] + "..."
        abstract_label = QLabel(f"<b>Abstract:</b> {abstract_text}")
        abstract_label.setWordWrap(True)
        abstract_font = QFont()
        abstract_font.setPointSize(base_font_size)
        abstract_label.setFont(abstract_font)
        abstract_label.setStyleSheet(
            f"color: {theme.get_color('text_primary')}; "
            f"line-height: 1.5; "
            f"padding-top: 4px; "
            f"border: none; "
            f"background: transparent;"
        )
        content_layout.addWidget(abstract_label)

        # Rating indicators (if rated)
        if self.paper.ratings:
            rating_text = "<b>Ratings:</b> "
            if self.paper.ratings.importance:
                rating_text += f"Importance: {self.paper.ratings.importance} | "
            if self.paper.ratings.comprehension:
                rating_text += f"Comprehension: {self.paper.ratings.comprehension} | "
            if self.paper.ratings.technicality:
                rating_text += f"Technicality: {self.paper.ratings.technicality}"
            rating_label = QLabel(rating_text)
            rating_font = QFont()
            rating_font.setPointSize(base_font_size)
            rating_label.setFont(rating_font)
            rating_label.setStyleSheet(
                f"color: {theme.get_color('success')}; "
                f"border: none; "
                f"background: transparent;"
            )
            content_layout.addWidget(rating_label)

        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        buttons_layout.setContentsMargins(0, 8, 0, 0)  # Add top spacing

        view_pdf_btn = QPushButton("View PDF")
        view_pdf_btn.setFixedHeight(28)
        view_pdf_btn.setMinimumWidth(100)
        view_pdf_btn.clicked.connect(lambda: self.view_pdf_clicked.emit(self.paper.id))
        view_pdf_btn.setStyleSheet(theme.get_widget_style('button_primary'))
        buttons_layout.addWidget(view_pdf_btn)

        self.notes_btn = QPushButton("Notes")
        self.notes_btn.setFixedHeight(28)
        self.notes_btn.setMinimumWidth(80)
        self.notes_btn.clicked.connect(self._toggle_notes)
        self.notes_btn.setStyleSheet(theme.get_widget_style('button_secondary'))
        buttons_layout.addWidget(self.notes_btn)

        self.rating_btn = QPushButton("Rate Paper")
        self.rating_btn.setFixedHeight(28)
        self.rating_btn.setMinimumWidth(100)
        self.rating_btn.clicked.connect(self._toggle_rating)
        self.rating_btn.setStyleSheet(theme.get_widget_style('button_success'))
        buttons_layout.addWidget(self.rating_btn)

        buttons_layout.addStretch()
        content_layout.addLayout(buttons_layout)

        # Inline rating widget (hidden by default)
        self.rating_widget = RatingWidget()
        self.rating_widget.setVisible(False)
        self.rating_widget.rating_changed.connect(self._on_rating_changed)
        # Load existing ratings
        if self.paper.ratings:
            self.rating_widget.set_ratings(
                self.paper.ratings.importance,
                self.paper.ratings.comprehension,
                self.paper.ratings.technicality
            )
        content_layout.addWidget(self.rating_widget)

        # Inline note editor (hidden by default)
        self.note_editor = NoteEditorWidget()
        self.note_editor.setVisible(False)
        self.note_editor.note_changed.connect(self._on_note_changed)
        # Load existing note
        if self.paper.notes and self.paper.notes.note_text:
            self.note_editor.set_note(self.paper.notes.note_text)
        content_layout.addWidget(self.note_editor)

        container_layout.addWidget(self.content_widget)

        main_layout.addWidget(self.container)

        # Set initial state
        self.content_widget.setVisible(self.is_expanded)

    def toggle_expanded(self):
        """Toggle expanded/collapsed state."""
        self.is_expanded = not self.is_expanded

        if self.is_expanded:
            self.arrow_label.setText("▼")
            self.content_widget.setVisible(True)
        else:
            self.arrow_label.setText("▶")
            self.content_widget.setVisible(False)

    def set_expanded(self, expanded: bool):
        """Set expanded state."""
        if self.is_expanded != expanded:
            self.toggle_expanded()

    def _toggle_rating(self):
        """Toggle rating widget visibility."""
        self.rating_visible = not self.rating_visible
        self.rating_widget.setVisible(self.rating_visible)

        # Update button text
        if self.rating_visible:
            self.rating_btn.setText("⭐ Hide Rating")
        else:
            self.rating_btn.setText("⭐ Rate Paper")

    def _toggle_notes(self):
        """Toggle notes editor visibility."""
        self.notes_visible = not self.notes_visible
        self.note_editor.setVisible(self.notes_visible)

        # Update button text
        if self.notes_visible:
            self.notes_btn.setText("✏️ Hide Notes")
        else:
            self.notes_btn.setText("✏️ Add/Edit Notes")

    def _on_rating_changed(self, importance: str, comprehension: str, technicality: str):
        """Handle rating change."""
        self.rating_changed.emit(self.paper.id, importance, comprehension, technicality)

    def _on_note_changed(self, note_text: str):
        """Handle note change."""
        self.note_changed.emit(self.paper.id, note_text)
