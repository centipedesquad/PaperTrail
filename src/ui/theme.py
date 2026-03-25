"""
Theme management system for PaperTrail.
Editorial/Scholarly design system with warm amber accent and stone neutrals.
See DESIGN.md for the full design system specification.
"""

import logging
import os
from enum import Enum
from typing import Dict
from PySide6.QtGui import QPalette, QColor, QFontDatabase, QFont
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

# Font family constants — used throughout the application
FONT_DISPLAY = 'Source Serif 4'
FONT_BODY = 'DM Sans'
FONT_MONO = 'JetBrains Mono'

# Fallback stacks for each role
FONT_DISPLAY_STACK = f"'{FONT_DISPLAY}', Georgia, serif"
FONT_BODY_STACK = f"'{FONT_BODY}', -apple-system, sans-serif"
FONT_MONO_STACK = f"'{FONT_MONO}', 'SF Mono', monospace"


class ThemeMode(Enum):
    """Available theme modes."""
    LIGHT = "light"
    DARK = "dark"


class ColorPalette:
    """Color palette definition for a theme."""

    def __init__(self, colors: Dict[str, str]):
        self.colors = colors

    def get(self, name: str) -> str:
        """Get color by name."""
        return self.colors.get(name, "#000000")


# Light Theme — Warm stone neutrals + amber accent (DESIGN.md)
LIGHT_PALETTE = ColorPalette({
    # Backgrounds
    'background': '#FDFBF7',           # Warm white
    'surface': '#FFFFFF',              # Pure white for cards/panels
    'surface_hover': '#F5F2ED',        # Warm hover state
    'surface_alt': '#F7F4EF',          # Alternate background (sidebar)

    # Text
    'text_primary': '#1C1917',         # Warm near-black (stone-900)
    'text_secondary': '#78716C',       # Warm medium gray (stone-500)
    'text_tertiary': '#A8A29E',        # Warm light gray (stone-400)

    # Borders
    'border': '#E7E5E4',              # Warm stone (stone-300)
    'border_hover': '#D6D3D1',        # Darker stone (stone-400)

    # Primary accent — Amber (NOT blue)
    'primary': '#B45309',             # Amber-700
    'primary_hover': '#92400E',       # Amber-800
    'primary_light': '#FEF3C7',       # Amber-100

    # Success — Olive green
    'success': '#4D7C0F',             # Lime-700
    'success_hover': '#3F6212',       # Lime-800
    'success_light': '#ECFCCB',       # Lime-100

    # Warning — Amber
    'warning': '#D97706',             # Amber-600
    'warning_hover': '#B45309',       # Amber-700
    'warning_light': '#FEF3C7',       # Amber-100

    # Secondary — Warm stone for secondary actions
    'secondary': '#78716C',           # Stone-500
    'secondary_hover': '#57534E',     # Stone-600
    'secondary_light': '#F5F5F4',     # Stone-100

    # Special states
    'error': '#BE123C',               # Rose-700
    'info': '#0369A1',                # Sky-700
    'disabled': '#D6D3D1',            # Stone-300
})


# Dark Theme — Warm dark + bright amber accent (DESIGN.md)
DARK_PALETTE = ColorPalette({
    # Backgrounds
    'background': '#1C1917',           # Warm dark (stone-900)
    'surface': '#292524',              # Elevated (stone-800)
    'surface_hover': '#3D3835',        # Lighter hover
    'surface_alt': '#242120',          # Alternate dark

    # Text
    'text_primary': '#F5F5F4',         # Warm white (stone-50)
    'text_secondary': '#A8A29E',       # Medium stone (stone-400)
    'text_tertiary': '#78716C',        # Darker stone (stone-500)

    # Borders
    'border': '#3D3835',              # Warm dark border
    'border_hover': '#57534E',        # Lighter border (stone-600)

    # Primary accent — Bright amber for dark backgrounds
    'primary': '#F59E0B',             # Amber-400
    'primary_hover': '#FBBF24',       # Amber-300 (lighter for hover)
    'primary_light': '#451A03',       # Amber-950 dark bg

    # Success — Bright lime
    'success': '#84CC16',             # Lime-400
    'success_hover': '#A3E635',       # Lime-300
    'success_light': '#1A2E05',       # Dark lime bg

    # Warning — Bright amber
    'warning': '#FBBF24',             # Amber-300
    'warning_hover': '#F59E0B',       # Amber-400
    'warning_light': '#451A03',       # Amber-950

    # Secondary — Light stone
    'secondary': '#A8A29E',           # Stone-400
    'secondary_hover': '#D6D3D1',     # Stone-300
    'secondary_light': '#3D3835',     # Dark stone bg

    # Special states
    'error': '#FB7185',               # Rose-400
    'info': '#38BDF8',                # Sky-400
    'disabled': '#57534E',            # Stone-600
})


