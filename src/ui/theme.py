"""
Theme management system for myArXiv.
Provides light and dark theme color palettes and styling.
"""

import logging
from enum import Enum
from typing import Dict
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


class ThemeMode(Enum):
    """Available theme modes."""
    LIGHT = "light"
    DARK = "dark"


class ColorPalette:
    """Color palette definition for a theme."""

    def __init__(self, colors: Dict[str, str]):
        """
        Initialize color palette.

        Args:
            colors: Dictionary mapping color names to hex values
        """
        self.colors = colors

    def get(self, name: str) -> str:
        """Get color by name."""
        return self.colors.get(name, "#000000")


# Light Theme Color Palette (Tailwind-inspired)
LIGHT_PALETTE = ColorPalette({
    # Backgrounds
    'background': '#F8F9FA',           # Soft white
    'surface': '#FFFFFF',              # Pure white for cards
    'surface_hover': '#F1F5F9',        # Light hover state

    # Text
    'text_primary': '#1F2937',         # Dark gray
    'text_secondary': '#6B7280',       # Medium gray
    'text_tertiary': '#9CA3AF',        # Light gray

    # Borders
    'border': '#E5E7EB',               # Subtle gray
    'border_hover': '#D1D5DB',         # Darker on hover

    # Primary accent (Professional blue)
    'primary': '#2563EB',              # Main blue
    'primary_hover': '#1D4ED8',        # Darker blue
    'primary_light': '#DBEAFE',        # Light blue background

    # Success (Modern green)
    'success': '#10B981',              # Green
    'success_hover': '#059669',        # Darker green
    'success_light': '#D1FAE5',        # Light green background

    # Warning/Important (Amber)
    'warning': '#F59E0B',              # Amber
    'warning_hover': '#D97706',        # Darker amber
    'warning_light': '#FEF3C7',        # Light amber background

    # Secondary (Slate)
    'secondary': '#64748B',            # Slate
    'secondary_hover': '#475569',      # Darker slate
    'secondary_light': '#F1F5F9',      # Light slate background

    # Special states
    'error': '#EF4444',                # Red
    'info': '#3B82F6',                 # Blue
    'disabled': '#D1D5DB',             # Light gray
})


# Dark Theme Color Palette (Tailwind-inspired)
DARK_PALETTE = ColorPalette({
    # Backgrounds
    'background': '#0F172A',           # Deep navy
    'surface': '#1E293B',              # Elevated dark
    'surface_hover': '#334155',        # Lighter on hover

    # Text
    'text_primary': '#F1F5F9',         # Light gray
    'text_secondary': '#94A3B8',       # Medium slate
    'text_tertiary': '#64748B',        # Darker slate

    # Borders
    'border': '#334155',               # Subtle dark
    'border_hover': '#475569',         # Lighter on hover

    # Primary accent (Bright blue)
    'primary': '#60A5FA',              # Bright blue
    'primary_hover': '#3B82F6',        # Slightly darker
    'primary_light': '#1E3A8A',        # Dark blue background

    # Success (Bright green)
    'success': '#34D399',              # Bright green
    'success_hover': '#10B981',        # Darker green
    'success_light': '#064E3B',        # Dark green background

    # Warning/Important (Bright amber)
    'warning': '#FBBF24',              # Bright amber
    'warning_hover': '#F59E0B',        # Darker amber
    'warning_light': '#78350F',        # Dark amber background

    # Secondary (Light slate)
    'secondary': '#94A3B8',            # Light slate
    'secondary_hover': '#CBD5E1',      # Lighter slate
    'secondary_light': '#334155',      # Dark slate background

    # Special states
    'error': '#F87171',                # Bright red
    'info': '#60A5FA',                 # Bright blue
    'disabled': '#475569',             # Dark gray
})


