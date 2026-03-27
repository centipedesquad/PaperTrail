"""
Fetch papers dialog.
UI for fetching papers from arXiv.
"""

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QCheckBox,
    QGroupBox, QProgressBar, QMessageBox, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, Signal
from typing import List
from ui.theme import get_theme_manager

logger = logging.getLogger(__name__)


class FetchPapersDialog(QDialog):
    """Dialog for fetching papers from arXiv."""

    # Signal emitted when fetch is requested
    fetch_requested = Signal(str, list, int, int)  # (mode, categories, max_results, days)

    def __init__(self, config_service=None, parent=None):
        """
        Initialize fetch papers dialog.

        Args:
            config_service: Optional ConfigService to load saved preferences
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Fetch Papers from arXiv")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._setup_ui()
        if config_service:
            self._load_preferences(config_service)

    def _setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout(self)

        # Mode selection
        mode_group = QGroupBox("Fetch Mode")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("New Submissions (Today)", "new")
        self.mode_combo.addItem("Recent Papers (Last N Days)", "recent")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)

        # Days selection (for recent mode)
        days_layout = QHBoxLayout()
        days_label = QLabel("Number of days:")
        days_layout.addWidget(days_label)

        self.days_spin = QSpinBox()
        self.days_spin.setMinimum(1)
        self.days_spin.setMaximum(30)
        self.days_spin.setValue(7)
        days_layout.addWidget(self.days_spin)
        days_layout.addStretch()

        self.days_widget = QWidget()
        self.days_widget.setLayout(days_layout)
        self.days_widget.setVisible(False)  # Hidden by default
        mode_layout.addWidget(self.days_widget)

        layout.addWidget(mode_group)

        # Categories selection
        categories_group = QGroupBox("arXiv Categories")
        categories_layout = QVBoxLayout(categories_group)

        # Scroll area for categories
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(200)

        categories_widget = QWidget()
        categories_grid = QVBoxLayout(categories_widget)

        # Common categories
        self.category_checkboxes = {}
        common_categories = [
            ('hep-th', 'High Energy Physics - Theory'),
            ('hep-ph', 'High Energy Physics - Phenomenology'),
            ('hep-ex', 'High Energy Physics - Experiment'),
            ('gr-qc', 'General Relativity and Quantum Cosmology'),
            ('astro-ph', 'Astrophysics (all)'),
            ('astro-ph.CO', 'Astrophysics - Cosmology'),
            ('astro-ph.HE', 'Astrophysics - High Energy'),
            ('astro-ph.GA', 'Astrophysics - Galaxies'),
            ('quant-ph', 'Quantum Physics'),
            ('cond-mat', 'Condensed Matter (all)'),
            ('cond-mat.stat-mech', 'Condensed Matter - Statistical Mechanics'),
            ('cond-mat.str-el', 'Condensed Matter - Strongly Correlated'),
            ('cond-mat.mes-hall', 'Condensed Matter - Mesoscale'),
            ('cond-mat.mtrl-sci', 'Condensed Matter - Materials Science'),
            ('cond-mat.soft', 'Condensed Matter - Soft Matter'),
            ('nucl-th', 'Nuclear Theory'),
            ('nucl-ex', 'Nuclear Experiment'),
            ('math-ph', 'Mathematical Physics'),
            ('math.DG', 'Mathematics - Differential Geometry'),
            ('cs.AI', 'Computer Science - Artificial Intelligence'),
            ('cs.LG', 'Computer Science - Machine Learning'),
        ]

        for code, name in common_categories:
            checkbox = QCheckBox(f"{code} - {name}")
            checkbox.setProperty("category_code", code)
            self.category_checkboxes[code] = checkbox
            categories_grid.addWidget(checkbox)

        scroll_area.setWidget(categories_widget)
        categories_layout.addWidget(scroll_area)

        # Select all / Clear all buttons
        select_buttons_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all_categories)
        select_buttons_layout.addWidget(select_all_btn)

        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.clicked.connect(self._clear_all_categories)
        select_buttons_layout.addWidget(clear_all_btn)

        categories_layout.addLayout(select_buttons_layout)

        layout.addWidget(categories_group)

        # Max results
        results_layout = QHBoxLayout()
        results_label = QLabel("Max results per category:")
        results_layout.addWidget(results_label)

        self.max_results_spin = QSpinBox()
        self.max_results_spin.setMinimum(10)
        self.max_results_spin.setMaximum(500)
        self.max_results_spin.setValue(50)
        results_layout.addWidget(self.max_results_spin)
        results_layout.addStretch()

        layout.addLayout(results_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        theme = get_theme_manager()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {theme.get_color('text_secondary')}; font-style: italic;")
        layout.addWidget(self.status_label)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.fetch_button = QPushButton("Fetch Papers")
        self.fetch_button.clicked.connect(self._on_fetch_clicked)
        self.fetch_button.setStyleSheet(theme.get_widget_style('button_primary'))
        buttons_layout.addWidget(self.fetch_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)

        layout.addLayout(buttons_layout)

    def _load_preferences(self, config_service):
        """Load saved preferences from config service."""
        mode = config_service.get_fetch_mode()
        idx = self.mode_combo.findData(mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.days_spin.setValue(config_service.get_recent_days())
        self.max_results_spin.setValue(config_service.get_max_fetch_results())

    def _on_mode_changed(self, index):
        """Handle mode selection change."""
        mode = self.mode_combo.itemData(index)
        self.days_widget.setVisible(mode == "recent")

    def _select_all_categories(self):
        """Select all category checkboxes."""
        for checkbox in self.category_checkboxes.values():
            checkbox.setChecked(True)

    def _clear_all_categories(self):
        """Clear all category checkboxes."""
        for checkbox in self.category_checkboxes.values():
            checkbox.setChecked(False)

    def _on_fetch_clicked(self):
        """Handle fetch button click."""
        # Get selected categories
        selected_categories = [
            code for code, checkbox in self.category_checkboxes.items()
            if checkbox.isChecked()
        ]

        if not selected_categories:
            QMessageBox.warning(
                self,
                "No Categories Selected",
                "Please select at least one category to fetch papers from."
            )
            return

        # Get other parameters
        mode = self.mode_combo.currentData()
        max_results = self.max_results_spin.value()
        days = self.days_spin.value() if mode == "recent" else 0

        # Disable fetch button
        self.fetch_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting fetch...")

        # Emit signal
        self.fetch_requested.emit(mode, selected_categories, max_results, days)

    def set_progress(self, percentage: int, message: str):
        """
        Update progress.

        Args:
            percentage: Progress percentage (0-100)
            message: Status message
        """
        self.progress_bar.setValue(percentage)
        self.status_label.setText(message)

    def fetch_complete(self, result: dict):
        """
        Handle fetch completion.

        Args:
            result: Fetch result dictionary
        """
        self.progress_bar.setVisible(False)
        self.fetch_button.setEnabled(True)

        fetched = result.get('fetched', 0)
        created = result.get('created', 0)
        duplicates = result.get('duplicates', 0)
        message = (
            f"Fetch complete!\n\n"
            f"Fetched: {fetched} papers\n"
            f"New: {created} papers\n"
            f"Duplicates: {duplicates} papers"
        )

        self.raise_()
        self.activateWindow()
        QMessageBox.information(self, "Fetch Complete", message)
        self.accept()

    def fetch_failed(self, error: str):
        """
        Handle fetch failure.

        Args:
            error: Error message
        """
        self.progress_bar.setVisible(False)
        self.fetch_button.setEnabled(True)
        self.status_label.setText("Fetch failed")

        QMessageBox.critical(
            self,
            "Fetch Failed",
            f"Failed to fetch papers:\n\n{error}"
        )