def load_fonts():
    """Load bundled fonts from assets/fonts/ directory."""
    fonts_dir = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts')
    fonts_dir = os.path.normpath(fonts_dir)

    if not os.path.isdir(fonts_dir):
        logger.warning(f"Fonts directory not found: {fonts_dir}")
        return

    loaded = 0
    for filename in os.listdir(fonts_dir):
        if filename.endswith(('.ttf', '.otf')):
            font_path = os.path.join(fonts_dir, filename)
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id >= 0:
                families = QFontDatabase.applicationFontFamilies(font_id)
                logger.info(f"Loaded font: {filename} -> {families}")
                loaded += 1
            else:
                logger.warning(f"Failed to load font: {filename}")

    logger.info(f"Loaded {loaded} font files from {fonts_dir}")


class ThemeManager:
    """Manages application theming, color palettes, and typography."""

    def __init__(self):
        self._current_mode = ThemeMode.LIGHT
        self._palettes = {
            ThemeMode.LIGHT: LIGHT_PALETTE,
            ThemeMode.DARK: DARK_PALETTE,
        }
        self._fonts_loaded = False

    @property
    def current_mode(self) -> ThemeMode:
        """Get current theme mode."""
        return self._current_mode

    @property
    def palette(self) -> ColorPalette:
        """Get current color palette."""
        return self._palettes[self._current_mode]

    def set_theme(self, mode: ThemeMode):
        if mode != self._current_mode:
            self._current_mode = mode
            logger.info(f"Theme changed to: {mode.value}")

    def get_color(self, name: str) -> str:
        return self.palette.get(name)

    def get_display_font(self, size_pt: int = None, bold: bool = False) -> QFont:
        """Return a QFont for display/heading use (Source Serif 4)."""
        font = QFont(FONT_DISPLAY)
        if size_pt:
            font.setPointSize(size_pt)
        if bold:
            font.setBold(True)
        return font

    def get_body_font(self, size_pt: int = None, weight: int = None) -> QFont:
        """Return a QFont for body/UI use (DM Sans)."""
        font = QFont(FONT_BODY)
        if size_pt:
            font.setPointSize(size_pt)
        if weight:
            font.setWeight(weight)
        return font

    def get_mono_font(self, size_pt: int = None) -> QFont:
        """Return a QFont for data/metadata use (JetBrains Mono)."""
        font = QFont(FONT_MONO)
        if size_pt:
            font.setPointSize(size_pt)
        return font

    def apply_to_app(self, app: QApplication):
        # Load fonts on first apply
        if not self._fonts_loaded:
            load_fonts()
            self._fonts_loaded = True

        # Set application-wide font to DM Sans
        app_font = QFont(FONT_BODY)
        point_size = app.font().pointSize()
        if point_size > 0:
            app_font.setPointSize(point_size)
        else:
            app_font.setPointSize(11)
        app.setFont(app_font)

        palette = self._create_qt_palette()
        app.setPalette(palette)

        stylesheet = self._generate_stylesheet()
        app.setStyleSheet(stylesheet)

        logger.info(f"Applied {self._current_mode.value} theme to application")

    def _create_qt_palette(self) -> QPalette:
        """Create Qt palette from current theme colors."""
        palette = QPalette()

        palette.setColor(QPalette.Window, QColor(self.get_color('background')))
        palette.setColor(QPalette.WindowText, QColor(self.get_color('text_primary')))

        palette.setColor(QPalette.Base, QColor(self.get_color('surface')))
        palette.setColor(QPalette.AlternateBase, QColor(self.get_color('surface_hover')))
        palette.setColor(QPalette.Text, QColor(self.get_color('text_primary')))

        palette.setColor(QPalette.Button, QColor(self.get_color('surface')))
        palette.setColor(QPalette.ButtonText, QColor(self.get_color('text_primary')))

        palette.setColor(QPalette.Highlight, QColor(self.get_color('primary')))
        palette.setColor(QPalette.HighlightedText, QColor('#FFFFFF'))

        palette.setColor(QPalette.Link, QColor(self.get_color('primary')))
        palette.setColor(QPalette.LinkVisited, QColor(self.get_color('primary_hover')))

        return palette

    def _generate_stylesheet(self) -> str:
        """Generate global Qt stylesheet for current theme."""
        return f"""
        /* Global application styles — Editorial/Scholarly theme */
        QMainWindow, QDialog {{
            background-color: {self.get_color('background')};
            color: {self.get_color('text_primary')};
            font-family: {FONT_BODY_STACK};
        }}

        QWidget {{
            background-color: transparent;
            color: {self.get_color('text_primary')};
            font-family: {FONT_BODY_STACK};
        }}

        QMainWindow > QWidget {{
            background-color: {self.get_color('background')};
        }}

        /* Scroll bars */
        QScrollBar:vertical {{
            background: {self.get_color('surface')};
            width: 10px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {self.get_color('border_hover')};
            min-height: 20px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {self.get_color('text_tertiary')};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: {self.get_color('surface')};
            height: 10px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: {self.get_color('border_hover')};
            min-width: 20px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {self.get_color('text_tertiary')};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* Text inputs — 2px radius per DESIGN.md */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {self.get_color('surface')};
            border: 1px solid {self.get_color('border')};
            border-radius: 2px;
            padding: 6px;
            color: {self.get_color('text_primary')};
            font-family: {FONT_BODY_STACK};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {self.get_color('primary')};
        }}

        /* Combo boxes */
        QComboBox {{
            background-color: {self.get_color('surface')};
            border: 1px solid {self.get_color('border')};
            border-radius: 2px;
            padding: 5px 10px;
            color: {self.get_color('text_primary')};
            font-family: {FONT_BODY_STACK};
        }}
        QComboBox:hover {{
            border-color: {self.get_color('border_hover')};
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: {self.get_color('surface')};
            border: 1px solid {self.get_color('border')};
            selection-background-color: {self.get_color('primary')};
            color: {self.get_color('text_primary')};
        }}

        /* Buttons — 2px radius per DESIGN.md */
        QPushButton {{
            background-color: {self.get_color('surface')};
            border: 1px solid {self.get_color('border')};
            border-radius: 2px;
            padding: 6px 16px;
            color: {self.get_color('text_primary')};
            font-family: {FONT_BODY_STACK};
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {self.get_color('surface_hover')};
            border-color: {self.get_color('border_hover')};
        }}
        QPushButton:pressed {{
            background-color: {self.get_color('border')};
        }}
        QPushButton:disabled {{
            background-color: {self.get_color('disabled')};
            color: {self.get_color('text_tertiary')};
        }}

        /* Checkboxes */
        QCheckBox {{
            color: {self.get_color('text_primary')};
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 1px solid {self.get_color('border')};
            border-radius: 2px;
            background-color: {self.get_color('surface')};
        }}
        QCheckBox::indicator:hover {{
            border-color: {self.get_color('primary')};
        }}
        QCheckBox::indicator:checked {{
            background-color: {self.get_color('primary')};
            border-color: {self.get_color('primary')};
        }}

        /* Group boxes — 4px radius for cards/panels */
        QGroupBox {{
            border: 1px solid {self.get_color('border')};
            border-radius: 4px;
            margin-top: 12px;
            padding-top: 12px;
            font-weight: bold;
            color: {self.get_color('text_primary')};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            color: {self.get_color('text_primary')};
        }}

        /* Labels */
        QLabel {{
            color: {self.get_color('text_primary')};
        }}

        /* Menu bar */
        QMenuBar {{
            background-color: {self.get_color('surface')};
            color: {self.get_color('text_primary')};
        }}
        QMenuBar::item:selected {{
            background-color: {self.get_color('primary_light')};
        }}

        /* Menus */
        QMenu {{
            background-color: {self.get_color('surface')};
            border: 1px solid {self.get_color('border')};
            color: {self.get_color('text_primary')};
        }}
        QMenu::item:selected {{
            background-color: {self.get_color('primary')};
            color: white;
        }}

        /* Tool bar */
        QToolBar {{
            background-color: {self.get_color('surface')};
            border-bottom: 1px solid {self.get_color('border')};
            spacing: 8px;
            padding: 4px;
        }}

        /* Status bar */
        QStatusBar {{
            background-color: {self.get_color('surface')};
            border-top: 1px solid {self.get_color('border')};
            color: {self.get_color('text_secondary')};
        }}

        /* Tooltips */
        QToolTip {{
            background-color: {self.get_color('surface')};
            border: 1px solid {self.get_color('border')};
            color: {self.get_color('text_primary')};
            padding: 4px;
            border-radius: 2px;
        }}

        /* Date edit */
        QDateEdit {{
            background-color: {self.get_color('surface')};
            border: 1px solid {self.get_color('border')};
            border-radius: 2px;
            padding: 5px;
            color: {self.get_color('text_primary')};
        }}
        QDateEdit:focus {{
            border-color: {self.get_color('primary')};
        }}
        QDateEdit::drop-down {{
            border: none;
        }}

        /* Calendar widget */
        QCalendarWidget {{
            background-color: {self.get_color('surface')};
        }}
        QCalendarWidget QToolButton {{
            color: {self.get_color('text_primary')};
            background-color: {self.get_color('surface')};
        }}
        QCalendarWidget QMenu {{
            background-color: {self.get_color('surface')};
            color: {self.get_color('text_primary')};
        }}
        QCalendarWidget QSpinBox {{
            color: {self.get_color('text_primary')};
            background-color: {self.get_color('surface')};
        }}
        QCalendarWidget QAbstractItemView {{
            selection-background-color: {self.get_color('primary')};
            selection-color: white;
            color: {self.get_color('text_primary')};
            background-color: {self.get_color('surface')};
        }}
        """

    def get_widget_style(self, widget_type: str, **kwargs) -> str:
        """Generate custom stylesheet for specific widget types."""
        styles = {
            'paper_cell': f"""
                QFrame {{
                    border: none;
                    border-bottom: 1px solid {self.get_color('border')};
                    border-left: 3px solid transparent;
                    border-radius: 0px;
                    background-color: {self.get_color('surface')};
                }}
                QFrame:hover {{
                    border-left: 3px solid {self.get_color('primary')};
                    background-color: {self.get_color('surface_hover')};
                }}
                QFrame QWidget {{
                    background-color: transparent;
                    border: none;
                }}
                QFrame QLabel {{
                    background-color: transparent;
                    border: none;
                }}
            """,
            'button_primary': f"""
                QPushButton {{
                    background-color: {self.get_color('primary')};
                    color: white;
                    border: none;
                    padding: 4px 12px;
                    border-radius: 2px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {self.get_color('primary_hover')};
                }}
                QPushButton:pressed {{
                    background-color: {self.get_color('primary_hover')};
                }}
            """,
            'button_success': f"""
                QPushButton {{
                    background-color: {self.get_color('success')};
                    color: white;
                    border: none;
                    padding: 4px 12px;
                    border-radius: 2px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {self.get_color('success_hover')};
                }}
                QPushButton:pressed {{
                    background-color: {self.get_color('success_hover')};
                }}
            """,
            'button_secondary': f"""
                QPushButton {{
                    background-color: {self.get_color('secondary')};
                    color: white;
                    border: none;
                    padding: 4px 12px;
                    border-radius: 2px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {self.get_color('secondary_hover')};
                }}
                QPushButton:pressed {{
                    background-color: {self.get_color('secondary_hover')};
                }}
            """,
            'filter_panel': f"""
                QWidget {{
                    background-color: {self.get_color('surface')};
                    border-right: 1px solid {self.get_color('border')};
                }}
            """,
        }

        return styles.get(widget_type, "")


# Global theme manager instance
_theme_manager = None


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance."""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager
