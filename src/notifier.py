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
        Format anomaly as human-readable message with boxed styling.
        
        Args:
            anomaly: Anomaly dictionary
            
        Returns:
            Formatted message string with boxes and brackets
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
        
        # Box drawing characters
        top_left = '┌'
        top_right = '┐'
        bottom_left = '└'
        bottom_right = '┘'
        horizontal = '─'
        vertical = '│'
        
        # Calculate box width (minimum 70, adjust based on content)
        box_width = 70
        
        def make_box(title: str, content_lines: list) -> list:
            """Create a boxed section with title and content."""
            box_lines = []
            # Top border with title
            title_text = f" {title} "
            padding = box_width - len(title_text) - 2
            if padding < 0:
                padding = 0
            box_lines.append(top_left + title_text + horizontal * padding + top_right)
            
            # Content lines
            for line in content_lines:
                # Truncate if too long
                if len(line) > box_width - 4:
                    line = line[:box_width - 7] + "..."
                padding = box_width - len(line) - 4
                if padding < 0:
                    padding = 0
                box_lines.append(vertical + " " + line + " " * padding + " " + vertical)
            
            # Bottom border
            box_lines.append(bottom_left + horizontal * (box_width - 2) + bottom_right)
            return box_lines
        
        # Build main anomaly box content
        main_content = [
            f"{severity_indicator} [Severity] {severity}",
            f"[Timestamp] {timestamp}",
            f"[Type] {anomaly_type}",
            f"[Aircraft] {icao24}"
        ]
        
        # Add callsign if available
        if details.get('callsign'):
            main_content.append(f"[Callsign] {details['callsign']}")
        
        # Build aircraft info box if available
        aircraft_info = anomaly.get('aircraft_info')
        aircraft_content = []
        if aircraft_info:
            n_number = aircraft_info.get('n_number', 'N/A')
            aircraft_content.append(f"[N-Number] {n_number}")
            
            # Add FlightAware link if we have an N-number
            flightaware_url = aircraft_info.get('flightaware_url')
            if flightaware_url:
                aircraft_content.append(f"[FlightAware] {flightaware_url}")
            
            # Add Broadcastify link for nearest county PD radio
            broadcastify_url = aircraft_info.get('broadcastify_url')
            if broadcastify_url:
                aircraft_content.append(f"[Local PD Radio] {broadcastify_url}")
            
            model = aircraft_info.get('model_name', 'N/A')
            manufacturer = aircraft_info.get('manufacturer', 'N/A')
            aircraft_content.append(f"[Model] {model} ({manufacturer})")
            
            owner_name = aircraft_info.get('owner_name', 'N/A')
            if len(owner_name) > 45:
                owner_name = owner_name[:42] + "..."
            aircraft_content.append(f"[Owner] {owner_name}")
            
            owner_location = f"{aircraft_info.get('owner_city', '')}, {aircraft_info.get('owner_state', '')}".strip(', ')
            if owner_location:
                aircraft_content.append(f"[Location] {owner_location}")
        
        # Build anomaly details box
        details_content = []
        if anomaly_type == 'high_speed':
            details_content.append(f"[Speed] {details.get('velocity_knots', 'N/A')} knots")
            details_content.append(f"[Threshold] {details.get('threshold_knots', 'N/A')} knots")
        
        elif anomaly_type == 'sudden_speed_increase':
            details_content.append(f"[Speed Increase] {details.get('increase_percent', 'N/A')}%")
            if details.get('baseline_velocity_knots'):
                details_content.append(f"[Baseline (avg)] {details.get('baseline_velocity_knots', 'N/A')} knots")
            else:
                details_content.append(f"[Previous] {details.get('previous_velocity_knots', 'N/A')} knots")
            details_content.append(f"[Current] {details.get('current_velocity_knots', 'N/A')} knots")
            if details.get('absolute_increase_knots'):
                details_content.append(f"[Absolute Increase] {details.get('absolute_increase_knots', 'N/A')} knots")
        
        elif anomaly_type == 'rapid_climb':
            details_content.append(f"[Climb Rate] {details.get('vertical_rate_ft_min', 'N/A')} ft/min")
            if details.get('altitude_ft'):
                details_content.append(f"[Altitude] {details['altitude_ft']} ft")
        
        elif anomaly_type == 'rapid_descent':
            details_content.append(f"[Altitude Drop] {details.get('altitude_drop_ft', 'N/A')} ft")
            details_content.append(f"[Previous] {details.get('previous_altitude_ft', 'N/A')} ft")
            details_content.append(f"[Current] {details.get('current_altitude_ft', 'N/A')} ft")
        
        elif anomaly_type.startswith('emergency_squawk'):
            details_content.append(f"[Squawk Code] {details.get('squawk_code', 'N/A')}")
            details_content.append(f"[Type] {details.get('squawk_type', 'N/A')}")
        
        elif anomaly_type == 'multiple_launch':
            details_content.append(f"[Aircraft Count] {details.get('aircraft_count', 'N/A')}")
            details_content.append(f"[Time Span] {details.get('time_span_seconds', 'N/A')} seconds")
            aircraft_list = details.get('aircraft', [])
            if aircraft_list:
                details_content.append("[Aircraft List]")
                for ac in aircraft_list[:5]:  # Limit to 5 for readability
                    callsign = ac.get('callsign', 'N/A')
                    details_content.append(f"  • {ac.get('icao24', 'N/A')} ({callsign})")
                if len(aircraft_list) > 5:
                    details_content.append(f"  ... and {len(aircraft_list) - 5} more")
        
        elif anomaly_type == 'erratic_heading':
            details_content.append(f"[Large Heading Changes] {details.get('large_heading_changes', 'N/A')}")
            details_content.append(f"[Average Change] {details.get('average_change', 'N/A')}°")
        
        elif anomaly_type == 'hovering_high_altitude':
            details_content.append(f"[Average Altitude] {details.get('average_altitude_ft', 'N/A')} ft")
            details_content.append(f"[Average Speed] {details.get('average_velocity_knots', 'N/A')} knots")
        
        # Hospital proximity (geo context)
        if 'distance_hospital_km' in details:
            dist = details.get('distance_hospital_km')
            near = details.get('near_hospital', False)
            name = details.get('hospital_name', '')
            if near and name:
                details_content.append(f"[Hospital] Within {dist} km of {name}")
            elif near:
                details_content.append(f"[Hospital] Within {dist} km of hospital")
            else:
                details_content.append(f"[Hospital] Nearest hospital {dist} km away")
        
        # Build final output
        output_lines = []
        
        # Main anomaly box
        output_lines.extend(make_box("ANOMALY DETECTED", main_content))
        output_lines.append("")  # Blank line between boxes
        
        # Aircraft info box (if available)
        if aircraft_content:
            output_lines.extend(make_box("AIRCRAFT INFORMATION", aircraft_content))
            output_lines.append("")  # Blank line between boxes
        
        # Anomaly details box (if available)
        if details_content:
            output_lines.extend(make_box("ANOMALY DETAILS", details_content))
        
        return "\n".join(output_lines)
    
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
            
            # Box drawing characters
            top_left = '┌'
            top_right = '┐'
            bottom_left = '└'
            bottom_right = '┘'
            horizontal = '─'
            vertical = '│'
            box_width = 70
            
            # Build summary content
            content = [
                f"[Timestamp] {timestamp}",
                f"[Poll Number] #{poll_count}",
                f"[Active Aircraft] {active_aircraft}",
                f"[Anomalies Detected] {anomalies_detected}"
            ]
            
            # Create box
            lines = []
            title = " MONITORING SUMMARY "
            padding = box_width - len(title) - 2
            if padding < 0:
                padding = 0
            lines.append(top_left + title + horizontal * padding + top_right)
            
            for line in content:
                if len(line) > box_width - 4:
                    line = line[:box_width - 7] + "..."
                padding = box_width - len(line) - 4
                if padding < 0:
                    padding = 0
                lines.append(vertical + " " + line + " " * padding + " " + vertical)
            
            lines.append(bottom_left + horizontal * (box_width - 2) + bottom_right)
            
            print("\n" + "\n".join(lines) + "\n")
