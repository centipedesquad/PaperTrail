"""
PDF action dialog.
Asks user whether to download or stream PDF.
"""

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QButtonGroup, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from ui.theme import get_theme_manager

logger = logging.getLogger(__name__)


class PDFActionDialog(QDialog):
    """Dialog for choosing PDF download action."""

    def __init__(self, paper_title: str, parent=None):
        """
        Initialize PDF action dialog.

        Args:
            paper_title: Title of the paper
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("View PDF")
        self.setMinimumWidth(500)

        self.selected_action = None  # 'download' or 'stream'
        self.remember_choice = False

        self._setup_ui(paper_title)

    def _setup_ui(self, paper_title: str):
        """Setup UI components."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("PDF not downloaded yet")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Paper info
        theme = get_theme_manager()
        paper_label = QLabel(f"Paper: {paper_title}")
        paper_label.setWordWrap(True)
        paper_label.setStyleSheet(f"color: {theme.get_color('text_secondary')}; margin-bottom: 10px;")
        layout.addWidget(paper_label)

        # Explanation
        explanation = QLabel(
            "This paper has not been downloaded yet. "
            "Choose how you want to access it:"
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        # Options
        self.button_group = QButtonGroup(self)

        # Download option
        self.download_radio = QRadioButton()
        self.download_radio.setChecked(True)
        self.button_group.addButton(self.download_radio)

        download_layout = QVBoxLayout()
        download_title = QLabel("Download & Keep")
        download_title_font = QFont()
        download_title_font.setBold(True)
        download_title.setFont(download_title_font)
        download_layout.addWidget(download_title)

        download_desc = QLabel(
            "• Saves PDF to your library with custom filename\n"
            "• Available offline\n"
            "• Opens faster on subsequent views\n"
            "• Recommended for papers you'll reference often"
        )
        download_desc.setStyleSheet(f"color: {theme.get_color('text_secondary')}; margin-left: 20px;")
        download_layout.addWidget(download_desc)

        download_widget = QVBoxLayout()
        download_widget.addWidget(self.download_radio)
        download_widget.addLayout(download_layout)

        layout.addLayout(download_widget)
        layout.addSpacing(10)

        # Stream option
        self.stream_radio = QRadioButton()
        self.button_group.addButton(self.stream_radio)

        stream_layout = QVBoxLayout()
        stream_title = QLabel("Stream (Temporary)")
        stream_title_font = QFont()
        stream_title_font.setBold(True)
        stream_title.setFont(stream_title_font)
        stream_layout.addWidget(stream_title)

        stream_desc = QLabel(
            "• Downloads to temporary cache\n"
            "• Automatically deleted when app closes\n"
            "• Saves disk space\n"
            "• Good for quick previews"
        )
        stream_desc.setStyleSheet(f"color: {theme.get_color('text_secondary')}; margin-left: 20px;")
        stream_layout.addWidget(stream_desc)

        stream_widget = QVBoxLayout()
        stream_widget.addWidget(self.stream_radio)
        stream_widget.addLayout(stream_layout)

        layout.addLayout(stream_widget)
        layout.addSpacing(20)

        # Remember choice checkbox
        self.remember_checkbox = QCheckBox("Remember my choice and don't ask again")
        self.remember_checkbox.setStyleSheet(f"font-style: italic; color: {theme.get_color('text_secondary')};")
        layout.addWidget(self.remember_checkbox)

        layout.addSpacing(10)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        proceed_button = QPushButton("Proceed")
        proceed_button.clicked.connect(self._on_proceed)
        proceed_button.setDefault(True)
        proceed_button.setStyleSheet(theme.get_widget_style('button_primary'))
        buttons_layout.addWidget(proceed_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)

        layout.addLayout(buttons_layout)

    def _on_proceed(self):
        """Handle proceed button click."""
        if self.download_radio.isChecked():
            self.selected_action = "download"
        elif self.stream_radio.isChecked():
            self.selected_action = "stream"

        self.remember_choice = self.remember_checkbox.isChecked()

        self.accept()

    def get_action(self) -> str:
        """
        Get selected action.

        Returns:
            'download' or 'stream'
        """
        return self.selected_action

    def should_remember(self) -> bool:
        """
        Check if user wants to remember choice.

        Returns:
            True if remember choice is checked
        """
        return self.remember_choice
