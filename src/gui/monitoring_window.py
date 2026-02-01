"""
Main monitoring dashboard window.
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QMessageBox, QLabel, QDialog,
                             QMenuBar, QMenu, QFileDialog, QHeaderView, QPushButton,
                             QGroupBox, QComboBox, QRadioButton, QButtonGroup, QLineEdit)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import QPixmap, QAction
from PyQt6.QtWebEngineWidgets import QWebEngineView
from pathlib import Path
from typing import Dict, List, Optional
import csv
import json

from gui.widgets.monitoring_info import MonitoringInfo

# Project root for assets (monitoring_window.py is in src/gui/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOGO_PATH = _PROJECT_ROOT / "assets" / "logo.png"

# Leaflet/OSM map HTML for embedded flight location (updatePosition(lat, lon, label) exposed)
_MAP_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>html,body{margin:0;padding:0;height:100%;}</style>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head>
<body>
  <div id="hint" style="position:absolute;top:8px;left:50%;transform:translateX(-50%);z-index:1000;
    background:rgba(255,255,255,0.9);padding:4px 12px;border-radius:4px;font-size:12px;">
    Select a flight to see location
  </div>
  <div id="map" style="position:absolute;top:0;left:0;right:0;bottom:0;"></div>
  <script>
    var map = L.map('map').setView([39.5, -98.5], 4);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);
    var marker = null;
    function updatePosition(lat, lon, label) {
      if (marker) map.removeLayer(marker);
      marker = L.marker([lat, lon]).addTo(map);
      if (label) marker.bindPopup(label).openPopup();
      map.setView([lat, lon], 10);
      var h = document.getElementById('hint');
      if (h) h.style.display = 'none';
    }
  </script>
</body>
</html>
"""

