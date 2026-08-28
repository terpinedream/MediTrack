"""
Centralized theme configuration for MediTrack GUI.
"""

LIGHT_COLORS = {
    'primary': '#2563eb',
    'primary_hover': '#1d4ed8',
    'primary_pressed': '#1e40af',
    'success': '#10b981',
    'success_hover': '#059669',
    'warning': '#f59e0b',
    'warning_hover': '#d97706',
    'star': '#eab308',
    'error': '#ef4444',
    'error_hover': '#dc2626',
    'critical': '#dc2626',
    'high': '#f59e0b',
    'medium': '#eab308',
    'low': '#10b981',
    'unknown': '#6b7280',
    'bg_main': '#f0f2f5',
    'bg_panel': '#ffffff',
    'bg_card': '#ffffff',
    'bg_elevated': '#f9fafb',
    'bg_secondary': '#f3f4f6',
    'bg_hover': '#e5e7eb',
    'text_primary': '#111827',
    'text_secondary': '#4b5563',
    'text_muted': '#6b7280',
    'text_inverse': '#ffffff',
    'text_link': '#2563eb',
    'border': '#e2e8f0',
    'border_dark': '#cbd5e1',
    'selection': '#3b82f6',
    'selection_bg': '#dbeafe',
    'anomaly_row_bg': '#fef3c7',
    'status_stopped': '#9ca3af',
    'map_hint_bg': 'rgba(255,255,255,0.92)',
    'map_hint_text': '#374151',
}

DARK_COLORS = {
    'primary': '#60a5fa',
    'primary_hover': '#3b82f6',
    'primary_pressed': '#2563eb',
    'success': '#34d399',
    'success_hover': '#10b981',
    'warning': '#fbbf24',
    'warning_hover': '#f59e0b',
    'star': '#facc15',
    'error': '#f87171',
    'error_hover': '#ef4444',
    'critical': '#f87171',
    'high': '#fbbf24',
    'medium': '#fde047',
    'low': '#34d399',
    'unknown': '#94a3b8',
    'bg_main': '#0b0f14',
    'bg_panel': '#121820',
    'bg_card': '#171f2b',
    'bg_elevated': '#1e2836',
    'bg_secondary': '#243044',
    'bg_hover': '#2d3a4f',
    'text_primary': '#f1f5f9',
    'text_secondary': '#cbd5e1',
    'text_muted': '#94a3b8',
    'text_inverse': '#0b0f14',
    'text_link': '#93c5fd',
    'border': '#2a3547',
    'border_dark': '#3d4f66',
    'selection': '#3b82f6',
    'selection_bg': '#1e3a5f',
    'anomaly_row_bg': '#422006',
    'status_stopped': '#64748b',
    'map_hint_bg': 'rgba(23,31,43,0.92)',
    'map_hint_text': '#cbd5e1',
}

COLORS = dict(DARK_COLORS)
_current_theme = 'dark'

SPACING = {
    'xs': 4,
    'sm': 6,
    'md': 8,
    'lg': 12,
    'xl': 16,
    'xxl': 20,
}

# Uniform padding for left-sidebar cards (top, left, bottom, right)
SIDEBAR_CARD_MARGINS = (
    SPACING['lg'],
    SPACING['lg'],
    SPACING['lg'],
    SPACING['lg'],
)

FONT_FAMILY = '"Segoe UI", "Inter", "Helvetica Neue", sans-serif'
FONT_FAMILY_MONO = '"JetBrains Mono Nerd Font", "JetBrains Mono", monospace'
FONT_SIZES = {
    'xs': 10,
    'sm': 11,
    'base': 12,
    'md': 14,
    'lg': 16,
    'xl': 18,
}

RADIUS = {
    'sm': 6,
    'md': 10,
    'lg': 14,
    'xl': 18,
}

SEVERITY_BADGES = {
    'CRITICAL': 'CRIT',
    'HIGH': 'HIGH',
    'MEDIUM': 'MED',
    'LOW': 'LOW',
    'UNKNOWN': '???',
}


def set_theme(mode: str) -> None:
    """Switch between light and dark themes."""
    global COLORS, _current_theme
    mode = (mode or 'dark').lower()
    if mode == 'dark':
        COLORS = dict(DARK_COLORS)
        _current_theme = 'dark'
    else:
        COLORS = dict(LIGHT_COLORS)
        _current_theme = 'light'


def get_current_theme() -> str:
    return _current_theme


def get_section_title_stylesheet() -> str:
    """Stylesheet for panel section titles."""
    return (
        f"font-size: {FONT_SIZES['md']}px; font-weight: 600; "
        f"color: {COLORS['text_primary']}; background: transparent; "
        f"padding-bottom: {SPACING['xs']}px;"
    )


