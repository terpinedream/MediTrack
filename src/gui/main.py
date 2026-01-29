"""
Main application entry point for MediTrack GUI.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.setup_window import SetupWindow
from gui.monitoring_window import MonitoringWindow
from gui.theme import get_global_stylesheet, FONT_SIZES


def main():
    """Main application entry point."""
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("MediTrack")
    app.setOrganizationName("MediTrack")
    
    # Set unified global font with Symbola for monochrome emoji support
    # Qt will automatically use Symbola for emoji characters and Jetbrains Mono for text
    font = QFont("Jetbrains Mono Nerd Font", FONT_SIZES['base'])
    font.setStyleHint(QFont.StyleHint.Monospace)
    
    # Set font families: primary for text, Symbola for emoji fallback
    font.setFamilies([
        "Jetbrains Mono Nerd Font",  # Primary font for text
        "Jetbrains Mono",            # Fallback
        "Symbola",                   # Monochrome emoji support
        "monospace"                  # Final fallback
    ])
    
    app.setFont(font)
    
    # Apply global stylesheet
    app.setStyleSheet(get_global_stylesheet())
    
    # Show setup window
    setup = SetupWindow()
    
    # If user accepts setup, show monitoring window
    if setup.exec() == QDialog.DialogCode.Accepted:
        config = setup.get_config()
        
        if config:
            # Create and show monitoring window
            monitoring_window = MonitoringWindow(config)
            monitoring_window.show()
            
            # Run application
            sys.exit(app.exec())
        else:
            sys.exit(0)
    else:
        # User cancelled
        sys.exit(0)


if __name__ == "__main__":
    main()
