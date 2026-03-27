"""
Note editor widget for paper notes.
Provides inline text editor with auto-save functionality.
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer
from ui.theme import get_theme_manager, FONT_BODY_STACK

logger = logging.getLogger(__name__)


class NoteEditorWidget(QWidget):
    """Widget for editing paper notes with auto-save."""

    # Signal emitted when note should be saved (debounced)
    note_changed = Signal(str)  # note_text

    def __init__(self, parent=None):
        """
        Initialize note editor widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._on_save_timer)

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(5)

        # Get theme manager
        theme = get_theme_manager()

        # Title
        title_label = QLabel("Notes:")
        title_label.setStyleSheet(f"font-weight: bold; color: {theme.get_color('text_primary')};")
        layout.addWidget(title_label)

        # Text editor
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Add your notes here...\n\nAuto-saves 2 seconds after you stop typing.")
        self.text_edit.setMinimumHeight(100)
        self.text_edit.setMaximumHeight(300)
        self.text_edit.textChanged.connect(self._on_text_changed)

        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {theme.get_color('border')};
                border-radius: 4px;
                padding: 8px;
                font-family: {FONT_BODY_STACK};
                font-size: {QApplication.instance().font().pointSize() or 11}pt;
                background-color: {theme.get_color('surface')};
                color: {theme.get_color('text_primary')};
            }}
            QTextEdit:focus {{
                border-color: {theme.get_color('primary')};
            }}
        """)

        layout.addWidget(self.text_edit)

        # Auto-save indicator
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {theme.get_color('text_tertiary')}; font-size: 9pt; font-style: italic;")
        layout.addWidget(self.status_label)

    def _on_text_changed(self):
        """Handle text change - start auto-save timer."""
        # Cancel existing timer
        self._save_timer.stop()

        # Show "typing" indicator
        self.status_label.setText("Typing...")

        # Start 2-second timer for auto-save
        self._save_timer.start(2000)

    def _on_save_timer(self):
        """Handle save timer timeout - emit save signal."""
        note_text = self.text_edit.toPlainText().strip()

        # Update status
        if note_text:
            self.status_label.setText("Saved")
        else:
            self.status_label.setText("")

        # Emit signal
        self.note_changed.emit(note_text)

        # Clear status after 2 seconds
        QTimer.singleShot(2000, lambda: self.status_label.setText(""))

    def set_note(self, note_text: str):
        """
        Set note text. Flushes any pending auto-save first to prevent
        the timer from firing against the wrong paper.

        Args:
            note_text: Note content
        """
        # Flush pending save before switching content
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._on_save_timer()
        # Block signals while setting text
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(note_text or "")
        self.text_edit.blockSignals(False)

    def get_note(self) -> str:
        """
        Get current note text.

        Returns:
            Note content
        """
        return self.text_edit.toPlainText().strip()

    def has_note(self) -> bool:
        """
        Check if note has content.

        Returns:
            True if note is not empty
        """
        return bool(self.get_note())

    def clear(self):
        """Clear the note editor."""
        self.text_edit.clear()
        self.status_label.setText("")