from gui.widgets.aircraft_table import AircraftTable
from gui.widgets.anomaly_list import AnomalyList
from gui.widgets.monitoring_controls import MonitoringControls
from gui.widgets.aircraft_detail_dialog import AircraftDetailDialog
from gui.workers.monitor_worker import MonitorWorker
from gui.setup_window import SetupWindow
from gui.setup_data_dialog import SetupDataDialog
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
        self._sync_config_to_sidebar()
    
    def _sync_config_to_sidebar(self):
        """Sync database/region/state widgets from self.config."""
        db = self.config.get('database_type', 'ems')
        self.db_combo.setCurrentText(db.upper() if db else 'EMS')
        region = self.config.get('region')
        states = self.config.get('states')
        if states is not None and len(states) == 0:
            self.all_radio.setChecked(True)
            self.region_combo.setEnabled(False)
            self.state_input.setEnabled(False)
        elif region is not None:
            self.region_radio.setChecked(True)
            self.region_combo.setEnabled(True)
            self.state_input.setEnabled(False)
            region_map = {'northeast': 'Northeast', 'midwest': 'Midwest', 'south': 'South', 'west': 'West'}
            self.region_combo.setCurrentText(region_map.get(region, 'Northeast'))
        else:
            self.state_radio.setChecked(True)
            self.region_combo.setEnabled(False)
            self.state_input.setEnabled(True)
            self.state_input.setText(', '.join(states) if states else '')
    
    def _on_region_toggled(self, checked):
        if checked:
            self.region_combo.setEnabled(True)
            self.state_input.setEnabled(False)
            self._on_config_area_changed()
    
    def _on_state_toggled(self, checked):
        if checked:
            self.region_combo.setEnabled(False)
            self.state_input.setEnabled(True)
            self._on_config_area_changed()
    
    def _on_all_toggled(self, checked):
        if checked:
            self.region_combo.setEnabled(False)
            self.state_input.setEnabled(False)
            self.config['region'] = None
            self.config['states'] = []
            self.monitoring_info.set_config(
                region=self.config.get('region'),
                states=self.config.get('states'),
                database_type=self.config.get('database_type'),
                total_aircraft=len(self.aircraft_db) if self.aircraft_db else 0
            )
    
    def _on_config_area_changed(self):
        """Update config from region/state widgets and refresh monitoring info."""
        if self.all_radio.isChecked():
            self.config['region'] = None
            self.config['states'] = []
        elif self.region_radio.isChecked():
            region_map = {'Northeast': 'northeast', 'Midwest': 'midwest', 'South': 'south', 'West': 'west'}
            self.config['region'] = region_map.get(self.region_combo.currentText(), 'northeast')
            self.config['states'] = None
        else:
            from regions import is_valid_state_code, get_all_state_codes
            state_str = self.state_input.text().strip().upper()
            if not state_str:
                return
            states = [s.strip() for s in state_str.split(',')]
            invalid = [s for s in states if not is_valid_state_code(s)]
            if invalid:
                QMessageBox.warning(
                    self, "Invalid state(s)",
                    f"Invalid: {', '.join(invalid)}. Valid: {', '.join(sorted(get_all_state_codes())[:10])}..."
                )
                return
            self.config['region'] = None
            self.config['states'] = states
        self.monitoring_info.set_config(
            region=self.config.get('region'),
            states=self.config.get('states'),
            database_type=self.config.get('database_type'),
            total_aircraft=len(self.aircraft_db) if self.aircraft_db else 0
        )
    
    def _on_db_combo_changed(self, text):
        """Update database type and reload aircraft list."""
        self.config['database_type'] = text.lower() if text else 'ems'
        self.load_aircraft_database()
        total_aircraft = len(self.aircraft_db) if self.aircraft_db else 0
        self.monitoring_info.set_config(
            region=self.config.get('region'),
            states=self.config.get('states'),
            database_type=self.config.get('database_type'),
            total_aircraft=total_aircraft
        )
        if self.worker and self.worker.isRunning():
            QMessageBox.information(
                self, "Database changed",
                "Restart monitoring for the new database type to take effect."
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
        
        # Monitoring information
        self.monitoring_info = MonitoringInfo()
        left_layout.addWidget(self.monitoring_info)
        
        # Setup data button (FAA download + build EMS/Police databases)
        self.setup_data_button = QPushButton("Setup data")
        setup_data_style = get_button_style('primary')
        setup_data_style += f"""
            QPushButton {{
                border-top: none;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: {RADIUS['md']}px;
                border-bottom-right-radius: {RADIUS['md']}px;
                margin-top: 0px;
            }}
        """
        self.setup_data_button.setStyleSheet(setup_data_style)
        self.setup_data_button.clicked.connect(self.open_setup_data)
        left_layout.addWidget(self.setup_data_button)
        
        # Database type and region/state (below Setup data)
        config_group = QGroupBox("Monitoring")
        config_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: {RADIUS['md']}px;
                margin-top: {SPACING['sm']}px;
                padding-top: {SPACING['md']}px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {SPACING['md']}px;
                padding: 0 {SPACING['xs']}px;
            }}
        """)
        config_layout = QVBoxLayout()
        config_layout.addWidget(QLabel("Database:"))
        self.db_combo = QComboBox()
        self.db_combo.addItems(["EMS", "Police"])
        self.db_combo.currentTextChanged.connect(self._on_db_combo_changed)
        config_layout.addWidget(self.db_combo)
        config_layout.addWidget(QLabel("Area:"))
        self.region_radio = QRadioButton("Region")
        self.state_radio = QRadioButton("State(s)")
        self.all_radio = QRadioButton("All US")
        self.area_button_group = QButtonGroup()
        self.area_button_group.addButton(self.region_radio)
        self.area_button_group.addButton(self.state_radio)
        self.area_button_group.addButton(self.all_radio)
        config_layout.addWidget(self.region_radio)
        config_layout.addWidget(self.state_radio)
        config_layout.addWidget(self.all_radio)
        self.region_combo = QComboBox()
        self.region_combo.addItems(["Northeast", "Midwest", "South", "West"])
        config_layout.addWidget(self.region_combo)
        self.state_input = QLineEdit()
        self.state_input.setPlaceholderText("e.g. NJ or NJ,DE,PA")
        config_layout.addWidget(self.state_input)
        self.region_radio.toggled.connect(self._on_region_toggled)
        self.state_radio.toggled.connect(self._on_state_toggled)
        self.all_radio.toggled.connect(self._on_all_toggled)
        self.region_combo.currentTextChanged.connect(self._on_config_area_changed)
        self.state_input.editingFinished.connect(self._on_config_area_changed)
        config_group.setLayout(config_layout)
        left_layout.addWidget(config_group)
        
        left_layout.addStretch()
        
        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setMinimumWidth(250)
        left_widget.setMaximumWidth(320)
        
        # Right side - main content
        right_layout = QVBoxLayout()
        right_layout.setSpacing(SPACING['md'])
        right_layout.setContentsMargins(0, 0, 0, 0)  # no extra padding so map aligns to bottom
        
        # Aircraft table
        aircraft_title = QLabel("Active Aircraft")
        aircraft_title.setStyleSheet(f"font-size: {FONT_SIZES['md']}px; font-weight: 600; color: {COLORS['text_primary']};")
        right_layout.addWidget(aircraft_title)
        
        self.aircraft_table = AircraftTable(model_lookup=self.model_lookup)
        right_layout.addWidget(self.aircraft_table, stretch=3)  # Give more space to table
        
        # Bottom row: Anomalies (left) | Map (right)
        self._bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Anomalies
        anomaly_widget = QWidget()
        anomaly_widget.setMinimumWidth(280)
        anomaly_layout = QVBoxLayout()
        anomaly_layout.setContentsMargins(0, 0, 0, 0)
        anomaly_title = QLabel("Anomalies")
        anomaly_title.setStyleSheet(f"font-size: {FONT_SIZES['md']}px; font-weight: 600; color: {COLORS['text_primary']};")
        anomaly_layout.addWidget(anomaly_title)
        self.anomaly_list = AnomalyList()
        self.anomaly_list.anomaly_clicked.connect(self._on_anomaly_navigate)
        self.anomaly_list.setMinimumHeight(200)
        anomaly_layout.addWidget(self.anomaly_list, 1)  # stretch so list fills height
        anomaly_widget.setLayout(anomaly_layout)
        self._bottom_splitter.addWidget(anomaly_widget)
        
        # Right: Map
        map_widget = QWidget()
        map_layout = QVBoxLayout()
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_title = QLabel("Selected flight")
        map_title.setStyleSheet(f"font-size: {FONT_SIZES['md']}px; font-weight: 600; color: {COLORS['text_primary']};")
        map_layout.addWidget(map_title)
        self._map_view = QWebEngineView()
        self._map_view.setMinimumHeight(200)
        self._map_loaded = False
        self._map_view.loadFinished.connect(self._on_map_loaded)
        self._map_view.setHtml(_MAP_HTML, QUrl("https://unpkg.com/"))
        map_layout.addWidget(self._map_view, 1)  # stretch so map fills height to match anomalies
        map_widget.setLayout(map_layout)
        self._bottom_splitter.addWidget(map_widget)
        
        self._bottom_splitter.setSizes([350, 450])  # anomalies narrower, map gets more space
        right_layout.addWidget(self._bottom_splitter, stretch=2)
        
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        
        # Splitter for resizable layout
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.addWidget(left_widget)
        self._main_splitter.addWidget(right_widget)
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(self._main_splitter)
        central_widget.setLayout(main_layout)
        
        # Connect aircraft table click signal
        self.aircraft_table.aircraft_clicked.connect(self._on_aircraft_clicked)
        
        # Menu bar
        self._build_menu_bar()
        
        # Set initial state
        self.controls.set_running(False)
    
    def _build_menu_bar(self):
        """Build File, Edit, Settings, and Help menus."""
        menubar = self.menuBar()
        
        # File
        file_menu = menubar.addMenu("&File")
        export_anomalies_txt = QAction("Export Anomalies as Text...", self)
        export_anomalies_txt.triggered.connect(lambda: self._export_anomalies("txt"))
        file_menu.addAction(export_anomalies_txt)
        export_anomalies_csv = QAction("Export Anomalies as CSV...", self)
        export_anomalies_csv.triggered.connect(lambda: self._export_anomalies("csv"))
        file_menu.addAction(export_anomalies_csv)
        file_menu.addSeparator()
        export_aircraft_txt = QAction("Export Active Aircraft as Text...", self)
        export_aircraft_txt.triggered.connect(lambda: self._export_aircraft("txt"))
        file_menu.addAction(export_aircraft_txt)
        export_aircraft_csv = QAction("Export Active Aircraft as CSV...", self)
        export_aircraft_csv.triggered.connect(lambda: self._export_aircraft("csv"))
        file_menu.addAction(export_aircraft_csv)
        
        # Edit
        edit_menu = menubar.addMenu("&Edit")
        visible_menu = edit_menu.addMenu("Visible columns")
        self._column_actions = []
        col_names = ['Model', 'ICAO24', 'Callsign', 'N-Number', 'Status', 'Speed (kts)', 'Altitude (ft)', 'Location']
        for col, name in enumerate(col_names):
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(True)
            act.triggered.connect(lambda checked, c=col: self._on_column_visibility(c, checked))
            self._column_actions.append((col, act))
            visible_menu.addAction(act)
        visible_menu.aboutToShow.connect(self._sync_column_visibility_actions)
        edit_menu.addSeparator()
        reset_cols = QAction("Reset column widths", self)
        reset_cols.triggered.connect(self._reset_column_widths)
        edit_menu.addAction(reset_cols)
        reset_layout = QAction("Reset layout", self)
        reset_layout.triggered.connect(self._reset_layout)
        edit_menu.addAction(reset_layout)
        
        # Settings
        settings_menu = menubar.addMenu("&Settings")
        settings_act = QAction("Monitoring configuration...", self)
        settings_act.triggered.connect(self.open_settings)
        settings_menu.addAction(settings_act)
        
        # Help
        help_menu = menubar.addMenu("&Help")
        about_act = QAction("About MediTrack", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)
    
    def _sync_column_visibility_actions(self):
        """Sync Visible columns menu check state from table."""
        if hasattr(self, '_column_actions'):
            for col, act in self._column_actions:
                act.setChecked(not self.aircraft_table.isColumnHidden(col))
    
    def _on_column_visibility(self, col: int, visible: bool):
        """Toggle aircraft table column visibility."""
        self.aircraft_table.setColumnHidden(col, not visible)
    
    def _reset_column_widths(self):
        """Reset aircraft table columns to resize to contents."""
        header = self.aircraft_table.horizontalHeader()
        for col in range(self.aircraft_table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
    
    def _reset_layout(self):
        """Reset main splitter to default sizes."""
        self._main_splitter.setSizes([250, 700])  # left, right
    
    def _show_about(self):
        """Show About dialog."""
        QMessageBox.about(
            self,
            "About MediTrack",
            "MediTrack - EMS & Police Aircraft Tracking\n\n"
            "Track and monitor EMS and Police/Law Enforcement aircraft in the US "
            "using the OpenSky Network API.\n\n"
            "Identifies aircraft from the FAA registry and flags unusual flight patterns."
        )
    
    def _export_anomalies(self, fmt: str):
        """Export current anomalies to text or CSV file."""
        anomalies = getattr(self.anomaly_list, 'anomalies', [])
        if not anomalies:
            QMessageBox.information(self, "Export", "No anomalies to export.")
            return
        filter_str = "Text files (*.txt);;CSV files (*.csv)" if fmt == "txt" else "CSV files (*.csv);;Text files (*.txt)"
        path, selected_filter = QFileDialog.getSaveFileName(self, "Export Anomalies", "", filter_str)
        if not path:
            return
        path = Path(path)
        if not path.suffix and "CSV" in (selected_filter or ""):
            path = path.with_suffix(".csv")
        elif not path.suffix:
            path = path.with_suffix(".txt")
        try:
            use_csv = fmt == "csv" or path.suffix.lower() == ".csv"
            if use_csv:
                self._write_anomalies_csv(path, anomalies)
            else:
                self._write_anomalies_txt(path, anomalies)
            QMessageBox.information(self, "Export", f"Exported {len(anomalies)} anomaly(ies) to {path.name}.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))
    
    def _write_anomalies_txt(self, path: Path, anomalies: List[Dict]):
        lines = []
        for a in anomalies:
            icao = a.get('icao24', 'N/A')
            typ = a.get('type', 'unknown')
            sev = a.get('severity', 'UNKNOWN')
            det = a.get('detected_at', '')
            info = a.get('aircraft_info', {})
            n = info.get('n_number', 'N/A')
            lines.append(f"[{det}] {icao} {typ} {sev} (N-number: {n})")
            details = a.get('details', {})
            if details:
                for k, v in details.items():
                    if v is not None and str(v).strip():
                        lines.append(f"  {k}: {v}")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
    
    def _write_anomalies_csv(self, path: Path, anomalies: List[Dict]):
        columns = ['icao24', 'type', 'severity', 'detected_at', 'n_number', 'callsign',
                   'velocity_knots', 'altitude_drop_ft', 'distance_hospital_km', 'hospital_name']
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            w.writeheader()
            for a in anomalies:
                row = {k: a.get(k, '') for k in ['icao24', 'type', 'severity', 'detected_at']}
                info = a.get('aircraft_info', {})
                row['n_number'] = info.get('n_number', '')
                row['callsign'] = info.get('callsign', '')
                details = a.get('details', {})
                row['velocity_knots'] = details.get('velocity_knots', '')
                row['altitude_drop_ft'] = details.get('altitude_drop_ft', '')
                row['distance_hospital_km'] = details.get('distance_hospital_km', '')
                row['hospital_name'] = details.get('hospital_name', '')
                w.writerow(row)
    
    def _export_aircraft(self, fmt: str):
        """Export current active aircraft table to text or CSV file."""
        rows = self.aircraft_table.get_export_rows()
        if not rows:
            QMessageBox.information(self, "Export", "No active aircraft to export.")
            return
        filter_str = "Text files (*.txt);;CSV files (*.csv)" if fmt == "txt" else "CSV files (*.csv);;Text files (*.txt)"
        path, selected_filter = QFileDialog.getSaveFileName(self, "Export Active Aircraft", "", filter_str)
        if not path:
            return
        path = Path(path)
        if not path.suffix and "CSV" in (selected_filter or ""):
            path = path.with_suffix(".csv")
        elif not path.suffix:
            path = path.with_suffix(".txt")
        try:
            use_csv = fmt == "csv" or path.suffix.lower() == ".csv"
            if use_csv:
                self._write_aircraft_csv(path, rows)
            else:
                self._write_aircraft_txt(path, rows)
            QMessageBox.information(self, "Export", f"Exported {len(rows)} aircraft to {path.name}.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))
    
    def _write_aircraft_txt(self, path: Path, rows: List[Dict[str, str]]):
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        headers = list(rows[0].keys())
        lines = ["\t".join(headers)]
        for r in rows:
            lines.append("\t".join(str(r.get(h, "")) for h in headers))
        path.write_text("\n".join(lines), encoding="utf-8")
    
    def _write_aircraft_csv(self, path: Path, rows: List[Dict[str, str]]):
        if not rows:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                f.write("")
            return
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    
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
    
    def open_setup_data(self):
        """Open setup data dialog (FAA download + build EMS & Police databases)."""
        dialog = SetupDataDialog(self)
        dialog.databases_built.connect(self._on_databases_built)
        dialog.exec()
    
    def _on_databases_built(self):
        """Refresh aircraft list and monitoring info after databases were built."""
        self.load_aircraft_database()
        total_aircraft = len(self.aircraft_db) if self.aircraft_db else 0
        self.monitoring_info.set_config(
            region=self.config.get('region'),
            states=self.config.get('states'),
            database_type=self.config.get('database_type'),
            total_aircraft=total_aircraft
        )
    
    def _maybe_show_initial_setup(self):
        """If neither EMS nor Police database exists, open setup data dialog once."""
        import config
        if not config.EMS_DB_JSON.exists() and not config.POLICE_DB_JSON.exists():
            dialog = SetupDataDialog(self)
            dialog.databases_built.connect(self._on_databases_built)
            dialog.exec()
    
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
    
    def _on_map_loaded(self, ok: bool):
        """Mark map as ready so runJavaScript can be used."""
        self._map_loaded = ok
    
    def _update_map_position(self, lat: float, lon: float, label: str = ""):
        """Update embedded map to show position (call only when map is loaded)."""
        if not self._map_loaded:
            return
        label_js = json.dumps(str(label))
        js = f"updatePosition({lat}, {lon}, {label_js})"
        self._map_view.page().runJavaScript(js)
    
    def _on_aircraft_clicked(self, icao24: str):
        """Handle aircraft row click - show detail dialog and update map."""
        # Get current aircraft state
        aircraft_state = self.aircraft_table.get_aircraft_state(icao24)
        if not aircraft_state:
            return
        
        # Update embedded map to plane location when position available
        lat = aircraft_state.get('latitude')
        lon = aircraft_state.get('longitude')
        if lat is not None and lon is not None:
            label = aircraft_state.get('callsign') or aircraft_state.get('icao24') or icao24
            self._update_map_position(float(lat), float(lon), label)
        
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
