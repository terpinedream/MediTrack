"""
Main monitoring dashboard window.
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QMessageBox, QLabel, QDialog,
                             QMenuBar, QMenu, QFileDialog, QHeaderView, QPushButton,
                             QComboBox, QRadioButton, QButtonGroup, QLineEdit,
                             QStatusBar, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QUrl, QSettings
from PyQt6.QtGui import QAction, QShortcut, QKeySequence
from PyQt6.QtWebEngineWidgets import QWebEngineView
from pathlib import Path
from typing import Dict, List, Optional
import csv
import json

from gui.widgets.monitoring_info import MonitoringInfo

# Leaflet/OSM map HTML for embedded flight location
def _build_map_html(hint_bg: str, hint_text: str) -> str:
    """Build map HTML with plane icons for selected and starred aircraft."""
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body {{ margin: 0; padding: 0; height: 100%; }}
    .plane-marker-icon {{ background: transparent; border: none; }}
    #hint {{
      position: absolute; top: 10px; left: 50%; transform: translateX(-50%); z-index: 1000;
      background: {hint_bg}; color: {hint_text}; padding: 6px 14px; border-radius: 10px;
      font-size: 12px; font-family: sans-serif; box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    }}
  </style>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head>
<body>
  <div id="hint">Select a flight to see location</div>
  <div id="map" style="position:absolute;top:0;left:0;right:0;bottom:0;"></div>
  <script>
    var map = L.map('map').setView([39.5, -98.5], 4);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }}).addTo(map);

    var selectedMarker = null;
    var starredMarkers = {{}};

    function planeIcon(color, size) {{
      var html = '<div style="width:' + size + 'px;height:' + size + 'px;display:flex;align-items:center;justify-content:center;">' +
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="' + size + '" height="' + size + '">' +
        '<path fill="' + color + '" stroke="rgba(0,0,0,0.35)" stroke-width="0.6" ' +
        'd="M21 16v-2l-8-5V3.5a1.5 1.5 0 00-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/>' +
        '</svg></div>';
      return L.divIcon({{
        className: 'plane-marker-icon',
        html: html,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
        popupAnchor: [0, -size / 2]
      }});
    }}

    function updatePosition(lat, lon, label) {{
      if (selectedMarker) map.removeLayer(selectedMarker);
      selectedMarker = L.marker([lat, lon], {{ icon: planeIcon('#60a5fa', 34), zIndexOffset: 1000 }}).addTo(map);
      if (label) selectedMarker.bindPopup(label).openPopup();
      map.setView([lat, lon], 10);
      var h = document.getElementById('hint');
      if (h) h.style.display = 'none';
    }}

    function updateStarredMarkers(items) {{
      var seen = {{}};
      (items || []).forEach(function(item) {{
        if (item.lat == null || item.lon == null) return;
        seen[item.icao] = true;
        var pos = [item.lat, item.lon];
        if (starredMarkers[item.icao]) {{
          starredMarkers[item.icao].setLatLng(pos);
        }} else {{
          starredMarkers[item.icao] = L.marker(pos, {{
            icon: planeIcon('#facc15', 26),
            zIndexOffset: 500
          }}).addTo(map);
          if (item.label) starredMarkers[item.icao].bindPopup(item.label);
        }}
      }});
      Object.keys(starredMarkers).forEach(function(icao) {{
        if (!seen[icao]) {{
          map.removeLayer(starredMarkers[icao]);
          delete starredMarkers[icao];
        }}
      }});
    }}

    function invalidateMapSize() {{
      if (map) map.invalidateSize();
    }}
  </script>
</body>
</html>
"""

