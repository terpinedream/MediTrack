"""
Main application entry point for MediTrack GUI.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QFont

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.monitoring_window import MonitoringWindow
from gui.theme import get_global_stylesheet, FONT_SIZES, FONT_FAMILY, set_theme


def get_default_config():
    """Default config when opening directly to monitoring screen."""
    return {
        'database_type': 'ems',
        'interval_seconds': 60,
        'credentials_file': None,
        'region': None,
        'states': [],
    }


def main():
    import traceback
    try:
        settings = QSettings("MediTrack", "MediTrack")
        theme = settings.value("appearance/theme", "dark")
        set_theme(str(theme) if theme else "dark")

        app = QApplication(sys.argv)
        app.setApplicationName("MediTrack")
        app.setOrganizationName("MediTrack")

        font = QFont()
        font.setFamilies(FONT_FAMILY.replace('"', '').split(', '))
        font.setPointSize(FONT_SIZES['base'])
        app.setFont(font)
        app.setStyleSheet(get_global_stylesheet())

        config = get_default_config()
        monitoring_window = MonitoringWindow(config)
        monitoring_window.show()
        sys.exit(app.exec())
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
