"""
Monitoring information widget displaying search parameters and statistics.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox
from PyQt6.QtCore import Qt
from gui.theme import COLORS, SPACING, FONT_SIZES, RADIUS


class MonitoringInfo(QWidget):
    """Widget displaying monitoring configuration and statistics."""
    
    def __init__(self, parent=None):
        """Initialize monitoring info widget."""
        super().__init__(parent)
        self.init_ui()
        
        # Store current values
        self.region = None
        self.states = None
        self.database_type = None
        self.active_flights = 0
        self.total_aircraft_in_db = 0
        self.poll_count = 0
    
    def init_ui(self):
        """Initialize UI components."""
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, SPACING['sm'], 0, SPACING['sm'])  # Small padding top and bottom
        main_layout.setSpacing(0)
        
        # Create a group box to wrap everything in one unified box
        self.group_box = QGroupBox("Monitoring Information")
        self.group_box.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {COLORS['border']};
                border-top: none;
                border-bottom: none;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                margin-top: 0px;
                margin-bottom: 0px;
                padding-top: {SPACING['md']}px;
                background-color: {COLORS['bg_panel']};
                font-weight: 600;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {SPACING['md']}px;
                padding: 0 {SPACING['sm']}px;
                color: {COLORS['text_primary']};
            }}
        """)
        
        # Layout for group box contents
        content_layout = QVBoxLayout()
        content_layout.setSpacing(SPACING['sm'])
        content_layout.setContentsMargins(SPACING['md'], SPACING['sm'], SPACING['md'], SPACING['sm'])
        
        # Database type
        self.db_label = QLabel("Database: N/A")
        self.db_label.setStyleSheet(f"font-size: {FONT_SIZES['sm']}px; color: {COLORS['text_primary']};")
        content_layout.addWidget(self.db_label)
        
        # Region/State
        self.region_label = QLabel("Region/State: N/A")
        self.region_label.setStyleSheet(f"font-size: {FONT_SIZES['sm']}px; color: {COLORS['text_primary']};")
        content_layout.addWidget(self.region_label)
        
        # Total aircraft in database
        self.total_aircraft_label = QLabel("Aircraft in DB: 0")
        self.total_aircraft_label.setStyleSheet(f"font-size: {FONT_SIZES['sm']}px; color: {COLORS['text_secondary']};")
        content_layout.addWidget(self.total_aircraft_label)
        
        # Active flights
        self.active_flights_label = QLabel("Active Flights: 0")
        self.active_flights_label.setStyleSheet(f"font-size: {FONT_SIZES['sm']}px; font-weight: 600; color: {COLORS['text_primary']};")
        content_layout.addWidget(self.active_flights_label)
        
        # Poll count
        self.poll_label = QLabel("Poll Count: 0")
        self.poll_label.setStyleSheet(f"font-size: {FONT_SIZES['sm']}px; color: {COLORS['text_secondary']};")
        content_layout.addWidget(self.poll_label)
        
        self.group_box.setLayout(content_layout)
        
        main_layout.addWidget(self.group_box)
        self.setLayout(main_layout)
    
    def set_config(self, region=None, states=None, database_type=None, total_aircraft=0):
        """Set monitoring configuration."""
        self.region = region
        self.states = states
        self.database_type = database_type
        self.total_aircraft_in_db = total_aircraft
        self._update_display()
    
    def update_active_flights(self, count: int):
        """Update active flights count."""
        self.active_flights = count
        self._update_display()
    
    def update_poll_count(self, count: int):
        """Update poll count."""
        self.poll_count = count
        self._update_display()
    
    def _update_display(self):
        """Update all displayed information."""
        # Database type
        if self.database_type:
            db_text = self.database_type.upper()
        else:
            db_text = "N/A"
        self.db_label.setText(f"Database: {db_text}")
        
        # Region/State
        if self.states:
            if isinstance(self.states, list):
                states_text = ", ".join(self.states)
            else:
                states_text = str(self.states)
            self.region_label.setText(f"State(s): {states_text}")
        elif self.region:
            self.region_label.setText(f"Region: {self.region}")
        else:
            self.region_label.setText("Region/State: All")
        
        # Total aircraft
        self.total_aircraft_label.setText(f"Aircraft in DB: {self.total_aircraft_in_db}")
        
        # Active flights
        self.active_flights_label.setText(f"Active Flights: {self.active_flights}")
        
        # Poll count
        self.poll_label.setText(f"Poll Count: {self.poll_count}")
