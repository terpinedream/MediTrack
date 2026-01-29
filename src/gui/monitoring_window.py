"""
Main monitoring dashboard window.
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QMessageBox, QLabel, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap
from pathlib import Path
from typing import Dict, List, Optional

from gui.widgets.monitoring_info import MonitoringInfo

# Project root for assets (monitoring_window.py is in src/gui/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOGO_PATH = _PROJECT_ROOT / "assets" / "logo.png"
from gui.widgets.aircraft_table import AircraftTable
from gui.widgets.anomaly_list import AnomalyList
from gui.widgets.monitoring_controls import MonitoringControls
from gui.widgets.aircraft_detail_dialog import AircraftDetailDialog
from gui.workers.monitor_worker import MonitorWorker
from gui.setup_window import SetupWindow
from gui.theme import COLORS, SPACING, FONT_SIZES, RADIUS, get_button_style
from gui.model_lookup import ModelLookup


class MonitoringWindow(QMainWindow):
    """Main monitoring dashboard window."""
    
    def __init__(self, config: dict, parent=None):
        """
        Initialize monitoring window.
        
        Args:
            config: Configuration dictionary from setup window
        """
        super().__init__(parent)
        self.config = config
        self.worker = None
        self.aircraft_db = []
        self.active_anomalies = {}  # Track active anomalies by ICAO24
        self.pending_aircraft_update = None
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._process_aircraft_update)
        # Initialize model lookup utility (before init_ui since it's used there)
        self.model_lookup = ModelLookup()
        self.init_ui()
        self.load_aircraft_database()
        
        # Update monitoring info after database is loaded
        total_aircraft = len(self.aircraft_db) if self.aircraft_db else 0
        self.monitoring_info.set_config(
            region=self.config.get('region'),
            states=self.config.get('states'),
            database_type=self.config.get('database_type'),
            total_aircraft=total_aircraft
        )
    
    def init_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("MediTrack - Monitoring Dashboard")
        self.setMinimumSize(1000, 700)
        
        # Central widget
        central_widget = QWidget()
        central_widget.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(SPACING['md'], SPACING['md'], SPACING['md'], SPACING['md'])
        main_layout.setSpacing(SPACING['md'])
        
        # Left side - logo, controls and info
        left_layout = QVBoxLayout()
        left_layout.setSpacing(SPACING['md'])  # Even padding between controls, info, and settings
        
        # Logo (top left)
        logo_label = QLabel()
        if LOGO_PATH.exists():
            pixmap = QPixmap(str(LOGO_PATH))
            if not pixmap.isNull():
                pixmap = pixmap.scaledToWidth(180, Qt.TransformationMode.SmoothTransformation)
                logo_label.setPixmap(pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        logo_label.setStyleSheet("background: transparent;")
        left_layout.addWidget(logo_label)
        
        # Monitoring controls
        self.controls = MonitoringControls()
        self.controls.start_clicked.connect(self.start_monitoring)
        self.controls.stop_clicked.connect(self.stop_monitoring)
        self.controls.pause_clicked.connect(self.pause_monitoring)
        self.controls.resume_clicked.connect(self.resume_monitoring)
        left_layout.addWidget(self.controls)
        
        # Monitoring information (between stop and settings buttons)
        self.monitoring_info = MonitoringInfo()
        left_layout.addWidget(self.monitoring_info)
        
        # Settings button (separate from controls)
        from PyQt6.QtWidgets import QPushButton
        self.settings_button = QPushButton("Settings")
        # Custom styling to connect seamlessly with monitoring info box
        settings_style = get_button_style('primary')
        settings_style += f"""
            QPushButton {{
                border-top: none;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: {RADIUS['md']}px;
                border-bottom-right-radius: {RADIUS['md']}px;
                margin-top: 0px;
            }}
        """
        self.settings_button.setStyleSheet(settings_style)
        self.settings_button.clicked.connect(self.open_settings)
        left_layout.addWidget(self.settings_button)
        
        left_layout.addStretch()
        
        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setMinimumWidth(250)
        left_widget.setMaximumWidth(320)
        
        # Right side - main content
        right_layout = QVBoxLayout()
        right_layout.setSpacing(SPACING['md'])
        
        # Aircraft table
        aircraft_title = QLabel("Active Aircraft")
        aircraft_title.setStyleSheet(f"font-size: {FONT_SIZES['md']}px; font-weight: 600; color: {COLORS['text_primary']};")
        right_layout.addWidget(aircraft_title)
        
        self.aircraft_table = AircraftTable(model_lookup=self.model_lookup)
        right_layout.addWidget(self.aircraft_table, stretch=3)  # Give more space to table
        
        # Anomaly list
        anomaly_title = QLabel("Anomalies")
        anomaly_title.setStyleSheet(f"font-size: {FONT_SIZES['md']}px; font-weight: 600; color: {COLORS['text_primary']};")
        right_layout.addWidget(anomaly_title)
        
        self.anomaly_list = AnomalyList()
        self.anomaly_list.anomaly_clicked.connect(self._on_anomaly_navigate)
        self.anomaly_list.setMinimumHeight(300)  # Ensure enough height to see multiple items
        right_layout.addWidget(self.anomaly_list, stretch=2)  # Give more space to anomaly list
        
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        
        # Splitter for resizable layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)
        
        # Connect aircraft table click signal
        self.aircraft_table.aircraft_clicked.connect(self._on_aircraft_clicked)
        
        # Set initial state
        self.controls.set_running(False)
    
    def load_aircraft_database(self):
        """Load aircraft database for table display."""
        try:
            import config
            from opensky_client import load_ems_aircraft_db
            
            if self.config['database_type'] == 'police':
                db_path = config.POLICE_DB_JSON
            else:
                db_path = config.EMS_DB_JSON
            
            if db_path.exists():
                self.aircraft_db = load_ems_aircraft_db(db_path)
                # Update monitoring info with total aircraft count
                total_aircraft = len(self.aircraft_db) if self.aircraft_db else 0
                self.monitoring_info.set_config(
                    region=self.config.get('region'),
                    states=self.config.get('states'),
                    database_type=self.config.get('database_type'),
                    total_aircraft=total_aircraft
                )
            else:
                self.aircraft_db = []
                QMessageBox.warning(
                    self,
                    "Database Not Found",
                    f"Aircraft database not found at {db_path}.\n"
                    f"Please run the database creation script first."
                )
        except Exception as e:
            self.aircraft_db = []
            QMessageBox.critical(self, "Error", f"Failed to load aircraft database: {e}")
    
    def start_monitoring(self):
        """Start monitoring."""
        if self.worker and self.worker.isRunning():
            return
        
        try:
            # Create worker
            credentials_file = None
            if self.config.get('credentials_file'):
                credentials_file = Path(self.config['credentials_file'])
            
            self.worker = MonitorWorker(
                region=self.config.get('region'),
                states=self.config.get('states'),
                interval_seconds=self.config['interval_seconds'],
                credentials_file=credentials_file,
                database_type=self.config['database_type']
            )
            
            # Connect signals
            self.worker.aircraft_updated.connect(self._on_aircraft_updated)
            self.worker.anomaly_detected.connect(self._on_anomaly_detected)
            self.worker.summary_updated.connect(self._on_summary_updated)
            self.worker.error_occurred.connect(self._on_error)
            self.worker.status_changed.connect(self._on_status_changed)
            
            # Start worker
            self.worker.start()
            self.controls.set_running(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start monitoring: {e}")
    
    def stop_monitoring(self):
        """Stop monitoring."""
        if self.worker:
            self.worker.stop_monitoring()
            self.worker.wait(5000)  # Wait up to 5 seconds
            if self.worker.isRunning():
                self.worker.terminate()
            self.worker = None
        
        self.controls.set_running(False)
        self.monitoring_info.update_poll_count(0)
    
    def pause_monitoring(self):
        """Pause monitoring."""
        if self.worker:
            self.worker.pause_monitoring()
            self.controls.set_paused(True)
    
    def resume_monitoring(self):
        """Resume monitoring."""
        if self.worker:
            self.worker.resume_monitoring()
            self.controls.set_paused(False)
    
    def open_settings(self):
        """Open settings window."""
        # Stop monitoring if running
        was_running = False
        if self.worker and self.worker.isRunning():
            was_running = True
            self.stop_monitoring()
        
        # Show setup window
        setup = SetupWindow(self)
        if setup.exec() == QDialog.DialogCode.Accepted:
            new_config = setup.get_config()
            self.config = new_config
            self.load_aircraft_database()
            
            # Restart if was running
            if was_running:
                self.start_monitoring()
    
    def _on_aircraft_updated(self, aircraft_states: Dict):
        """Handle aircraft update signal (throttled to prevent freezing)."""
        # Store pending update
        self.pending_aircraft_update = (aircraft_states, self.aircraft_db)
        
        # Throttle updates - only process if timer not running
        if not self.update_timer.isActive():
            self.update_timer.start(100)  # 100ms delay to batch rapid updates
    
    def _process_aircraft_update(self):
        """Process pending aircraft update."""
        if self.pending_aircraft_update:
            aircraft_states, aircraft_db = self.pending_aircraft_update
            self.aircraft_table.update_aircraft(aircraft_states, aircraft_db, set(self.active_anomalies.keys()))
            
            # Update active flights count
            active_count = len(aircraft_states)
            self.monitoring_info.update_active_flights(active_count)
            
            # Clean up anomalies for aircraft no longer active
            current_icao24s = set(aircraft_states.keys())
            inactive_icao24s = set(self.active_anomalies.keys()) - current_icao24s
            for icao24 in inactive_icao24s:
                del self.active_anomalies[icao24]
            
            self.pending_aircraft_update = None
    
    def _on_anomaly_detected(self, anomaly: Dict):
        """Handle anomaly detected signal."""
        icao24 = anomaly.get('icao24')
        if icao24:
            # Ensure aircraft_info is complete - supplement from database if needed
            aircraft_info = anomaly.get('aircraft_info', {})
            
            # Try to get full info from database
            db_info = next(
                (ac for ac in self.aircraft_db
                 if ac.get('mode_s_hex', '').strip().upper() == icao24.upper()),
                None
            )
            
            if db_info:
                # Merge database info into aircraft_info
                if not aircraft_info:
                    aircraft_info = {}
                
                # Update missing fields from database
                for key in ['type_aircraft', 'model_code', 'owner_name', 'owner_city', 'owner_state', 'n_number']:
                    if key not in aircraft_info or not aircraft_info.get(key):
                        aircraft_info[key] = db_info.get(key, 'N/A' if key != 'type_aircraft' else '')
                
                # Handle model_name and manufacturer - use model lookup if "Unknown"
                model_name = aircraft_info.get('model_name', '')
                manufacturer = aircraft_info.get('manufacturer', '')
                model_code = aircraft_info.get('model_code', '')
                
                # Treat "Unknown" as missing
                if not model_name or model_name.upper().strip() in ['UNKNOWN', 'N/A', '']:
                    model_name = ''
                if not manufacturer or manufacturer.upper().strip() in ['UNKNOWN', 'N/A', '']:
                    manufacturer = ''
                
                # If model name is missing, try model lookup
                if not model_name and model_code:
                    model_info = self.model_lookup.lookup(model_code)
                    if model_info:
                        model_name = model_info.get('model', '')
                        if not manufacturer:
                            manufacturer = model_info.get('manufacturer', '')
                
                # If still missing, get from database
                if not model_name:
                    db_model = db_info.get('model_name', '')
                    if db_model and db_model.upper().strip() not in ['UNKNOWN', 'N/A', '']:
                        model_name = db_model
                
                if not manufacturer:
                    db_mfr = db_info.get('manufacturer', '')
                    if db_mfr and db_mfr.upper().strip() not in ['UNKNOWN', 'N/A', '']:
                        manufacturer = db_mfr
                
                # Update aircraft_info with resolved values
                aircraft_info['model_name'] = model_name if model_name else 'N/A'
                aircraft_info['manufacturer'] = manufacturer if manufacturer else 'N/A'
                
                anomaly['aircraft_info'] = aircraft_info
            
            # Store anomaly for active aircraft
            self.active_anomalies[icao24] = anomaly
        
        self.anomaly_list.add_anomaly(anomaly)
        # Refresh table so this aircraft row gets anomaly highlight immediately (no wait for next poll)
        if self.aircraft_table.aircraft_states and self.aircraft_db:
            self.aircraft_table.update_aircraft(
                self.aircraft_table.aircraft_states,
                self.aircraft_db,
                set(self.active_anomalies.keys())
            )
        # Anomalies are displayed in the anomaly list - no popup needed
    
    def _on_summary_updated(self, poll_count: int, active_aircraft: int, anomalies: int):
        """Handle summary update signal."""
        self.monitoring_info.update_active_flights(active_aircraft)
        self.monitoring_info.update_poll_count(poll_count)
    
    def _on_error(self, error_msg: str):
        """Handle error signal."""
        QMessageBox.critical(self, "Monitoring Error", error_msg)
    
    def _on_status_changed(self, status: str):
        """Handle status change signal."""
        if status == 'running':
            self.controls.set_running(True)
            self.controls.set_paused(False)
        elif status == 'paused':
            self.controls.set_paused(True)
        else:
            self.controls.set_running(False)
    
    def _on_anomaly_navigate(self, icao24: str):
        """Handle anomaly click - navigate to aircraft in table."""
        self.aircraft_table.select_aircraft_by_icao24(icao24)
    
    def _on_aircraft_clicked(self, icao24: str):
        """Handle aircraft row click - show detail dialog."""
        # Get current aircraft state
        aircraft_state = self.aircraft_table.get_aircraft_state(icao24)
        if not aircraft_state:
            return
        
        # Get aircraft database info
        aircraft_info = self.aircraft_table.get_aircraft_info(icao24)
        
        # Also try to get from aircraft_db if not in table data
        if not aircraft_info:
            aircraft_info = next(
                (ac for ac in self.aircraft_db
                 if ac.get('mode_s_hex', '').strip().upper() == icao24.upper()),
                None
            )
        
        # Ensure we have all fields from database if available
        if not aircraft_info or aircraft_info.get('model_name') in ['N/A', 'Unknown', None, '']:
            # Try to get full info from database
            db_info = next(
                (ac for ac in self.aircraft_db
                 if ac.get('mode_s_hex', '').strip().upper() == icao24.upper()),
                None
            )
            if db_info:
                # Merge database info, preserving any existing data
                if not aircraft_info:
                    aircraft_info = {}
                # Update missing fields from database
                for key in ['model_name', 'manufacturer', 'type_aircraft', 'n_number', 
                           'owner_name', 'owner_city', 'owner_state', 'model_code']:
                    if key not in aircraft_info or aircraft_info.get(key) in ['N/A', 'Unknown', None, '']:
                        aircraft_info[key] = db_info.get(key, 'N/A' if key != 'type_aircraft' else '')
        
        # If model_name is still missing or "Unknown", try model lookup
        if aircraft_info and (not aircraft_info.get('model_name') or 
                              aircraft_info.get('model_name') in ['N/A', 'Unknown', '']):
            model_code = aircraft_info.get('model_code', '')
            if model_code and self.model_lookup:
                model_info = self.model_lookup.lookup(model_code)
                if model_info:
                    if not aircraft_info.get('model_name') or aircraft_info.get('model_name') in ['N/A', 'Unknown', '']:
                        aircraft_info['model_name'] = model_info.get('model', 'N/A')
                    if not aircraft_info.get('manufacturer') or aircraft_info.get('manufacturer') in ['N/A', 'Unknown', '']:
                        aircraft_info['manufacturer'] = model_info.get('manufacturer', 'N/A')
        
        # Get active anomaly if any
        anomaly = self.active_anomalies.get(icao24)
        
        # Get Broadcastify URL if available (from anomaly or generate)
        if aircraft_info:
            # Check if anomaly has broadcastify URL
            if anomaly and anomaly.get('aircraft_info', {}).get('broadcastify_url'):
                aircraft_info['broadcastify_url'] = anomaly['aircraft_info']['broadcastify_url']
            # Otherwise, try to generate from current location
            elif aircraft_state.get('latitude') and aircraft_state.get('longitude'):
                try:
                    from location_utils import get_broadcastify_url_simple
                    lat = aircraft_state.get('latitude')
                    lon = aircraft_state.get('longitude')
                    broadcastify_url = get_broadcastify_url_simple(lat, lon)
                    if broadcastify_url:
                        aircraft_info['broadcastify_url'] = broadcastify_url
                except Exception:
                    pass  # Silently fail if geocoding unavailable
        
        # Create and show dialog
        dialog = AircraftDetailDialog(
            aircraft_state=aircraft_state,
            aircraft_info=aircraft_info,
            anomaly=anomaly,
            parent=self
        )
        dialog.exec()
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Confirm Exit",
                "Monitoring is active. Do you want to stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_monitoring()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
