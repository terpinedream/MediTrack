"""
State tracking database for EMS aircraft monitoring.

Stores aircraft state history and anomaly logs in SQLite database.
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class StateTracker:
    """Manages aircraft state history and anomaly logging."""
    
    def __init__(self, db_path: Path):
        """
        Initialize state tracker with database path.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Aircraft history table - stores state snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aircraft_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                icao24 TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                latitude REAL,
                longitude REAL,
                altitude REAL,
                velocity REAL,
                on_ground INTEGER,
                vertical_rate REAL,
                callsign TEXT,
                heading REAL,
                squawk TEXT,
                last_contact INTEGER,
                UNIQUE(icao24, timestamp)
            )
        """)
        
        # Create index for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_icao24_timestamp 
            ON aircraft_history(icao24, timestamp DESC)
        """)
        
        # Anomaly log table - records detected anomalies
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                icao24 TEXT,
                anomaly_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                details TEXT,
                acknowledged INTEGER DEFAULT 0
            )
        """)
        
        # Create index for anomaly queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomaly_timestamp 
            ON anomaly_log(timestamp DESC)
        """)
        
        conn.commit()
        conn.close()
    
    def save_state_snapshot(self, icao24: str, state: Dict, timestamp: Optional[int] = None):
        """
        Save a state snapshot for an aircraft.
        
        Args:
            icao24: ICAO24 hex code
            state: State dictionary with fields: latitude, longitude, altitude, 
                   velocity, on_ground, vertical_rate, callsign, heading, squawk, last_contact
            timestamp: Unix timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = int(datetime.now().timestamp())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO aircraft_history 
                (icao24, timestamp, latitude, longitude, altitude, velocity, 
                 on_ground, vertical_rate, callsign, heading, squawk, last_contact)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                icao24.upper(),
                timestamp,
                state.get('latitude'),
                state.get('longitude'),
                state.get('baro_altitude') or state.get('geo_altitude'),
                state.get('velocity'),
                1 if state.get('on_ground') else 0,
                state.get('vertical_rate'),
                state.get('callsign'),
                state.get('true_track'),
                state.get('squawk'),
                state.get('last_contact')
            ))
            conn.commit()
        finally:
            conn.close()
    
    def get_aircraft_history(self, icao24: str, 
                            since_timestamp: Optional[int] = None,
                            limit: int = 100) -> List[Dict]:
        """
        Get recent history for an aircraft.
        
        Args:
            icao24: ICAO24 hex code
            since_timestamp: Only return records after this timestamp (optional)
            limit: Maximum number of records to return
        
        Returns:
            List of state dictionaries, most recent first
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = """
            SELECT * FROM aircraft_history 
            WHERE icao24 = ?
        """
        params = [icao24.upper()]
        
        if since_timestamp:
            query += " AND timestamp > ?"
            params.append(since_timestamp)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_latest_state(self, icao24: str) -> Optional[Dict]:
        """
        Get the most recent state for an aircraft.
        
        Args:
            icao24: ICAO24 hex code
        
        Returns:
            State dictionary or None if not found
        """
        history = self.get_aircraft_history(icao24, limit=1)
        return history[0] if history else None
    
    def get_all_latest_states(self, since_timestamp: Optional[int] = None) -> Dict[str, Dict]:
        """
        Get latest state for all aircraft.
        
        Args:
            since_timestamp: Only return aircraft with states after this timestamp
        
        Returns:
            Dictionary mapping icao24 to latest state
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if since_timestamp:
            # Get most recent state for each aircraft after timestamp
            query = """
                SELECT h1.*
                FROM aircraft_history h1
                INNER JOIN (
                    SELECT icao24, MAX(timestamp) as max_timestamp
                    FROM aircraft_history
                    WHERE timestamp > ?
                    GROUP BY icao24
                ) h2 ON h1.icao24 = h2.icao24 AND h1.timestamp = h2.max_timestamp
            """
            cursor.execute(query, [since_timestamp])
        else:
            # Get most recent state for each aircraft
            query = """
                SELECT h1.*
                FROM aircraft_history h1
                INNER JOIN (
                    SELECT icao24, MAX(timestamp) as max_timestamp
                    FROM aircraft_history
                    GROUP BY icao24
                ) h2 ON h1.icao24 = h2.icao24 AND h1.timestamp = h2.max_timestamp
            """
            cursor.execute(query)
        
        rows = cursor.fetchall()
        conn.close()
        
        return {row['icao24']: dict(row) for row in rows}
    
    def log_anomaly(self, icao24: Optional[str], anomaly_type: str, 
                   severity: str, details: Dict, timestamp: Optional[int] = None):
        """
        Log a detected anomaly.
        
        Args:
            icao24: ICAO24 hex code (optional)
            anomaly_type: Type of anomaly (e.g., 'high_speed', 'multiple_launch')
            severity: Severity level ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')
            details: Additional details as dictionary
            timestamp: Unix timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = int(datetime.now().timestamp())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO anomaly_log 
                (timestamp, icao24, anomaly_type, severity, details)
                VALUES (?, ?, ?, ?, ?)
            """, (
                timestamp,
                icao24.upper() if icao24 else None,
                anomaly_type,
                severity,
                json.dumps(details)
            ))
            conn.commit()
        finally:
            conn.close()
    
    def get_recent_anomalies(self, since_timestamp: Optional[int] = None,
                            limit: int = 100) -> List[Dict]:
        """
        Get recent anomalies.
        
        Args:
            since_timestamp: Only return anomalies after this timestamp
            limit: Maximum number of records to return
        
        Returns:
            List of anomaly dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM anomaly_log WHERE 1=1"
        params = []
        
        if since_timestamp:
            query += " AND timestamp > ?"
            params.append(since_timestamp)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        anomalies = []
        for row in rows:
            anomaly = dict(row)
            # Parse JSON details
            if anomaly['details']:
                try:
                    anomaly['details'] = json.loads(anomaly['details'])
                except:
                    pass
            anomalies.append(anomaly)
        
        return anomalies
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """
        Remove old state history data to keep database size manageable.
        
        Args:
            days_to_keep: Number of days of history to keep
        """
        cutoff_timestamp = int((datetime.now() - timedelta(days=days_to_keep)).timestamp())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM aircraft_history 
                WHERE timestamp < ?
            """, [cutoff_timestamp])
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        finally:
            conn.close()
