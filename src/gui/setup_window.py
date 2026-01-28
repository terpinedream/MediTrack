"""
Setup/Configuration window for monitoring parameters.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                             QSpinBox, QPushButton, QLineEdit, QFileDialog, QRadioButton,
                             QButtonGroup, QMessageBox, QGroupBox)
from PyQt6.QtCore import Qt
from pathlib import Path
from typing import Optional, List
from regions import is_valid_state_code, get_all_state_codes


class SetupWindow(QDialog):
    """Setup window for configuring monitoring parameters."""
    
    def __init__(self, parent=None):
        """Initialize setup window."""
        super().__init__(parent)
        self.config = {}
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("MediTrack - Setup")
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Monitoring Configuration")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # Database type
        db_group = QGroupBox("Database Type")
        db_layout = QVBoxLayout()
        self.db_combo = QComboBox()
        self.db_combo.addItems(["EMS", "Police"])
        db_layout.addWidget(self.db_combo)
        db_group.setLayout(db_layout)
        layout.addWidget(db_group)
        
        # Region/State selection
        region_group = QGroupBox("Monitoring Area")
        region_layout = QVBoxLayout()
        
        # Radio buttons
        self.region_radio = QRadioButton("Region")
        self.state_radio = QRadioButton("State(s)")
        self.all_radio = QRadioButton("All US")
        
        self.region_radio.setChecked(True)
        
        self.area_button_group = QButtonGroup()
        self.area_button_group.addButton(self.region_radio, 0)
        self.area_button_group.addButton(self.state_radio, 1)
        self.area_button_group.addButton(self.all_radio, 2)
        
        region_layout.addWidget(self.region_radio)
        region_layout.addWidget(self.state_radio)
        region_layout.addWidget(self.all_radio)
        
        # Region combo
        self.region_combo = QComboBox()
        self.region_combo.addItems(["Northeast", "Midwest", "South", "West"])
        region_layout.addWidget(QLabel("Region:"))
        region_layout.addWidget(self.region_combo)
        
        # State input
        self.state_input = QLineEdit()
        self.state_input.setPlaceholderText("Enter state code(s), e.g., NJ or NJ,DE,PA")
        region_layout.addWidget(QLabel("State Code(s):"))
        region_layout.addWidget(self.state_input)
        
        # Connect radio buttons
        self.region_radio.toggled.connect(self._on_region_toggled)
        self.state_radio.toggled.connect(self._on_state_toggled)
        self.all_radio.toggled.connect(self._on_all_toggled)
        
        region_group.setLayout(region_layout)
        layout.addWidget(region_group)
        
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
        self.start_button = QPushButton("Start Monitoring")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.start_button.clicked.connect(self._on_start_clicked)
        button_layout.addStretch()
        button_layout.addWidget(self.start_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Initial state
        self._on_region_toggled(True)
    
    def _on_region_toggled(self, checked):
        """Handle region radio button toggle."""
        if checked:
            self.region_combo.setEnabled(True)
            self.state_input.setEnabled(False)
    
    def _on_state_toggled(self, checked):
        """Handle state radio button toggle."""
        if checked:
            self.region_combo.setEnabled(False)
            self.state_input.setEnabled(True)
    
    def _on_all_toggled(self, checked):
        """Handle all radio button toggle."""
        if checked:
            self.region_combo.setEnabled(False)
            self.state_input.setEnabled(False)
    
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
        # Validate state codes if state mode
        if self.state_radio.isChecked():
            state_str = self.state_input.text().strip()
            if not state_str:
                QMessageBox.warning(self, "Validation Error", "Please enter state code(s).")
                return False
            
            states = [s.strip().upper() for s in state_str.split(',')]
            invalid_states = [s for s in states if not is_valid_state_code(s)]
            if invalid_states:
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Invalid state code(s): {', '.join(invalid_states)}\n\n"
                    f"Valid codes: {', '.join(sorted(get_all_state_codes()))}"
                )
                return False
        
        # Validate credentials file if provided
        creds_path = self.creds_input.text().strip()
        if creds_path:
            if not Path(creds_path).exists():
                QMessageBox.warning(self, "Validation Error", "Credentials file not found.")
                return False
        
        return True
    
    def get_config(self) -> dict:
        """Get configuration dictionary."""
        return self.config
    
    def accept(self):
        """Accept configuration and close."""
        if self._validate_inputs():
            # Build config
            self.config = {
                'database_type': self.db_combo.currentText().lower(),
                'interval_seconds': self.interval_spin.value(),
                'credentials_file': self.creds_input.text().strip() if self.creds_input.text().strip() else None
            }
            
            # Add region/state config
            if self.all_radio.isChecked():
                self.config['region'] = None
                self.config['states'] = []  # Empty list means "all US"
            elif self.region_radio.isChecked():
                region_map = {
                    'Northeast': 'northeast',
                    'Midwest': 'midwest',
                    'South': 'south',
                    'West': 'west'
                }
                self.config['region'] = region_map[self.region_combo.currentText()]
                self.config['states'] = None
            else:  # state radio
                state_str = self.state_input.text().strip().upper()
                states = [s.strip() for s in state_str.split(',')]
                self.config['region'] = None
                self.config['states'] = states
            
            super().accept()
