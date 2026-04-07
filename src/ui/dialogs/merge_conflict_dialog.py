"""
Merge conflict resolution dialog for PaperTrail.
Shown when merging libraries that contain papers with the same arXiv IDs.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt
from typing import Optional
from ui.theme import get_theme_manager, FONT_BODY_STACK


class MergeConflictDialog(QDialog):
    """Dialog for choosing how to handle duplicate papers during a merge."""

    def __init__(self, duplicate_count: int, parent=None):
        super().__init__(parent)
        self._strategy = None

        self.setWindowTitle("Duplicate Papers Found")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._setup_ui(duplicate_count)

    def _setup_ui(self, duplicate_count: int):
        theme = get_theme_manager()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        header = QLabel("Duplicate Papers Found")
        header.setStyleSheet(
            f"font-family: {FONT_BODY_STACK}; font-size: 16px; font-weight: 500; "
            f"color: {theme.get_color('text_primary')};"
        )
        layout.addWidget(header)

        desc = QLabel(
            f"{duplicate_count} paper{'s' if duplicate_count != 1 else ''} "
            f"in your library already exist{'s' if duplicate_count == 1 else ''} "
            f"in the destination. How should duplicates be handled?"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; font-size: 13px;"
        )
        layout.addWidget(desc)

        self._button_group = QButtonGroup(self)

        self._keep_existing = QRadioButton("Keep existing versions")
        self._keep_existing.setChecked(True)
        self._button_group.addButton(self._keep_existing, 0)
        layout.addWidget(self._keep_existing)

        existing_desc = QLabel(
            "Skip your duplicates. The destination papers are preserved."
        )
        existing_desc.setWordWrap(True)
        existing_desc.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; font-size: 12px; "
            f"margin-left: 24px; margin-bottom: 8px;"
        )
        layout.addWidget(existing_desc)

        self._keep_incoming = QRadioButton("Keep incoming versions")
        self._button_group.addButton(self._keep_incoming, 1)
        layout.addWidget(self._keep_incoming)

        incoming_desc = QLabel(
            "Replace destination papers with yours, including notes and ratings."
        )
        incoming_desc.setWordWrap(True)
        incoming_desc.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; font-size: 12px; "
            f"margin-left: 24px; margin-bottom: 8px;"
        )
        layout.addWidget(incoming_desc)

        self._keep_both = QRadioButton("Keep both")
        self._button_group.addButton(self._keep_both, 2)
        layout.addWidget(self._keep_both)

        both_desc = QLabel(
            "Import your duplicates alongside existing ones. "
            "Copies will have a _copy suffix on the arXiv ID."
        )
        both_desc.setWordWrap(True)
        both_desc.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; font-size: 12px; "
            f"margin-left: 24px;"
        )
        layout.addWidget(both_desc)

        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        continue_btn = QPushButton("Continue")
        continue_btn.setStyleSheet(theme.get_widget_style('button_primary'))
        continue_btn.clicked.connect(self._on_continue)
        buttons.addWidget(continue_btn)

        layout.addLayout(buttons)

    def _on_continue(self):
        checked = self._button_group.checkedId()
        if checked == 0:
            self._strategy = "keep_existing"
        elif checked == 1:
            self._strategy = "keep_incoming"
        elif checked == 2:
            self._strategy = "keep_both"
        self.accept()

    def get_strategy(self) -> Optional[str]:
        """Show dialog and return the chosen strategy, or None if cancelled."""
        result = self.exec()
        if result == QDialog.Accepted:
            return self._strategy
        return None
