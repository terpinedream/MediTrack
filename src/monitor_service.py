"""
Main monitoring service for EMS aircraft anomaly detection.

Orchestrates polling, state tracking, and anomaly detection.
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# Add project root to path for config import
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import config
from opensky_client import OpenSkyClient, load_ems_aircraft_db
from monitor_state import StateTracker
from anomaly_detector import AnomalyDetector
from notifier import Notifier
from geo_context import GeoContext
from region_selector import select_region, select_region_or_state, filter_aircraft_by_states
from regions import get_states_bbox
from location_utils import get_broadcastify_url_simple


class MonitorService:
    """Main monitoring service."""
    
    def __init__(self, 
                 region: Optional[str] = None,
                 states: Optional[List[str]] = None,
                 interval_seconds: int = 60,
                 credentials_file: Optional[Path] = None,
                 database_type: str = 'ems',
                 skip_interactive: bool = False):
        """
        Initialize monitoring service.

        Args:
            region: Region to monitor ('northeast', 'midwest', 'south', 'west', 'all')
                   Mutually exclusive with states parameter
            states: List of state codes to monitor (e.g., ['NJ'] or ['NJ', 'DE', 'PA'])
                   Mutually exclusive with region parameter. Use empty list [] for "all US"
            interval_seconds: Polling interval in seconds
            credentials_file: Path to OpenSky credentials file
            database_type: Type of database to use ('ems' or 'police')
            skip_interactive: If True, skip interactive selection even if both region and states are None
        """
        self.interval_seconds = interval_seconds
        self.project_root = Path(__file__).parent.parent
        self.database_type = database_type.lower()
        
        # Load aircraft database based on type
        if self.database_type == 'police':
            db_path = config.POLICE_DB_JSON
            db_name = "police"
            script_name = "filter_police_aircraft.py"
        else:
            db_path = config.EMS_DB_JSON
            db_name = "EMS"
            script_name = "create_ems_database.py"
        
        if not db_path.exists():
            raise FileNotFoundError(
                f"{db_name} aircraft database not found at {db_path}. "
                f"Run {script_name} first."
            )
        
        self.aircraft = load_ems_aircraft_db(db_path)  # Same function works for both
        
        # Keep ems_aircraft for backward compatibility (used in handle_anomalies)
        self.ems_aircraft = self.aircraft
        
        # Select region or state
        self.region = None
        self.states = None
        self.region_bbox = None
        self.state_bbox = None
        
        # If both region and states are provided, states takes precedence
        # Handle empty list as "all US" (explicitly no filtering)
        if states is not None:
            if len(states) == 0:
                # Empty list means "all US" - no filtering
                self.states = None
                self.state_bbox = None
                print("Monitoring all US (no regional filter)")
            else:
                # Validate state codes
                from regions import is_valid_state_code
                invalid_states = [s for s in states if not is_valid_state_code(s)]
                if invalid_states:
                    raise ValueError(f"Invalid state code(s): {', '.join(invalid_states)}")
                self.states = [s.upper() for s in states]
                self.state_bbox = get_states_bbox(self.states)
                
                # Filter aircraft by states
                self.aircraft = filter_aircraft_by_states(self.aircraft, self.states)
                
                print(f"Monitoring states: {', '.join(self.states)}")
                if self.state_bbox:
                    print(f"  Bounding box: ({self.state_bbox[0]:.2f}, {self.state_bbox[1]:.2f}) to ({self.state_bbox[2]:.2f}, {self.state_bbox[3]:.2f})")
        elif region:
            from regions import get_region
            self.region = get_region(region)
            if not self.region:
                raise ValueError(f"Invalid region: {region}")
            
            # Filter aircraft by region
            from region_selector import filter_aircraft_by_region
            self.aircraft = filter_aircraft_by_region(self.aircraft, self.region)
            
            print(f"Monitoring region: {self.region.display_name}")
            print(f"  States: {', '.join(self.region.states)}")
            self.region_bbox = self.region.bbox
        elif skip_interactive:
            # Skip interactive selection (GUI mode with "All US" selected)
            self.states = None
            self.region = None
            self.state_bbox = None
            self.region_bbox = None
            print("Monitoring all US (no regional filter)")
        else:
            # Interactive selection (CLI mode)
            selected_region, selected_states = select_region_or_state(self.project_root)
            
            if selected_states is not None:
                self.states = selected_states
                self.state_bbox = get_states_bbox(self.states)
                
                # Filter aircraft by states
                self.aircraft = filter_aircraft_by_states(self.aircraft, self.states)
                
                print(f"Monitoring states: {', '.join(self.states)}")
                if self.state_bbox:
                    print(f"  Bounding box: ({self.state_bbox[0]:.2f}, {self.state_bbox[1]:.2f}) to ({self.state_bbox[2]:.2f}, {self.state_bbox[3]:.2f})")
            elif selected_region:
                self.region = selected_region
                
                # Filter aircraft by region
                from region_selector import filter_aircraft_by_region
                self.aircraft = filter_aircraft_by_region(self.aircraft, self.region)
                
                print(f"Monitoring region: {self.region.display_name}")
                print(f"  States: {', '.join(self.region.states)}")
                self.region_bbox = self.region.bbox
            else:
                print("Monitoring all US (no regional filter)")
        
        # Build mode_s_set from filtered aircraft
        self.mode_s_set = {
            ac['mode_s_hex'].upper().strip() 
            for ac in self.aircraft 
            if ac.get('mode_s_hex') and ac['mode_s_hex'].strip()
        }
        self.ems_mode_s_set = self.mode_s_set
        
        print(f"Loaded {len(self.aircraft)} {db_name} aircraft from database (after filtering)")
        print(f"Found {len(self.mode_s_set)} aircraft with Mode S codes")
        
        # Initialize OpenSky client
        if credentials_file and credentials_file.exists():
            self.client = OpenSkyClient(
                credentials_file=credentials_file,
                cache_dir=self.project_root / "data" / "cache"
            )
        else:
            # Try credentials.json in project root
            creds_file = self.project_root / "credentials.json"
            if creds_file.exists():
                self.client = OpenSkyClient(
                    credentials_file=creds_file,
                    cache_dir=self.project_root / "data" / "cache"
                )
            else:
                # Use environment variables
                self.client = OpenSkyClient(
                    client_id=config.OPENSKY_CLIENT_ID if hasattr(config, 'OPENSKY_CLIENT_ID') else None,
                    client_secret=config.OPENSKY_CLIENT_SECRET if hasattr(config, 'OPENSKY_CLIENT_SECRET') else None,
                    username=config.OPENSKY_USERNAME,
                    password=config.OPENSKY_PASSWORD,
                    cache_dir=self.project_root / "data" / "cache"
                )
        
        # Test authentication
        if self.client.authenticated:
            if not self.client.test_authentication():
                print("Warning: Authentication test failed. Continuing anyway...")
        else:
            print("Warning: Not authenticated. Some endpoints may not work.")
        
        # Initialize state tracker
        self.state_tracker = StateTracker(config.MONITOR_STATE_DB)
        
        # Initialize anomaly detector
        self.anomaly_detector = AnomalyDetector(
            speed_threshold_knots=config.ANOMALY_SPEED_THRESHOLD_KNOTS,
            multi_launch_window_seconds=config.ANOMALY_MULTI_LAUNCH_WINDOW_SECONDS,
            rapid_climb_rate_ft_min=config.ANOMALY_RAPID_CLIMB_RATE_FT_MIN,
            rapid_descent_ft=config.ANOMALY_RAPID_DESCENT_FT,
            rapid_descent_window_seconds=config.ANOMALY_RAPID_DESCENT_WINDOW_SECONDS
        )
        
        # Initialize notifier
        self.notifier = Notifier(
            log_file=config.ANOMALY_LOG_FILE,
            console_output=True
        )
        
        # Geographic context for airport/hospital proximity (suppress false positives, enrich)
        self.geo_context = GeoContext(config.AIRPORTS_CSV, config.HOSPITALS_CSV)
        
        self.poll_count = 0
        self.running = False
        self.paused = False
        self.current_states = {}
        self.recent_anomalies = []
    
    def run_monitoring_loop(self):
        """Run the main monitoring loop."""
        self.running = True
        self.paused = False
        print(f"\nStarting monitoring service (polling every {self.interval_seconds} seconds)")
        print("Press Ctrl+C to stop\n")
        
        try:
            while self.running:
                # Check if paused
                while self.paused and self.running:
                    time.sleep(0.5)  # Small sleep to avoid busy waiting
                
                if not self.running:
                    break
                
                self.poll_count += 1
                
                try:
                    # Poll aircraft states
                    current_states = self.poll_aircraft_states()
                    self.current_states = current_states
                    
                    # Get previous states for comparison
                    previous_states = self.state_tracker.get_all_latest_states()
                    
                    # Get state history for each aircraft
                    state_history = {}
                    for icao24 in current_states.keys():
                        # Get last 20 states for this aircraft (for better analysis)
                        # This gives us ~20 minutes of history at 60s intervals
                        history = self.state_tracker.get_aircraft_history(icao24, limit=20)
                        state_history[icao24] = history
                    
                    # Process state changes and detect anomalies
                    anomalies = self.process_state_changes(
                        current_states, 
                        previous_states,
                        state_history
                    )
                    
                    # Store recent anomalies
                    if anomalies:
                        self.recent_anomalies.extend(anomalies)
                        # Keep only last 100 anomalies
                        if len(self.recent_anomalies) > 100:
                            self.recent_anomalies = self.recent_anomalies[-100:]
                    
                    # Handle anomalies
                    if anomalies:
                        self.handle_anomalies(anomalies, current_states)
                    
                    # Print summary
                    self.notifier.notify_summary(
                        self.poll_count,
                        len(current_states),
                        len(anomalies)
                    )
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"Error in monitoring loop: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Sleep until next poll
                if self.running:
                    time.sleep(self.interval_seconds)
        
        except KeyboardInterrupt:
            print("\n\nStopping monitoring service...")
            self.running = False
    
    def pause(self):
        """Pause monitoring (can be resumed)."""
        self.paused = True
    
    def resume(self):
        """Resume paused monitoring."""
        self.paused = False
    
    def get_current_states(self) -> Dict[str, Dict]:
        """Get current aircraft states."""
        return self.current_states.copy()
    
    def get_recent_anomalies(self, limit: int = 50) -> List[Dict]:
        """Get recent anomalies."""
        return self.recent_anomalies[-limit:] if self.recent_anomalies else []
    
    def poll_aircraft_states(self) -> Dict[str, Dict]:
        """
        Poll OpenSky API for active aircraft in region or state(s).
        
        Returns:
            Dictionary mapping icao24 to state dictionary
        """
        # Use state_bbox if in state mode, otherwise use region_bbox
        bbox = self.state_bbox if self.states else self.region_bbox
        
        # Query all active aircraft in region/state (one API call)
        response = self.client.get_states(icao24=None, bbox=bbox)
        all_states = response.get('states') if response else None
        
        if all_states is None:
            all_states = []
        elif not isinstance(all_states, list):
            all_states = []
        
        # Match against EMS database
        ems_states = {}
        for state in all_states:
            if state and len(state) >= 1:
                icao24 = state[0].upper() if state[0] else None
                if icao24 and icao24 in self.mode_s_set:
                    # This is one of our EMS aircraft!
                    latitude = state[6] if len(state) > 6 and state[6] is not None else None
                    longitude = state[5] if len(state) > 5 and state[5] is not None else None
                    
                    ems_states[icao24] = {
                        'icao24': icao24,
                        'callsign': state[1] if len(state) > 1 and state[1] else None,
                        'origin_country': state[2] if len(state) > 2 and state[2] else None,
                        'time_position': state[3] if len(state) > 3 and state[3] else None,
                        'last_contact': state[4] if len(state) > 4 and state[4] else None,
                        'longitude': longitude,
                        'latitude': latitude,
                        'baro_altitude': state[7] if len(state) > 7 and state[7] else None,
                        'on_ground': state[8] if len(state) > 8 and state[8] else None,
                        'velocity': state[9] if len(state) > 9 and state[9] else None,
                        'true_track': state[10] if len(state) > 10 and state[10] else None,
                        'vertical_rate': state[11] if len(state) > 11 and state[11] else None,
                        'sensors': state[12] if len(state) > 12 and state[12] else None,
                        'geo_altitude': state[13] if len(state) > 13 and state[13] else None,
                        'squawk': state[14] if len(state) > 14 and state[14] else None,
                        'spi': state[15] if len(state) > 15 and state[15] else None,
                        'position_source': state[16] if len(state) > 16 and state[16] else None,
                        'timestamp': int(datetime.now().timestamp())
                    }
        
        return ems_states
    
    def process_state_changes(self, 
                             current_states: Dict[str, Dict],
                             previous_states: Dict[str, Dict],
                             state_history: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Process state changes and detect anomalies.
        
        Args:
            current_states: Current aircraft states
            previous_states: Previous aircraft states
            state_history: State history for each aircraft
        
        Returns:
            List of detected anomalies
        """
        # Save current states to database
        current_timestamp = int(datetime.now().timestamp())
        for icao24, state in current_states.items():
            self.state_tracker.save_state_snapshot(icao24, state, current_timestamp)
        
        # Detect anomalies
        anomalies = self.anomaly_detector.detect_anomalies(
            current_states,
            previous_states,
            state_history
        )
        
        # Geo filter: suppress rapid_descent when near airport and descending (likely landing)
        filtered = []
        for anomaly in anomalies:
            if anomaly.get("type") == "rapid_descent":
                icao24 = anomaly.get("icao24")
                state = current_states.get(icao24) if icao24 else None
                if state:
                    lat = state.get("latitude")
                    lon = state.get("longitude")
                    vr = state.get("vertical_rate")
                    if lat is not None and lon is not None and vr is not None and vr < 0:
                        if self.geo_context.is_near_airport(lat, lon, config.GEO_NEAR_AIRPORT_KM):
                            continue  # suppress
            filtered.append(anomaly)
        anomalies = filtered
        
        # Enrich with hospital proximity
        for anomaly in anomalies:
            icao24 = anomaly.get("icao24")
            if not icao24:
                continue
            state = current_states.get(icao24)
            if not state:
                continue
            lat = state.get("latitude")
            lon = state.get("longitude")
            if lat is None or lon is None:
                continue
            dist_km, hospital_name = self.geo_context.distance_to_nearest_hospital(lat, lon)
            details = anomaly.setdefault("details", {})
            details["distance_hospital_km"] = round(dist_km, 1)
            details["near_hospital"] = dist_km <= config.GEO_NEAR_HOSPITAL_KM
            if hospital_name is not None:
                details["hospital_name"] = hospital_name
        
        return anomalies
    
    def handle_anomalies(self, anomalies: List[Dict], current_states: Dict[str, Dict]):
        """
        Handle detected anomalies (log and notify).
        
        Args:
            anomalies: List of anomaly dictionaries
            current_states: Current aircraft states (for location data)
        """
        for anomaly in anomalies:
            # Add aircraft info to anomaly for verbose output
            icao24 = anomaly.get('icao24')
            if icao24:
                # Look up aircraft info from database
                aircraft_info = next(
                    (ac for ac in self.aircraft 
                     if ac.get('mode_s_hex', '').strip().upper() == icao24.upper()),
                    None
                )
                if aircraft_info:
                    n_number = aircraft_info.get('n_number', 'N/A')
                    # Ensure N-number has 'N' prefix for FlightAware URL
                    if n_number and n_number != 'N/A':
                        # Remove any existing 'N' prefix and add it back to ensure consistency
                        n_number_clean = n_number.upper().strip()
                        if not n_number_clean.startswith('N'):
                            n_number_clean = 'N' + n_number_clean
                        flightaware_url = f"https://www.flightaware.com/live/flight/{n_number_clean}"
                    else:
                        flightaware_url = None
                    
                    # Get current location for Broadcastify URL (optional - don't block on this)
                    broadcastify_url = None
                    try:
                        current_state = current_states.get(icao24)
                        if current_state:
                            latitude = current_state.get('latitude')
                            longitude = current_state.get('longitude')
                            if latitude is not None and longitude is not None:
                                # Try to get Broadcastify URL, but don't let it break the service
                                # This may take a moment due to geocoding API call, but it's optional
                                try:
                                    broadcastify_url = get_broadcastify_url_simple(latitude, longitude)
                                except Exception:
                                    # Geocoding failed - that's okay, just skip it
                                    broadcastify_url = None
                    except Exception:
                        # Silently fail - geocoding is optional and shouldn't break monitoring
                        broadcastify_url = None
                    
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
            self.state_tracker.log_anomaly(
                icao24=icao24,
                anomaly_type=anomaly.get('type', 'unknown'),
                severity=anomaly.get('severity', 'UNKNOWN'),
                details=anomaly.get('details', {})
            )
            
            # Notify
            self.notifier.notify_anomaly(anomaly)
    
    def stop(self):
        """Stop the monitoring service."""
        self.running = False


if __name__ == "__main__":
    """Allow running monitor_service.py directly (for convenience)."""
    import sys
    from pathlib import Path
    
    # Import run_monitor's main function
    run_monitor_path = Path(__file__).parent / "run_monitor.py"
    if run_monitor_path.exists():
        print("Note: Use 'python src/run_monitor.py' for full functionality with command-line options.")
        print("Running with default settings...\n")
        
        # Simple default run
        try:
            service = MonitorService()
            service.run_monitoring_loop()
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")
            sys.exit(0)
        except Exception as e:
            print(f"\nError: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print("Error: run_monitor.py not found. Please use the proper entry point.")
        sys.exit(1)
