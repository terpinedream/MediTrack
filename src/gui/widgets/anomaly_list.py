"""
Anomaly list widget displaying detected anomalies.
"""

from PyQt6.QtWidgets import QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt
from typing import Dict, List
from datetime import datetime
import webbrowser


class AnomalyList(QListWidget):
    """List widget displaying anomalies."""
    
    # Severity colors
    SEVERITY_COLORS = {
        'CRITICAL': '#d32f2f',  # Red
        'HIGH': '#f57c00',      # Orange
        'MEDIUM': '#fbc02d',    # Yellow
        'LOW': '#388e3c',       # Green
        'UNKNOWN': '#616161'    # Gray
    }
    
    def __init__(self, parent=None):
        """Initialize anomaly list."""
        super().__init__(parent)
        self.init_ui()
        self.anomalies = []  # Store full anomaly data
    
    def init_ui(self):
        """Initialize UI components."""
        self.setAlternatingRowColors(True)
        self.setWordWrap(True)
        
        self.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #ddd;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
    
    def add_anomaly(self, anomaly: Dict):
        """Add an anomaly to the list."""
        self.anomalies.append(anomaly)
        
        # Create item
        item = QListWidgetItem()
        
        # Format text
        icao24 = anomaly.get('icao24', 'UNKNOWN')
        anomaly_type = anomaly.get('type', 'unknown')
        severity = anomaly.get('severity', 'UNKNOWN')
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Get aircraft info
        aircraft_info = anomaly.get('aircraft_info', {})
        n_number = aircraft_info.get('n_number', 'N/A')
        
        # Build display text
        text = f"[{timestamp}] {severity}: {anomaly_type.upper()}\n"
        text += f"Aircraft: {icao24}"
        if n_number != 'N/A':
            text += f" (N-Number: {n_number})"
        
        item.setText(text)
        
        # Set color based on severity
        color = self.SEVERITY_COLORS.get(severity, self.SEVERITY_COLORS['UNKNOWN'])
        item.setForeground(Qt.GlobalColor.white if severity == 'CRITICAL' else Qt.GlobalColor.black)
        
        # Set background color
        item.setBackground(self._color_from_hex(color))
        
        # Store anomaly data in item
        item.setData(Qt.ItemDataRole.UserRole, anomaly)
        
        # Insert at top
        self.insertItem(0, item)
        
        # Limit to 100 items
        if self.count() > 100:
            self.takeItem(self.count() - 1)
    
    def _color_from_hex(self, hex_color: str):
        """Convert hex color to QBrush."""
        from PyQt6.QtGui import QColor, QBrush
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        color = QColor(r, g, b, 50)  # 50 = semi-transparent
        return QBrush(color)
    
    def get_selected_anomaly(self) -> Dict:
        """Get currently selected anomaly data."""
        item = self.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None
    
    def open_links(self, anomaly: Dict):
        """Open FlightAware and Broadcastify links for anomaly."""
        aircraft_info = anomaly.get('aircraft_info', {})
        
        flightaware_url = aircraft_info.get('flightaware_url')
        if flightaware_url:
            webbrowser.open(flightaware_url)
        
        broadcastify_url = aircraft_info.get('broadcastify_url')
        if broadcastify_url:
            webbrowser.open(broadcastify_url)
