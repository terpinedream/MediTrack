"""
Monitoring control buttons widget.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PyQt6.QtCore import pyqtSignal
from gui.theme import (
    get_compact_button_style,
    SPACING,
    apply_card_style,
    SIDEBAR_CARD_MARGINS,
)


class MonitoringControls(QWidget):
    """Control buttons for monitoring."""

    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    resume_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.is_running = False
        self.is_paused = False

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QWidget()
        apply_card_style(card)
        layout = QVBoxLayout(card)
        layout.setSpacing(SPACING['md'])
        layout.setContentsMargins(*SIDEBAR_CARD_MARGINS)

        self.start_button = QPushButton("Start Monitoring")
        self.start_button.setAccessibleName("Start monitoring")
        self.start_button.setAccessibleDescription("Begin polling OpenSky for active aircraft")
        self.start_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.start_button.setStyleSheet(get_compact_button_style('success'))
        self.start_button.clicked.connect(self.start_clicked.emit)
        layout.addWidget(self.start_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setAccessibleName("Pause monitoring")
        self.pause_button.setEnabled(False)
        self.pause_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pause_button.setStyleSheet(get_compact_button_style('warning'))
        self.pause_button.clicked.connect(self._on_pause_clicked)
        layout.addWidget(self.pause_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setAccessibleName("Stop monitoring")
        self.stop_button.setEnabled(False)
        self.stop_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.stop_button.setStyleSheet(get_compact_button_style('error'))
        self.stop_button.clicked.connect(self.stop_clicked.emit)
        layout.addWidget(self.stop_button)

        self.settings_button = QPushButton("Settings")
        self.settings_button.setAccessibleName("Monitoring settings")
        self.settings_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.settings_button.setStyleSheet(get_compact_button_style('primary'))
        self.settings_button.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_button)

        root.addWidget(card)
        self._card = card
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    def refresh_theme(self):
        """Re-apply styles after theme change."""
        apply_card_style(self._card)
        self.start_button.setStyleSheet(get_compact_button_style('success'))
        self.pause_button.setStyleSheet(get_compact_button_style('warning'))
        self.stop_button.setStyleSheet(get_compact_button_style('error'))
        self.settings_button.setStyleSheet(get_compact_button_style('primary'))

    def _on_pause_clicked(self):
        if self.is_paused:
            self.resume_clicked.emit()
        else:
            self.pause_clicked.emit()

    def set_running(self, running: bool):
        self.is_running = running
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.pause_button.setEnabled(running)

        if not running:
            self.is_paused = False
            self.pause_button.setText("Pause")

    def set_paused(self, paused: bool):
        self.is_paused = paused
        self.pause_button.setText("Resume" if paused else "Pause")

    def set_config_enabled(self, enabled: bool):
        """Enable/disable is handled by parent; placeholder for tooltip wiring."""
        pass
