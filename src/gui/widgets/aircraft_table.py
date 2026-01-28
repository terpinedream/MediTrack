"""
Aircraft data table widget.
"""

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QClipboard
from typing import Dict, Optional
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
    
    def __init__(self, parent=None):
        """Initialize aircraft table."""
        super().__init__(parent)
        self.init_ui()
        self.aircraft_data = {}  # Store full aircraft data for links
        self.location_cache = {}  # Cache location lookups: (lat, lon) -> location_name
        self.pending_updates = {}  # Queue for batched updates
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._process_pending_updates)
        self.active_lookup_workers = []  # Track active workers
    
    def init_ui(self):
        """Initialize UI components."""
        # Set columns
        columns = ['ICAO24', 'Callsign', 'N-Number', 'Model', 'Speed (kts)', 'Altitude (ft)', 'Location']
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        
        # Configure table
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        
        # Resize columns to content
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # ICAO24
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Model
        
        # Style
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #ddd;
                background-color: white;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #2196f3;
                color: white;
            }
        """)
    
    def update_aircraft(self, aircraft_states: Dict, aircraft_db: list):
        """Update table with new aircraft data (batched to prevent freezing)."""
        # Disable sorting during update for performance
        was_sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)
        
        try:
            # Get current aircraft ICAO24s
            current_icao24s = set(aircraft_states.keys())
            existing_icao24s = set()
            
            # Find existing rows
            for row in range(self.rowCount()):
                item = self.item(row, 0)
                if item:
                    existing_icao24s.add(item.text())
            
            # Remove aircraft that are no longer active
            rows_to_remove = []
            for row in range(self.rowCount() - 1, -1, -1):
                item = self.item(row, 0)
                if item and item.text() not in current_icao24s:
                    rows_to_remove.append(row)
            
            for row in rows_to_remove:
                self.removeRow(row)
            
            # Update or add aircraft
            for icao24, state in aircraft_states.items():
                # Find existing row
                existing_row = None
                for row in range(self.rowCount()):
                    item = self.item(row, 0)
                    if item and item.text() == icao24:
                        existing_row = row
                        break
                
                # Find aircraft in database
                aircraft_info = next(
                    (ac for ac in aircraft_db
                     if ac.get('mode_s_hex', '').strip().upper() == icao24.upper()),
                    None
                )
                
                if existing_row is not None:
                    # Update existing row
                    row = existing_row
                else:
                    # Add new row
                    row = self.rowCount()
                    self.insertRow(row)
                
                # ICAO24
                if existing_row is None:
                    self.setItem(row, 0, QTableWidgetItem(icao24))
                else:
                    self.item(row, 0).setText(icao24)
                
                # Callsign
                callsign = state.get('callsign', 'N/A')
                callsign_text = callsign if callsign else 'N/A'
                if existing_row is None:
                    self.setItem(row, 1, QTableWidgetItem(callsign_text))
                else:
                    self.item(row, 1).setText(callsign_text)
                
                # N-Number
                n_number = aircraft_info.get('n_number', 'N/A') if aircraft_info else 'N/A'
                if existing_row is None:
                    self.setItem(row, 2, QTableWidgetItem(n_number))
                else:
                    self.item(row, 2).setText(n_number)
                
                # Model
                if aircraft_info:
                    model = f"{aircraft_info.get('model_name', 'N/A')} ({aircraft_info.get('manufacturer', 'N/A')})"
                else:
                    model = 'N/A'
                if existing_row is None:
                    self.setItem(row, 3, QTableWidgetItem(model))
                else:
                    self.item(row, 3).setText(model)
                
                # Speed
                velocity = state.get('velocity')
                speed_text = f"{velocity:.0f}" if velocity is not None else "N/A"
                if existing_row is None:
                    self.setItem(row, 4, QTableWidgetItem(speed_text))
                else:
                    self.item(row, 4).setText(speed_text)
                
                # Altitude
                altitude = state.get('baro_altitude') or state.get('geo_altitude')
                alt_text = f"{altitude:.0f}" if altitude is not None else "N/A"
                if existing_row is None:
                    self.setItem(row, 5, QTableWidgetItem(alt_text))
                else:
                    self.item(row, 5).setText(alt_text)
                
                # Location - use cached or show coordinates (lookups done async to prevent freezing)
                lat = state.get('latitude')
                lon = state.get('longitude')
                location_item = None
                if existing_row is None:
                    location_item = QTableWidgetItem()
                    self.setItem(row, 6, location_item)
                else:
                    location_item = self.item(row, 6)
                
                if lat is not None and lon is not None:
                    # Round coordinates for cache key (0.01 degree ~= 1km)
                    lat_key = round(lat, 2)
                    lon_key = round(lon, 2)
                    cache_key = (lat_key, lon_key)
                    
                    # Store coordinates
                    coords_str = f"{lat:.6f}, {lon:.6f}"
                    location_item.setData(Qt.ItemDataRole.UserRole, coords_str)
                    location_item.setToolTip(f"Click to copy coordinates: {coords_str}")
                    
                    if cache_key in self.location_cache:
                        # Use cached location name
                        location_text = self.location_cache[cache_key]
                        location_item.setText(location_text)
                        location_item.setForeground(Qt.GlobalColor.blue)
                    else:
                        # Show coordinates initially, lookup location name asynchronously
                        location_text = f"{lat:.4f}, {lon:.4f}"
                        location_item.setText(location_text)
                        location_item.setForeground(Qt.GlobalColor.black)
                        
                        # Schedule async lookup in background thread (don't block UI)
                        # Use a queue to limit concurrent lookups
                        if not hasattr(self, '_location_lookup_queue'):
                            self._location_lookup_queue = []
                            self._location_lookup_timer = QTimer()
                            self._location_lookup_timer.setSingleShot(True)
                            self._location_lookup_timer.timeout.connect(self._process_location_lookup)
                        
                        # Only queue if not already queued and not in cache
                        if cache_key not in [q[0] for q in self._location_lookup_queue]:
                            self._location_lookup_queue.append((cache_key, lat, lon, location_item))
                            if not self._location_lookup_timer.isActive():
                                self._location_lookup_timer.start(500)  # Start lookup after 500ms
                else:
                    location_item.setText("N/A")
                    location_item.setData(Qt.ItemDataRole.UserRole, None)
                    location_item.setForeground(Qt.GlobalColor.black)
                
                # Store aircraft data for potential link access
                if aircraft_info:
                    self.aircraft_data[icao24] = {
                        'n_number': n_number,
                        'flightaware_url': None,
                        'broadcastify_url': None
                    }
                    
                    # Build FlightAware URL
                    if n_number and n_number != 'N/A':
                        n_clean = n_number.upper().strip()
                        if not n_clean.startswith('N'):
                            n_clean = 'N' + n_clean
                        self.aircraft_data[icao24]['flightaware_url'] = f"https://www.flightaware.com/live/flight/{n_clean}"
        
        finally:
            # Re-enable sorting
            self.setSortingEnabled(was_sorting)
            if was_sorting:
                self.sortItems(0, Qt.SortOrder.AscendingOrder)
    
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
    
    def mousePressEvent(self, event):
        """Handle mouse clicks on location cells to copy coordinates."""
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item and item.column() == 6:  # Location column
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
