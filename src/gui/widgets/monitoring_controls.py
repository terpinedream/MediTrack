"""
Monitoring control buttons widget.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from gui.theme import COLORS, SPACING, FONT_SIZES, RADIUS, get_button_style


class MonitoringControls(QWidget):
    """Control buttons for monitoring."""
    
    # Signals
    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    resume_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        """Initialize monitoring controls."""
        super().__init__(parent)
        self.init_ui()
        self.is_running = False
        self.is_paused = False
    
    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()
        layout.setSpacing(SPACING['md'])
        layout.setContentsMargins(SPACING['md'], SPACING['md'], SPACING['md'], 0)  # No bottom margin
        
        # Buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(SPACING['md'])
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.start_button = QPushButton("Start Monitoring")
        self.start_button.setMinimumHeight(40)
        self.start_button.setMinimumWidth(180)
        self.start_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.start_button.setStyleSheet(get_button_style('success'))
        self.start_button.clicked.connect(self.start_clicked.emit)
        button_layout.addWidget(self.start_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setEnabled(False)
        self.pause_button.setMinimumHeight(40)
        self.pause_button.setMinimumWidth(180)
        self.pause_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pause_button.setStyleSheet(get_button_style('warning'))
        self.pause_button.clicked.connect(self._on_pause_clicked)
        button_layout.addWidget(self.pause_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setMinimumWidth(180)
        self.stop_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.stop_button.setStyleSheet(get_button_style('error'))
        self.stop_button.clicked.connect(self.stop_clicked.emit)
        button_layout.addWidget(self.stop_button)
        
        layout.addLayout(button_layout)
        # No stretch - let it sit directly on top of monitoring info
        
        self.setLayout(layout)
        self.setMinimumWidth(200)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_panel']};
                border: 1px solid {COLORS['border']};
                border-top-left-radius: {RADIUS['md']}px;
                border-top-right-radius: {RADIUS['md']}px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                padding: {SPACING['md']}px;
                padding-bottom: 0px;
            }}
        """)
    
    def _on_pause_clicked(self):
        """Handle pause/resume button click."""
        if self.is_paused:
            self.resume_clicked.emit()
        else:
            self.pause_clicked.emit()
    
    def set_running(self, running: bool):
        """Update running state."""
        self.is_running = running
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.pause_button.setEnabled(running)
        
        if not running:
            self.is_paused = False
            self.pause_button.setText("Pause")
    
    def set_paused(self, paused: bool):
        """Update paused state."""
        self.is_paused = paused
        if paused:
            self.pause_button.setText("Resume")
        else:
            self.pause_button.setText("Pause")
