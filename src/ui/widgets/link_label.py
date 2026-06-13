"""
Reusable clickable link label.

A plain-text QLabel styled as an amber editorial link (DESIGN.md: amber primary,
no underline, caller-supplied font such as JetBrains Mono). On a LEFT click it
opens its href in the system browser (if set) and emits ``clicked``, then
consumes the event WITHOUT calling ``super().mousePressEvent`` — so the click
does NOT propagate to an ancestor widget's ``mousePressEvent`` (e.g. a paper
card's select-on-click). Other mouse buttons are delegated to the base class so
a future context menu still works.

Plain text (not rich text) is deliberate: the amber comes from an ordinary
stylesheet ``color`` and there is no markup to escape. The font is a constructor
parameter, so the same widget serves the arXiv ID (mono) today and clickable
author names (body font) later.

Click handling:

    left-click  ──> open href (if set) ──> emit clicked(text) ──> accept,
                    do NOT call super() ──> ancestor mousePressEvent skipped
    other button ─> super().mousePressEvent(event)   (normal propagation)
"""

import logging
from typing import Optional

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QCursor

from ui.theme import get_theme_manager

logger = logging.getLogger(__name__)


class LinkLabel(QLabel):
    """A plain-text QLabel that behaves as an amber clickable link."""

    clicked = Signal(str)  # emitted with the label text on left-click

    def __init__(self, text: str = "", href: Optional[str] = None, *,
                 font=None, parent=None):
        super().__init__(text, parent)
        self._href = href
        if font is not None:
            self.setFont(font)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self._apply_color(hover=False)

    def set_href(self, href: Optional[str]):
        """Update the URL opened on click (the text is set via ``setText``)."""
        self._href = href

    def _apply_color(self, hover: bool):
        theme = get_theme_manager()
        color = theme.get_color('primary_hover') if hover else theme.get_color('primary')
        self.setStyleSheet(
            f"color: {color}; background: transparent; border: none; "
            f"text-decoration: none;"
        )

    def enterEvent(self, event):
        self._apply_color(hover=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_color(hover=False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._href:
                QDesktopServices.openUrl(QUrl(self._href))
            self.clicked.emit(self.text())
            event.accept()
            # Intentionally NOT calling super(): consuming the event here keeps
            # the click from reaching an ancestor's mousePressEvent (which is
            # how a PaperCellWidget selects the card). See link_label docstring.
            return
        super().mousePressEvent(event)