CARD_PANEL_OBJECT_NAME = "cardPanel"


def get_card_widget_stylesheet() -> str:
    """Stylesheet for a top-level card frame (does not cascade to children)."""
    name = CARD_PANEL_OBJECT_NAME
    return f"""
        QWidget#{name} {{
            background-color: {COLORS['bg_card']};
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['lg']}px;
        }}
    """


def apply_card_style(widget) -> None:
    """Mark a widget as a card panel and apply card styling."""
    widget.setObjectName(CARD_PANEL_OBJECT_NAME)
    widget.setStyleSheet(get_card_widget_stylesheet())


def get_card_stylesheet(padding: int = None) -> str:
    """Inline style properties for custom selectors (no padding — use layout margins)."""
    return f"""
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: {RADIUS['lg']}px;
    """


def get_table_stylesheet() -> str:
    """Stylesheet for data tables."""
    return f"""
        QTableWidget {{
            gridline-color: {COLORS['border']};
            background-color: {COLORS['bg_elevated']};
            alternate-background-color: {COLORS['bg_card']};
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['md']}px;
            selection-background-color: {COLORS['selection']};
            selection-color: {COLORS['text_inverse']};
        }}
        QTableWidget::item {{
            padding: {SPACING['xs']}px {SPACING['sm']}px;
            font-family: {FONT_FAMILY};
            color: {COLORS['text_primary']};
        }}
        QTableWidget::item:selected {{
            background-color: {COLORS['selection']};
            color: {COLORS['text_inverse']};
        }}
        QHeaderView::section {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_secondary']};
            padding: {SPACING['sm']}px {SPACING['md']}px;
            border: none;
            border-bottom: 1px solid {COLORS['border']};
            border-right: 1px solid {COLORS['border']};
            font-weight: 600;
            font-size: {FONT_SIZES['sm']}px;
        }}
        QTableCornerButton::section {{
            background: {COLORS['bg_secondary']};
            border: none;
        }}
    """


def get_list_stylesheet() -> str:
    """Stylesheet for list widgets."""
    return f"""
        QListWidget {{
            background-color: {COLORS['bg_elevated']};
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['md']}px;
            color: {COLORS['text_primary']};
        }}
        QListWidget::item {{
            padding: {SPACING['sm']}px {SPACING['md']}px;
            border-bottom: 1px solid {COLORS['border']};
            min-height: 24px;
        }}
        QListWidget::item:selected {{
            border: 2px solid {COLORS['selection']};
            border-left: 4px solid {COLORS['selection']};
        }}
    """


