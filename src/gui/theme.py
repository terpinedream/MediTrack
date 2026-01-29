"""
Centralized theme configuration for MediTrack GUI.
"""

# Color Palette
COLORS = {
    # Primary colors
    'primary': '#2563eb',      # Modern blue
    'primary_hover': '#1d4ed8',
    'primary_pressed': '#1e40af',
    
    # Status colors
    'success': '#10b981',      # Green for running
    'success_hover': '#059669',
    'warning': '#f59e0b',      # Amber for paused
    'warning_hover': '#d97706',
    'error': '#ef4444',        # Red for stopped/critical
    'error_hover': '#dc2626',
    
    # Severity colors
    'critical': '#dc2626',      # Red
    'high': '#f59e0b',          # Amber
    'medium': '#eab308',        # Yellow
    'low': '#10b981',           # Green
    'unknown': '#6b7280',        # Gray
    
    # Background colors
    'bg_main': '#ffffff',       # White
    'bg_panel': '#f9fafb',      # Very light gray
    'bg_secondary': '#f3f4f6',  # Light gray
    'bg_hover': '#e5e7eb',      # Hover gray
    
    # Text colors
    'text_primary': '#111827',  # Near black
    'text_secondary': '#4b5563', # Dark gray
    'text_muted': '#6b7280',     # Medium gray
    'text_inverse': '#ffffff',   # White
    
    # Border colors
    'border': '#e5e7eb',         # Light gray
    'border_dark': '#d1d5db',   # Medium gray
    
    # Selection
    'selection': '#3b82f6',     # Blue
    'selection_bg': '#dbeafe',  # Light blue

    # Anomaly row highlight in aircraft table
    'anomaly_row_bg': '#fef3c7',  # Light amber
}

# Spacing constants (reduced by ~20%)
SPACING = {
    'xs': 4,
    'sm': 6,
    'md': 8,
    'lg': 12,
    'xl': 16,
}

# Font configuration - primary font for text, emoji fonts handled by Qt automatically
FONT_FAMILY = '"Jetbrains Mono Nerd Font", "Jetbrains Mono", monospace'
FONT_SIZES = {
    'xs': 10,
    'sm': 11,
    'base': 12,
    'md': 14,
    'lg': 16,
    'xl': 18,
}

# Border radius
RADIUS = {
    'sm': 3,
    'md': 4,
    'lg': 6,
}


def get_global_stylesheet() -> str:
    """
    Generate global application stylesheet with Jetbrains Mono Nerd Font.
    
    Returns:
        Complete stylesheet string for QApplication
    """
    return f"""
        /* Global font */
        * {{
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZES['base']}px;
        }}
        
        /* Main window */
        QMainWindow {{
            background-color: {COLORS['bg_main']};
            color: {COLORS['text_primary']};
        }}
        
        /* Widgets */
        QWidget {{
            background-color: {COLORS['bg_main']};
            color: {COLORS['text_primary']};
        }}
        
        /* Labels */
        QLabel {{
            color: {COLORS['text_primary']};
        }}
        
        /* Buttons */
        QPushButton {{
            background-color: {COLORS['primary']};
            color: {COLORS['text_inverse']};
            border: none;
            border-radius: {RADIUS['md']}px;
            padding: {SPACING['md']}px {SPACING['lg']}px;
            font-weight: 600;
            font-size: {FONT_SIZES['base']}px;
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
        
        /* Group boxes */
        QGroupBox {{
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['md']}px;
            margin-top: {SPACING['md']}px;
            padding-top: {SPACING['lg']}px;
            font-weight: 600;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {SPACING['md']}px;
            padding: 0 {SPACING['sm']}px;
        }}
        
        /* Line edits */
        QLineEdit {{
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['md']}px;
            padding: {SPACING['sm']}px {SPACING['md']}px;
            background-color: {COLORS['bg_main']};
        }}
        
        QLineEdit:focus {{
            border: 1px solid {COLORS['primary']};
        }}
        
        /* Combo boxes */
        QComboBox {{
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['md']}px;
            padding: {SPACING['sm']}px {SPACING['md']}px;
            background-color: {COLORS['bg_main']};
        }}
        
        QComboBox:focus {{
            border: 1px solid {COLORS['primary']};
        }}
        
        /* Spin boxes */
        QSpinBox {{
            border: 1px solid {COLORS['border']};
            border-radius: {RADIUS['md']}px;
            padding: {SPACING['sm']}px {SPACING['md']}px;
            background-color: {COLORS['bg_main']};
        }}
        
        /* Radio buttons */
        QRadioButton {{
            spacing: {SPACING['sm']}px;
        }}
    """


def get_button_style(color_type: str = 'primary') -> str:
    """
    Get button style for specific color type.
    
    Args:
        color_type: 'primary', 'success', 'warning', 'error'
        
    Returns:
        Stylesheet string for button
    """
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
            padding: {SPACING['md']}px {SPACING['lg']}px;
            font-weight: 600;
            font-size: {FONT_SIZES['base']}px;
            min-height: 40px;
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