class ThemeManager:
    """Manages application theming and color palettes."""

    def __init__(self):
        """Initialize theme manager."""
        self._current_mode = ThemeMode.LIGHT
        self._palettes = {
            ThemeMode.LIGHT: LIGHT_PALETTE,
            ThemeMode.DARK: DARK_PALETTE,
        }

    @property
    def current_mode(self) -> ThemeMode:
        """Get current theme mode."""
        return self._current_mode

    @property
    def palette(self) -> ColorPalette:
        """Get current color palette."""
        return self._palettes[self._current_mode]

    def set_theme(self, mode: ThemeMode):
        """
        Set the current theme mode.

        Args:
            mode: Theme mode to set
        """
        if mode != self._current_mode:
            self._current_mode = mode
            logger.info(f"Theme changed to: {mode.value}")

    def get_color(self, name: str) -> str:
        """
        Get color from current palette.

        Args:
            name: Color name (e.g., 'primary', 'background')

        Returns:
            Hex color string
        """
        return self.palette.get(name)

    def apply_to_app(self, app: QApplication):
        """
        Apply current theme to Qt application.

        Args:
            app: QApplication instance
        """
        # Set application palette
        palette = self._create_qt_palette()
        app.setPalette(palette)

        # Set global stylesheet
        stylesheet = self._generate_stylesheet()
        app.setStyleSheet(stylesheet)

        logger.info(f"Applied {self._current_mode.value} theme to application")

    def _create_qt_palette(self) -> QPalette:
        """Create Qt palette from current theme colors."""
        palette = QPalette()

        # Window colors
        palette.setColor(QPalette.Window, QColor(self.get_color('background')))
        palette.setColor(QPalette.WindowText, QColor(self.get_color('text_primary')))

        # Base colors (for text entry, etc.)
        palette.setColor(QPalette.Base, QColor(self.get_color('surface')))
        palette.setColor(QPalette.AlternateBase, QColor(self.get_color('surface_hover')))
        palette.setColor(QPalette.Text, QColor(self.get_color('text_primary')))

        # Button colors
        palette.setColor(QPalette.Button, QColor(self.get_color('surface')))
        palette.setColor(QPalette.ButtonText, QColor(self.get_color('text_primary')))

        # Highlights
        palette.setColor(QPalette.Highlight, QColor(self.get_color('primary')))
        palette.setColor(QPalette.HighlightedText, QColor('#FFFFFF'))

        # Links
        palette.setColor(QPalette.Link, QColor(self.get_color('primary')))
        palette.setColor(QPalette.LinkVisited, QColor(self.get_color('primary_hover')))

        return palette

    def _generate_stylesheet(self) -> str:
        """Generate global Qt stylesheet for current theme."""
        return f"""
        /* Global application styles */
        QMainWindow, QDialog, QWidget {{
            background-color: {self.get_color('background')};
            color: {self.get_color('text_primary')};
        }}

        /* Scroll bars */
        QScrollBar:vertical {{
            background: {self.get_color('surface')};
            width: 12px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {self.get_color('border_hover')};
            min-height: 20px;
            border-radius: 6px;
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
            height: 12px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: {self.get_color('border_hover')};
            min-width: 20px;
            border-radius: 6px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {self.get_color('text_tertiary')};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* Text inputs */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {self.get_color('surface')};
            border: 1px solid {self.get_color('border')};
            border-radius: 4px;
            padding: 6px;
            color: {self.get_color('text_primary')};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {self.get_color('primary')};
        }}

        /* Combo boxes */
        QComboBox {{
            background-color: {self.get_color('surface')};
            border: 1px solid {self.get_color('border')};
            border-radius: 4px;
            padding: 5px 10px;
            color: {self.get_color('text_primary')};
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

        /* Buttons */
        QPushButton {{
            background-color: {self.get_color('surface')};
            border: 1px solid {self.get_color('border')};
            border-radius: 4px;
            padding: 6px 16px;
            color: {self.get_color('text_primary')};
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
            border-radius: 3px;
            background-color: {self.get_color('surface')};
        }}
        QCheckBox::indicator:hover {{
            border-color: {self.get_color('primary')};
        }}
        QCheckBox::indicator:checked {{
            background-color: {self.get_color('primary')};
            border-color: {self.get_color('primary')};
        }}

        /* Group boxes */
        QGroupBox {{
            border: 1px solid {self.get_color('border')};
            border-radius: 6px;
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
        }}

        /* Date edit */
        QDateEdit {{
            background-color: {self.get_color('surface')};
            border: 1px solid {self.get_color('border')};
            border-radius: 4px;
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
        """
        Generate custom stylesheet for specific widget types.

        Args:
            widget_type: Type of widget (e.g., 'paper_cell', 'button_primary')
            **kwargs: Additional parameters

        Returns:
            CSS stylesheet string
        """
        styles = {
            'paper_cell': f"""
                QFrame {{
                    border: 1px solid {self.get_color('border')};
                    border-radius: 8px;
                    background-color: {self.get_color('surface')};
                }}
                QFrame:hover {{
                    border-color: {self.get_color('primary')};
                }}
            """,
            'button_primary': f"""
                QPushButton {{
                    background-color: {self.get_color('primary')};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
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
                    padding: 8px 16px;
                    border-radius: 6px;
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
                    padding: 8px 16px;
                    border-radius: 6px;
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