def get_global_stylesheet() -> str:
    """Generate global application stylesheet."""
    return f"""
        * {{
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZES['base']}px;
        }}

        QMainWindow {{
            background-color: {COLORS['bg_main']};
            color: {COLORS['text_primary']};
        }}

        QWidget {{
            background-color: {COLORS['bg_main']};
            color: {COLORS['text_primary']};
        }}

        QLabel {{
            color: {COLORS['text_primary']};
        }}

        QPushButton {{
            background-color: {COLORS['primary']};
            color: {COLORS['text_inverse']};
            border: none;
            border-radius: {RADIUS['md']}px;
            padding: {SPACING['sm']}px {SPACING['lg']}px;
            font-weight: 600;
            font-size: {FONT_SIZES['base']}px;
            min-height: 20px;
        }}

        QPushButton:hover {{
            background-color: {COLORS['primary_hover']};
        }}

        QPushButton:pressed {{
            background-color: {COLORS['primary_pressed']};
        }}

        QPushButton:disabled {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_muted']};
        }}

        QGroupBox {{
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['lg']}px;
            margin-top: {SPACING['xl']}px;
            padding: {SPACING['xl']}px {SPACING['lg']}px {SPACING['lg']}px {SPACING['lg']}px;
            font-weight: 600;
            background-color: {COLORS['bg_card']};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {SPACING['lg']}px;
            padding: 0 {SPACING['sm']}px;
            color: {COLORS['text_primary']};
        }}

        QLineEdit {{
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['md']}px;
            padding: {SPACING['sm']}px {SPACING['md']}px;
            background-color: {COLORS['bg_elevated']};
            color: {COLORS['text_primary']};
        }}

        QLineEdit:focus {{
            border: 1px solid {COLORS['primary']};
        }}

        QComboBox {{
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['md']}px;
            padding: {SPACING['sm']}px {SPACING['md']}px;
            background-color: {COLORS['bg_elevated']};
            color: {COLORS['text_primary']};
        }}

        QComboBox:focus {{
            border: 1px solid {COLORS['primary']};
        }}

        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}

        QComboBox QAbstractItemView {{
            background-color: {COLORS['bg_card']};
            border: 1px solid {COLORS['border']};
            selection-background-color: {COLORS['selection_bg']};
            selection-color: {COLORS['text_primary']};
        }}

        QSpinBox {{
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['md']}px;
            padding: {SPACING['sm']}px {SPACING['md']}px;
            background-color: {COLORS['bg_elevated']};
            color: {COLORS['text_primary']};
        }}

        QRadioButton {{
            spacing: {SPACING['sm']}px;
            color: {COLORS['text_primary']};
        }}

        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
        }}

        QCheckBox {{
            color: {COLORS['text_secondary']};
            spacing: {SPACING['sm']}px;
            background: transparent;
        }}

        QMenuBar {{
            background-color: {COLORS['bg_panel']};
            color: {COLORS['text_primary']};
            border-bottom: 1px solid {COLORS['border']};
        }}
        QMenuBar::item {{
            padding: {SPACING['sm']}px {SPACING['md']}px;
            background: transparent;
        }}
        QMenuBar::item:selected {{
            background-color: {COLORS['bg_hover']};
            border-radius: {RADIUS['sm']}px;
        }}
        QMenuBar::item:pressed {{
            background-color: {COLORS['border']};
        }}

        QMenu {{
            background-color: {COLORS['bg_card']};
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['md']}px;
            padding: {SPACING['xs']}px;
        }}
        QMenu::item {{
            padding: {SPACING['sm']}px {SPACING['lg']}px;
            border-radius: {RADIUS['sm']}px;
        }}
        QMenu::item:selected {{
            background-color: {COLORS['selection_bg']};
        }}

        QStatusBar {{
            background-color: {COLORS['bg_panel']};
            color: {COLORS['text_secondary']};
            border-top: 1px solid {COLORS['border']};
        }}

        QSplitter::handle {{
            background: transparent;
            width: 0px;
            height: 0px;
        }}

        QScrollBar:vertical {{
            background: {COLORS['bg_elevated']};
            width: 10px;
            border-radius: 5px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {COLORS['border_dark']};
            border-radius: 5px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {COLORS['text_muted']};
        }}
        QScrollBar:horizontal {{
            background: {COLORS['bg_elevated']};
            height: 10px;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal {{
            background: {COLORS['border_dark']};
            border-radius: 5px;
            min-width: 24px;
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            width: 0;
            height: 0;
        }}

        QProgressBar {{
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['md']}px;
            background-color: {COLORS['bg_elevated']};
            text-align: center;
            color: {COLORS['text_primary']};
        }}
        QProgressBar::chunk {{
            background-color: {COLORS['primary']};
            border-radius: {RADIUS['sm']}px;
        }}

        QPlainTextEdit {{
            background-color: {COLORS['bg_elevated']};
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['md']}px;
            color: {COLORS['text_primary']};
            padding: {SPACING['sm']}px;
        }}
    """


def _button_style_block(color_type: str, *, min_height: int, padding_v: int, padding_h: int, font_size: int) -> str:
    color_map = {
        'primary': ('primary', 'primary_hover', 'primary_pressed'),
        'success': ('success', 'success_hover', 'success'),
        'warning': ('warning', 'warning_hover', 'warning'),
        'error': ('error', 'error_hover', 'error'),
    }
    base, hover, pressed = color_map.get(color_type, color_map['primary'])
    return f"""
        QPushButton {{
            background-color: {COLORS[base]};
            color: {COLORS['text_inverse']};
            border: none;
            border-radius: {RADIUS['md']}px;
            padding: {padding_v}px {padding_h}px;
            font-weight: 600;
            font-size: {font_size}px;
            min-height: {min_height}px;
            max-height: {min_height}px;
        }}
        QPushButton:hover {{
            background-color: {COLORS[hover]};
        }}
        QPushButton:pressed {{
            background-color: {COLORS[pressed]};
        }}
        QPushButton:disabled {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_muted']};
        }}
    """


def get_button_style(color_type: str = 'primary') -> str:
    """Standard full-size button style."""
    return _button_style_block(
        color_type,
        min_height=36,
        padding_v=SPACING['sm'],
        padding_h=SPACING['lg'],
        font_size=FONT_SIZES['base'],
    )


def get_compact_button_style(color_type: str = 'primary') -> str:
    """Smaller button for sidebars and secondary actions."""
    return _button_style_block(
        color_type,
        min_height=30,
        padding_v=SPACING['xs'],
        padding_h=SPACING['md'],
        font_size=FONT_SIZES['sm'],
    )
