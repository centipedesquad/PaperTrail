"""
Paper cell widget.
Displays paper information as a compact card in the feed.
Click to select — details shown in the context panel.
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor
from models import Paper
from ui.theme import get_theme_manager

logger = logging.getLogger(__name__)


class PaperCellWidget(QWidget):
    """Compact paper card for the feed. Click to select."""

    # Signals
    clicked = Signal(object)  # Paper object

    def __init__(self, paper: Paper, parent=None):
        super().__init__(parent)
        self.paper = paper
        self.is_selected = False
        self.abstract_label = None
        self._base_font_size = QApplication.instance().font().pointSize() or 11
        self._setup_ui()

    def _setup_ui(self):
        theme = get_theme_manager()
        base_font_size = QApplication.instance().font().pointSize() or 11

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Container frame with left-border accent on hover
        self.container = QFrame()
        self.container.setFrameShape(QFrame.NoFrame)
        self.container.setCursor(QCursor(Qt.PointingHandCursor))
        self._apply_style(selected=False)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(16, 12, 16, 12)
        container_layout.setSpacing(4)

        # Title — Source Serif 4 (display font)
        self.title_label = QLabel(self.paper.title)
        self.title_label.setFont(theme.get_display_font(size_pt=int(base_font_size * 1.18)))
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(f"""
            color: {theme.get_color('text_primary')};
            border: none; background: transparent;
        """)
        container_layout.addWidget(self.title_label)

        # Authors — DM Sans body
        authors_text = ", ".join([a.name for a in self.paper.authors])
        if len(authors_text) > 150:
            authors_text = authors_text[:150] + "..."
        authors_label = QLabel(authors_text)
        authors_label.setWordWrap(True)
        authors_label.setFont(theme.get_body_font(size_pt=int(base_font_size * 0.91)))
        authors_label.setStyleSheet(f"""
            color: {theme.get_color('text_secondary')};
            border: none; background: transparent;
        """)
        container_layout.addWidget(authors_label)

        # Metadata row — JetBrains Mono
        meta_layout = QHBoxLayout()
        meta_layout.setContentsMargins(0, 2, 0, 2)
        meta_layout.setSpacing(12)

        arxiv_label = QLabel(f"arXiv:{self.paper.arxiv_id}")
        arxiv_label.setFont(theme.get_mono_font(size_pt=int(base_font_size * 0.82)))
        arxiv_label.setStyleSheet(f"color: {theme.get_color('text_tertiary')}; border: none; background: transparent;")
        meta_layout.addWidget(arxiv_label)

        if self.paper.categories:
            primary_cat = self.paper.categories[0].code if self.paper.categories else ""
            cat_label = QLabel(primary_cat)
            cat_label.setFont(theme.get_mono_font(size_pt=int(base_font_size * 0.82)))
            cat_label.setStyleSheet(f"""
                color: {theme.get_color('primary')};
                background: {theme.get_color('primary_light')};
                padding: 0px 4px;
                border-radius: 2px;
                border: none;
            """)
            meta_layout.addWidget(cat_label)

        date_label = QLabel(str(self.paper.publication_date))
        date_label.setFont(theme.get_mono_font(size_pt=int(base_font_size * 0.82)))
        date_label.setStyleSheet(f"color: {theme.get_color('text_tertiary')}; border: none; background: transparent;")
        meta_layout.addWidget(date_label)

        meta_layout.addStretch()
        container_layout.addLayout(meta_layout)

        # Abstract — truncated when collapsed, full when selected
        if self.paper.abstract:
            abstract_text = self.paper.abstract
            if len(abstract_text) > 200:
                abstract_text = abstract_text[:200] + "..."
            self.abstract_label = QLabel(abstract_text)
            self.abstract_label.setWordWrap(True)
            self.abstract_label.setMaximumHeight(int(base_font_size * 3.5))
            self.abstract_label.setFont(theme.get_body_font(size_pt=int(base_font_size * 0.91)))
            self.abstract_label.setStyleSheet(f"""
                color: {theme.get_color('text_secondary')};
                border: none; background: transparent;
            """)
            container_layout.addWidget(self.abstract_label)

        main_layout.addWidget(self.container)

    def _apply_style(self, selected: bool = False):
        theme = get_theme_manager()
        if selected:
            self.container.setStyleSheet(f"""
                QFrame {{
                    border: none;
                    border-bottom: 1px solid {theme.get_color('border')};
                    border-left: 3px solid {theme.get_color('primary')};
                    background-color: {theme.get_color('surface_hover')};
                    border-radius: 0px;
                }}
                QFrame QWidget {{ background-color: transparent; border: none; }}
                QFrame QLabel {{ background-color: transparent; border: none; }}
            """)
        else:
            self.container.setStyleSheet(f"""
                QFrame {{
                    border: none;
                    border-bottom: 1px solid {theme.get_color('border')};
                    border-left: 3px solid transparent;
                    background-color: {theme.get_color('surface')};
                    border-radius: 0px;
                }}
                QFrame:hover {{
                    border-left: 3px solid {theme.get_color('primary')};
                    background-color: {theme.get_color('surface_hover')};
                }}
                QFrame QWidget {{ background-color: transparent; border: none; }}
                QFrame QLabel {{ background-color: transparent; border: none; }}
            """)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self._apply_style(selected)
        if self.abstract_label and self.paper.abstract:
            if selected:
                self.abstract_label.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
                self.abstract_label.setText(self.paper.abstract)
            else:
                text = self.paper.abstract
                if len(text) > 200:
                    text = text[:200] + "..."
                self.abstract_label.setText(text)
                self.abstract_label.setMaximumHeight(int(self._base_font_size * 3.5))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.paper)
        super().mousePressEvent(event)
