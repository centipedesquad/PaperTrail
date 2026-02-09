"""
Paper feed widget.
Scrollable container for paper cells.
"""

import logging
from typing import List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel
)
from PySide6.QtCore import Qt, Signal
from models import Paper
from ui.widgets.paper_cell_widget import PaperCellWidget

logger = logging.getLogger(__name__)


class PaperFeedWidget(QWidget):
    """Scrollable feed of paper cells."""

    # Signals
    view_pdf_requested = Signal(int)  # paper_id
    rating_changed = Signal(int, str, str, str)  # paper_id, importance, comprehension, technicality
    note_changed = Signal(int, str)  # paper_id, note_text

    def __init__(self, parent=None):
        """
        Initialize paper feed widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.paper_cells = []
        self._setup_ui()

    def _setup_ui(self):
        """Setup UI components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Container widget for paper cells
        self.container_widget = QWidget()
        self.container_layout = QVBoxLayout(self.container_widget)
        self.container_layout.setContentsMargins(20, 20, 20, 20)  # More padding around content
        self.container_layout.setSpacing(0)  # Spacing handled by cells themselves
        self.container_layout.setAlignment(Qt.AlignTop)

        # Empty state label
        self.empty_label = QLabel("No papers to display.\n\nClick 'Fetch Papers' to get started.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("""
            QLabel {
                color: #999;
                font-size: 14pt;
                padding: 50px;
            }
        """)
        self.container_layout.addWidget(self.empty_label)

        scroll_area.setWidget(self.container_widget)
        main_layout.addWidget(scroll_area)

    def set_papers(self, papers: List[Paper]):
        """
        Set papers to display.

        Args:
            papers: List of Paper objects
        """
        # Clear existing cells
        self.clear_papers()

        if not papers:
            self.empty_label.setVisible(True)
            return

        self.empty_label.setVisible(False)

        # Create cells for each paper
        for paper in papers:
            cell = PaperCellWidget(paper)

            # Connect signals
            cell.view_pdf_clicked.connect(self.view_pdf_requested.emit)
            cell.rating_changed.connect(self.rating_changed.emit)
            cell.note_changed.connect(self.note_changed.emit)

            self.container_layout.addWidget(cell)
            self.paper_cells.append(cell)

        logger.info(f"Displaying {len(papers)} papers in feed")

    def add_paper(self, paper: Paper):
        """
        Add a single paper to the feed.

        Args:
            paper: Paper object
        """
        self.empty_label.setVisible(False)

        cell = PaperCellWidget(paper)

        # Connect signals
        cell.view_pdf_clicked.connect(self.view_pdf_requested.emit)
        cell.rating_changed.connect(self.rating_changed.emit)
        cell.note_changed.connect(self.note_changed.emit)

        # Insert at top (most recent first)
        self.container_layout.insertWidget(0, cell)
        self.paper_cells.insert(0, cell)

    def clear_papers(self):
        """Clear all papers from the feed."""
        for cell in self.paper_cells:
            cell.deleteLater()

        self.paper_cells.clear()

    def get_paper_count(self) -> int:
        """Get number of papers in feed."""
        return len(self.paper_cells)
