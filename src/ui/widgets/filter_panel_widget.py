"""
Navigation rail widget.
Slim left sidebar with library views and category navigation.
"""

import logging
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QApplication
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from ui.theme import get_theme_manager

logger = logging.getLogger(__name__)


class NavItem(QWidget):
    """Clickable navigation item with label and count."""

    clicked = Signal(str, object)  # item_key, filter_value

    def __init__(self, label: str, count: int = 0, key: str = "", filter_value=None, parent=None):
        super().__init__(parent)
        self.key = key
        self.filter_value = filter_value
        self.is_active = False

        self.setCursor(QCursor(Qt.PointingHandCursor))

        theme = get_theme_manager()
        base_font_size = QApplication.instance().font().pointSize() or 11

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(0)

        row = QWidget()
        from PySide6.QtWidgets import QHBoxLayout
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        self.label_widget = QLabel(label)
        self.label_widget.setStyleSheet(f"color: {theme.get_color('text_secondary')}; border: none; background: transparent;")
        row_layout.addWidget(self.label_widget)

        row_layout.addStretch()

        self.count_label = QLabel(str(count) if count > 0 else "")
        self.count_label.setFont(theme.get_mono_font(size_pt=int(base_font_size * 0.82)))
        self.count_label.setStyleSheet(f"color: {theme.get_color('text_tertiary')}; border: none; background: transparent;")
        row_layout.addWidget(self.count_label)

        layout.addWidget(row)
        self._apply_style()

    def set_active(self, active: bool):
        self.is_active = active
        self._apply_style()

    def set_count(self, count: int):
        self.count_label.setText(str(count) if count > 0 else "")

    def _apply_style(self):
        theme = get_theme_manager()
        if self.is_active:
            self.setStyleSheet(f"""
                QWidget {{
                    background-color: {theme.get_color('primary_light')};
                    border-radius: 2px;
                }}
            """)
            self.label_widget.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: 500; border: none; background: transparent;")
        else:
            self.setStyleSheet(f"""
                QWidget {{
                    background-color: transparent;
                    border-radius: 2px;
                }}
                QWidget:hover {{
                    background-color: {theme.get_color('surface_hover')};
                }}
            """)
            self.label_widget.setStyleSheet(f"color: {theme.get_color('text_secondary')}; border: none; background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.key, self.filter_value)
        super().mousePressEvent(event)


class FilterPanelWidget(QWidget):
    """Navigation rail with library views and category quick-access."""

    # Signal emitted when a nav item is selected — carries a filter dict
    filters_changed = Signal(dict)

    # Category groups for display ordering
    CATEGORY_GROUPS = {
        'Physics': ['hep-th', 'hep-ph', 'hep-ex', 'hep-lat', 'gr-qc', 'quant-ph', 'nucl-th', 'nucl-ex', 'physics'],
        'Condensed Matter': ['cond-mat'],
        'Astrophysics': ['astro-ph'],
        'Mathematics': ['math'],
        'Computer Science': ['cs'],
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nav_items = {}
        self.category_items = {}
        self.active_key = "all"
        self._total_count = 0
        self._category_counts = {}
        self._setup_ui()

    def _setup_ui(self):
        theme = get_theme_manager()
        base_font_size = QApplication.instance().font().pointSize() or 11

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {theme.get_color('surface')};
                border-right: 1px solid {theme.get_color('border')};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 16, 8, 16)
        main_layout.setSpacing(0)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("border: none;")

        container = QWidget()
        container.setStyleSheet("border: none;")
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        self.container_layout.setAlignment(Qt.AlignTop)

        # --- Library section ---
        self.container_layout.addWidget(self._make_section_heading("Library"))

        self._add_nav_item("All Papers", "all", {"view": "all"})
        self._add_nav_item("Recent", "recent", {"view": "recent"})
        self._add_nav_item("Unread", "unread", {"view": "unread"})
        self._add_nav_item("Rated", "rated", {"view": "rated"})

        # Set "All Papers" as active by default
        if "all" in self.nav_items:
            self.nav_items["all"].set_active(True)

        self.container_layout.addSpacing(16)

        # --- Categories section (populated dynamically) ---
        self.container_layout.addWidget(self._make_section_heading("Categories"))

        self.categories_container = QWidget()
        self.categories_container.setStyleSheet("border: none;")
        self.categories_layout = QVBoxLayout(self.categories_container)
        self.categories_layout.setContentsMargins(0, 0, 0, 0)
        self.categories_layout.setSpacing(0)
        self.container_layout.addWidget(self.categories_container)

        self.container_layout.addSpacing(16)

        # --- Actions section ---
        self.container_layout.addWidget(self._make_section_heading("Actions"))

        fetch_item = NavItem("Fetch Papers", key="action_fetch")
        fetch_item.clicked.connect(self._on_action_clicked)
        self.container_layout.addWidget(fetch_item)

        prefs_item = NavItem("Preferences", key="action_prefs")
        prefs_item.clicked.connect(self._on_action_clicked)
        self.container_layout.addWidget(prefs_item)

        self.container_layout.addStretch()

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
            padding: 4px 10px 6px 10px;
            border: none;
        """)
        return label

    def _add_nav_item(self, label: str, key: str, filter_value: dict):
        item = NavItem(label, key=key, filter_value=filter_value)
        item.clicked.connect(self._on_nav_clicked)
        self.container_layout.addWidget(item)
        self.nav_items[key] = item

    def _on_nav_clicked(self, key: str, filter_value):
        """Handle navigation item click."""
        # Update active state
        self._set_active(key)

        # Build filter dict from the view
        filters = self._build_filters(filter_value)
        self.filters_changed.emit(filters)

    def _on_action_clicked(self, key: str, filter_value):
        """Handle action item click — emit special filter with action key."""
        self.filters_changed.emit({"_action": key})

    def _on_category_clicked(self, key: str, filter_value):
        """Handle category item click."""
        self._set_active(key)
        filters = {"categories": [filter_value], "sort_by": "date_desc"}
        self.filters_changed.emit(filters)

    def _set_active(self, key: str):
        """Set the active nav item."""
        # Deactivate previous
        if self.active_key in self.nav_items:
            self.nav_items[self.active_key].set_active(False)
        if self.active_key in self.category_items:
            self.category_items[self.active_key].set_active(False)

        self.active_key = key

        if key in self.nav_items:
            self.nav_items[key].set_active(True)
        elif key in self.category_items:
            self.category_items[key].set_active(True)

    def _build_filters(self, view_filter: dict) -> dict:
        """Build a filter dict from a view selection."""
        view = view_filter.get("view", "all")
        filters = {"sort_by": "date_desc"}

        if view == "recent":
            from datetime import datetime, timedelta
            date_to = datetime.now().date()
            date_from = date_to - timedelta(days=7)
            filters["date_from"] = date_from.isoformat()
            filters["date_to"] = date_to.isoformat()
        elif view == "unread":
            filters["has_rating"] = False
        elif view == "rated":
            filters["has_rating"] = True
        # "all" has no extra filters

        return filters

    def set_categories(self, categories: List[tuple], category_counts: dict = None):
        """Populate the categories section of the nav rail."""
        category_counts = category_counts or {}
        self._category_counts = category_counts

        # Clear existing category items
        for item in self.category_items.values():
            item.deleteLater()
        self.category_items.clear()

        # Sort by count descending, take top items with papers
        cats_with_counts = [
            (code, name, category_counts.get(code, 0))
            for code, name in categories
        ]
        cats_with_counts.sort(key=lambda x: -x[2])

        # Show categories that have papers
        shown = 0
        for code, name, count in cats_with_counts:
            if count <= 0:
                continue
            if shown >= 15:
                break

            item = NavItem(code, count=count, key=f"cat_{code}", filter_value=code)
            item.clicked.connect(self._on_category_clicked)
            self.categories_layout.addWidget(item)
            self.category_items[f"cat_{code}"] = item
            shown += 1

        # Update library counts
        total = sum(category_counts.values()) if category_counts else 0
        self._total_count = total
        if "all" in self.nav_items:
            self.nav_items["all"].set_count(total)

        logger.info(f"Nav rail: {shown} categories shown, {total} total papers")

    def get_filters(self) -> dict:
        """Get current filter state based on active selection."""
        if self.active_key in self.nav_items:
            item = self.nav_items[self.active_key]
            return self._build_filters(item.filter_value)
        elif self.active_key in self.category_items:
            item = self.category_items[self.active_key]
            code = item.filter_value
            return {"categories": [code], "sort_by": "date_desc"}
        return {"sort_by": "date_desc"}

    def get_active_label(self) -> str:
        """Get the label of the currently active nav item."""
        if self.active_key in self.nav_items:
            return self.nav_items[self.active_key].label_widget.text()
        elif self.active_key in self.category_items:
            return self.category_items[self.active_key].label_widget.text()
        return "All Papers"

    def clear_filters(self):
        """Reset to 'All Papers' view."""
        self._set_active("all")
        self.filters_changed.emit(self._build_filters({"view": "all"}))
