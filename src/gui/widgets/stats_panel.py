"""
Statistics panel widget showing monitoring summary.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt


class StatsPanel(QWidget):
    """Panel displaying monitoring statistics."""
    
    def __init__(self, parent=None):
        """Initialize stats panel."""
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components."""
        from PyQt6.QtWidgets import QGridLayout
        
        layout = QGridLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Active Aircraft
        self.active_aircraft_label = QLabel("Active Aircraft: 0")
        self.active_aircraft_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.active_aircraft_label.setMinimumWidth(100)
        self.active_aircraft_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.active_aircraft_label, 0, 0)
        
        # Anomalies
        self.anomalies_label = QLabel("Anomalies: 0")
        self.anomalies_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #d32f2f;")
        self.anomalies_label.setMinimumWidth(100)
        self.anomalies_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.anomalies_label, 0, 1)
        
        # Poll Count
        self.poll_count_label = QLabel("Poll #0")
        self.poll_count_label.setStyleSheet("font-size: 13px;")
        self.poll_count_label.setMinimumWidth(100)
        self.poll_count_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.poll_count_label, 1, 0)
        
        # Status
        self.status_label = QLabel("Status: Stopped")
        self.status_label.setStyleSheet("font-size: 13px;")
        self.status_label.setMinimumWidth(100)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.status_label, 1, 1)
        
        # Set column stretch to make columns equal width
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        
        self.setLayout(layout)
        self.setMinimumHeight(80)
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 5px;
            }
            QLabel {
                padding: 5px;
            }
        """)
    
    def update_stats(self, active_aircraft: int, anomalies: int, poll_count: int):
        """Update statistics display."""
        self.active_aircraft_label.setText(f"Active Aircraft: {active_aircraft}")
        self.anomalies_label.setText(f"Anomalies: {anomalies}")
        self.poll_count_label.setText(f"Poll #{poll_count}")
    
    def update_status(self, status: str):
        """Update status display."""
        status_text = f"Status: {status.capitalize()}"
        self.status_label.setText(status_text)
        
        # Color code status
        if status == 'running':
            self.status_label.setStyleSheet("font-size: 14px; color: #388e3c; font-weight: bold;")
        elif status == 'paused':
            self.status_label.setStyleSheet("font-size: 14px; color: #f57c00; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("font-size: 14px; color: #616161;")
