"""
Configuration settings for MediTrack EMS Aircraft Tracking System.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
SRC_DIR = PROJECT_ROOT / "src"
FAA_DATA_DIR = PROJECT_ROOT / "ReleasableAircraft"

# Database files
EMS_DB_JSON = DATA_DIR / "ems_aircraft.json"
EMS_DB_CSV = DATA_DIR / "ems_aircraft.csv"
EMS_DB_SQLITE = DATA_DIR / "ems_aircraft.db"
POLICE_DB_JSON = DATA_DIR / "police_aircraft.json"

# Cache directory for API responses
CACHE_DIR = DATA_DIR / "cache"

# OpenSky API configuration
OPENSKY_USERNAME = os.getenv("OPENSKY_USERNAME", None)
OPENSKY_PASSWORD = os.getenv("OPENSKY_PASSWORD", None)
OPENSKY_CLIENT_ID = os.getenv("OPENSKY_CLIENT_ID", None)
OPENSKY_CLIENT_SECRET = os.getenv("OPENSKY_CLIENT_SECRET", None)

# Rate limiting settings
# Anonymous users: ~10 requests/second (conservative)
# Authenticated users: Better rate limits
OPENSKY_RATE_LIMIT_CALLS = int(os.getenv("OPENSKY_RATE_LIMIT_CALLS", "10"))
OPENSKY_RATE_LIMIT_PERIOD = float(os.getenv("OPENSKY_RATE_LIMIT_PERIOD", "1.0"))

# Cache settings
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_MAX_AGE_SECONDS = int(os.getenv("CACHE_MAX_AGE_SECONDS", "60"))

# Filtering settings
EXCLUDE_INDIVIDUAL_OWNERS = os.getenv("EXCLUDE_INDIVIDUAL_OWNERS", "false").lower() == "true"
MIN_CONFIDENCE_LEVEL = os.getenv("MIN_CONFIDENCE_LEVEL", "low")  # 'low', 'medium', 'high'

# Regional tracking settings
# Options: 'northeast', 'midwest', 'south', 'west', 'all', or None (prompts interactively)
TRACKING_REGION = os.getenv("TRACKING_REGION", None)

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Monitoring settings
MONITOR_INTERVAL_SECONDS = int(os.getenv("MONITOR_INTERVAL_SECONDS", "60"))
MONITOR_REGION = os.getenv("MONITOR_REGION", None)  # 'northeast', 'midwest', 'south', 'west', 'all'
MONITOR_STATE = os.getenv("MONITOR_STATE", None)  # Comma-separated state codes (e.g., 'NJ' or 'NJ,DE,PA')

# Anomaly detection thresholds
ANOMALY_SPEED_THRESHOLD_KNOTS = float(os.getenv("ANOMALY_SPEED_THRESHOLD_KNOTS", "150.0"))
ANOMALY_MULTI_LAUNCH_WINDOW_SECONDS = int(os.getenv("ANOMALY_MULTI_LAUNCH_WINDOW_SECONDS", "300"))
ANOMALY_RAPID_CLIMB_RATE_FT_MIN = float(os.getenv("ANOMALY_RAPID_CLIMB_RATE_FT_MIN", "2000.0"))
ANOMALY_RAPID_DESCENT_FT = float(os.getenv("ANOMALY_RAPID_DESCENT_FT", "1000.0"))
ANOMALY_RAPID_DESCENT_WINDOW_SECONDS = int(os.getenv("ANOMALY_RAPID_DESCENT_WINDOW_SECONDS", "30"))

# Anomaly logging
ANOMALY_LOG_FILE = Path(DATA_DIR) / os.getenv("ANOMALY_LOG_FILE", "anomalies.jsonl")
MONITOR_STATE_DB = Path(DATA_DIR) / os.getenv("MONITOR_STATE_DB", "monitor_state.db")