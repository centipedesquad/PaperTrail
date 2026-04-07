"""
Change Library Location dialog for PaperTrail.
Allows users to relocate the database and/or files (PDFs + sources)
to a new directory, with Export or Create New options.
"""

import os
import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QRadioButton, QButtonGroup,
    QGroupBox, QFormLayout, QFileDialog, QProgressBar,
    QMessageBox, QApplication
)
from PySide6.QtCore import Qt
from ui.theme import get_theme_manager, FONT_BODY_STACK
from utils.library_migration import (
    read_config, export_library, create_new_library,
    null_file_paths_in_db
)
from utils.async_utils import LibraryMigrationWorker
from database.connection import get_database, close_database

logger = logging.getLogger(__name__)


class ChangeLibraryDialog(QDialog):
    """Dialog for changing library database and files locations."""

    def __init__(self, config_service, parent=None):
        super().__init__(parent)
        self.config_service = config_service
        self._worker = None

        # Read current paths
        try:
            self._current_db_dir, self._current_files_dir = read_config()
        except (FileNotFoundError, ValueError):
            db_loc = config_service.get_database_location()
            self._current_db_dir = db_loc or ""
            self._current_files_dir = db_loc or ""

        self.setWindowTitle("Change Library Location")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        theme = get_theme_manager()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Header
        header = QLabel("Change Library Location")
        header.setStyleSheet(
            f"font-family: {FONT_BODY_STACK}; font-size: 18px; font-weight: 500; "
            f"color: {theme.get_color('text_primary')};"
        )
        layout.addWidget(header)

        desc = QLabel(
            "Choose new locations for your database and files. "
            "The application will restart after applying changes."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; font-size: 13px;"
        )
        layout.addWidget(desc)

        # Paths group
        paths_group = QGroupBox("Locations")
        paths_form = QFormLayout(paths_group)
        paths_form.setContentsMargins(16, 20, 16, 16)
        paths_form.setSpacing(12)
        paths_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Database path
        db_layout = QHBoxLayout()
        db_layout.setSpacing(8)
        self._db_path_edit = QLineEdit()
        self._db_path_edit.setText(self._current_db_dir)
        self._db_path_edit.setMinimumWidth(350)
        self._db_path_edit.setReadOnly(True)
        db_layout.addWidget(self._db_path_edit)

        db_browse_btn = QPushButton("Browse...")
        db_browse_btn.setMinimumWidth(90)
        db_browse_btn.clicked.connect(self._browse_db_dir)
        db_layout.addWidget(db_browse_btn)

        paths_form.addRow("Database:", db_layout)

        # Files path
        files_layout = QHBoxLayout()
        files_layout.setSpacing(8)
        self._files_path_edit = QLineEdit()
        self._files_path_edit.setText(self._current_files_dir)
        self._files_path_edit.setMinimumWidth(350)
        self._files_path_edit.setReadOnly(True)
        files_layout.addWidget(self._files_path_edit)

        files_browse_btn = QPushButton("Browse...")
        files_browse_btn.setMinimumWidth(90)
        files_browse_btn.clicked.connect(self._browse_files_dir)
        files_layout.addWidget(files_browse_btn)

        paths_form.addRow("PDF & Source Files:", files_layout)

        layout.addWidget(paths_group)

        # Mode group
        mode_group = QGroupBox("Migration Mode")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setContentsMargins(16, 20, 16, 16)
        mode_layout.setSpacing(8)

        self._mode_group = QButtonGroup(self)

        self._export_radio = QRadioButton("Export existing library")
        self._export_radio.setChecked(True)
        self._mode_group.addButton(self._export_radio, 0)
        mode_layout.addWidget(self._export_radio)

        export_desc = QLabel(
            "Copies your database and files to the new locations. "
            "All paper links are preserved. Old files remain at the current location."
        )
        export_desc.setWordWrap(True)
        export_desc.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; font-size: 12px; "
            f"margin-left: 24px; margin-bottom: 8px;"
        )
        mode_layout.addWidget(export_desc)

        self._create_new_radio = QRadioButton("Create new library")
        self._mode_group.addButton(self._create_new_radio, 1)
        mode_layout.addWidget(self._create_new_radio)

        new_desc = QLabel(
            "Creates a fresh, empty library. Your current library is untouched."
        )
        new_desc.setWordWrap(True)
        new_desc.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; font-size: 12px; "
            f"margin-left: 24px;"
        )
        mode_layout.addWidget(new_desc)

        layout.addWidget(mode_group)

        # Progress bar (hidden initially)
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setTextVisible(True)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        self._status_label.setVisible(False)
        self._status_label.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; font-size: 12px;"
        )
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        buttons_layout.addWidget(self._cancel_btn)

        self._apply_btn = QPushButton("Apply && Restart")
        self._apply_btn.setStyleSheet(theme.get_widget_style('button_primary'))
        self._apply_btn.clicked.connect(self._on_apply)
        buttons_layout.addWidget(self._apply_btn)

        layout.addLayout(buttons_layout)

    def _browse_db_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Choose Database Directory",
            self._db_path_edit.text() or str(Path.home()),
            QFileDialog.ShowDirsOnly
        )
        if path:
            self._db_path_edit.setText(path)

    def _browse_files_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Choose Files Directory",
            self._files_path_edit.text() or str(Path.home()),
            QFileDialog.ShowDirsOnly
        )
        if path:
            self._files_path_edit.setText(path)

    def _validate(self):
        """Validate paths. Returns (db_changed, files_changed) or None if invalid."""
        new_db = self._db_path_edit.text().strip()
        new_files = self._files_path_edit.text().strip()

        if not new_db or not new_files:
            QMessageBox.warning(self, "Invalid Path", "Both paths must be specified.")
            return None

        db_changed = os.path.normpath(new_db) != os.path.normpath(self._current_db_dir)
        files_changed = os.path.normpath(new_files) != os.path.normpath(self._current_files_dir)

        if not db_changed and not files_changed:
            QMessageBox.information(
                self, "No Changes",
                "The selected paths are the same as the current locations."
            )
            return None

        # Check that paths are writable
        for label, path in [("Database", new_db), ("Files", new_files)]:
            parent = os.path.dirname(path) if not os.path.exists(path) else path
            if not os.path.exists(parent):
                while parent and not os.path.exists(parent):
                    parent = os.path.dirname(parent)
            if parent and not os.access(parent, os.W_OK):
                QMessageBox.warning(
                    self, "Permission Denied",
                    f"Cannot write to {label.lower()} directory:\n{path}"
                )
                return None

        # Check not nested
        norm_db = os.path.normpath(new_db) + os.sep
        norm_files = os.path.normpath(new_files) + os.sep
        if norm_db != norm_files:
            if norm_db.startswith(norm_files) or norm_files.startswith(norm_db):
                QMessageBox.warning(
                    self, "Invalid Paths",
                    "Database and files directories cannot be nested inside each other."
                )
                return None

        # For Export mode, check destination doesn't already have a database
        if self._export_radio.isChecked() and db_changed:
            dest_db = os.path.join(new_db, "papertrail.db")
            if os.path.exists(dest_db):
                reply = QMessageBox.question(
                    self, "Database Exists",
                    f"A database already exists at:\n{dest_db}\n\n"
                    "Overwrite it?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return None

        return db_changed, files_changed

    def _on_apply(self):
        result = self._validate()
        if result is None:
            return

        db_changed, files_changed = result
        new_db = self._db_path_edit.text().strip()
        new_files = self._files_path_edit.text().strip()
        is_export = self._export_radio.isChecked()

        # Size estimate for export mode
        if is_export and files_changed:
            from utils.library_migration import count_directory_size
            old_pdfs = os.path.join(self._current_files_dir, "pdfs")
            old_sources = os.path.join(self._current_files_dir, "sources")
            total_bytes = count_directory_size(old_pdfs, old_sources)
            if total_bytes > 0:
                size_mb = total_bytes / (1024 * 1024)
                if size_mb >= 1024:
                    size_str = f"{size_mb / 1024:.1f} GB"
                else:
                    size_str = f"{size_mb:.0f} MB"
                reply = QMessageBox.question(
                    self, "Confirm Export",
                    f"About to copy {size_str} of files.\nContinue?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply != QMessageBox.Yes:
                    return

        # Quiesce workers via main window
        main_window = self.parent()
        if main_window and hasattr(main_window, '_stop_all_workers'):
            main_window._stop_all_workers()

        if is_export:
            self._run_export(new_db, new_files, db_changed, files_changed)
        else:
            self._run_create_new(new_db, new_files, db_changed, files_changed)

    def _run_export(self, new_db_dir: str, new_files_dir: str,
                    db_changed: bool, files_changed: bool):
        # WAL checkpoint before copy
        if db_changed:
            try:
                db = get_database()
                db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                close_database()
                logger.info("WAL checkpoint completed, database connection closed")
            except Exception as e:
                logger.warning(f"WAL checkpoint failed, proceeding with copy: {e}")

        # Disable UI during migration
        self._apply_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._status_label.setVisible(True)

        self._worker = LibraryMigrationWorker(
            export_library,
            old_db_dir=self._current_db_dir,
            new_db_dir=new_db_dir,
            old_files_dir=self._current_files_dir,
            new_files_dir=new_files_dir,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(
            lambda ok: self._on_export_finished(ok, new_db_dir, new_files_dir,
                                                 db_changed, files_changed)
        )
        self._worker.error.connect(self._on_migration_error)
        self._worker.start()

    def _run_create_new(self, new_db_dir: str, new_files_dir: str,
                        db_changed: bool, files_changed: bool):
        try:
            # If only files changed (DB stays), null out paths in current DB
            if not db_changed and files_changed:
                db_path = os.path.join(self._current_db_dir, "papertrail.db")
                null_file_paths_in_db(db_path)

                # Create new files directories
                for subdir in ["pdfs", "sources", "cache", os.path.join("cache", "sources")]:
                    os.makedirs(os.path.join(new_files_dir, subdir), exist_ok=True)

                # Update config (db stays same, files_dir changes)
                from utils.library_migration import write_config
                write_config(self._current_db_dir, new_files_dir)
            else:
                # Create entirely new library
                create_new_library(new_db_dir, new_files_dir)

            self._show_completion_dialog(new_db_dir, new_files_dir, False, False)

        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to create new library:\n\n{str(e)}"
            )
            self._apply_btn.setEnabled(True)

    def _on_progress(self, percentage: int, message: str):
        self._progress_bar.setValue(max(0, percentage))
        self._status_label.setText(message)

    def _on_export_finished(self, success: bool, new_db_dir: str, new_files_dir: str,
                            db_changed: bool, files_changed: bool):
        if success:
            self._show_completion_dialog(
                new_db_dir, new_files_dir,
                db_changed, files_changed
            )
        else:
            self._on_migration_error("Migration did not complete successfully.")

    def _on_migration_error(self, error_msg: str):
        self._progress_bar.setVisible(False)
        self._status_label.setVisible(False)
        self._apply_btn.setEnabled(True)
        QMessageBox.critical(
            self, "Migration Error",
            f"Library migration failed:\n\n{error_msg}\n\n"
            "Your current library is unchanged."
        )

    def _show_completion_dialog(self, new_db_dir: str, new_files_dir: str,
                                db_changed: bool, files_changed: bool):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Migration Complete")

        text = "Library moved successfully.\nPlease restart PaperTrail."

        # Show old paths for cleanup info
        old_paths = []
        if db_changed:
            old_paths.append(f"Database: {self._current_db_dir}")
        if files_changed:
            old_paths.append(f"Files: {self._current_files_dir}")

        if old_paths:
            text += "\n\nYour old library is still at:\n"
            text += "\n".join(f"  {p}" for p in old_paths)
            text += "\n\nYou can safely delete these folders."

        msg.setText(text)

        if old_paths:
            show_btn = msg.addButton("Show in Finder", QMessageBox.ActionRole)
        ok_btn = msg.addButton("OK", QMessageBox.AcceptRole)

        msg.exec()

        if old_paths and msg.clickedButton() == show_btn:
            old_dir = self._current_db_dir if db_changed else self._current_files_dir
            from utils.platform_utils import open_directory
            open_directory(old_dir)

        QApplication.quit()

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        self.reject()

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
