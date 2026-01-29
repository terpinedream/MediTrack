"""
Aircraft detail dialog showing comprehensive aircraft information.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QGroupBox, QScrollArea, QWidget)
from PyQt6.QtCore import Qt
from typing import Dict, Optional
import webbrowser
from gui.theme import COLORS, SPACING, FONT_SIZES, RADIUS, get_button_style


class AircraftDetailDialog(QDialog):
    """Dialog displaying detailed aircraft information and actions."""
    
    def __init__(self, aircraft_state: Dict, aircraft_info: Optional[Dict] = None, 
                 anomaly: Optional[Dict] = None, parent=None):
        """
        Initialize aircraft detail dialog.
        
        Args:
            aircraft_state: Current aircraft state from OpenSky API
            aircraft_info: Aircraft database information (optional)
            anomaly: Active anomaly information (optional)
            parent: Parent widget
        """
        super().__init__(parent)
        self.aircraft_state = aircraft_state
        self.aircraft_info = aircraft_info or {}
        self.anomaly = anomaly
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("Aircraft Details")
        self.setMinimumSize(500, 600)
        self.setModal(True)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(SPACING['md'])
        main_layout.setContentsMargins(SPACING['lg'], SPACING['lg'], SPACING['lg'], SPACING['lg'])
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {COLORS['bg_main']};
            }}
        """)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(SPACING['md'])
        
        # Aircraft Information Section
        aircraft_group = QGroupBox("Aircraft Information")
        aircraft_layout = QVBoxLayout()
        aircraft_layout.setSpacing(SPACING['sm'])
        
        # ICAO24
        icao24 = self.aircraft_state.get('icao24', 'N/A')
        self._add_info_row(aircraft_layout, "ICAO24:", icao24)
        
        # Callsign
        callsign = self.aircraft_state.get('callsign', 'N/A')
        if callsign:
            callsign = callsign.strip()
        else:
            callsign = 'N/A'
        self._add_info_row(aircraft_layout, "Callsign:", callsign)
        
        # N-Number
        n_number = self.aircraft_info.get('n_number', 'N/A')
        self._add_info_row(aircraft_layout, "N-Number:", n_number)
        
        # Model
        model_name = self.aircraft_info.get('model_name', 'N/A')
        manufacturer = self.aircraft_info.get('manufacturer', 'N/A')
        if model_name != 'N/A' and manufacturer != 'N/A':
            model_text = f"{model_name} ({manufacturer})"
        elif model_name != 'N/A':
            model_text = model_name
        else:
            model_text = 'N/A'
        self._add_info_row(aircraft_layout, "Model:", model_text)
        
        # Owner Information
        owner_name = self.aircraft_info.get('owner_name', 'N/A')
        owner_city = self.aircraft_info.get('owner_city', 'N/A')
        owner_state = self.aircraft_info.get('owner_state', 'N/A')
        if owner_name != 'N/A':
            owner_text = owner_name
            if owner_city != 'N/A' or owner_state != 'N/A':
                owner_location = ', '.join(filter(lambda x: x != 'N/A', [owner_city, owner_state]))
                owner_text += f" ({owner_location})"
            self._add_info_row(aircraft_layout, "Owner:", owner_text)
        
        aircraft_group.setLayout(aircraft_layout)
        content_layout.addWidget(aircraft_group)
        
        # Current State Section
        state_group = QGroupBox("Current State")
        state_layout = QVBoxLayout()
        state_layout.setSpacing(SPACING['sm'])
        
        # Speed
        velocity = self.aircraft_state.get('velocity')
        if velocity is not None:
            speed_text = f"{velocity * 1.94384:.1f} knots ({velocity:.1f} m/s)"
        else:
            speed_text = 'N/A'
        self._add_info_row(state_layout, "Speed:", speed_text)
        
        # Altitude
        baro_alt = self.aircraft_state.get('baro_altitude')
        geo_alt = self.aircraft_state.get('geo_altitude')
        if baro_alt is not None:
            alt_text = f"{baro_alt:.0f} ft (barometric)"
        elif geo_alt is not None:
            alt_text = f"{geo_alt:.0f} ft (geometric)"
        else:
            alt_text = 'N/A'
        self._add_info_row(state_layout, "Altitude:", alt_text)
        
        # Vertical Rate
        vert_rate = self.aircraft_state.get('vertical_rate')
        if vert_rate is not None:
            vert_text = f"{vert_rate:.0f} ft/min"
        else:
            vert_text = 'N/A'
        self._add_info_row(state_layout, "Vertical Rate:", vert_text)
        
        # Location
        lat = self.aircraft_state.get('latitude')
        lon = self.aircraft_state.get('longitude')
        if lat is not None and lon is not None:
            location_text = f"{lat:.6f}, {lon:.6f}"
        else:
            location_text = 'N/A'
        self._add_info_row(state_layout, "Location:", location_text)
        
        # Heading
        heading = self.aircraft_state.get('heading')
        if heading is not None:
            heading_text = f"{heading:.1f}°"
        else:
            heading_text = 'N/A'
        self._add_info_row(state_layout, "Heading:", heading_text)
        
        state_group.setLayout(state_layout)
        content_layout.addWidget(state_group)
        
        # Anomaly Information Section (if present)
        if self.anomaly:
            anomaly_group = QGroupBox("Active Anomaly")
            anomaly_layout = QVBoxLayout()
            anomaly_layout.setSpacing(SPACING['sm'])
            
            anomaly_type = self.anomaly.get('type', 'unknown')
            severity = self.anomaly.get('severity', 'UNKNOWN')
            details = self.anomaly.get('details', {})
            
            # Color code severity
            severity_color = COLORS.get(severity.lower(), COLORS['unknown'])
            severity_label = QLabel(f"Severity: {severity}")
            severity_label.setStyleSheet(f"color: {severity_color}; font-weight: 600;")
            anomaly_layout.addWidget(severity_label)
            
            self._add_info_row(anomaly_layout, "Type:", anomaly_type.replace('_', ' ').title())
            
            # Time of detection
            detected_at = self.anomaly.get('detected_at')
            if detected_at:
                try:
                    from datetime import datetime
                    s = detected_at.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(s)
                    detected_str = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                    self._add_info_row(anomaly_layout, "Detected:", detected_str)
                except Exception:
                    self._add_info_row(anomaly_layout, "Detected:", str(detected_at))
            
            # Add details if available
            if details:
                for key, value in details.items():
                    if value:
                        self._add_info_row(anomaly_layout, f"{key.replace('_', ' ').title()}:", str(value))
            
            anomaly_group.setLayout(anomaly_layout)
            content_layout.addWidget(anomaly_group)
        
        content_layout.addStretch()
        content_widget.setLayout(content_layout)
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(SPACING['md'])
        
        # FlightAware button
        flightaware_url = self.aircraft_info.get('flightaware_url') if self.aircraft_info else None
        if flightaware_url:
            flightaware_btn = QPushButton("FlightAware")
            flightaware_btn.setStyleSheet(get_button_style('primary'))
            flightaware_btn.clicked.connect(lambda: webbrowser.open(flightaware_url))
            button_layout.addWidget(flightaware_btn)
        
        # FlightRadar24 button (always available if we have callsign or ICAO24)
        flightradar24_url = self._get_flightradar24_url()
        if flightradar24_url:
            flightradar24_btn = QPushButton("FlightRadar24")
            flightradar24_btn.setStyleSheet(get_button_style('primary'))
            flightradar24_btn.clicked.connect(lambda: webbrowser.open(flightradar24_url))
            button_layout.addWidget(flightradar24_btn)
        
        # Broadcastify button
        broadcastify_url = self.aircraft_info.get('broadcastify_url') if self.aircraft_info else None
        if broadcastify_url:
            broadcastify_btn = QPushButton("Broadcastify")
            broadcastify_btn.setStyleSheet(get_button_style('primary'))
            broadcastify_btn.clicked.connect(lambda: webbrowser.open(broadcastify_url))
            button_layout.addWidget(broadcastify_btn)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(get_button_style('primary'))
        close_btn.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        
        # Apply theme styling
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_main']};
            }}
            QGroupBox {{
                border: 1px solid {COLORS['border']};
                border-radius: {RADIUS['md']}px;
                margin-top: {SPACING['md']}px;
                padding-top: {SPACING['lg']}px;
                font-weight: 600;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {SPACING['md']}px;
                padding: 0 {SPACING['sm']}px;
            }}
        """)
    
    def _add_info_row(self, layout: QVBoxLayout, label: str, value: str):
        """Add a label-value row to a layout."""
        row_layout = QHBoxLayout()
        
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"font-weight: 600; color: {COLORS['text_secondary']};")
        label_widget.setMinimumWidth(120)
        row_layout.addWidget(label_widget)
        
        value_widget = QLabel(value)
        value_widget.setStyleSheet(f"color: {COLORS['text_primary']};")
        value_widget.setWordWrap(True)
        row_layout.addWidget(value_widget, stretch=1)
        
        layout.addLayout(row_layout)
    
    def _get_flightradar24_url(self) -> Optional[str]:
        """Generate FlightRadar24 URL for the aircraft."""
        # Try callsign first
        callsign = self.aircraft_state.get('callsign')
        if callsign and callsign.strip():
            callsign_clean = callsign.strip().upper()
            return f"https://www.flightradar24.com/{callsign_clean}"
        
        # Fallback to ICAO24
        icao24 = self.aircraft_state.get('icao24')
        if icao24:
            return f"https://www.flightradar24.com/{icao24}"
        
        return None
