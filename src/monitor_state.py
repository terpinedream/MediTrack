"""
State tracking database for EMS aircraft monitoring.

Stores aircraft state history and anomaly logs in SQLite database.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _normalize_state_row(row: Dict) -> Dict:
    """Map DB column names to OpenSky-style field names used by anomaly detection."""
    normalized = dict(row)
    if 'altitude' in normalized and 'baro_altitude' not in normalized:
        normalized['baro_altitude'] = normalized['altitude']
    if 'heading' in normalized and 'true_track' not in normalized:
        normalized['true_track'] = normalized['heading']
    if 'on_ground' in normalized and normalized['on_ground'] is not None:
        normalized['on_ground'] = bool(normalized['on_ground'])
    return normalized


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
        self._conn: Optional[sqlite3.Connection] = None
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Return persistent SQLite connection (thread-safe for worker thread)."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        """Close persistent database connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None

    def _init_database(self):
        """Initialize database schema if it doesn't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()

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

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_icao24_timestamp
            ON aircraft_history(icao24, timestamp DESC)
        """)

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

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomaly_timestamp
            ON anomaly_log(timestamp DESC)
        """)

        conn.commit()

    def save_state_snapshot(self, icao24: str, state: Dict, timestamp: Optional[int] = None):
        """
        Save a state snapshot for an aircraft.

        Args:
            icao24: ICAO24 hex code
            state: State dictionary with OpenSky-style fields
            timestamp: Unix timestamp (defaults to current time)
        """
        self.save_state_snapshots_batch({icao24: state}, timestamp)

    def save_state_snapshots_batch(
        self,
        states: Dict[str, Dict],
        timestamp: Optional[int] = None,
    ) -> None:
        """
        Save state snapshots for multiple aircraft in one transaction.

        Args:
            states: Dictionary mapping icao24 to state dict
            timestamp: Unix timestamp (defaults to current time)
        """
        if not states:
            return

        if timestamp is None:
            timestamp = int(datetime.now().timestamp())

        conn = self._get_connection()
        cursor = conn.cursor()
        rows = []
        for icao24, state in states.items():
            rows.append((
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
                state.get('last_contact'),
            ))

        try:
            cursor.executemany("""
                INSERT OR REPLACE INTO aircraft_history
                (icao24, timestamp, latitude, longitude, altitude, velocity,
                 on_ground, vertical_rate, callsign, heading, squawk, last_contact)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.error("Failed to save state snapshots: %s", e)
            raise

    def get_aircraft_history(self,
                            icao24: str,
                            since_timestamp: Optional[int] = None,
                            limit: int = 100) -> List[Dict]:
        """
        Get recent history for an aircraft.

        Args:
            icao24: ICAO24 hex code
            since_timestamp: Only return records after this timestamp (optional)
            limit: Maximum number of records to return

        Returns:
            List of state dictionaries with normalized field names, most recent first
        """
        histories = self.get_histories_batch([icao24], since_timestamp=since_timestamp, limit=limit)
        return histories.get(icao24.upper(), [])

    def get_histories_batch(
        self,
        icao24_list: List[str],
        since_timestamp: Optional[int] = None,
        limit: int = 20,
    ) -> Dict[str, List[Dict]]:
        """
        Get recent history for multiple aircraft in one query.

        Args:
            icao24_list: List of ICAO24 hex codes
            since_timestamp: Only return records after this timestamp (optional)
            limit: Maximum records per aircraft

        Returns:
            Dictionary mapping icao24 to list of normalized state dicts
        """
        if not icao24_list:
            return {}

        normalized_ids = [i.upper() for i in icao24_list]
        placeholders = ','.join('?' * len(normalized_ids))
        conn = self._get_connection()
        cursor = conn.cursor()

        query = f"""
            SELECT * FROM aircraft_history
            WHERE icao24 IN ({placeholders})
        """
        params: list = list(normalized_ids)

        if since_timestamp:
            query += " AND timestamp > ?"
            params.append(since_timestamp)

        query += " ORDER BY icao24, timestamp DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        result: Dict[str, List[Dict]] = {icao: [] for icao in normalized_ids}
        for row in rows:
            icao = row['icao24']
            if len(result[icao]) < limit:
                result[icao].append(_normalize_state_row(dict(row)))

        return result

    def get_latest_state(self, icao24: str) -> Optional[Dict]:
        """
        Get the most recent state for an aircraft.

        Args:
            icao24: ICAO24 hex code

        Returns:
            Normalized state dictionary or None if not found
        """
        history = self.get_aircraft_history(icao24, limit=1)
        return history[0] if history else None

    def get_all_latest_states(self, since_timestamp: Optional[int] = None) -> Dict[str, Dict]:
        """
        Get latest state for all aircraft.

        Args:
            since_timestamp: Only return aircraft with states after this timestamp

        Returns:
            Dictionary mapping icao24 to normalized latest state
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if since_timestamp:
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
        return {row['icao24']: _normalize_state_row(dict(row)) for row in rows}

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

        conn = self._get_connection()
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
                json.dumps(details),
            ))
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.error("Failed to log anomaly: %s", e)
            raise

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
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM anomaly_log WHERE 1=1"
        params: list = []

        if since_timestamp:
            query += " AND timestamp > ?"
            params.append(since_timestamp)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        anomalies = []
        for row in rows:
            anomaly = dict(row)
            if anomaly['details']:
                try:
                    anomaly['details'] = json.loads(anomaly['details'])
                except json.JSONDecodeError:
                    pass
            anomalies.append(anomaly)

        return anomalies

    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """
        Remove old state history data to keep database size manageable.

        Args:
            days_to_keep: Number of days of history to keep

        Returns:
            Number of deleted rows
        """
        cutoff_timestamp = int((datetime.now() - timedelta(days=days_to_keep)).timestamp())

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                DELETE FROM aircraft_history
                WHERE timestamp < ?
            """, [cutoff_timestamp])
            deleted = cursor.rowcount
            conn.commit()
            if deleted:
                logger.info("Cleaned up %d old state history records", deleted)
            return deleted
        except sqlite3.Error as e:
            conn.rollback()
            logger.error("Failed to cleanup old data: %s", e)
            raise
