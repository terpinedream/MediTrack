"""
Main monitoring dashboard window.
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QMessageBox, QLabel, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from pathlib import Path
from typing import Dict, List, Optional

from gui.widgets.stats_panel import StatsPanel
from gui.widgets.aircraft_table import AircraftTable
from gui.widgets.anomaly_list import AnomalyList
from gui.widgets.monitoring_controls import MonitoringControls
from gui.workers.monitor_worker import MonitorWorker
from gui.setup_window import SetupWindow


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
        self.pending_aircraft_update = None
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._process_aircraft_update)
        self.init_ui()
        self.load_aircraft_database()
    
    def init_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("MediTrack - Monitoring Dashboard")
        self.setMinimumSize(1000, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Left side - controls and stats
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)
        
        # Stats panel
        self.stats_panel = StatsPanel()
        left_layout.addWidget(self.stats_panel)
        
        # Monitoring controls
        self.controls = MonitoringControls()
        self.controls.start_clicked.connect(self.start_monitoring)
        self.controls.stop_clicked.connect(self.stop_monitoring)
        self.controls.pause_clicked.connect(self.pause_monitoring)
        self.controls.resume_clicked.connect(self.resume_monitoring)
        self.controls.settings_clicked.connect(self.open_settings)
        left_layout.addWidget(self.controls)
        
        left_layout.addStretch()
        
        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setMinimumWidth(250)
        left_widget.setMaximumWidth(320)
        
        # Right side - main content
        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)
        
        # Aircraft table
        aircraft_title = QLabel("Active Aircraft")
        aircraft_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        right_layout.addWidget(aircraft_title)
        
        self.aircraft_table = AircraftTable()
        right_layout.addWidget(self.aircraft_table, stretch=2)
        
        # Anomaly list
        anomaly_title = QLabel("Anomalies")
        anomaly_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        right_layout.addWidget(anomaly_title)
        
        self.anomaly_list = AnomalyList()
        self.anomaly_list.itemDoubleClicked.connect(self._on_anomaly_double_clicked)
        right_layout.addWidget(self.anomaly_list, stretch=1)
        
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
        
        # Set initial state
        self.controls.set_running(False)
        self.stats_panel.update_status('stopped')
    
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
            else:
                QMessageBox.warning(
                    self,
                    "Database Not Found",
                    f"Aircraft database not found at {db_path}.\n"
                    f"Please run the database creation script first."
                )
        except Exception as e:
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
        self.stats_panel.update_status('stopped')
    
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
            self.aircraft_table.update_aircraft(aircraft_states, aircraft_db)
            self.pending_aircraft_update = None
    
    def _on_anomaly_detected(self, anomaly: Dict):
        """Handle anomaly detected signal."""
        self.anomaly_list.add_anomaly(anomaly)
        # Anomalies are displayed in the anomaly list - no popup needed
    
    def _on_summary_updated(self, poll_count: int, active_aircraft: int, anomalies: int):
        """Handle summary update signal."""
        self.stats_panel.update_stats(active_aircraft, anomalies, poll_count)
    
    def _on_error(self, error_msg: str):
        """Handle error signal."""
        QMessageBox.critical(self, "Monitoring Error", error_msg)
    
    def _on_status_changed(self, status: str):
        """Handle status change signal."""
        self.stats_panel.update_status(status)
        if status == 'running':
            self.controls.set_running(True)
            self.controls.set_paused(False)
        elif status == 'paused':
            self.controls.set_paused(True)
        else:
            self.controls.set_running(False)
    
    def _on_anomaly_double_clicked(self, item):
        """Handle anomaly double-click to open links."""
        anomaly = self.anomaly_list.get_selected_anomaly()
        if anomaly:
            self.anomaly_list.open_links(anomaly)
    
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
