"""
Preferences dialog.
Allows users to configure application settings.
"""

import os
import sys
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QSpinBox,
    QGroupBox, QFormLayout, QFileDialog, QTabWidget, QWidget
)
from PySide6.QtCore import Qt
from ui.theme import get_theme_manager

logger = logging.getLogger(__name__)


class PreferencesDialog(QDialog):
    """Dialog for application preferences."""

    def __init__(self, config_service, parent=None):
        """
        Initialize preferences dialog.

        Args:
            config_service: Configuration service instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.config_service = config_service
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        theme = get_theme_manager()

        # Create tab widget for different categories
        tabs = QTabWidget()

        # Storage tab
        storage_tab = QWidget()
        storage_layout = QVBoxLayout(storage_tab)
        storage_layout.setContentsMargins(16, 16, 16, 16)
        storage_layout.setSpacing(16)

        # Current locations group
        locations_group = QGroupBox("Current Library Locations")
        locations_form = QFormLayout(locations_group)
        locations_form.setContentsMargins(16, 20, 16, 16)
        locations_form.setSpacing(12)
        locations_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Database path
        db_row = QHBoxLayout()
        db_row.setSpacing(8)
        self._storage_db_label = QLineEdit()
        self._storage_db_label.setReadOnly(True)
        self._storage_db_label.setMinimumWidth(300)
        db_row.addWidget(self._storage_db_label)
        db_finder_btn = QPushButton("Show in Finder" if sys.platform == 'darwin' else "Open Folder")
        db_finder_btn.setMinimumWidth(120)
        db_finder_btn.clicked.connect(lambda: self._show_in_finder(self._storage_db_label.text()))
        db_row.addWidget(db_finder_btn)
        locations_form.addRow("Database:", db_row)

        # Files path
        files_row = QHBoxLayout()
        files_row.setSpacing(8)
        self._storage_files_label = QLineEdit()
        self._storage_files_label.setReadOnly(True)
        self._storage_files_label.setMinimumWidth(300)
        files_row.addWidget(self._storage_files_label)
        files_finder_btn = QPushButton("Show in Finder" if sys.platform == 'darwin' else "Open Folder")
        files_finder_btn.setMinimumWidth(120)
        files_finder_btn.clicked.connect(lambda: self._show_in_finder(self._storage_files_label.text()))
        files_row.addWidget(files_finder_btn)
        locations_form.addRow("PDF & Source Files:", files_row)

        storage_layout.addWidget(locations_group)

        # Change location button
        change_btn = QPushButton("Change Library Location...")
        change_btn.setMinimumWidth(220)
        change_btn.clicked.connect(self._open_change_library_dialog)
        change_btn_layout = QHBoxLayout()
        change_btn_layout.addWidget(change_btn)
        change_btn_layout.addStretch()
        storage_layout.addLayout(change_btn_layout)

        # Previous library section (shown only if previous paths exist)
        self._prev_group = QGroupBox("Previous Library (can be deleted)")
        prev_layout = QVBoxLayout(self._prev_group)
        prev_layout.setContentsMargins(16, 20, 16, 16)
        prev_layout.setSpacing(8)

        self._prev_db_row = QHBoxLayout()
        self._prev_db_label = QLabel()
        self._prev_db_label.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; font-size: 12px;"
        )
        self._prev_db_row.addWidget(self._prev_db_label)
        self._prev_db_finder_btn = QPushButton("Show in Finder" if sys.platform == 'darwin' else "Open Folder")
        self._prev_db_finder_btn.setMaximumWidth(120)
        self._prev_db_row.addWidget(self._prev_db_finder_btn)
        prev_layout.addLayout(self._prev_db_row)

        self._prev_files_row = QHBoxLayout()
        self._prev_files_label = QLabel()
        self._prev_files_label.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; font-size: 12px;"
        )
        self._prev_files_row.addWidget(self._prev_files_label)
        self._prev_files_finder_btn = QPushButton("Show in Finder" if sys.platform == 'darwin' else "Open Folder")
        self._prev_files_finder_btn.setMaximumWidth(120)
        self._prev_files_row.addWidget(self._prev_files_finder_btn)
        prev_layout.addLayout(self._prev_files_row)

        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.setMaximumWidth(100)
        dismiss_btn.clicked.connect(self._dismiss_previous_paths)
        prev_layout.addWidget(dismiss_btn)

        storage_layout.addWidget(self._prev_group)

        storage_layout.addStretch()

        # General tab
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_layout.setContentsMargins(16, 16, 16, 16)
        general_layout.setSpacing(16)

        # Theme settings
        theme_group = QGroupBox("Appearance")
        theme_form = QFormLayout(theme_group)
        theme_form.setContentsMargins(16, 20, 16, 16)
        theme_form.setSpacing(12)
        theme_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.setMinimumWidth(200)
        theme_form.addRow("Theme:", self.theme_combo)

        general_layout.addWidget(theme_group)

        # Font size settings
        font_group = QGroupBox("Font Size")
        font_form = QFormLayout(font_group)
        font_form.setContentsMargins(16, 20, 16, 16)
        font_form.setSpacing(12)
        font_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setMinimum(8)
        self.font_size_spin.setMaximum(20)
        self.font_size_spin.setValue(11)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setMinimumWidth(100)
        font_form.addRow("Base font size:", self.font_size_spin)

        font_help = QLabel("Changes will apply after restarting the application")
        font_help.setWordWrap(True)
        font_help.setStyleSheet(f"color: {theme.get_color('text_secondary')}; font-size: 10pt; font-style: italic;")
        font_form.addRow("", font_help)

        general_layout.addWidget(font_group)
        general_layout.addStretch()

        tabs.addTab(general_tab, "General")

        # PDF tab
        pdf_tab = QWidget()
        pdf_layout = QVBoxLayout(pdf_tab)
        pdf_layout.setContentsMargins(16, 16, 16, 16)
        pdf_layout.setSpacing(16)

        # PDF reader settings
        reader_group = QGroupBox("PDF Reader")
        reader_form = QFormLayout(reader_group)
        reader_form.setContentsMargins(16, 20, 16, 16)
        reader_form.setSpacing(12)
        reader_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        reader_layout = QHBoxLayout()
        reader_layout.setSpacing(8)
        self.reader_path_edit = QLineEdit()
        self.reader_path_edit.setPlaceholderText("Leave empty for system default")
        self.reader_path_edit.setMinimumWidth(300)
        reader_layout.addWidget(self.reader_path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.setMinimumWidth(100)
        browse_btn.clicked.connect(self._browse_reader)
        reader_layout.addWidget(browse_btn)

        reader_form.addRow("PDF Reader Path:", reader_layout)

        pdf_layout.addWidget(reader_group)

        # PDF download settings
        download_group = QGroupBox("PDF Download")
        download_form = QFormLayout(download_group)
        download_form.setContentsMargins(16, 20, 16, 16)
        download_form.setSpacing(12)
        download_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.download_preference_combo = QComboBox()
        self.download_preference_combo.addItem("Always ask", "ask")
        self.download_preference_combo.addItem("Always download & keep", "download")
        self.download_preference_combo.addItem("Always stream (temporary)", "stream")
        self.download_preference_combo.setMinimumWidth(200)
        download_form.addRow("Default action:", self.download_preference_combo)

        pdf_layout.addWidget(download_group)

        # PDF naming settings
        naming_group = QGroupBox("PDF File Naming")
        naming_form = QFormLayout(naming_group)
        naming_form.setContentsMargins(16, 20, 16, 16)
        naming_form.setSpacing(12)
        naming_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.naming_pattern_edit = QLineEdit()
        self.naming_pattern_edit.setPlaceholderText("[{author1}_{author2}][{title}][{arxiv_id}].pdf")
        self.naming_pattern_edit.setMinimumWidth(300)
        naming_form.addRow("Pattern:", self.naming_pattern_edit)

        pattern_help = QLabel(
            "Available variables: {author1}, {author2}, {authors_all}, "
            "{title}, {arxiv_id}, {year}"
        )
        pattern_help.setWordWrap(True)
        pattern_help.setStyleSheet(f"color: {theme.get_color('text_secondary')}; font-size: 10pt; font-style: italic;")
        naming_form.addRow("", pattern_help)

        pdf_layout.addWidget(naming_group)
        pdf_layout.addStretch()

        tabs.addTab(pdf_tab, "PDF")

        # Fetch tab
        fetch_tab = QWidget()
        fetch_layout = QVBoxLayout(fetch_tab)
        fetch_layout.setContentsMargins(16, 16, 16, 16)
        fetch_layout.setSpacing(16)

        fetch_group = QGroupBox("Paper Fetching")
        fetch_form = QFormLayout(fetch_group)
        fetch_form.setContentsMargins(16, 20, 16, 16)
        fetch_form.setSpacing(12)
        fetch_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.max_results_spin = QSpinBox()
        self.max_results_spin.setMinimum(10)
        self.max_results_spin.setMaximum(500)
        self.max_results_spin.setValue(50)
        self.max_results_spin.setMinimumWidth(100)
        fetch_form.addRow("Max results per category:", self.max_results_spin)

        self.fetch_mode_combo = QComboBox()
        self.fetch_mode_combo.addItem("New submissions", "new")
        self.fetch_mode_combo.addItem("Recent papers", "recent")
        self.fetch_mode_combo.setMinimumWidth(200)
        fetch_form.addRow("Default mode:", self.fetch_mode_combo)

        self.recent_days_spin = QSpinBox()
        self.recent_days_spin.setMinimum(1)
        self.recent_days_spin.setMaximum(30)
        self.recent_days_spin.setValue(7)
        self.recent_days_spin.setMinimumWidth(100)
        fetch_form.addRow("Recent papers (days):", self.recent_days_spin)

        fetch_layout.addWidget(fetch_group)
        fetch_layout.addStretch()

        tabs.addTab(fetch_tab, "Fetching")

        tabs.addTab(storage_tab, "Storage")

        layout.addWidget(tabs)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        buttons_layout.addWidget(reset_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_settings)
        save_btn.setDefault(True)
        save_btn.setStyleSheet(theme.get_widget_style('button_primary'))
        buttons_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

    def _load_settings(self):
        """Load current settings into UI."""
        # Storage paths
        try:
            from utils.library_migration import read_config, read_previous_paths
            db_dir, files_dir = read_config()
            self._storage_db_label.setText(db_dir)
            self._storage_files_label.setText(files_dir)

            prev_db, prev_files = read_previous_paths()
            if prev_db or prev_files:
                self._prev_group.setVisible(True)
                if prev_db:
                    self._prev_db_label.setText(f"Database: {prev_db}")
                    self._prev_db_finder_btn.clicked.connect(
                        lambda checked=False, p=prev_db: self._show_in_finder(p)
                    )
                else:
                    self._prev_db_label.setVisible(False)
                    self._prev_db_finder_btn.setVisible(False)

                if prev_files:
                    self._prev_files_label.setText(f"Files: {prev_files}")
                    self._prev_files_finder_btn.clicked.connect(
                        lambda checked=False, p=prev_files: self._show_in_finder(p)
                    )
                else:
                    self._prev_files_label.setVisible(False)
                    self._prev_files_finder_btn.setVisible(False)
            else:
                self._prev_group.setVisible(False)
        except (FileNotFoundError, ValueError):
            db_loc = self.config_service.get_database_location() or ""
            self._storage_db_label.setText(db_loc)
            self._storage_files_label.setText(db_loc)
            self._prev_group.setVisible(False)

        # Theme
        theme = self.config_service.get_theme()
        index = self.theme_combo.findData(theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        # Font size
        font_size = self.config_service.get_font_size()
        self.font_size_spin.setValue(font_size)

        # PDF reader
        reader_path = self.config_service.get_pdf_reader_path()
        if reader_path:
            self.reader_path_edit.setText(reader_path)

        # Download preference
        download_pref = self.config_service.get_download_preference()
        index = self.download_preference_combo.findData(download_pref)
        if index >= 0:
            self.download_preference_combo.setCurrentIndex(index)

        # Naming pattern
        pattern = self.config_service.get_pdf_naming_pattern()
        self.naming_pattern_edit.setText(pattern)

        # Fetch settings
        self.max_results_spin.setValue(self.config_service.get_max_fetch_results())

        fetch_mode = self.config_service.get_fetch_mode()
        index = self.fetch_mode_combo.findData(fetch_mode)
        if index >= 0:
            self.fetch_mode_combo.setCurrentIndex(index)

        self.recent_days_spin.setValue(self.config_service.get_recent_days())

    def _save_settings(self):
        """Save settings from UI to config."""
        try:
            # Theme
            theme = self.theme_combo.currentData()
            self.config_service.set_theme(theme)

            # Font size
            font_size = self.font_size_spin.value()
            self.config_service.set_font_size(font_size)

            # PDF reader
            reader_path = self.reader_path_edit.text().strip()
            if reader_path:
                self.config_service.set_pdf_reader_path(reader_path)
            else:
                # Clear the setting if empty
                self.config_service.delete('pdf_reader_path')

            # Download preference
            download_pref = self.download_preference_combo.currentData()
            self.config_service.set_download_preference(download_pref)

            # Naming pattern
            pattern = self.naming_pattern_edit.text().strip()
            if pattern:
                self.config_service.set_pdf_naming_pattern(pattern)

            # Fetch settings
            self.config_service.set_max_fetch_results(self.max_results_spin.value())
            self.config_service.set_fetch_mode(self.fetch_mode_combo.currentData())
            self.config_service.set_recent_days(self.recent_days_spin.value())

            logger.info("Settings saved successfully")
            self.accept()

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings:\n\n{str(e)}"
            )

    def _reset_defaults(self):
        """Reset all settings to defaults."""
        self.theme_combo.setCurrentIndex(0)  # Light
        self.font_size_spin.setValue(11)  # Default font size
        self.reader_path_edit.clear()
        self.download_preference_combo.setCurrentIndex(0)  # Ask
        self.naming_pattern_edit.setText("[{author1}_{author2}][{title}][{arxiv_id}].pdf")
        self.max_results_spin.setValue(50)
        self.fetch_mode_combo.setCurrentIndex(0)  # New
        self.recent_days_spin.setValue(7)

    def _show_in_finder(self, path: str):
        """Open a directory in the system file manager."""
        if not path:
            return
        from utils.platform_utils import open_directory
        open_directory(path)

    def _open_change_library_dialog(self):
        """Open the Change Library Location dialog."""
        from ui.dialogs.change_library_dialog import ChangeLibraryDialog
        dialog = ChangeLibraryDialog(self.config_service, self.parent())
        dialog.exec()

    def _dismiss_previous_paths(self):
        """Remove previous library path info from config."""
        from utils.library_migration import dismiss_previous_paths
        dismiss_previous_paths()
        self._prev_group.setVisible(False)

    def _browse_reader(self):
        """Browse for PDF reader application."""
        if sys.platform == 'darwin':
            start_dir = '/Applications'
            filter_str = 'Applications (*.app);;All Files (*)'
        else:
            start_dir = '/usr/bin'
            filter_str = 'All Files (*)'
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select PDF Reader", start_dir, filter_str
        )
        if file_path:
            self.reader_path_edit.setText(file_path)
