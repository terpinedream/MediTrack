"""
Anomaly list widget displaying detected anomalies.
"""

from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QStyledItemDelegate
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen, QFont, QFontMetrics
from typing import Dict, List
from datetime import datetime
import webbrowser
from gui.theme import COLORS, SPACING
from gui.utils import is_helicopter


class AnomalyItemDelegate(QStyledItemDelegate):
    """Custom delegate to ensure background colors are properly rendered."""
    
    def paint(self, painter: QPainter, option, index):
        """Custom paint to ensure background colors are visible."""
        # Get background brush from item
        background = index.data(Qt.ItemDataRole.BackgroundRole)
        if background:
            # Fill entire item background
            if isinstance(background, QBrush):
                painter.fillRect(option.rect, background)
            elif isinstance(background, QColor):
                painter.fillRect(option.rect, background)
        
        # Let Qt handle text rendering with the global font (which includes Symbola for emoji)
        super().paint(painter, option, index)


class AnomalyList(QListWidget):
    """List widget displaying anomalies."""
    
    # Severity colors (using theme colors)
    SEVERITY_COLORS = {
        'CRITICAL': COLORS['critical'],
        'HIGH': COLORS['high'],
        'MEDIUM': COLORS['medium'],
        'LOW': COLORS['low'],
        'UNKNOWN': COLORS['unknown']
    }
    
    # Signal emitted when anomaly is clicked (for navigation)
    anomaly_clicked = pyqtSignal(str)  # Emits ICAO24
    
    def __init__(self, parent=None):
        """Initialize anomaly list."""
        super().__init__(parent)
        self.init_ui()
        self.anomalies = []  # Store full anomaly data
        # Set custom delegate to ensure backgrounds render
        self.setItemDelegate(AnomalyItemDelegate(self))
    
    def init_ui(self):
        """Initialize UI components."""
        self.setAlternatingRowColors(False)  # Disable alternating colors - we use severity colors
        self.setWordWrap(False)  # Single line items
        self.setMinimumHeight(200)  # Ensure list has enough height to show multiple items
        
        # Font is inherited from global application font (set in main.py)
        # which includes Symbola for monochrome emoji support
        
        # Connect item click to emit signal
        self.itemClicked.connect(self._on_item_clicked)
        
        # Connect selection change to update text color
        self.itemSelectionChanged.connect(self._on_selection_changed)
        
        self.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS['bg_main']};
                border: 1px solid {COLORS['border']};
            }}
            QListWidget::item {{
                padding: {SPACING['sm']}px {SPACING['md']}px;
                border-bottom: 1px solid {COLORS['border']};
                min-height: 24px;
            }}
            QListWidget::item:selected {{
                border: 2px solid {COLORS['selection']};
                border-left: 4px solid {COLORS['selection']};
            }}
        """)
    
    def _on_selection_changed(self):
        """Handle selection change to ensure text is readable."""
        # Update all items to restore proper colors and ensure backgrounds are visible
        for row in range(self.count()):
            item = self.item(row)
            if item:
                severity = item.data(Qt.ItemDataRole.UserRole + 1)
                is_selected = item.isSelected()
                
                # Re-apply background color to ensure it's visible
                if severity:
                    color_hex = self.SEVERITY_COLORS.get(severity, self.SEVERITY_COLORS['UNKNOWN'])
                    item.setBackground(self._color_from_hex(color_hex, opacity=255))
                    item.setData(Qt.ItemDataRole.BackgroundRole, self._color_from_hex(color_hex, opacity=255))
                
                # Set text color based on severity (not selection state)
                # The blue border indicates selection, text should remain readable on colored background
                if severity in ['CRITICAL', 'HIGH']:
                    item.setForeground(Qt.GlobalColor.white)
                else:
                    item.setForeground(Qt.GlobalColor.black)
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle item click - emit ICAO24 for navigation."""
        anomaly = item.data(Qt.ItemDataRole.UserRole)
        if anomaly:
            icao24 = anomaly.get('icao24')
            if icao24:
                self.anomaly_clicked.emit(icao24)
    
    def add_anomaly(self, anomaly: Dict):
        """Add an anomaly to the list."""
        self.anomalies.append(anomaly)
        
        # Create item
        item = QListWidgetItem()
        
        # Get aircraft info
        aircraft_info = anomaly.get('aircraft_info', {})
        n_number = aircraft_info.get('n_number', 'N/A')
        anomaly_type = anomaly.get('type', 'unknown')
        severity = str(anomaly.get('severity', 'UNKNOWN')).upper()  # Ensure uppercase
        
        # Determine aircraft type tag
        is_heli = is_helicopter(aircraft_info)
        tag = '[HELI]' if is_heli else '[PLANE]'
        plane_symbol = '✈'
        anomaly_type_title = anomaly_type.replace('_', ' ').title()
        
        # Time of detection
        time_str = ''
        tooltip_time = ''
        detected_at = anomaly.get('detected_at')
        if detected_at:
            try:
                s = detected_at.replace('Z', '+00:00')
                dt = datetime.fromisoformat(s)
                time_str = dt.strftime('%H:%M')
                tooltip_time = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
            except Exception:
                pass
        
        # Build display text: [time] ✈ [TAG] N-Number: Anomaly Type
        if n_number != 'N/A':
            base = f"{plane_symbol} {tag} {n_number}: {anomaly_type_title}"
        else:
            icao24 = anomaly.get('icao24', 'UNKNOWN')
            base = f"{plane_symbol} {tag} {icao24}: {anomaly_type_title}"
        text = f"{time_str} - {base}" if time_str else base
        item.setText(text)
        if tooltip_time:
            item.setToolTip(f"Detected: {tooltip_time}")
        
        # Set color based on severity (ensure we have a valid color)
        color_hex = self.SEVERITY_COLORS.get(severity, self.SEVERITY_COLORS['UNKNOWN'])
        
        # Create background brush with full opacity
        bg_brush = self._color_from_hex(color_hex, opacity=255)
        
        # Set background color - use both methods to ensure it's applied
        item.setBackground(bg_brush)
        item.setData(Qt.ItemDataRole.BackgroundRole, bg_brush)
        
        # Set text color based on severity and background brightness
        # For critical/high (red/amber), use white text
        # For medium/low (yellow/green), use dark text
        if severity in ['CRITICAL', 'HIGH']:
            text_color = Qt.GlobalColor.white
        else:
            text_color = Qt.GlobalColor.black
        
        item.setForeground(text_color)
        item.setData(Qt.ItemDataRole.ForegroundRole, text_color)
        
        # Store severity for selection handling
        item.setData(Qt.ItemDataRole.UserRole + 1, severity)
        
        # Force update to ensure colors are rendered
        self.update()
        
        # Store anomaly data in item
        item.setData(Qt.ItemDataRole.UserRole, anomaly)
        
        # Insert at top
        self.insertItem(0, item)
        
        # Limit to 100 items
        if self.count() > 100:
            self.takeItem(self.count() - 1)
    
    def _color_from_hex(self, hex_color: str, opacity: int = 255):
        """
        Convert hex color to QBrush with specified opacity.
        
        Args:
            hex_color: Hex color string (with or without #)
            opacity: Opacity value 0-255 (255 = fully opaque for maximum visibility)
        """
        from PyQt6.QtGui import QColor, QBrush
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            color = QColor(r, g, b, opacity)
            return QBrush(color)
        # Fallback
        return QBrush(QColor(128, 128, 128, opacity))
    
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
