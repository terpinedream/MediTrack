"""
Monitoring control buttons widget.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon


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
        layout.setSpacing(10)
        
        # Status indicator
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("font-size: 24px; color: #616161;")
        self.status_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_indicator)
        
        # Status text
        self.status_text = QLabel("Stopped")
        self.status_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_text.setStyleSheet("font-size: 12px; color: #616161;")
        layout.addWidget(self.status_text)
        
        layout.addSpacing(10)
        
        # Buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(8)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.start_button = QPushButton("Start Monitoring")
        self.start_button.setMinimumHeight(45)
        self.start_button.setMinimumWidth(180)
        self.start_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
                min-width: 180px;
                min-height: 45px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.start_button.clicked.connect(self.start_clicked.emit)
        button_layout.addWidget(self.start_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setEnabled(False)
        self.pause_button.setMinimumHeight(45)
        self.pause_button.setMinimumWidth(180)
        self.pause_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pause_button.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
                min-width: 180px;
                min-height: 45px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        self.pause_button.clicked.connect(self._on_pause_clicked)
        button_layout.addWidget(self.pause_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.setMinimumHeight(45)
        self.stop_button.setMinimumWidth(180)
        self.stop_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
                min-width: 180px;
                min-height: 45px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        self.stop_button.clicked.connect(self.stop_clicked.emit)
        button_layout.addWidget(self.stop_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        # Settings button
        self.settings_button = QPushButton("Settings")
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.settings_button.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_button)
        
        self.setLayout(layout)
        self.setMinimumWidth(200)
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
            }
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
        
        if running:
            self.status_indicator.setStyleSheet("font-size: 24px; color: #4caf50;")
            self.status_text.setText("Running")
        else:
            self.status_indicator.setStyleSheet("font-size: 24px; color: #616161;")
            self.status_text.setText("Stopped")
            self.is_paused = False
            self.pause_button.setText("Pause")
    
    def set_paused(self, paused: bool):
        """Update paused state."""
        self.is_paused = paused
        if paused:
            self.status_indicator.setStyleSheet("font-size: 24px; color: #ff9800;")
            self.status_text.setText("Paused")
            self.pause_button.setText("Resume")
        else:
            self.status_indicator.setStyleSheet("font-size: 24px; color: #4caf50;")
            self.status_text.setText("Running")
            self.pause_button.setText("Pause")
