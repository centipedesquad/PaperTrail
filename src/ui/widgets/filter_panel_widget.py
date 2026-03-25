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
from ui.theme import get_theme_manager

logger = logging.getLogger(__name__)


class FilterPanelWidget(QWidget):
    """Widget for filtering and searching papers."""

    # Signal emitted when filters change
    filters_changed = Signal(dict)  # filter_dict

    # Category groups for hierarchical display
    CATEGORY_GROUPS = {
        'Physics': ['hep-th', 'hep-ph', 'hep-ex', 'hep-lat', 'gr-qc', 'quant-ph', 'nucl-th', 'nucl-ex', 'physics'],
        'Condensed Matter': ['cond-mat', 'cond-mat.stat-mech', 'cond-mat.str-el', 'cond-mat.mes-hall',
                             'cond-mat.mtrl-sci', 'cond-mat.soft', 'cond-mat.supr-con', 'cond-mat.dis-nn', 'cond-mat.quant-gas'],
        'Astrophysics': ['astro-ph', 'astro-ph.CO', 'astro-ph.HE', 'astro-ph.GA', 'astro-ph.SR', 'astro-ph.IM', 'astro-ph.EP'],
        'Mathematics': ['math', 'math.DG', 'math.AG', 'math.AT', 'math.AP', 'math.CT', 'math.CO', 'math-ph'],
        'Computer Science': ['cs', 'cs.AI', 'cs.LG', 'cs.CL', 'cs.CV', 'cs.NE', 'cs.IT'],
    }

    def __init__(self, parent=None):
        """
        Initialize filter panel widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.available_categories = []
        self.category_checkboxes = {}
        self.category_groups_widgets = {}
        self.my_categories_group = None
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
        self.search_input.setToolTip("Full-text search across paper titles, abstracts, and authors")
        self.search_input.returnPressed.connect(self._on_filters_changed)
        search_layout.addWidget(self.search_input)

        search_btn = QPushButton("Search")
        search_btn.setToolTip("Apply search query")
        search_btn.clicked.connect(self._on_filters_changed)
        search_layout.addWidget(search_btn)

        container_layout.addWidget(search_group)

        # Categories filter - hierarchical with search
        self.categories_group = QGroupBox("Categories")
        self.categories_layout = QVBoxLayout(self.categories_group)
        self.categories_layout.setSpacing(8)

        # Category search box
        self.category_search = QLineEdit()
        self.category_search.setPlaceholderText("Search categories...")
        self.category_search.textChanged.connect(self._on_category_search_changed)
        self.categories_layout.addWidget(self.category_search)

        # "All Categories" checkbox
        self.all_categories_cb = QCheckBox("All Categories")
        self.all_categories_cb.setChecked(True)
        self.all_categories_cb.stateChanged.connect(self._on_all_categories_changed)
        self.categories_layout.addWidget(self.all_categories_cb)

        # Scroll area for category groups
        categories_scroll = QScrollArea()
        categories_scroll.setWidgetResizable(True)
        categories_scroll.setFrameShape(QScrollArea.NoFrame)
        categories_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        categories_scroll.setMaximumHeight(300)

        self.categories_container = QWidget()
        self.categories_container_layout = QVBoxLayout(self.categories_container)
        self.categories_container_layout.setContentsMargins(0, 0, 0, 0)
        self.categories_container_layout.setSpacing(5)
        self.categories_container_layout.setAlignment(Qt.AlignTop)

        # Category groups will be added dynamically

        categories_scroll.setWidget(self.categories_container)
        self.categories_layout.addWidget(categories_scroll)

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
        clear_btn.setToolTip("Reset all search and filter criteria")
        clear_btn.clicked.connect(self.clear_filters)
        container_layout.addWidget(clear_btn)

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        # Apply theme styling
        theme = get_theme_manager()
        self.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {theme.get_color('border')};
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {theme.get_color('text_primary')};
            }}
        """ + theme.get_widget_style('filter_panel'))

    def _get_category_group(self, code: str) -> Optional[str]:
        """
        Determine which group a category belongs to using prefix matching.

        Args:
            code: Category code (e.g., 'math.QA', 'physics.optics')

        Returns:
            Group name or None if no match
        """
        # First check explicit matches
        for group_name, group_codes in self.CATEGORY_GROUPS.items():
            if code in group_codes:
                return group_name

        # Then check prefix matches
        # math, math.* -> Mathematics
        if code == 'math' or code.startswith('math.') or code == 'math-ph':
            return 'Mathematics'
        # physics, physics.* -> Physics
        if code == 'physics' or code.startswith('physics.'):
            return 'Physics'
        # cs, cs.* -> Computer Science
        if code == 'cs' or code.startswith('cs.'):
            return 'Computer Science'
        # astro-ph, astro-ph.* -> Astrophysics
        if code == 'astro-ph' or code.startswith('astro-ph.'):
            return 'Astrophysics'
        # cond-mat, cond-mat.* -> Condensed Matter
        if code == 'cond-mat' or code.startswith('cond-mat.'):
            return 'Condensed Matter'
        # hep-*, gr-qc, quant-ph, nucl-*, physics -> Physics (already covered by explicit matching mostly)
        if any(code.startswith(prefix) for prefix in ['hep-', 'nucl-']):
            return 'Physics'
        if code in ['gr-qc', 'quant-ph']:
            return 'Physics'

        return None

    def set_categories(self, categories: List[tuple], category_counts: dict = None):
        """
        Set available categories with hierarchical grouping.

        Args:
            categories: List of (code, name) tuples
            category_counts: Optional dict of {code: count} for "My Categories"
        """
        logger.info(f"set_categories called with {len(categories)} categories and counts: {bool(category_counts)}")
        self.available_categories = categories
        category_counts = category_counts or {}
        logger.info(f"Category counts: {category_counts}")

        # Clear existing widgets
        for cb in self.category_checkboxes.values():
            cb.deleteLater()
        self.category_checkboxes.clear()

        for widget in self.category_groups_widgets.values():
            widget.deleteLater()
        self.category_groups_widgets.clear()

        # Create hierarchical category groups
        logger.info("Creating hierarchical category groups")

        # Group categories by their group name
        grouped_categories = {}
        ungrouped_categories = []

        for code, name in categories:
            group_name = self._get_category_group(code)
            if group_name:
                if group_name not in grouped_categories:
                    grouped_categories[group_name] = []
                grouped_categories[group_name].append((code, name))
            else:
                ungrouped_categories.append((code, name))

        # Create groups in the order defined in CATEGORY_GROUPS
        for group_name in self.CATEGORY_GROUPS.keys():
            if group_name in grouped_categories:
                logger.info(f"Creating group '{group_name}' with {len(grouped_categories[group_name])} categories")
                self._create_category_group(group_name, grouped_categories[group_name], category_counts)

        # Add "Other" group for ungrouped categories
        if ungrouped_categories:
            logger.info(f"Creating 'Other' group with {len(ungrouped_categories)} categories")
            self._create_category_group("Other", ungrouped_categories, category_counts, collapsed=True)

        logger.info(f"Set {len(categories)} categories in hierarchical filter panel")

    def _create_my_categories_group(self, categories: List[tuple], counts: dict):
        """Create 'My Categories' group with paper counts."""
        from PySide6.QtWidgets import QToolButton

        # Container for the group
        group_widget = QWidget()
        group_layout = QVBoxLayout(group_widget)
        group_layout.setContentsMargins(0, 0, 0, 10)
        group_layout.setSpacing(8)

        # Collapsible header
        header = QToolButton()
        header.setText(f"▼ My Categories ({len(categories)})")
        header.setCheckable(True)
        header.setChecked(True)
        header.setStyleSheet("QToolButton { border: none; font-weight: bold; text-align: left; }")
        header.setToolButtonStyle(Qt.ToolButtonTextOnly)

        # Content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(15, 8, 0, 8)
        content_layout.setSpacing(8)

        # Add checkboxes
        for code, name, count in sorted(categories, key=lambda x: x[2], reverse=True):
            cb = QCheckBox(f"{code} ({count})")
            cb.setToolTip(name)
            cb.setChecked(False)
            cb.stateChanged.connect(self._on_category_changed)
            content_layout.addWidget(cb)
            self.category_checkboxes[code] = cb

        # Connect header toggle
        def toggle_content(checked):
            content.setVisible(checked)
            header.setText(f"{'▼' if checked else '▶'} My Categories ({len(categories)})")

        header.toggled.connect(toggle_content)

        group_layout.addWidget(header)
        group_layout.addWidget(content)

        self.categories_container_layout.addWidget(group_widget)
        self.category_groups_widgets['my_categories'] = group_widget

    def _create_category_group(self, group_name: str, categories: List[tuple],
                               category_counts: dict = None, collapsed: bool = True):
        """Create a collapsible category group."""
        from PySide6.QtWidgets import QToolButton

        category_counts = category_counts or {}

        # Container for the group
        group_widget = QWidget()
        group_layout = QVBoxLayout(group_widget)
        group_layout.setContentsMargins(0, 0, 0, 10)
        group_layout.setSpacing(8)

        # Count how many categories in this group have papers
        group_paper_count = sum(1 for code, _ in categories if code in category_counts and category_counts[code] > 0)

        # Collapsible header
        header = QToolButton()
        arrow = '▶' if collapsed else '▼'
        header_text = f"{arrow} {group_name}"
        if group_paper_count > 0:
            header_text += f" ({group_paper_count})"
        header.setText(header_text)
        header.setCheckable(True)
        header.setChecked(not collapsed)
        header.setStyleSheet("QToolButton { border: none; font-weight: bold; text-align: left; }")
        header.setToolButtonStyle(Qt.ToolButtonTextOnly)

        # Content widget
        content = QWidget()
        content.setVisible(not collapsed)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(15, 8, 0, 8)
        content_layout.setSpacing(8)

        # Sort categories: those with papers first (by count desc), then alphabetically
        def sort_key(cat):
            code, name = cat
            count = category_counts.get(code, 0)
            return (-count if count > 0 else 0, code)

        # Add checkboxes
        for code, name in sorted(categories, key=sort_key):
            # Skip if already added
            if code in self.category_checkboxes:
                continue

            # Show count if category has papers
            if code in category_counts and category_counts[code] > 0:
                cb = QCheckBox(f"{code} ({category_counts[code]})")
            else:
                cb = QCheckBox(code)

            cb.setToolTip(f"{code} - {name}")
            cb.setChecked(False)
            cb.stateChanged.connect(self._on_category_changed)
            content_layout.addWidget(cb)
            self.category_checkboxes[code] = cb

        # Connect header toggle
        def toggle_content(checked):
            content.setVisible(checked)
            header.setText(f"{'▼' if checked else '▶'} {group_name}")

        header.toggled.connect(toggle_content)

        group_layout.addWidget(header)
        group_layout.addWidget(content)

        self.categories_container_layout.addWidget(group_widget)
        self.category_groups_widgets[group_name] = group_widget

    def _on_category_search_changed(self, text: str):
        """Filter visible categories based on search text."""
        search_text = text.lower()

        for code, cb in self.category_checkboxes.items():
            # Get full category name from tooltip or text
            tooltip = cb.toolTip().lower() if cb.toolTip() else ""
            checkbox_text = cb.text().lower()

            # Show if search matches code or name
            matches = (not search_text or
                      search_text in code.lower() or
                      search_text in checkbox_text or
                      search_text in tooltip)

            cb.setVisible(matches)

        # Hide empty groups
        for group_name, group_widget in self.category_groups_widgets.items():
            if group_name == 'my_categories':
                continue

            # Check if any checkboxes in this group are visible
            has_visible = any(cb.isVisible()
                            for code, cb in self.category_checkboxes.items()
                            if cb.parent().parent() == group_widget)

            group_widget.setVisible(has_visible or not search_text)

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
