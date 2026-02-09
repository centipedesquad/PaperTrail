"""
Filter panel widget for searching and filtering papers.
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QCheckBox, QDateEdit, QComboBox, QPushButton, QGroupBox,
    QScrollArea
)
from PySide6.QtCore import Qt, Signal, QDate

logger = logging.getLogger(__name__)


class FilterPanelWidget(QWidget):
    """Widget for filtering and searching papers."""

    # Signal emitted when filters change
    filters_changed = Signal(dict)  # filter_dict

    def __init__(self, parent=None):
        """
        Initialize filter panel widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.available_categories = []
        self.category_checkboxes = {}
        self._setup_ui()

    def _setup_ui(self):
        """Setup UI components."""
        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Scroll area for filters
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Container for all filter widgets
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(15)
        container_layout.setAlignment(Qt.AlignTop)

        # Search box
        search_group = QGroupBox("Search")
        search_layout = QVBoxLayout(search_group)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search titles, abstracts, authors...")
        self.search_input.returnPressed.connect(self._on_filters_changed)
        search_layout.addWidget(self.search_input)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._on_filters_changed)
        search_layout.addWidget(search_btn)

        container_layout.addWidget(search_group)

        # Categories filter
        self.categories_group = QGroupBox("Categories")
        self.categories_layout = QVBoxLayout(self.categories_group)

        # "All Categories" checkbox
        self.all_categories_cb = QCheckBox("All Categories")
        self.all_categories_cb.setChecked(True)
        self.all_categories_cb.stateChanged.connect(self._on_all_categories_changed)
        self.categories_layout.addWidget(self.all_categories_cb)

        # Category checkboxes will be added dynamically

        container_layout.addWidget(self.categories_group)

        # Date range filter
        date_group = QGroupBox("Date Range")
        date_layout = QVBoxLayout(date_group)

        # Quick date filters
        quick_dates_layout = QHBoxLayout()
        self.date_quick_combo = QComboBox()
        self.date_quick_combo.addItem("Any time", None)
        self.date_quick_combo.addItem("Last 7 days", 7)
        self.date_quick_combo.addItem("Last 30 days", 30)
        self.date_quick_combo.addItem("Last 90 days", 90)
        self.date_quick_combo.addItem("Last year", 365)
        self.date_quick_combo.addItem("Custom range", "custom")
        self.date_quick_combo.currentIndexChanged.connect(self._on_quick_date_changed)
        quick_dates_layout.addWidget(QLabel("Quick:"))
        quick_dates_layout.addWidget(self.date_quick_combo)
        date_layout.addLayout(quick_dates_layout)

        # Custom date range (hidden by default)
        self.custom_date_widget = QWidget()
        custom_date_layout = QVBoxLayout(self.custom_date_widget)
        custom_date_layout.setContentsMargins(0, 5, 0, 0)

        from_layout = QHBoxLayout()
        from_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.dateChanged.connect(self._on_filters_changed)
        from_layout.addWidget(self.date_from)
        custom_date_layout.addLayout(from_layout)

        to_layout = QHBoxLayout()
        to_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self._on_filters_changed)
        to_layout.addWidget(self.date_to)
        custom_date_layout.addLayout(to_layout)

        self.custom_date_widget.setVisible(False)
        date_layout.addWidget(self.custom_date_widget)

        container_layout.addWidget(date_group)

        # Rating filter
        rating_group = QGroupBox("Ratings")
        rating_layout = QVBoxLayout(rating_group)

        self.rating_filter_combo = QComboBox()
        self.rating_filter_combo.addItem("All papers", None)
        self.rating_filter_combo.addItem("Only rated papers", True)
        self.rating_filter_combo.addItem("Only unrated papers", False)
        self.rating_filter_combo.currentIndexChanged.connect(self._on_filters_changed)
        rating_layout.addWidget(self.rating_filter_combo)

        container_layout.addWidget(rating_group)

        # PDF status filter
        pdf_group = QGroupBox("PDF Status")
        pdf_layout = QVBoxLayout(pdf_group)

        self.pdf_filter_combo = QComboBox()
        self.pdf_filter_combo.addItem("All papers", None)
        self.pdf_filter_combo.addItem("Has local PDF", True)
        self.pdf_filter_combo.addItem("No local PDF", False)
        self.pdf_filter_combo.currentIndexChanged.connect(self._on_filters_changed)
        pdf_layout.addWidget(self.pdf_filter_combo)

        container_layout.addWidget(pdf_group)

        # Sorting
        sort_group = QGroupBox("Sort By")
        sort_layout = QVBoxLayout(sort_group)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Date (newest first)", "date_desc")
        self.sort_combo.addItem("Date (oldest first)", "date_asc")
        self.sort_combo.addItem("Title (A-Z)", "title_asc")
        self.sort_combo.addItem("Title (Z-A)", "title_desc")
        self.sort_combo.currentIndexChanged.connect(self._on_filters_changed)
        sort_layout.addWidget(self.sort_combo)

        container_layout.addWidget(sort_group)

        # Clear filters button
        clear_btn = QPushButton("Clear All Filters")
        clear_btn.clicked.connect(self.clear_filters)
        container_layout.addWidget(clear_btn)

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        # Style
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #2c3e50;
            }
        """)

    def set_categories(self, categories: List[tuple]):
        """
        Set available categories.

        Args:
            categories: List of (code, name) tuples
        """
        self.available_categories = categories

        # Clear existing checkboxes (except "All Categories")
        for cb in self.category_checkboxes.values():
            cb.deleteLater()
        self.category_checkboxes.clear()

        # Add checkboxes for each category
        for code, name in sorted(categories, key=lambda x: x[0]):
            cb = QCheckBox(f"{code} - {name}")
            cb.setChecked(False)
            cb.stateChanged.connect(self._on_category_changed)
            self.categories_layout.addWidget(cb)
            self.category_checkboxes[code] = cb

        logger.info(f"Set {len(categories)} categories in filter panel")

    def _on_all_categories_changed(self, state):
        """Handle all categories checkbox change."""
        checked = (state == Qt.Checked)

        # Update all category checkboxes
        for cb in self.category_checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.setEnabled(not checked)
            cb.blockSignals(False)

        self._on_filters_changed()

    def _on_category_changed(self):
        """Handle individual category checkbox change."""
        # If any category is checked, uncheck "All Categories"
        any_checked = any(cb.isChecked() for cb in self.category_checkboxes.values())
        if any_checked:
            self.all_categories_cb.blockSignals(True)
            self.all_categories_cb.setChecked(False)
            self.all_categories_cb.blockSignals(False)

        self._on_filters_changed()

    def _on_quick_date_changed(self):
        """Handle quick date selection change."""
        days = self.date_quick_combo.currentData()

        if days == "custom":
            self.custom_date_widget.setVisible(True)
        else:
            self.custom_date_widget.setVisible(False)
            self._on_filters_changed()

    def _on_filters_changed(self):
        """Emit signal when any filter changes."""
        filters = self.get_filters()
        self.filters_changed.emit(filters)

    def get_filters(self) -> dict:
        """
        Get current filter values.

        Returns:
            Dictionary with filter values
        """
        filters = {}

        # Search text
        search_text = self.search_input.text().strip()
        if search_text:
            filters['search_text'] = search_text

        # Categories
        if not self.all_categories_cb.isChecked():
            selected_categories = [
                code for code, cb in self.category_checkboxes.items()
                if cb.isChecked()
            ]
            if selected_categories:
                filters['categories'] = selected_categories

        # Date range
        date_days = self.date_quick_combo.currentData()
        if date_days == "custom":
            filters['date_from'] = self.date_from.date().toString("yyyy-MM-dd")
            filters['date_to'] = self.date_to.date().toString("yyyy-MM-dd")
        elif date_days is not None:
            # Calculate date range from days
            date_to = datetime.now().date()
            date_from = date_to - timedelta(days=date_days)
            filters['date_from'] = date_from.isoformat()
            filters['date_to'] = date_to.isoformat()

        # Rating filter
        has_rating = self.rating_filter_combo.currentData()
        if has_rating is not None:
            filters['has_rating'] = has_rating

        # PDF filter
        has_pdf = self.pdf_filter_combo.currentData()
        if has_pdf is not None:
            filters['has_pdf'] = has_pdf

        # Sorting
        filters['sort_by'] = self.sort_combo.currentData()

        return filters

    def clear_filters(self):
        """Clear all filters."""
        # Clear search
        self.search_input.clear()

        # Check "All Categories"
        self.all_categories_cb.setChecked(True)

        # Reset date filter
        self.date_quick_combo.setCurrentIndex(0)

        # Reset rating filter
        self.rating_filter_combo.setCurrentIndex(0)

        # Reset PDF filter
        self.pdf_filter_combo.setCurrentIndex(0)

        # Reset sort
        self.sort_combo.setCurrentIndex(0)

        self._on_filters_changed()
