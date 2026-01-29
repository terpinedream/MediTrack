"""
Aircraft data table widget.
"""

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QStyledItemDelegate
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QClipboard, QBrush, QColor, QPainter
from typing import Dict, Optional, Set
import webbrowser
import sys
from pathlib import Path

# Add project paths for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from location_utils import get_location_name_from_coordinates
from gui.theme import COLORS, SPACING


class AircraftTableDelegate(QStyledItemDelegate):
    """Delegate that paints item BackgroundRole so anomaly row color is visible."""

    def paint(self, painter: QPainter, option, index):
        background = index.data(Qt.ItemDataRole.BackgroundRole)
        if background:
            if isinstance(background, QBrush):
                painter.fillRect(option.rect, background)
            elif isinstance(background, QColor):
                painter.fillRect(option.rect, background)
        super().paint(painter, option, index)


class LocationLookupWorker(QThread):
    """Worker thread for location lookups to prevent UI blocking."""
    
    location_found = pyqtSignal(tuple, str, object)  # cache_key, location_text, location_item
    
    def __init__(self, cache_key, lat, lon, location_item):
        super().__init__()
        self.cache_key = cache_key
        self.lat = lat
        self.lon = lon
        self.location_item = location_item
    
    def run(self):
        """Perform location lookup in background thread."""
        try:
            location_info = get_location_name_from_coordinates(self.lat, self.lon, skip_rate_limit=False)
            if location_info and location_info.get('display'):
                location_text = location_info['display']
                self.location_found.emit(self.cache_key, location_text, self.location_item)
        except Exception:
            pass


