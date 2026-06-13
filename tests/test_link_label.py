"""
Tests for the reusable LinkLabel widget and its integration on paper cards.

These are the repo's first qtbot widget tests. Each verifies one branch of
LinkLabel's click / hover behaviour, plus the PaperCellWidget integration
(arXiv id rendered as a link, empty id falling back to no link).

The browser open is stubbed via the `captured_urls` fixture so tests never
launch a real browser, and the critical guard test asserts that clicking the
link does NOT reach an ancestor's mousePressEvent (which is how a card selects).
"""

import pytest
from PySide6.QtCore import Qt, QPointF, QEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtGui import QEnterEvent

from ui.widgets.link_label import LinkLabel
from ui.theme import get_theme_manager
from models import Paper


@pytest.fixture
def captured_urls(monkeypatch):
    """Capture QDesktopServices.openUrl calls instead of launching a browser."""
    urls = []
    monkeypatch.setattr(
        "ui.widgets.link_label.QDesktopServices.openUrl",
        lambda url: urls.append(url) or True,
    )
    return urls


def _paper(arxiv_id):
    return Paper(
        arxiv_id=arxiv_id,
        title="A Paper",
        abstract="An abstract.",
        publication_date="2023-01-01",
    )


# --- LinkLabel: click behaviour ------------------------------------------------

def test_left_click_opens_href(qtbot, captured_urls):
    label = LinkLabel("arXiv:2301.00001", href="https://arxiv.org/abs/2301.00001")
    qtbot.addWidget(label)
    qtbot.mouseClick(label, Qt.LeftButton)
    assert len(captured_urls) == 1
    assert captured_urls[0].toString() == "https://arxiv.org/abs/2301.00001"


def test_left_click_emits_clicked_with_text(qtbot, captured_urls):
    label = LinkLabel("arXiv:2301.00001", href="https://arxiv.org/abs/2301.00001")
    qtbot.addWidget(label)
    with qtbot.waitSignal(label.clicked, timeout=1000) as blocker:
        qtbot.mouseClick(label, Qt.LeftButton)
    assert blocker.args == ["arXiv:2301.00001"]


def test_left_click_does_not_propagate_to_parent(qtbot, captured_urls):
    """CRITICAL: clicking the link must not reach an ancestor's mousePressEvent
    (that is how a PaperCellWidget selects the card)."""

    class ParentProbe(QWidget):
        def __init__(self):
            super().__init__()
            self.pressed = False

        def mousePressEvent(self, event):
            self.pressed = True
            super().mousePressEvent(event)

    parent = ParentProbe()
    layout = QVBoxLayout(parent)
    label = LinkLabel("arXiv:2301.00001", href="https://arxiv.org/abs/2301.00001")
    layout.addWidget(label)
    qtbot.addWidget(parent)
    qtbot.mouseClick(label, Qt.LeftButton)
    assert parent.pressed is False


def test_right_click_does_not_open(qtbot, captured_urls):
    label = LinkLabel("arXiv:2301.00001", href="https://arxiv.org/abs/2301.00001")
    qtbot.addWidget(label)
    qtbot.mouseClick(label, Qt.RightButton)
    assert captured_urls == []


def test_click_without_href_emits_but_opens_nothing(qtbot, captured_urls):
    """Author-style usage: no href, just a click signal to wire a search."""
    label = LinkLabel("Jane Doe")
    qtbot.addWidget(label)
    with qtbot.waitSignal(label.clicked, timeout=1000):
        qtbot.mouseClick(label, Qt.LeftButton)
    assert captured_urls == []


def test_legacy_slash_id_url_preserves_slash(qtbot, captured_urls):
    label = LinkLabel(
        "arXiv:hep-th/9901001", href="https://arxiv.org/abs/hep-th/9901001"
    )
    qtbot.addWidget(label)
    qtbot.mouseClick(label, Qt.LeftButton)
    assert captured_urls[0].toString() == "https://arxiv.org/abs/hep-th/9901001"


# --- LinkLabel: hover colour ---------------------------------------------------

def test_hover_swaps_color(qtbot):
    theme = get_theme_manager()
    primary = theme.get_color("primary").lower()
    primary_hover = theme.get_color("primary_hover").lower()
    label = LinkLabel("arXiv:2301.00001", href="https://arxiv.org/abs/2301.00001")
    qtbot.addWidget(label)

    assert primary in label.styleSheet().lower()

    label.enterEvent(QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(0, 0)))
    assert primary_hover in label.styleSheet().lower()

    label.leaveEvent(QEvent(QEvent.Type.Leave))
    assert primary in label.styleSheet().lower()


# --- PaperCellWidget integration ----------------------------------------------

def test_paper_cell_renders_link_for_arxiv_id(qtbot):
    from ui.widgets.paper_cell_widget import PaperCellWidget

    cell = PaperCellWidget(_paper("2301.00001"))
    qtbot.addWidget(cell)
    links = cell.findChildren(LinkLabel)
    assert any(link.text() == "arXiv:2301.00001" for link in links)


def test_paper_cell_empty_id_renders_no_link(qtbot):
    """Defensive: an empty arxiv_id (no current code path produces one) must not
    create a link or a bare 'arXiv:' stub, and must not crash."""
    from ui.widgets.paper_cell_widget import PaperCellWidget

    cell = PaperCellWidget(_paper(""))
    qtbot.addWidget(cell)
    assert cell.findChildren(LinkLabel) == []
