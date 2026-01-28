"""
Worker thread for running MonitorService in background.
"""

from PyQt6.QtCore import QThread, pyqtSignal
from typing import Dict, List
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from monitor_service import MonitorService


class MonitorWorker(QThread):
    """Worker thread that runs MonitorService in background."""
    
    # Signals for communication with main thread
    aircraft_updated = pyqtSignal(dict)  # Emits current_states dict
    anomaly_detected = pyqtSignal(dict)  # Emits anomaly dict
    summary_updated = pyqtSignal(int, int, int)  # poll_count, active_aircraft, anomalies
    error_occurred = pyqtSignal(str)  # Error message
    status_changed = pyqtSignal(str)  # Status: 'running', 'paused', 'stopped'
    
    def __init__(self, 
                 region: str = None,
                 states: List[str] = None,
                 interval_seconds: int = 60,
                 credentials_file: Path = None,
                 database_type: str = 'ems'):
        """
        Initialize worker.
        
        Args:
            region: Region to monitor
            states: List of state codes to monitor
            interval_seconds: Polling interval
            credentials_file: Path to credentials file
            database_type: 'ems' or 'police'
        """
        super().__init__()
        self.region = region
        self.states = states
        self.interval_seconds = interval_seconds
        self.credentials_file = credentials_file
        self.database_type = database_type
        self.monitor_service = None
        self._should_pause = False
    
    def run(self):
        """Run the monitoring service in this thread."""
        try:
            # Disable console output for GUI mode
            # Convert None/None to empty list for "All US" case
            states_param = self.states if self.states is not None else []
            if self.region is None and self.states is None:
                states_param = []  # Empty list means "all US"
            
            self.monitor_service = MonitorService(
                region=self.region,
                states=states_param,
                interval_seconds=self.interval_seconds,
                credentials_file=self.credentials_file,
                database_type=self.database_type,
                skip_interactive=True  # Skip interactive selection in GUI mode
            )
            self.monitor_service.notifier.console_output = False
            
            self.status_changed.emit('running')
            
            # Run monitoring loop with callbacks
            self._run_monitoring_loop()
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            self.status_changed.emit('stopped')
    
    def _run_monitoring_loop(self):
        """Run monitoring loop with signal emissions."""
        self.monitor_service.running = True
        self.monitor_service.paused = False
        
        try:
            while self.monitor_service.running:
                # Handle pause
                while self._should_pause and self.monitor_service.running:
                    self.monitor_service.paused = True
                    self.status_changed.emit('paused')
                    self.msleep(500)
                
                if not self.monitor_service.running:
                    break
                
                self.monitor_service.paused = False
                self.status_changed.emit('running')
                self.monitor_service.poll_count += 1
                
                try:
                    # Poll aircraft states
                    current_states = self.monitor_service.poll_aircraft_states()
                    self.monitor_service.current_states = current_states
                    
                    # Emit aircraft update
                    self.aircraft_updated.emit(current_states)
                    
                    # Get previous states for comparison
                    previous_states = self.monitor_service.state_tracker.get_all_latest_states()
                    
                    # Get state history
                    state_history = {}
                    for icao24 in current_states.keys():
                        history = self.monitor_service.state_tracker.get_aircraft_history(icao24, limit=20)
                        state_history[icao24] = history
                    
                    # Process state changes and detect anomalies
                    anomalies = self.monitor_service.process_state_changes(
                        current_states,
                        previous_states,
                        state_history
                    )
                    
                    # Store and emit anomalies
                    if anomalies:
                        self.monitor_service.recent_anomalies.extend(anomalies)
                        if len(self.monitor_service.recent_anomalies) > 100:
                            self.monitor_service.recent_anomalies = self.monitor_service.recent_anomalies[-100:]
                        
                        for anomaly in anomalies:
                            # Add aircraft info
                            icao24 = anomaly.get('icao24')
                            if icao24:
                                aircraft_info = next(
                                    (ac for ac in self.monitor_service.aircraft
                                     if ac.get('mode_s_hex', '').strip().upper() == icao24.upper()),
                                    None
                                )
                                if aircraft_info:
                                    n_number = aircraft_info.get('n_number', 'N/A')
                                    if n_number and n_number != 'N/A':
                                        n_number_clean = n_number.upper().strip()
                                        if not n_number_clean.startswith('N'):
                                            n_number_clean = 'N' + n_number_clean
                                        flightaware_url = f"https://www.flightaware.com/live/flight/{n_number_clean}"
                                    else:
                                        flightaware_url = None
                                    
                                    # Get Broadcastify URL
                                    broadcastify_url = None
                                    try:
                                        current_state = current_states.get(icao24)
                                        if current_state:
                                            latitude = current_state.get('latitude')
                                            longitude = current_state.get('longitude')
                                            if latitude is not None and longitude is not None:
                                                from location_utils import get_broadcastify_url_simple
                                                broadcastify_url = get_broadcastify_url_simple(latitude, longitude)
                                    except Exception:
                                        pass
                                    
                                    anomaly['aircraft_info'] = {
                                        'n_number': n_number,
                                        'model_name': aircraft_info.get('model_name', 'N/A'),
                                        'manufacturer': aircraft_info.get('manufacturer', 'N/A'),
                                        'owner_name': aircraft_info.get('owner_name', 'N/A'),
                                        'owner_city': aircraft_info.get('owner_city', 'N/A'),
                                        'owner_state': aircraft_info.get('owner_state', 'N/A'),
                                        'flightaware_url': flightaware_url,
                                        'broadcastify_url': broadcastify_url
                                    }
                            
                            # Log to database
                            self.monitor_service.state_tracker.log_anomaly(
                                icao24=icao24,
                                anomaly_type=anomaly.get('type', 'unknown'),
                                severity=anomaly.get('severity', 'UNKNOWN'),
                                details=anomaly.get('details', {})
                            )
                            
                            # Write to log file (if configured)
                            if self.monitor_service.notifier.log_file:
                                self.monitor_service.notifier._write_to_log(anomaly)
                            
                            # Emit anomaly signal
                            self.anomaly_detected.emit(anomaly)
                    
                    # Emit summary
                    self.summary_updated.emit(
                        self.monitor_service.poll_count,
                        len(current_states),
                        len(anomalies)
                    )
                    
                except Exception as e:
                    self.error_occurred.emit(f"Error in monitoring loop: {e}")
                
                # Sleep until next poll
                if self.monitor_service.running:
                    self.msleep(self.interval_seconds * 1000)
        
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.status_changed.emit('stopped')
    
    def stop_monitoring(self):
        """Stop the monitoring service."""
        if self.monitor_service:
            self.monitor_service.running = False
        self._should_pause = False
    
    def pause_monitoring(self):
        """Pause monitoring."""
        self._should_pause = True
    
    def resume_monitoring(self):
        """Resume monitoring."""
        self._should_pause = False
    
    def get_current_states(self) -> Dict:
        """Get current aircraft states."""
        if self.monitor_service:
            return self.monitor_service.get_current_states()
        return {}
    
    def get_recent_anomalies(self, limit: int = 50) -> List[Dict]:
        """Get recent anomalies."""
        if self.monitor_service:
            return self.monitor_service.get_recent_anomalies(limit)
        return []
