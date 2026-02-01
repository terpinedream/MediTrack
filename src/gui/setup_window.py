"""
Setup/Configuration window for monitoring parameters.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
                             QPushButton, QLineEdit, QFileDialog, QMessageBox, QGroupBox)
from pathlib import Path
from gui.theme import COLORS, SPACING, FONT_SIZES, get_button_style


class SetupWindow(QDialog):
    """Setup window for configuring monitoring parameters."""
    
    def __init__(self, parent=None):
        """Initialize setup window."""
        super().__init__(parent)
        self.config = {}
        self.init_ui()
        # Load current interval/credentials from parent
        if parent and hasattr(parent, 'config'):
            self.interval_spin.setValue(parent.config.get('interval_seconds', 60))
            creds = parent.config.get('credentials_file')
            self.creds_input.setText(creds or '')
    
    def init_ui(self):
        """Initialize UI components (interval and credentials only; database/region are in main window sidebar)."""
        self.setWindowTitle("MediTrack - Setup")
        self.setMinimumSize(480, 280)
        self.resize(520, 320)
        
        layout = QVBoxLayout()
        layout.setSpacing(SPACING['lg'])
        layout.setContentsMargins(SPACING['xl'], SPACING['xl'], SPACING['xl'], SPACING['xl'])
        
        # Title
        title = QLabel("Monitoring Configuration")
        title.setStyleSheet(f"font-size: {FONT_SIZES['lg']}px; font-weight: 600; color: {COLORS['text_primary']};")
        layout.addWidget(title)
        
        # Polling interval
        interval_group = QGroupBox("Polling Interval")
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval (seconds):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setMinimum(10)
        self.interval_spin.setMaximum(3600)
        self.interval_spin.setValue(60)
        interval_layout.addWidget(self.interval_spin)
        interval_layout.addStretch()
        interval_group.setLayout(interval_layout)
        layout.addWidget(interval_group)
        
        # Credentials file (optional)
        creds_group = QGroupBox("Credentials (Optional)")
        creds_layout = QHBoxLayout()
        self.creds_input = QLineEdit()
        self.creds_input.setPlaceholderText("Path to credentials.json")
        creds_browse = QPushButton("Browse...")
        creds_browse.clicked.connect(self._browse_credentials)
        creds_layout.addWidget(self.creds_input)
        creds_layout.addWidget(creds_browse)
        creds_group.setLayout(creds_layout)
        layout.addWidget(creds_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Apply")
        self.start_button.setStyleSheet(get_button_style('success'))
        self.start_button.clicked.connect(self._on_start_clicked)
        button_layout.addStretch()
        button_layout.addWidget(self.start_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _browse_credentials(self):
        """Browse for credentials file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Credentials File",
            str(Path.home()),
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.creds_input.setText(file_path)
    
    def _on_start_clicked(self):
        """Handle start button click."""
        self.accept()
    
    def _validate_inputs(self) -> bool:
        """Validate user inputs."""
        creds_path = self.creds_input.text().strip()
        if creds_path and not Path(creds_path).exists():
            QMessageBox.warning(self, "Validation Error", "Credentials file not found.")
            return False
        return True
    
    def get_config(self) -> dict:
        """Get configuration dictionary."""
        return self.config
    
    def accept(self):
        """Accept configuration and close. Keep database/region from parent, update interval and credentials."""
        if self._validate_inputs():
            # Start from parent's config (database/region set in sidebar)
            parent = self.parent()
            self.config = getattr(parent, 'config', {}).copy() if parent else {}
            self.config['interval_seconds'] = self.interval_spin.value()
            self.config['credentials_file'] = self.creds_input.text().strip() or None
            super().accept()
