"""
Collapsible paper cell widget.
Displays paper information in an expandable card.
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QCursor
from models import Paper

logger = logging.getLogger(__name__)


class PaperCellWidget(QWidget):
    """Collapsible widget for displaying paper information."""

    # Signals
    view_pdf_clicked = Signal(int)  # paper_id
    add_note_clicked = Signal(int)  # paper_id
    rate_paper_clicked = Signal(int)  # paper_id

    def __init__(self, paper: Paper, parent=None):
        """
        Initialize paper cell widget.

        Args:
            paper: Paper object to display
            parent: Parent widget
        """
        super().__init__(parent)
        self.paper = paper
        self.is_expanded = True  # Start expanded

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Container frame with border
        self.container = QFrame()
        self.container.setFrameShape(QFrame.Box)
        self.container.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: white;
            }
            QFrame:hover {
                border-color: #4a90e2;
            }
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(15, 10, 15, 10)
        container_layout.setSpacing(10)

        # Header (always visible) - clickable to toggle
        header_widget = QWidget()
        header_widget.setCursor(QCursor(Qt.PointingHandCursor))
        header_widget.mousePressEvent = lambda e: self.toggle_expanded()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Expand/collapse arrow
        self.arrow_label = QLabel("▼")
        self.arrow_label.setFixedWidth(20)
        header_layout.addWidget(self.arrow_label)

        # Title
        title_label = QLabel(self.paper.title)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("color: #2c3e50;")
        header_layout.addWidget(title_label, 1)

        container_layout.addWidget(header_widget)

        # Content (expandable)
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(20, 0, 0, 0)
        content_layout.setSpacing(8)

        # Authors
        authors_text = ", ".join([a.name for a in self.paper.authors])
        if len(authors_text) > 150:
            authors_text = authors_text[:150] + "..."
        authors_label = QLabel(f"<b>Authors:</b> {authors_text}")
        authors_label.setWordWrap(True)
        authors_label.setStyleSheet("color: #555;")
        content_layout.addWidget(authors_label)

        # Metadata (arXiv ID, categories, date)
        meta_text = f"<b>arXiv:</b> {self.paper.arxiv_id} | "
        categories = ", ".join([c.code for c in self.paper.categories])
        meta_text += f"<b>Categories:</b> {categories} | "
        meta_text += f"<b>Date:</b> {self.paper.publication_date}"
        meta_label = QLabel(meta_text)
        meta_label.setWordWrap(True)
        meta_label.setStyleSheet("color: #666; font-size: 10pt;")
        content_layout.addWidget(meta_label)

        # Abstract (truncated)
        abstract_text = self.paper.abstract
        if len(abstract_text) > 500:
            abstract_text = abstract_text[:500] + "..."
        abstract_label = QLabel(f"<b>Abstract:</b> {abstract_text}")
        abstract_label.setWordWrap(True)
        abstract_label.setStyleSheet("color: #444; font-size: 10pt;")
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
            rating_label.setStyleSheet("color: #27ae60; font-size: 10pt;")
            content_layout.addWidget(rating_label)

        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        view_pdf_btn = QPushButton("View PDF")
        view_pdf_btn.clicked.connect(lambda: self.view_pdf_clicked.emit(self.paper.id))
        view_pdf_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
        """)
        buttons_layout.addWidget(view_pdf_btn)

        add_note_btn = QPushButton("Add/Edit Notes")
        add_note_btn.clicked.connect(lambda: self.add_note_clicked.emit(self.paper.id))
        add_note_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        buttons_layout.addWidget(add_note_btn)

        rate_paper_btn = QPushButton("Rate Paper")
        rate_paper_btn.clicked.connect(lambda: self.rate_paper_clicked.emit(self.paper.id))
        rate_paper_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        buttons_layout.addWidget(rate_paper_btn)

        buttons_layout.addStretch()
        content_layout.addLayout(buttons_layout)

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