class AircraftTable(QTableWidget):
    """Table widget displaying active aircraft."""
    
    # Signal emitted when aircraft row is clicked
    aircraft_clicked = pyqtSignal(str)  # Emits ICAO24
    
    def __init__(self, parent=None, model_lookup=None):
        """
        Initialize aircraft table.
        
        Args:
            parent: Parent widget
            model_lookup: Optional ModelLookup instance for looking up model names
        """
        super().__init__(parent)
        self.model_lookup = model_lookup
        self.init_ui()
        self.aircraft_data = {}  # Store full aircraft data for links
        self.aircraft_states = {}  # Store current aircraft states
        self.location_cache = {}  # Cache location lookups: (lat, lon) -> location_name
        self.pending_updates = {}  # Queue for batched updates
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._process_pending_updates)
        self.active_lookup_workers = []  # Track active workers
    
    def init_ui(self):
        """Initialize UI components."""
        # Set columns: Model, ICAO24, Callsign, N-Number, Status, Speed, Altitude, Location
        columns = ['Model', 'ICAO24', 'Callsign', 'N-Number', 'Status', 'Speed (kts)', 'Altitude (ft)', 'Location']
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        
        # Configure table
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        
        # Connect item click signal
        self.itemClicked.connect(self._on_item_clicked)
        
        # Delegate so anomaly row BackgroundRole is painted (not overridden by alternating rows)
        self.setItemDelegate(AircraftTableDelegate(self))
        
        # Resize columns to content
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Model
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # ICAO24
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)  # Location
        
        # Style
        self.setStyleSheet(f"""
            QTableWidget {{
                gridline-color: {COLORS['border']};
                background-color: {COLORS['bg_main']};
            }}
            QTableWidget::item {{
                padding: {SPACING['xs']}px;
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS['selection']};
                color: {COLORS['text_inverse']};
            }}
        """)
    
    def update_aircraft(self, aircraft_states: Dict, aircraft_db: list, anomaly_icao24s: Optional[Set[str]] = None):
        """Update table with new aircraft data (batched to prevent freezing)."""
        # Store current states for popup access
        self.aircraft_states = aircraft_states.copy()
        
        # Disable sorting during update for performance
        was_sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)
        
        try:
            # Get current aircraft ICAO24s
            current_icao24s = set(aircraft_states.keys())
            
            # Remove aircraft that are no longer active (ICAO24 is column 1)
            rows_to_remove = []
            for row in range(self.rowCount() - 1, -1, -1):
                item = self.item(row, 1)
                if item and item.text() not in current_icao24s:
                    rows_to_remove.append(row)
            
            for row in rows_to_remove:
                self.removeRow(row)
            
            # Anomaly row background
            anomaly_brush = None
            if anomaly_icao24s:
                hex_bg = COLORS.get('anomaly_row_bg', COLORS['selection_bg'])
                hex_bg = hex_bg.lstrip('#')
                if len(hex_bg) == 6:
                    r, g, b = int(hex_bg[0:2], 16), int(hex_bg[2:4], 16), int(hex_bg[4:6], 16)
                    anomaly_brush = QBrush(QColor(r, g, b, 255))
            
            # Update or add aircraft
            for icao24, state in aircraft_states.items():
                # Find existing row (ICAO24 is column 1)
                existing_row = None
                for r in range(self.rowCount()):
                    item = self.item(r, 1)
                    if item and item.text() == icao24:
                        existing_row = r
                        break
                
                # Find aircraft in database
                aircraft_info = next(
                    (ac for ac in aircraft_db
                     if ac.get('mode_s_hex', '').strip().upper() == icao24.upper()),
                    None
                )
                
                if existing_row is not None:
                    row = existing_row
                else:
                    row = self.rowCount()
                    self.insertRow(row)
                
                model_name_looked_up = ''
                manufacturer_looked_up = ''
                
                # Model (column 0)
                if aircraft_info:
                    model_name = aircraft_info.get('model_name', '')
                    manufacturer = aircraft_info.get('manufacturer', '')
                    model_code = aircraft_info.get('model_code', '')
                    
                    if model_name and model_name.upper().strip() in ['UNKNOWN', 'N/A', '']:
                        model_name = ''
                    if manufacturer and manufacturer.upper().strip() in ['UNKNOWN', 'N/A', '']:
                        manufacturer = ''
                    
                    if not model_name or model_name.strip() == '':
                        if model_code and self.model_lookup:
                            model_info = self.model_lookup.lookup(model_code)
                            if model_info:
                                model_name = model_info.get('model', '')
                                manufacturer_looked_up = model_info.get('manufacturer', '')
                                if not manufacturer:
                                    manufacturer = manufacturer_looked_up
                                model_name_looked_up = model_name
                    
                    if model_name and model_name.strip():
                        model = f"{model_name} ({manufacturer})" if (manufacturer and manufacturer.strip()) else model_name
                    elif manufacturer and manufacturer.strip():
                        model = manufacturer
                    else:
                        model = 'N/A'
                else:
                    model = 'N/A'
                if existing_row is None:
                    self.setItem(row, 0, QTableWidgetItem(model))
                else:
                    self.item(row, 0).setText(model)
                
                # ICAO24 (column 1)
                if existing_row is None:
                    self.setItem(row, 1, QTableWidgetItem(icao24))
                else:
                    self.item(row, 1).setText(icao24)
                
                # Callsign (column 2)
                callsign = state.get('callsign', 'N/A')
                callsign_text = callsign if callsign else 'N/A'
                if existing_row is None:
                    self.setItem(row, 2, QTableWidgetItem(callsign_text))
                else:
                    self.item(row, 2).setText(callsign_text)
                
                # N-Number (column 3)
                n_number = aircraft_info.get('n_number', 'N/A') if aircraft_info else 'N/A'
                if existing_row is None:
                    self.setItem(row, 3, QTableWidgetItem(n_number))
                else:
                    self.item(row, 3).setText(n_number)
                
                # Status (column 4) - in air / on ground
                on_ground = state.get('on_ground')
                if on_ground is True:
                    status_text = 'On ground'
                elif on_ground is False:
                    status_text = 'In air'
                else:
                    status_text = 'N/A'
                if existing_row is None:
                    self.setItem(row, 4, QTableWidgetItem(status_text))
                else:
                    self.item(row, 4).setText(status_text)
                
                # Speed (column 5)
                velocity = state.get('velocity')
                speed_text = f"{velocity:.0f}" if velocity is not None else "N/A"
                if existing_row is None:
                    self.setItem(row, 5, QTableWidgetItem(speed_text))
                else:
                    self.item(row, 5).setText(speed_text)
                
                # Altitude (column 6)
                altitude = state.get('baro_altitude') or state.get('geo_altitude')
                alt_text = f"{altitude:.0f}" if altitude is not None else "N/A"
                if existing_row is None:
                    self.setItem(row, 6, QTableWidgetItem(alt_text))
                else:
                    self.item(row, 6).setText(alt_text)
                
                # Location (column 7)
                lat = state.get('latitude')
                lon = state.get('longitude')
                if existing_row is None:
                    location_item = QTableWidgetItem()
                    self.setItem(row, 7, location_item)
                else:
                    location_item = self.item(row, 7)
                
                if lat is not None and lon is not None:
                    lat_key = round(lat, 2)
                    lon_key = round(lon, 2)
                    cache_key = (lat_key, lon_key)
                    coords_str = f"{lat:.6f}, {lon:.6f}"
                    location_item.setData(Qt.ItemDataRole.UserRole, coords_str)
                    location_item.setToolTip(f"Click to copy coordinates: {coords_str}")
                    
                    if cache_key in self.location_cache:
                        location_item.setText(self.location_cache[cache_key])
                        location_item.setForeground(Qt.GlobalColor.blue)
                    else:
                        location_item.setText(f"{lat:.4f}, {lon:.4f}")
                        location_item.setForeground(Qt.GlobalColor.black)
                        if not hasattr(self, '_location_lookup_queue'):
                            self._location_lookup_queue = []
                            self._location_lookup_timer = QTimer()
                            self._location_lookup_timer.setSingleShot(True)
                            self._location_lookup_timer.timeout.connect(self._process_location_lookup)
                        if cache_key not in [q[0] for q in self._location_lookup_queue]:
                            self._location_lookup_queue.append((cache_key, lat, lon, location_item))
                            if not self._location_lookup_timer.isActive():
                                self._location_lookup_timer.start(500)
                else:
                    location_item.setText("N/A")
                    location_item.setData(Qt.ItemDataRole.UserRole, None)
                    location_item.setForeground(Qt.GlobalColor.black)
                
                # Store aircraft data for link access
                if aircraft_info:
                    model_display = model
                    model_name_stored = model_display
                    manufacturer_stored = ''
                    if ' (' in model_display and model_display.endswith(')'):
                        parts = model_display.rsplit(' (', 1)
                        model_name_stored = parts[0]
                        manufacturer_stored = parts[1].rstrip(')')
                    elif model_display != 'N/A':
                        model_name_stored = model_display
                    final_model_name = model_name_stored if model_name_stored != 'N/A' else (model_name_looked_up or aircraft_info.get('model_name', 'N/A'))
                    final_manufacturer = manufacturer_stored or manufacturer_looked_up or aircraft_info.get('manufacturer', 'N/A')
                    self.aircraft_data[icao24] = {
                        'n_number': n_number,
                        'model_name': final_model_name,
                        'manufacturer': final_manufacturer,
                        'owner_name': aircraft_info.get('owner_name', 'N/A'),
                        'owner_city': aircraft_info.get('owner_city', 'N/A'),
                        'owner_state': aircraft_info.get('owner_state', 'N/A'),
                        'type_aircraft': aircraft_info.get('type_aircraft', ''),
                        'type_engine': aircraft_info.get('type_engine', ''),
                        'model_code': aircraft_info.get('model_code', ''),
                        'flightaware_url': None,
                        'broadcastify_url': None
                    }
                    if n_number and n_number != 'N/A':
                        n_clean = n_number.upper().strip()
                        if not n_clean.startswith('N'):
                            n_clean = 'N' + n_clean
                        self.aircraft_data[icao24]['flightaware_url'] = f"https://www.flightaware.com/live/flight/{n_clean}"
                
                # Store state and aircraft_info on ICAO24 cell (column 1)
                icao_item = self.item(row, 1)
                if icao_item:
                    icao_item.setData(Qt.ItemDataRole.UserRole + 1, state)
                    if aircraft_info:
                        icao_item.setData(Qt.ItemDataRole.UserRole + 2, aircraft_info)
                
                # Anomaly row background
                if anomaly_brush and icao24 in anomaly_icao24s:
                    for col in range(8):
                        cell = self.item(row, col)
                        if cell:
                            cell.setData(Qt.ItemDataRole.BackgroundRole, anomaly_brush)
                        else:
                            c = QTableWidgetItem('')
                            c.setData(Qt.ItemDataRole.BackgroundRole, anomaly_brush)
                            self.setItem(row, col, c)
            
            # Clear background for rows without an anomaly
            if anomaly_icao24s is not None:
                for row in range(self.rowCount()):
                    icao_item = self.item(row, 1)
                    if icao_item and icao_item.text() not in anomaly_icao24s:
                        for col in range(8):
                            cell = self.item(row, col)
                            if cell:
                                cell.setData(Qt.ItemDataRole.BackgroundRole, None)
        
        finally:
            self.setSortingEnabled(was_sorting)
            if was_sorting:
                self.sortItems(1, Qt.SortOrder.AscendingOrder)
    
    def _process_location_lookup(self):
        """Process one location lookup from queue using background thread."""
        if not hasattr(self, '_location_lookup_queue') or not self._location_lookup_queue:
            return
        
        # Limit concurrent workers to prevent too many threads
        if len(self.active_lookup_workers) >= 2:
            # Too many active, reschedule
            self._location_lookup_timer.start(500)
            return
        
        cache_key, lat, lon, location_item = self._location_lookup_queue.pop(0)
        
        # Create worker thread for lookup
        worker = LocationLookupWorker(cache_key, lat, lon, location_item)
        worker.location_found.connect(self._on_location_found)
        worker.finished.connect(lambda: self.active_lookup_workers.remove(worker) if worker in self.active_lookup_workers else None)
        self.active_lookup_workers.append(worker)
        worker.start()
        
        # Process next item in queue after delay (rate limiting)
        if self._location_lookup_queue:
            self._location_lookup_timer.start(1000)  # Wait 1 second between starting lookups
    
    def _on_location_found(self, cache_key, location_text, location_item):
        """Handle location lookup result."""
        self.location_cache[cache_key] = location_text
        # Update the item if it still exists and is valid
        if location_item:
            try:
                location_item.setText(location_text)
                location_item.setForeground(Qt.GlobalColor.blue)
            except RuntimeError:
                # Item may have been deleted, ignore
                pass
    
    def _process_pending_updates(self):
        """Process pending location updates (for async lookups)."""
        # This can be used for async location lookups in the future
        pass
    
    def _on_item_clicked(self, item: QTableWidgetItem):
        """Handle item click - emit ICAO24 signal for detail dialog."""
        row = item.row()
        icao24_item = self.item(row, 1)  # ICAO24 is column 1
        if icao24_item:
            icao24 = icao24_item.text()
            if icao24:
                self.aircraft_clicked.emit(icao24)
    
    def select_aircraft_by_icao24(self, icao24: str) -> bool:
        """Select and scroll to aircraft with given ICAO24."""
        for row in range(self.rowCount()):
            item = self.item(row, 1)  # ICAO24 is column 1
            if item and item.text() == icao24:
                self.selectRow(row)
                self.scrollToItem(item)
                return True
        return False
    
    def get_aircraft_state(self, icao24: str) -> Optional[Dict]:
        """Get current aircraft state for given ICAO24."""
        return self.aircraft_states.get(icao24)
    
    def get_aircraft_info(self, icao24: str) -> Optional[Dict]:
        """Get aircraft database info for given ICAO24."""
        return self.aircraft_data.get(icao24)
    
    def mousePressEvent(self, event):
        """Handle mouse clicks on location cells to copy coordinates."""
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item and item.column() == 7:  # Location column
                coords = item.data(Qt.ItemDataRole.UserRole)
                if coords:
                    # Copy to clipboard
                    from PyQt6.QtWidgets import QApplication
                    QApplication.clipboard().setText(coords)
                    
                    # Visual feedback - briefly change text color
                    original_color = item.foreground()
                    item.setForeground(Qt.GlobalColor.green)
                    
                    # Reset color after 500ms
                    QTimer.singleShot(500, lambda: item.setForeground(original_color))
        super().mousePressEvent(event)
