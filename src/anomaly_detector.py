"""
Anomaly detection engine for EMS aircraft monitoring.

Detects unusual flight patterns that may indicate emergencies.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import math


class AnomalyDetector:
    """Detects anomalies in aircraft flight patterns."""
    
    def __init__(self, 
                 speed_threshold_knots: float = 150.0,
                 multi_launch_window_seconds: int = 300,
                 rapid_climb_rate_ft_min: float = 2000.0,
                 rapid_descent_ft: float = 1000.0,
                 rapid_descent_window_seconds: int = 30):
        """
        Initialize anomaly detector with thresholds.
        
        Args:
            speed_threshold_knots: Speed threshold for high-speed anomaly (knots)
            multi_launch_window_seconds: Time window for detecting multiple launches
            rapid_climb_rate_ft_min: Vertical rate threshold for rapid climb (ft/min)
            rapid_descent_ft: Altitude drop threshold for rapid descent (feet)
            rapid_descent_window_seconds: Time window for rapid descent detection
        """
        self.speed_threshold_knots = speed_threshold_knots
        self.multi_launch_window_seconds = multi_launch_window_seconds
        self.rapid_climb_rate_ft_min = rapid_climb_rate_ft_min
        self.rapid_descent_ft = rapid_descent_ft
        self.rapid_descent_window_seconds = rapid_descent_window_seconds
        
        # Emergency squawk codes
        self.emergency_squawks = {
            '7500': 'hijack',
            '7600': 'radio_failure',
            '7700': 'emergency'
        }
    
    def detect_anomalies(self, current_states: Dict[str, Dict], 
                        previous_states: Dict[str, Dict],
                        state_history: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Detect anomalies in current aircraft states.
        
        Args:
            current_states: Dictionary mapping icao24 to current state
            previous_states: Dictionary mapping icao24 to previous state
            state_history: Dictionary mapping icao24 to list of recent states
        
        Returns:
            List of anomaly dictionaries with keys: icao24, type, severity, details
        """
        anomalies = []
        
        for icao24, current_state in current_states.items():
            previous_state = previous_states.get(icao24)
            history = state_history.get(icao24, [])
            
            # Check each type of anomaly
            anomalies.extend(self.check_speed_anomaly(icao24, current_state, previous_state, history))
            anomalies.extend(self.check_altitude_anomaly(icao24, current_state, previous_state, history))
            anomalies.extend(self.check_emergency_squawk(icao24, current_state))
            anomalies.extend(self.check_flight_pattern(icao24, current_state, history))
        
        # Multi-aircraft anomalies (check across all aircraft)
        anomalies.extend(self.check_multiple_launch(current_states, previous_states))
        
        return anomalies
    
    def check_speed_anomaly(self, icao24: str, current_state: Dict, 
                           previous_state: Optional[Dict],
                           history: List[Dict]) -> List[Dict]:
        """
        Check for high speed anomalies.
        
        Uses recent history to detect more accurate speed changes.
        
        Returns:
            List of anomaly dictionaries (empty if none detected)
        """
        anomalies = []
        velocity_ms = current_state.get('velocity')
        
        if velocity_ms is None:
            return anomalies
        
        # Convert m/s to knots
        velocity_knots = velocity_ms * 1.94384
        
        # Check absolute speed threshold
        if velocity_knots > self.speed_threshold_knots:
            anomalies.append({
                'icao24': icao24,
                'type': 'high_speed',
                'severity': 'HIGH',
                'details': {
                    'velocity_knots': round(velocity_knots, 1),
                    'threshold_knots': self.speed_threshold_knots,
                    'velocity_ms': round(velocity_ms, 1)
                }
            })
        
        # Check for sudden speed increase using recent history
        # Look at states from last 2-3 minutes to get a better baseline
        if len(history) >= 2:
            # Get average velocity from 2-4 polls ago (2-4 minutes ago)
            # This gives us a better baseline than just the previous poll
            baseline_states = history[-4:-1] if len(history) >= 4 else history[:-1]
            baseline_velocities = [
                h.get('velocity', 0) for h in baseline_states 
                if h.get('velocity') is not None and h.get('velocity', 0) > 0
            ]
            
            if baseline_velocities:
                # Use average of baseline velocities
                avg_baseline_ms = sum(baseline_velocities) / len(baseline_velocities)
                avg_baseline_knots = avg_baseline_ms * 1.94384
                
                # Only flag if there's a significant increase from baseline
                # and current speed is above a minimum threshold (avoid false positives from low speeds)
                if avg_baseline_ms > 0 and velocity_knots > 30:  # At least 30 knots current speed
                    speed_increase_pct = ((velocity_ms - avg_baseline_ms) / avg_baseline_ms) * 100
                    
                    # Require larger increase for detection (60% instead of 50%)
                    # and absolute increase of at least 20 knots
                    absolute_increase_knots = velocity_knots - avg_baseline_knots
                    if speed_increase_pct > 60 and absolute_increase_knots > 20:
                        anomalies.append({
                            'icao24': icao24,
                            'type': 'sudden_speed_increase',
                            'severity': 'MEDIUM',
                            'details': {
                                'baseline_velocity_knots': round(avg_baseline_knots, 1),
                                'current_velocity_knots': round(velocity_knots, 1),
                                'increase_percent': round(speed_increase_pct, 1),
                                'absolute_increase_knots': round(absolute_increase_knots, 1),
                                'baseline_samples': len(baseline_velocities)
                            }
                        })
        
        return anomalies
    
    def check_altitude_anomaly(self, icao24: str, current_state: Dict,
                               previous_state: Optional[Dict],
                               history: List[Dict]) -> List[Dict]:
        """
        Check for rapid altitude changes.
        
        Returns:
            List of anomaly dictionaries
        """
        anomalies = []
        current_altitude = current_state.get('baro_altitude') or current_state.get('geo_altitude')
        vertical_rate = current_state.get('vertical_rate')
        
        if vertical_rate is not None:
            # Convert m/s to ft/min
            vertical_rate_ft_min = vertical_rate * 196.85
            
            # Check for rapid climb
            if vertical_rate_ft_min > self.rapid_climb_rate_ft_min:
                anomalies.append({
                    'icao24': icao24,
                    'type': 'rapid_climb',
                    'severity': 'HIGH',
                    'details': {
                        'vertical_rate_ft_min': round(vertical_rate_ft_min, 0),
                        'threshold_ft_min': self.rapid_climb_rate_ft_min,
                        'altitude_ft': round(current_altitude * 3.28084, 0) if current_altitude else None
                    }
                })
        
        # Check for rapid descent (compare with recent history)
        if current_altitude is not None and len(history) > 0:
            # Find state from rapid_descent_window_seconds ago
            current_time = current_state.get('last_contact') or current_state.get('timestamp', 0)
            cutoff_time = current_time - self.rapid_descent_window_seconds
            
            for past_state in history:
                past_time = past_state.get('last_contact') or past_state.get('timestamp', 0)
                if past_time >= cutoff_time:
                    past_altitude = past_state.get('baro_altitude') or past_state.get('geo_altitude')
                    if past_altitude is not None:
                        altitude_drop_ft = (past_altitude - current_altitude) * 3.28084
                        if altitude_drop_ft > self.rapid_descent_ft:
                            anomalies.append({
                                'icao24': icao24,
                                'type': 'rapid_descent',
                                'severity': 'CRITICAL',
                                'details': {
                                    'altitude_drop_ft': round(altitude_drop_ft, 0),
                                    'previous_altitude_ft': round(past_altitude * 3.28084, 0),
                                    'current_altitude_ft': round(current_altitude * 3.28084, 0),
                                    'time_window_seconds': self.rapid_descent_window_seconds
                                }
                            })
                            break  # Only report once per descent
        
        return anomalies
    
    def check_emergency_squawk(self, icao24: str, current_state: Dict) -> List[Dict]:
        """
        Check for emergency squawk codes.
        
        Returns:
            List of anomaly dictionaries
        """
        anomalies = []
        squawk = current_state.get('squawk')
        
        if squawk and str(squawk) in self.emergency_squawks:
            squawk_type = self.emergency_squawks[str(squawk)]
            anomalies.append({
                'icao24': icao24,
                'type': f'emergency_squawk_{squawk_type}',
                'severity': 'CRITICAL',
                'details': {
                    'squawk_code': str(squawk),
                    'squawk_type': squawk_type,
                    'callsign': current_state.get('callsign')
                }
            })
        
        return anomalies
    
    def check_flight_pattern(self, icao24: str, current_state: Dict,
                             history: List[Dict]) -> List[Dict]:
        """
        Check for unusual flight patterns (erratic heading, hovering).
        
        Returns:
            List of anomaly dictionaries
        """
        anomalies = []
        
        if len(history) < 3:
            return anomalies
        
        # Check for erratic heading changes
        heading_changes = []
        for i in range(len(history) - 1):
            prev_heading = history[i].get('heading')
            curr_heading = history[i + 1].get('heading')
            
            if prev_heading is not None and curr_heading is not None:
                # Calculate heading change (handle wrap-around at 360/0)
                change = abs(curr_heading - prev_heading)
                if change > 180:
                    change = 360 - change
                heading_changes.append(change)
        
        # If we have multiple large heading changes, it's erratic
        large_changes = [c for c in heading_changes if c > 90]
        if len(large_changes) >= 3:
            anomalies.append({
                'icao24': icao24,
                'type': 'erratic_heading',
                'severity': 'MEDIUM',
                'details': {
                    'large_heading_changes': len(large_changes),
                    'total_changes': len(heading_changes),
                    'average_change': round(sum(heading_changes) / len(heading_changes), 1) if heading_changes else 0
                }
            })
        
        # Check for hovering at unusual altitude (helicopter staying at high altitude)
        if len(history) >= 5:
            altitudes = [h.get('baro_altitude') or h.get('geo_altitude') 
                        for h in history[-5:] if h.get('baro_altitude') or h.get('geo_altitude')]
            velocities = [h.get('velocity', 0) for h in history[-5:] if h.get('velocity')]
            
            if len(altitudes) >= 3 and len(velocities) >= 3:
                avg_altitude_ft = (sum(altitudes) / len(altitudes)) * 3.28084
                avg_velocity_knots = (sum(velocities) / len(velocities)) * 1.94384
                
                # Hovering = low speed at high altitude (>5000 ft)
                if avg_altitude_ft > 5000 and avg_velocity_knots < 30:
                    anomalies.append({
                        'icao24': icao24,
                        'type': 'hovering_high_altitude',
                        'severity': 'LOW',
                        'details': {
                            'average_altitude_ft': round(avg_altitude_ft, 0),
                            'average_velocity_knots': round(avg_velocity_knots, 1)
                        }
                    })
        
        return anomalies
    
    def check_multiple_launch(self, current_states: Dict[str, Dict],
                              previous_states: Dict[str, Dict]) -> List[Dict]:
        """
        Check for multiple aircraft launching simultaneously.
        
        Returns:
            List of anomaly dictionaries
        """
        anomalies = []
        
        # Find aircraft that transitioned from on_ground=True to on_ground=False
        launches = []
        for icao24, current_state in current_states.items():
            current_on_ground = current_state.get('on_ground')
            previous_state = previous_states.get(icao24)
            
            if previous_state:
                previous_on_ground = previous_state.get('on_ground')
                
                # Transition from ground to air
                if previous_on_ground and not current_on_ground:
                    launches.append({
                        'icao24': icao24,
                        'timestamp': current_state.get('last_contact') or current_state.get('timestamp', 0),
                        'callsign': current_state.get('callsign')
                    })
        
        # If 3+ aircraft launched within the time window, it's a multi-launch
        if len(launches) >= 3:
            # Check if launches are within the time window
            if launches:
                timestamps = [l['timestamp'] for l in launches]
                time_span = max(timestamps) - min(timestamps)
                
                if time_span <= self.multi_launch_window_seconds:
                    anomalies.append({
                        'icao24': None,  # Multi-aircraft anomaly
                        'type': 'multiple_launch',
                        'severity': 'CRITICAL',
                        'details': {
                            'aircraft_count': len(launches),
                            'time_span_seconds': time_span,
                            'aircraft': [{'icao24': l['icao24'], 'callsign': l.get('callsign')} 
                                        for l in launches]
                        }
                    })
        
        return anomalies