from gui.widgets.aircraft_table import AircraftTable, COL_STAR
from gui.widgets.anomaly_list import AnomalyList
from gui.widgets.monitoring_controls import MonitoringControls
from gui.widgets.aircraft_detail_dialog import AircraftDetailDialog
from gui.workers.monitor_worker import MonitorWorker
from gui.setup_window import SetupWindow
from gui.setup_data_dialog import SetupDataDialog
from gui.logo import load_logo_pixmap, LOGO_PATH
from gui.starred_store import StarredAircraftStore
from gui.theme import (
    COLORS, SPACING, FONT_SIZES, RADIUS, get_button_style, set_theme, get_current_theme,
    get_card_stylesheet, get_card_widget_stylesheet, get_section_title_stylesheet,
    get_table_stylesheet, apply_card_style, get_compact_button_style,
    SIDEBAR_CARD_MARGINS,
)
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
        self.aircraft_db_by_icao = {}
        self.active_anomalies = {}  # Track active anomalies by ICAO24
        self.session_anomaly_count = 0
        self._last_error_msg = ""
        self._detail_dialog = None
        self.starred_store = StarredAircraftStore()
        self._last_active_states: Dict[str, dict] = {}
        self.pending_aircraft_update = None
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._process_aircraft_update)
        # Initialize model lookup utility (before init_ui since it's used there)
        self.model_lookup = ModelLookup()
        settings = QSettings("MediTrack", "MediTrack")
        self._show_starred_panel = settings.value("ui/show_starred_panel", True, type=bool)
        self._map_fullscreen_dialog = None
        self._map_fullscreen_layout = None
        self._map_fullscreen_active = False
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
        self._maybe_show_initial_setup()
        self._setup_shortcuts()
        self._setup_accessibility()
        self._refresh_starred_table(set())
        self._sync_starred_map_markers()

    @staticmethod
    def _make_panel(title: str, panel_registry: list = None) -> tuple:
        """Create a rounded card panel; returns (panel, content_layout, header_row)."""
        panel = QWidget()
        apply_card_style(panel)
        if panel_registry is not None:
            panel_registry.append(panel)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(SPACING['xl'], SPACING['xl'], SPACING['xl'], SPACING['xl'])
        outer.setSpacing(SPACING['md'])
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(SPACING['md'])
        title_label = QLabel(title)
        title_label.setStyleSheet(get_section_title_stylesheet())
        header_row.addWidget(title_label)
        header_row.addStretch()
        outer.addLayout(header_row)
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(SPACING['md'])
        outer.addLayout(content)
        return panel, content, header_row

    @staticmethod
    def _make_sidebar_card(panel_registry: list = None) -> tuple:
        """Title-less card for the left sidebar."""
        panel = QWidget()
        apply_card_style(panel)
        if panel_registry is not None:
            panel_registry.append(panel)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(*SIDEBAR_CARD_MARGINS)
        outer.setSpacing(SPACING['sm'])
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(SPACING['sm'])
        outer.addLayout(content)
        return panel, content

    def _sync_starred_map_markers(self):
        """Push starred aircraft positions to the map."""
        if not getattr(self, '_map_loaded', False):
            return
        markers = []
        for icao, entry in self.starred_store.entries.items():
            state = self._last_active_states.get(icao) or entry.get('last_state') or {}
            lat = state.get('latitude')
            lon = state.get('longitude')
            if lat is None or lon is None:
                continue
            label = state.get('callsign') or icao
            markers.append({'icao': icao, 'lat': float(lat), 'lon': float(lon), 'label': str(label)})
        js = f"updateStarredMarkers({json.dumps(markers)})"
        self._map_view.page().runJavaScript(js)

    def _update_starred_panel_visibility(self):
        has_starred = bool(self.starred_store.entries)
        if not has_starred:
            self._show_starred_panel = False
            if hasattr(self, 'show_starred_cb'):
                self.show_starred_cb.blockSignals(True)
                self.show_starred_cb.setChecked(False)
                self.show_starred_cb.setEnabled(False)
                self.show_starred_cb.blockSignals(False)
        elif hasattr(self, 'show_starred_cb'):
            self.show_starred_cb.setEnabled(True)

        visible = has_starred and self._show_starred_panel
        self._starred_panel.setVisible(visible)
        if hasattr(self, 'show_starred_cb') and has_starred:
            self.show_starred_cb.blockSignals(True)
            self.show_starred_cb.setChecked(visible)
            self.show_starred_cb.blockSignals(False)

    def _on_show_starred_panel_toggled(self, checked: bool):
        self._show_starred_panel = checked
        QSettings("MediTrack", "MediTrack").setValue("ui/show_starred_panel", checked)
        self._update_starred_panel_visibility()

    def _refresh_starred_table(self, active_icao24s: set):
        """Refresh starred table from store and current poll data."""
        states, db_list = self.starred_store.build_table_payload(self._last_active_states)
        starred = self.starred_store.starred_icao24s()
        self.starred_table.set_starred_icao24s(starred)
        self.aircraft_table.set_starred_icao24s(starred)
        if starred:
            self.starred_table.update_aircraft(
                states,
                db_list,
                set(self.active_anomalies.keys()),
                active_icao24s=active_icao24s,
            )
        else:
            self.starred_table.update_aircraft({}, [], set())
        self._update_starred_panel_visibility()
        self._sync_starred_map_markers()

    def _on_star_toggled(self, icao24: str, starred: bool):
        icao = icao24.upper()
        if starred:
            state = self.aircraft_table.get_aircraft_state(icao24) or self.starred_table.get_aircraft_state(icao24)
            info = self.aircraft_db_by_icao.get(icao) or self.aircraft_table.get_aircraft_info(icao24)
            self.starred_store.add(
                icao,
                info,
                state,
                database_type=self.config.get("database_type"),
            )
            self._show_starred_panel = True
            if hasattr(self, 'show_starred_cb'):
                self.show_starred_cb.blockSignals(True)
                self.show_starred_cb.setChecked(True)
                self.show_starred_cb.setEnabled(True)
                self.show_starred_cb.blockSignals(False)
            self.status_bar.showMessage(f"Starred {icao}")
        else:
            self.starred_store.remove(icao)
            self.status_bar.showMessage(f"Removed {icao} from starred")

        active = set(self._last_active_states.keys())
        self._refresh_starred_table(active)
    
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
        self._theme_panels = []
        
        # Central widget
        central_widget = QWidget()
        central_widget.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(SPACING['xl'], SPACING['xl'], SPACING['xl'], SPACING['xl'])
        main_layout.setSpacing(SPACING['xl'])
        
        # Left sidebar — controls and configuration
        left_layout = QVBoxLayout()
        left_layout.setSpacing(SPACING['xl'])
        left_layout.setContentsMargins(0, 0, 0, 0)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        logo_label.setStyleSheet("background: transparent;")
        logo_pixmap = load_logo_pixmap(LOGO_PATH, width=128)
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap)
        left_layout.addWidget(logo_label)
        
        # Monitoring controls
        self.controls = MonitoringControls()
        self.controls.start_clicked.connect(self.start_monitoring)
        self.controls.stop_clicked.connect(self.stop_monitoring)
        self.controls.pause_clicked.connect(self.pause_monitoring)
        self.controls.resume_clicked.connect(self.resume_monitoring)
        self.controls.settings_clicked.connect(self.open_settings)
        left_layout.addWidget(self.controls)
        
        # Monitoring information
        self.monitoring_info = MonitoringInfo()
        left_layout.addWidget(self.monitoring_info)
        
        # Database type and region/state
        config_panel, config_layout = self._make_sidebar_card(self._theme_panels)
        field_label_style = (
            f"background: transparent; color: {COLORS['text_secondary']}; "
            f"font-size: {FONT_SIZES['xs']}px;"
        )
        db_label = QLabel("Database")
        db_label.setStyleSheet(field_label_style)
        config_layout.addWidget(db_label)
        self.db_combo = QComboBox()
        self.db_combo.addItems(["EMS", "Police"])
        self.db_combo.currentTextChanged.connect(self._on_db_combo_changed)
        config_layout.addWidget(self.db_combo)
        area_label = QLabel("Area")
        area_label.setStyleSheet(field_label_style)
        config_layout.addWidget(area_label)
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
        left_layout.addWidget(config_panel)
        left_layout.addStretch()
        
        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setFixedWidth(340)
        left_widget.setStyleSheet("background: transparent;")
        
        # Right side - main content
        right_layout = QVBoxLayout()
        right_layout.setSpacing(SPACING['xl'])
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Aircraft tables (active + optional starred)
        aircraft_row = QWidget()
        aircraft_row.setStyleSheet("background: transparent;")
        aircraft_row_layout = QHBoxLayout(aircraft_row)
        aircraft_row_layout.setContentsMargins(0, 0, 0, 0)
        aircraft_row_layout.setSpacing(SPACING['xl'])

        active_panel, active_panel_layout, active_header = self._make_panel(
            "Active Aircraft", self._theme_panels
        )
        self.show_starred_cb = QCheckBox("Show starred")
        self.show_starred_cb.setToolTip("Show or hide the starred aircraft panel")
        self.show_starred_cb.setChecked(self._show_starred_panel and bool(self.starred_store.entries))
        self.show_starred_cb.setEnabled(bool(self.starred_store.entries))
        self.show_starred_cb.toggled.connect(self._on_show_starred_panel_toggled)
        active_header.addWidget(self.show_starred_cb)
        self.aircraft_table = AircraftTable(model_lookup=self.model_lookup)
        self.aircraft_table.set_starred_icao24s(self.starred_store.starred_icao24s())
        active_panel_layout.addWidget(self.aircraft_table, 1)

        starred_panel, starred_panel_layout, _ = self._make_panel("Starred", self._theme_panels)
        self.starred_table = AircraftTable(
            model_lookup=self.model_lookup,
            empty_message="No starred aircraft — click ☆ on an active aircraft",
        )
        self.starred_table.set_starred_icao24s(self.starred_store.starred_icao24s())
        starred_panel_layout.addWidget(self.starred_table, 1)
        self._starred_panel = starred_panel

        aircraft_row_layout.addWidget(active_panel, stretch=1)
        aircraft_row_layout.addWidget(starred_panel, stretch=1)
        self._update_starred_panel_visibility()
        right_layout.addWidget(aircraft_row, stretch=3)
        
        # Bottom row: Anomalies | Map
        bottom_row = QWidget()
        bottom_row.setStyleSheet("background: transparent;")
        bottom_row_layout = QHBoxLayout(bottom_row)
        bottom_row_layout.setContentsMargins(0, 0, 0, 0)
        bottom_row_layout.setSpacing(SPACING['xl'])
        
        anomaly_panel, anomaly_layout, _ = self._make_panel("Anomalies", self._theme_panels)
        anomaly_panel.setMinimumWidth(280)
        self.anomaly_list = AnomalyList()
        self.anomaly_list.anomaly_clicked.connect(self._on_anomaly_navigate)
        self.anomaly_list.setMinimumHeight(200)
        anomaly_layout.addWidget(self.anomaly_list, 1)
        clear_row = QHBoxLayout()
        clear_row.setContentsMargins(0, SPACING['sm'], 0, 0)
        clear_row.addStretch()
        self.clear_anomalies_btn = QPushButton("Clear session")
        self.clear_anomalies_btn.setStyleSheet(get_compact_button_style('primary'))
        self.clear_anomalies_btn.clicked.connect(self._clear_anomalies)
        clear_row.addWidget(self.clear_anomalies_btn)
        anomaly_layout.addLayout(clear_row)
        
        map_panel, map_layout, _ = self._make_panel("Selected flight", self._theme_panels)
        self._map_embed_layout = map_layout
        self._map_view = QWebEngineView()
        self._map_view.setMinimumHeight(200)
        self._map_view.setStyleSheet(
            f"border: 1px solid {COLORS['border']}; border-radius: {RADIUS['md']}px;"
        )
        self._map_loaded = False
        self._map_view.loadFinished.connect(self._on_map_loaded)
        map_html = _build_map_html(COLORS['map_hint_bg'], COLORS['map_hint_text'])
        self._map_view.setHtml(map_html, QUrl("https://unpkg.com/"))
        self._map_error_label = QLabel("Map unavailable (network required)", self._map_view)
        self._map_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._map_error_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 13px; "
            f"background: {COLORS['bg_card']}; border-radius: {RADIUS['md']}px;"
        )
        self._map_error_label.hide()
        map_layout.addWidget(self._map_view, 1)
        fullscreen_row = QHBoxLayout()
        fullscreen_row.setContentsMargins(0, SPACING['sm'], 0, 0)
        fullscreen_row.addStretch()
        self._map_fullscreen_btn = QPushButton("Fullscreen")
        self._map_fullscreen_btn.setCheckable(True)
        self._map_fullscreen_btn.setToolTip("Toggle fullscreen map view (Esc to exit)")
        self._map_fullscreen_btn.setStyleSheet(get_compact_button_style('primary'))
        self._map_fullscreen_btn.toggled.connect(self._toggle_map_fullscreen)
        fullscreen_row.addWidget(self._map_fullscreen_btn)
        map_layout.addLayout(fullscreen_row)

        bottom_row_layout.addWidget(anomaly_panel, stretch=2)
        bottom_row_layout.addWidget(map_panel, stretch=3)
        right_layout.addWidget(bottom_row, stretch=2)
        
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setStyleSheet("background: transparent;")
        
        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget, stretch=1)
        central_widget.setLayout(main_layout)
        
        # Connect aircraft table signals
        self.aircraft_table.aircraft_clicked.connect(self._on_aircraft_clicked)
        self.aircraft_table.star_toggled.connect(self._on_star_toggled)
        self.starred_table.aircraft_clicked.connect(self._on_aircraft_clicked)
        self.starred_table.star_toggled.connect(self._on_star_toggled)
        
        # Menu bar
        self._build_menu_bar()

        # Status bar for non-blocking errors
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
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
        for col in range(self.aircraft_table.columnCount()):
            if col == COL_STAR:
                continue
            header_item = self.aircraft_table.horizontalHeaderItem(col)
            name = header_item.text() if header_item else f"Column {col}"
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
        setup_data_act = QAction("Setup data (FAA download)...", self)
        setup_data_act.triggered.connect(self.open_setup_data)
        settings_menu.addAction(setup_data_act)
        settings_menu.addSeparator()
        self.dark_mode_act = QAction("Dark mode", self)
        self.dark_mode_act.setCheckable(True)
        self.dark_mode_act.setChecked(get_current_theme() == 'dark')
        self.dark_mode_act.triggered.connect(self._toggle_dark_mode)
        settings_menu.addAction(self.dark_mode_act)
        
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
        last_col = self.aircraft_table.columnCount() - 1
        if last_col >= 0:
            header.setSectionResizeMode(last_col, QHeaderView.ResizeMode.Stretch)
    
    def _reset_layout(self):
        """Restore default sidebar width hint."""
        self.status_bar.showMessage("Layout spacing is fixed — resize the window to adjust panels")
    
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
                self.aircraft_db_by_icao = {
                    ac.get('mode_s_hex', '').strip().upper(): ac
                    for ac in self.aircraft_db
                    if ac.get('mode_s_hex')
                }
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
                self.aircraft_db_by_icao = {}
                QMessageBox.warning(
                    self,
                    "Database Not Found",
                    f"Aircraft database not found at {db_path}.\n"
                    f"Please run the database creation script first."
                )
        except Exception as e:
            self.aircraft_db = []
            self.aircraft_db_by_icao = {}
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
            self.monitoring_info.set_fetching(True)
            self.monitoring_info.set_status('running')
            self._set_config_widgets_enabled(False)
            self.status_bar.showMessage("Monitoring started…")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start monitoring: {e}")
    
    def stop_monitoring(self):
        """Stop monitoring cooperatively."""
        if self.worker:
            self.worker.stop_monitoring()
            if not self.worker.wait(10000):
                logger_msg = "Worker did not stop cleanly within 10 seconds"
                self.status_bar.showMessage(logger_msg)
            self.worker = None
        
        self.controls.set_running(False)
        self.monitoring_info.update_poll_count(0)
        self.monitoring_info.set_fetching(False)
        self.monitoring_info.set_status('stopped')
        self._set_config_widgets_enabled(True)
        self.status_bar.showMessage("Monitoring stopped")
    
    def pause_monitoring(self):
        """Pause monitoring."""
        if self.worker:
            self.worker.pause_monitoring()
            self.controls.set_paused(True)
            self.monitoring_info.set_status('paused')
    
    def resume_monitoring(self):
        """Resume monitoring."""
        if self.worker:
            self.worker.resume_monitoring()
            self.controls.set_paused(False)
            self.monitoring_info.set_status('running')
    
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
            self._last_active_states = dict(aircraft_states)
            active_icao24s = set(aircraft_states.keys())
            self.aircraft_table.update_aircraft(
                aircraft_states, aircraft_db, set(self.active_anomalies.keys())
            )
            self._refresh_starred_table(active_icao24s)
            
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
            db_info = self.aircraft_db_by_icao.get(icao24.upper())
            
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
        self.session_anomaly_count += 1
        self.monitoring_info.update_anomaly_count(self.session_anomaly_count)
        # Refresh table so this aircraft row gets anomaly highlight immediately (no wait for next poll)
        if self.aircraft_table.aircraft_states and self.aircraft_db:
            self.aircraft_table.update_aircraft(
                self.aircraft_table.aircraft_states,
                self.aircraft_db,
                set(self.active_anomalies.keys()),
            )
            self._refresh_starred_table(set(self._last_active_states.keys()))
        # Anomalies are displayed in the anomaly list - no popup needed
    
    def _on_summary_updated(self, poll_count: int, active_aircraft: int, anomalies: int):
        """Handle summary update signal."""
        self.monitoring_info.update_active_flights(active_aircraft)
        self.monitoring_info.update_poll_count(poll_count)
        if poll_count > 0:
            self.monitoring_info.set_fetching(False)
        self.status_bar.showMessage(
            f"Poll #{poll_count}: {active_aircraft} active aircraft, {anomalies} new anomalies"
        )
    
    def _on_error(self, error_msg: str):
        """Handle error signal with non-blocking status bar."""
        self._last_error_msg = error_msg
        from datetime import datetime
        ts = datetime.now().strftime('%H:%M:%S')
        self.status_bar.showMessage(f"Error at {ts}: {error_msg}")
        fatal_keywords = ('authentication', 'auth', '401', 'not found', 'FileNotFoundError')
        if any(k.lower() in error_msg.lower() for k in fatal_keywords):
            QMessageBox.critical(self, "Monitoring Error", error_msg)
    
    def _on_status_changed(self, status: str):
        """Handle status change signal."""
        self.monitoring_info.set_status(status)
        if status == 'running':
            self.controls.set_running(True)
            self.controls.set_paused(False)
        elif status == 'paused':
            self.controls.set_paused(True)
        else:
            self.controls.set_running(False)
            self._set_config_widgets_enabled(True)
    
    def _on_anomaly_navigate(self, icao24: str):
        """Handle anomaly click - navigate to aircraft in table."""
        if not self.aircraft_table.select_aircraft_by_icao24(icao24):
            self.starred_table.select_aircraft_by_icao24(icao24)
    
    def _invalidate_map_size(self):
        """Tell Leaflet to recalculate dimensions after a layout change."""
        if self._map_loaded:
            self._map_view.page().runJavaScript("invalidateMapSize();")

    def _ensure_map_fullscreen_dialog(self):
        if self._map_fullscreen_dialog is not None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Selected flight — Map")
        dialog.setModal(False)
        dialog.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setStyleSheet(
            f"background-color: {COLORS['bg_panel']}; border-bottom: 1px solid {COLORS['border']};"
        )
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(SPACING['lg'], SPACING['sm'], SPACING['lg'], SPACING['sm'])
        bar_label = QLabel("Selected flight")
        bar_label.setStyleSheet(
            f"font-weight: 600; color: {COLORS['text_primary']}; background: transparent;"
        )
        bar.addWidget(bar_label)
        bar.addStretch()
        exit_btn = QPushButton("Exit fullscreen")
        exit_btn.setStyleSheet(get_compact_button_style('primary'))
        exit_btn.clicked.connect(lambda: self._set_map_fullscreen(False))
        bar.addWidget(exit_btn)
        layout.addWidget(toolbar)

        host = QWidget()
        self._map_fullscreen_layout = QVBoxLayout(host)
        self._map_fullscreen_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(host, 1)

        dialog.rejected.connect(lambda: self._set_map_fullscreen(False))
        QShortcut(QKeySequence("Escape"), dialog, lambda: self._set_map_fullscreen(False))
        self._map_fullscreen_dialog = dialog

    def _toggle_map_fullscreen(self, checked: bool):
        self._set_map_fullscreen(checked)

    def _set_map_fullscreen(self, enabled: bool):
        if enabled == self._map_fullscreen_active:
            if not enabled and hasattr(self, '_map_fullscreen_btn'):
                self._map_fullscreen_btn.blockSignals(True)
                self._map_fullscreen_btn.setChecked(False)
                self._map_fullscreen_btn.blockSignals(False)
            return

        self._ensure_map_fullscreen_dialog()

        if enabled:
            self._map_embed_layout.removeWidget(self._map_view)
            self._map_fullscreen_layout.addWidget(self._map_view, 1)
            self._map_fullscreen_dialog.showFullScreen()
            self._map_fullscreen_active = True
            self._map_fullscreen_btn.setText("Exit fullscreen")
        else:
            if self._map_fullscreen_active:
                self._map_fullscreen_layout.removeWidget(self._map_view)
                self._map_embed_layout.addWidget(self._map_view, 1)
                self._map_fullscreen_dialog.hide()
            self._map_fullscreen_active = False
            self._map_fullscreen_btn.blockSignals(True)
            self._map_fullscreen_btn.setChecked(False)
            self._map_fullscreen_btn.setText("Fullscreen")
            self._map_fullscreen_btn.blockSignals(False)

        QTimer.singleShot(200, self._invalidate_map_size)

    def _on_map_loaded(self, ok: bool):
        """Mark map as ready so runJavaScript can be used."""
        self._map_loaded = ok
        if ok:
            self._map_error_label.hide()
            self._sync_starred_map_markers()
        else:
            self._map_error_label.setGeometry(self._map_view.rect())
            self._map_error_label.show()
            self._map_error_label.raise_()
    
    def _update_map_position(self, lat: float, lon: float, label: str = ""):
        """Update embedded map to show position (call only when map is loaded)."""
        if not self._map_loaded:
            return
        label_js = json.dumps(str(label))
        js = f"updatePosition({lat}, {lon}, {label_js})"
        self._map_view.page().runJavaScript(js)
    
    def _on_aircraft_clicked(self, icao24: str):
        """Handle aircraft row click - show detail dialog and update map."""
        aircraft_state = self.aircraft_table.get_aircraft_state(icao24)
        if not aircraft_state:
            aircraft_state = self.starred_table.get_aircraft_state(icao24)
        if not aircraft_state:
            entry = self.starred_store.entries.get(icao24.upper())
            if entry:
                aircraft_state = entry.get("last_state")
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
        if not aircraft_info:
            aircraft_info = self.starred_table.get_aircraft_info(icao24)
        if not aircraft_info:
            entry = self.starred_store.entries.get(icao24.upper())
            if entry:
                aircraft_info = entry.get("aircraft_info")
        
        # Also try to get from aircraft_db if not in table data
        if not aircraft_info:
            aircraft_info = self.aircraft_db_by_icao.get(icao24.upper())
        
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

    def _setup_shortcuts(self):
        """Register keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+R"), self, self._shortcut_start)
        QShortcut(QKeySequence("Ctrl+P"), self, self._shortcut_pause)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self.stop_monitoring)
        QShortcut(QKeySequence("Ctrl+E"), self, lambda: self._export_aircraft("csv"))
        QShortcut(QKeySequence("Escape"), self, self._close_detail_dialog)

    def _shortcut_start(self):
        if not (self.worker and self.worker.isRunning()):
            self.start_monitoring()
        elif self.controls.is_paused:
            self.resume_monitoring()

    def _shortcut_pause(self):
        if self.worker and self.worker.isRunning():
            if self.controls.is_paused:
                self.resume_monitoring()
            else:
                self.pause_monitoring()

    def _close_detail_dialog(self):
        if self._detail_dialog and self._detail_dialog.isVisible():
            self._detail_dialog.close()

    def _setup_accessibility(self):
        self.db_combo.setAccessibleName("Database type")
        self.region_combo.setAccessibleName("Monitoring region")
        self.state_input.setAccessibleName("Monitoring states")
        self.anomaly_list.setAccessibleDescription("List of detected flight anomalies")

    def _set_config_widgets_enabled(self, enabled: bool):
        self.db_combo.setEnabled(enabled)
        self.region_combo.setEnabled(enabled and self.region_radio.isChecked())
        self.state_input.setEnabled(enabled and self.state_radio.isChecked())
        self.region_radio.setEnabled(enabled)
        self.state_radio.setEnabled(enabled)
        self.all_radio.setEnabled(enabled)
        tip = "" if enabled else "Stop monitoring to change database or area settings"
        for w in (self.db_combo, self.region_combo, self.state_input):
            w.setToolTip(tip)

    def _clear_anomalies(self):
        self.anomaly_list.clear_session()
        self.active_anomalies.clear()
        self.session_anomaly_count = 0
        self.monitoring_info.update_anomaly_count(0)
        if self.aircraft_table.aircraft_states and self.aircraft_db:
            self.aircraft_table.update_aircraft(
                self.aircraft_table.aircraft_states,
                self.aircraft_db,
                set(),
            )
        self._refresh_starred_table(set(self._last_active_states.keys()))

    def _toggle_dark_mode(self, checked: bool):
        set_theme('dark' if checked else 'light')
        from PyQt6.QtWidgets import QApplication
        from gui.theme import get_global_stylesheet
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_global_stylesheet())
        self._refresh_theme_styles()
        settings = QSettings("MediTrack", "MediTrack")
        settings.setValue("appearance/theme", 'dark' if checked else 'light')
        self.status_bar.showMessage(f"{'Dark' if checked else 'Light'} theme applied")

    def _refresh_theme_styles(self):
        """Re-apply component styles after theme toggle."""
        self.centralWidget().setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.controls.refresh_theme()
        self.monitoring_info.refresh_theme()
        self.clear_anomalies_btn.setStyleSheet(get_compact_button_style('primary'))
        if hasattr(self, '_map_fullscreen_btn'):
            self._map_fullscreen_btn.setStyleSheet(get_compact_button_style('primary'))
        self.aircraft_table.setStyleSheet(get_table_stylesheet())
        self.starred_table.setStyleSheet(get_table_stylesheet())
        self.anomaly_list.refresh_theme()
        for panel in getattr(self, '_theme_panels', []):
            apply_card_style(panel)
        self._map_error_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 13px; "
            f"background: {COLORS['bg_card']}; border-radius: {RADIUS['md']}px;"
        )
        self._map_view.setStyleSheet(
            f"border: 1px solid {COLORS['border']}; border-radius: {RADIUS['md']}px;"
        )
        if self._map_loaded:
            if self._map_fullscreen_active:
                self._set_map_fullscreen(False)
            map_html = _build_map_html(COLORS['map_hint_bg'], COLORS['map_hint_text'])
            self._map_view.setHtml(map_html, QUrl("https://unpkg.com/"))
            self._map_loaded = False
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self._map_fullscreen_active:
            self._set_map_fullscreen(False)
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
