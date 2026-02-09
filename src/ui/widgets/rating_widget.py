"""
Rating widget for paper ratings.
Provides inline dropdowns for the three-metric rating system.
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox
)
from PySide6.QtCore import Qt, Signal
from models import ImportanceLevel, ComprehensionLevel, TechnicalityLevel

logger = logging.getLogger(__name__)


class RatingWidget(QWidget):
    """Widget for rating papers with three metrics."""

    # Signal emitted when any rating changes
    rating_changed = Signal(str, str, str)  # (importance, comprehension, technicality)

    def __init__(self, parent=None):
        """
        Initialize rating widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._importance = None
        self._comprehension = None
        self._technicality = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI components."""
        from ui.theme import get_theme_manager
        theme = get_theme_manager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(10)

        # Title
        title_label = QLabel("Rate this paper:")
        title_label.setStyleSheet(f"font-weight: bold; color: {theme.get_color('text_primary')};")
        layout.addWidget(title_label)

        # Importance
        importance_layout = QHBoxLayout()
        importance_label = QLabel("Importance:")
        importance_label.setMinimumWidth(120)
        importance_layout.addWidget(importance_label)

        self.importance_combo = QComboBox()
        self.importance_combo.addItem("-- Not rated --", None)
        for level in ImportanceLevel.all():
            self.importance_combo.addItem(level.title(), level)
        self.importance_combo.currentIndexChanged.connect(self._on_rating_changed)
        importance_layout.addWidget(self.importance_combo, 1)

        layout.addLayout(importance_layout)

        # Comprehension
        comprehension_layout = QHBoxLayout()
        comprehension_label = QLabel("Comprehension:")
        comprehension_label.setMinimumWidth(120)
        comprehension_layout.addWidget(comprehension_label)

        self.comprehension_combo = QComboBox()
        self.comprehension_combo.addItem("-- Not rated --", None)
        for level in ComprehensionLevel.all():
            self.comprehension_combo.addItem(level.title(), level)
        self.comprehension_combo.currentIndexChanged.connect(self._on_rating_changed)
        comprehension_layout.addWidget(self.comprehension_combo, 1)

        layout.addLayout(comprehension_layout)

        # Technicality
        technicality_layout = QHBoxLayout()
        technicality_label = QLabel("Technicality:")
        technicality_label.setMinimumWidth(120)
        technicality_layout.addWidget(technicality_label)

        self.technicality_combo = QComboBox()
        self.technicality_combo.addItem("-- Not rated --", None)
        for level in TechnicalityLevel.all():
            self.technicality_combo.addItem(level.title(), level)
        self.technicality_combo.currentIndexChanged.connect(self._on_rating_changed)
        technicality_layout.addWidget(self.technicality_combo, 1)

        layout.addLayout(technicality_layout)

        # Style the combos with theme colors
        combo_style = f"""
            QComboBox {{
                padding: 5px;
                border: 1px solid {theme.get_color('border')};
                border-radius: 3px;
                background-color: {theme.get_color('surface')};
                color: {theme.get_color('text_primary')};
            }}
            QComboBox:hover {{
                border-color: {theme.get_color('primary')};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {theme.get_color('surface')};
                color: {theme.get_color('text_primary')};
                selection-background-color: {theme.get_color('primary')};
                selection-color: white;
            }}
        """
        self.importance_combo.setStyleSheet(combo_style)
        self.comprehension_combo.setStyleSheet(combo_style)
        self.technicality_combo.setStyleSheet(combo_style)

    def _on_rating_changed(self):
        """Handle rating change."""
        self._importance = self.importance_combo.currentData()
        self._comprehension = self.comprehension_combo.currentData()
        self._technicality = self.technicality_combo.currentData()

        # Emit signal
        self.rating_changed.emit(
            self._importance or "",
            self._comprehension or "",
            self._technicality or ""
        )

    def set_ratings(self, importance: str = None, comprehension: str = None, technicality: str = None):
        """
        Set current ratings.

        Args:
            importance: Importance rating
            comprehension: Comprehension rating
            technicality: Technicality rating
        """
        # Block signals while setting values
        self.importance_combo.blockSignals(True)
        self.comprehension_combo.blockSignals(True)
        self.technicality_combo.blockSignals(True)

        # Set importance
        if importance:
            index = self.importance_combo.findData(importance)
            if index >= 0:
                self.importance_combo.setCurrentIndex(index)
        else:
            self.importance_combo.setCurrentIndex(0)

        # Set comprehension
        if comprehension:
            index = self.comprehension_combo.findData(comprehension)
            if index >= 0:
                self.comprehension_combo.setCurrentIndex(index)
        else:
            self.comprehension_combo.setCurrentIndex(0)

        # Set technicality
        if technicality:
            index = self.technicality_combo.findData(technicality)
            if index >= 0:
                self.technicality_combo.setCurrentIndex(index)
        else:
            self.technicality_combo.setCurrentIndex(0)

        # Unblock signals
        self.importance_combo.blockSignals(False)
        self.comprehension_combo.blockSignals(False)
        self.technicality_combo.blockSignals(False)

        # Update internal state
        self._importance = importance
        self._comprehension = comprehension
        self._technicality = technicality

    def get_ratings(self) -> tuple:
        """
        Get current ratings.

        Returns:
            Tuple of (importance, comprehension, technicality)
        """
        return (self._importance, self._comprehension, self._technicality)

    def has_any_rating(self) -> bool:
        """
        Check if any rating is set.

        Returns:
            True if at least one rating is set
        """
        return any([self._importance, self._comprehension, self._technicality])
