"""
Notification system for anomaly alerts.

Provides simple console and file-based notifications for POC.
"""

import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


class Notifier:
    """Handles anomaly notifications."""
    
    def __init__(self, log_file: Optional[Path] = None, console_output: bool = True):
        """
        Initialize notifier.
        
        Args:
            log_file: Path to JSON log file (JSONL format - one JSON object per line)
            console_output: Whether to print to console
        """
        self.log_file = log_file
        self.console_output = console_output
        
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def notify_anomaly(self, anomaly: Dict):
        """
        Notify about a detected anomaly.
        
        Args:
            anomaly: Anomaly dictionary with keys: icao24, type, severity, details
        """
        message = self.format_anomaly_message(anomaly)
        
        if self.console_output:
            print(message)
        
        if self.log_file:
            self._write_to_log(anomaly)
    
    def format_anomaly_message(self, anomaly: Dict) -> str:
        """
        Format anomaly as human-readable message.
        
        Args:
            anomaly: Anomaly dictionary
        
        Returns:
            Formatted message string
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        icao24 = anomaly.get('icao24', 'UNKNOWN')
        anomaly_type = anomaly.get('type', 'unknown')
        severity = anomaly.get('severity', 'UNKNOWN')
        details = anomaly.get('details', {})
        
        # Format severity with emoji/indicator
        severity_indicator = {
            'CRITICAL': '🚨',
            'HIGH': '⚠️',
            'MEDIUM': '⚡',
            'LOW': 'ℹ️'
        }.get(severity, '•')
        
        # Build message
        lines = [
            f"{severity_indicator} [{severity}] {timestamp}",
            f"  Type: {anomaly_type}",
            f"  Aircraft: {icao24}"
        ]
        
        # Add verbose aircraft information if available
        aircraft_info = anomaly.get('aircraft_info')
        if aircraft_info:
            n_number = aircraft_info.get('n_number', 'N/A')
            lines.append(f"  N-Number: {n_number}")
            
            # Add FlightAware link if we have an N-number
            flightaware_url = aircraft_info.get('flightaware_url')
            if flightaware_url:
                lines.append(f"  FlightAware: {flightaware_url}")
            
            # Add Broadcastify link for nearest county PD radio
            broadcastify_url = aircraft_info.get('broadcastify_url')
            if broadcastify_url:
                lines.append(f"  Local PD Radio: {broadcastify_url}")
            
            lines.append(f"  Model: {aircraft_info.get('model_name', 'N/A')} ({aircraft_info.get('manufacturer', 'N/A')})")
            owner_name = aircraft_info.get('owner_name', 'N/A')
            if len(owner_name) > 50:
                owner_name = owner_name[:47] + "..."
            lines.append(f"  Owner: {owner_name}")
            owner_location = f"{aircraft_info.get('owner_city', '')}, {aircraft_info.get('owner_state', '')}".strip(', ')
            if owner_location:
                lines.append(f"  Location: {owner_location}")
        
        # Add callsign if available (from current state, not aircraft_info)
        if details.get('callsign'):
            lines.append(f"  Callsign: {details['callsign']}")
        
        # Add type-specific details
        if anomaly_type == 'high_speed':
            lines.append(f"  Speed: {details.get('velocity_knots', 'N/A')} knots (threshold: {details.get('threshold_knots', 'N/A')})")
        
        elif anomaly_type == 'sudden_speed_increase':
            lines.append(f"  Speed increase: {details.get('increase_percent', 'N/A')}%")
            if details.get('baseline_velocity_knots'):
                lines.append(f"  Baseline (avg): {details.get('baseline_velocity_knots', 'N/A')} knots")
            else:
                lines.append(f"  Previous: {details.get('previous_velocity_knots', 'N/A')} knots")
            lines.append(f"  Current: {details.get('current_velocity_knots', 'N/A')} knots")
            if details.get('absolute_increase_knots'):
                lines.append(f"  Absolute increase: {details.get('absolute_increase_knots', 'N/A')} knots")
        
        elif anomaly_type == 'rapid_climb':
            lines.append(f"  Climb rate: {details.get('vertical_rate_ft_min', 'N/A')} ft/min")
            if details.get('altitude_ft'):
                lines.append(f"  Altitude: {details['altitude_ft']} ft")
        
        elif anomaly_type == 'rapid_descent':
            lines.append(f"  Altitude drop: {details.get('altitude_drop_ft', 'N/A')} ft")
            lines.append(f"  Previous: {details.get('previous_altitude_ft', 'N/A')} ft")
            lines.append(f"  Current: {details.get('current_altitude_ft', 'N/A')} ft")
        
        elif anomaly_type.startswith('emergency_squawk'):
            lines.append(f"  Squawk code: {details.get('squawk_code', 'N/A')}")
            lines.append(f"  Type: {details.get('squawk_type', 'N/A')}")
        
        elif anomaly_type == 'multiple_launch':
            lines.append(f"  Multiple aircraft launched: {details.get('aircraft_count', 'N/A')}")
            lines.append(f"  Time span: {details.get('time_span_seconds', 'N/A')} seconds")
            aircraft_list = details.get('aircraft', [])
            if aircraft_list:
                lines.append("  Aircraft:")
                for ac in aircraft_list[:5]:  # Limit to 5 for readability
                    callsign = ac.get('callsign', 'N/A')
                    lines.append(f"    - {ac.get('icao24', 'N/A')} ({callsign})")
                if len(aircraft_list) > 5:
                    lines.append(f"    ... and {len(aircraft_list) - 5} more")
        
        elif anomaly_type == 'erratic_heading':
            lines.append(f"  Large heading changes: {details.get('large_heading_changes', 'N/A')}")
            lines.append(f"  Average change: {details.get('average_change', 'N/A')}°")
        
        elif anomaly_type == 'hovering_high_altitude':
            lines.append(f"  Average altitude: {details.get('average_altitude_ft', 'N/A')} ft")
            lines.append(f"  Average speed: {details.get('average_velocity_knots', 'N/A')} knots")
        
        lines.append("")  # Blank line for readability
        
        return "\n".join(lines)
    
    def _write_to_log(self, anomaly: Dict):
        """
        Write anomaly to JSON log file (JSONL format).
        
        Args:
            anomaly: Anomaly dictionary
        """
        try:
            # Add timestamp if not present
            log_entry = anomaly.copy()
            if 'timestamp' not in log_entry:
                log_entry['timestamp'] = int(datetime.now().timestamp())
            
            # Write as JSON line (JSONL format)
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Warning: Failed to write to log file: {e}")
    
    def notify_summary(self, poll_count: int, active_aircraft: int, anomalies_detected: int):
        """
        Notify about monitoring summary.
        
        Args:
            poll_count: Number of polls completed
            active_aircraft: Number of active aircraft found
            anomalies_detected: Number of anomalies detected in this poll
        """
        if self.console_output:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{timestamp}] Poll #{poll_count}: {active_aircraft} active aircraft, {anomalies_detected} anomalies detected")
