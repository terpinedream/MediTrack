# MediTrack - EMS & Police Aircraft Tracking System

A system for tracking and monitoring Emergency Medical Service (EMS) and Police/Law Enforcement aircraft in the United States using the OpenSky Network API. The system identifies aircraft from the FAA registry database and monitors them for unusual activity patterns.

## Overview

MediTrack filters the FAA aircraft registration database to identify EMS/emergency medical service and Police/Law Enforcement aircraft, then tracks them via the OpenSky Network API. The system is designed to:

- Accurately identify EMS and Police aircraft from the FAA database
- Track active flights in real-time
- Detect unusual flight patterns that may indicate emergencies
- Provide rate-limited API access to minimize API usage
- Monitor aircraft by region with anomaly detection

## Features

- **Multi-criteria filtering**: Identifies EMS and Police aircraft by model type, owner name keywords, and N-number patterns
- **Dual database support**: Filter and monitor both EMS and Police/Law Enforcement aircraft
- **Confidence scoring**: Categorizes matches as high, medium, or low confidence
- **Anomaly detection**: Monitors for unusual flight patterns (speed, altitude, multiple launches, emergency squawks)
- **Regional monitoring**: Track aircraft by US region (Northeast, Midwest, South, West, or All)
- **Rate-limited API client**: Respects OpenSky API rate limits with automatic retry logic
- **Response caching**: Reduces API calls by caching responses
- **OAuth2 authentication**: Supports OpenSky's OAuth2 Client Credentials Flow

## Project Structure

```
MediTrack/
├── data/                    # Generated databases and cache (gitignored)
│   ├── ems_aircraft.json    # EMS aircraft database (JSON)
│   ├── police_aircraft.json # Police aircraft database (JSON)
│   ├── ems_aircraft.csv     # EMS aircraft database (CSV)
│   ├── ems_aircraft.db      # EMS aircraft database (SQLite)
│   ├── monitor_state.db     # Monitoring state database
│   ├── anomalies.jsonl      # Anomaly log file
│   └── cache/               # API response cache
├── src/                     # Source code
│   ├── filter_ems_aircraft.py      # EMS aircraft filtering
│   ├── filter_police_aircraft.py   # Police aircraft filtering
│   ├── create_ems_database.py      # Database generation
│   ├── opensky_client.py            # OpenSky API client
│   ├── monitor_service.py           # Monitoring service
│   ├── anomaly_detector.py          # Anomaly detection logic
│   ├── monitor_state.py             # State tracking database
│   ├── notifier.py                  # Notification system
│   ├── location_utils.py            # Location/geocoding utilities
│   ├── region_selector.py           # Region selection
│   ├── regions.py                   # Region definitions
│   └── run_monitor.py               # Monitor entry point
├── ReleasableAircraft/      # FAA database files
│   ├── MASTER.txt           # Aircraft registration database
│   ├── ACFTREF.txt          # Aircraft model reference
│   └── ...
├── mediModels.txt           # EMS aircraft models list
├── config.py                # Configuration settings
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Installation

1. **Clone or download this repository**

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up OpenSky API authentication (recommended for better rate limits):**
   
   Create a `credentials.json` file in the project root:
   ```json
   {
     "client_id": "your-client-id",
     "client_secret": "your-client-secret"
   }
   ```
   
   Or copy the example file and edit it:
   ```bash
   cp .env.example .env
   # Then edit .env with your credentials
   ```
   
   **Get your OpenSky API credentials:**
   - Visit: https://opensky-network.org/accounts/login
   - Create an account (free for research/non-commercial use)
   - Create an API Client in your account settings
   - Use the Client ID and Client Secret in your configuration
   
   **Note:** The system uses OAuth2 Client Credentials Flow. Authentication is required for better rate limits and full API access.

## Usage

### Step 1: Generate Aircraft Databases

Filter the FAA database to create filtered datasets:

**For EMS aircraft:**
```bash
python3 src/filter_ems_aircraft.py
```

**For Police aircraft:**
```bash
python3 src/filter_police_aircraft.py
```

These scripts will:
- Parse the FAA MASTER.txt and ACFTREF.txt files
- Filter for aircraft based on models, owner names, and N-number patterns
- Generate databases in JSON format
- Output statistics about the filtering process

The filtered databases will be saved in the `data/` directory.

### Step 2: Run the Monitoring Service

Start monitoring for anomalies:

```bash
python3 src/run_monitor.py
```

You'll be prompted to:
- Select database type (EMS or Police)
- Choose a region to monitor (or use --region flag)

The monitor will:
- Poll the OpenSky API for active aircraft in your selected region
- Match against your aircraft database
- Detect anomalies (speed, altitude, multiple launches, emergency squawks)
- Display notifications with aircraft details and links (FlightAware, Broadcastify)

**Command-line options:**
```bash
python3 src/run_monitor.py --database ems --region west --interval 60
```

### Step 3: Track Aircraft with OpenSky API (Programmatic)

Use the OpenSky client to track EMS aircraft:

```python
from pathlib import Path
from src.opensky_client import OpenSkyClient, load_ems_aircraft_db
import json

# Load EMS aircraft database
db_path = Path("data/ems_aircraft.json")
aircraft_list = load_ems_aircraft_db(db_path)

# Get Mode S codes (ICAO24 hex codes)
mode_s_codes = [ac['mode_s_hex'] for ac in aircraft_list 
                if ac.get('mode_s_hex') and ac['mode_s_hex'].strip()]

# Initialize OpenSky client
# Use environment variables or pass credentials directly
client = OpenSkyClient(
    username=None,  # Optional: set from .env
    password=None,   # Optional: set from .env
    cache_dir=Path("data/cache")
)

# Track aircraft
states = client.get_aircraft_states(mode_s_codes[:10])  # Limit to avoid rate limits

# Process results
for code, state in states.items():
    if state:
        print(f"{code}: {state.get('callsign')} at ({state.get('latitude')}, {state.get('longitude')})")
```

### Example Script

See `src/opensky_client.py` for a complete example in the `main()` function.

## Filtering Strategy

The system uses a multi-tier filtering approach:

1. **Model Matching** (Primary Filter)
   - Matches aircraft model codes against known EMS aircraft models
   - Uses normalized string matching with prefix support
   - Handles FAA model code variations (e.g., BE90, BE20, BE30 for King Air)

2. **Owner Name Keywords** (Secondary Filter)
   - Searches owner names for EMS-related keywords:
     - LIFE, MED, AIRMED, CARE, ANGEL, EMS, HEALTH, HOSPITAL, FLIGHT, AEROMED, MEDICAL, AMBULANCE, RESCUE, EMERGENCY

3. **Exclusions**
   - Piston engine aircraft (TYPE AIRCRAFT = 4, TYPE ENGINE = 1)
   - Airline aircraft (A320, B737, etc.)
   - Inactive registrations (STATUS CODE != 'V')
   - Optionally: Individual owners (configurable)

4. **Confidence Scoring**
   - **High**: Both model match and owner name match
   - **Medium**: Model match only
   - **Low**: Owner name match only

## EMS Aircraft Models

The system recognizes common EMS aircraft models including:

- **Helicopters**: Bell 206, 407, 407GXi, 429, 505, 412, 412EPX, 525
- **Airbus/Eurocopter**: EC135, EC145, H135, H145, H140, AS350, EC130, BO-105, BK-117, AS-365
- **Leonardo/AgustaWestland**: AW109, AW109S, AW109SP, AW119, AW119KX, AW119MKII, A-109, A-139
- **Sikorsky**: S-76
- **Turboprops**: Pilatus PC-12, Beechcraft King Air (BE90, BE20, BE30)
- **Light Jets**: Learjet 35/36/45, Cessna Citation 560/650

See `mediModels.txt` for the complete list.

## OpenSky API Authentication

The OpenSky API uses **Basic Authentication** (username/password). The client supports authentication via:

1. **Environment variables** (`.env` file):
   - `OPENSKY_USERNAME`: Your OpenSky username
   - `OPENSKY_PASSWORD`: Your OpenSky password

2. **Credentials file** (`credentials.json`):
   ```json
   {
     "client_id": "your-client-id",
     "client_secret": "your-client-secret"
   }
   ```

3. **Environment variables** (`.env` file):
   ```bash
   OPENSKY_CLIENT_ID=your-client-id
   OPENSKY_CLIENT_SECRET=your-client-secret
   ```

**Priority order:** credentials.json > environment variables

### Rate Limits

- **Anonymous users**: Limited to recent state vectors only (~10 requests/second)
- **Authenticated users**: Better rate limits and access to historical data

The client implements automatic rate limiting and retry logic. For production use, register for an OpenSky account at https://opensky-network.org/accounts/login.

## Configuration

Edit `config.py` or set environment variables in `.env`:

### Authentication
- `OPENSKY_USERNAME`: OpenSky API username (required for authentication)
- `OPENSKY_PASSWORD`: OpenSky API password (required for authentication)

### Rate Limiting
- `OPENSKY_RATE_LIMIT_CALLS`: Max API calls per period (default: 10)
- `OPENSKY_RATE_LIMIT_PERIOD`: Time period in seconds (default: 1.0)

### Caching
- `CACHE_ENABLED`: Enable response caching (default: true)
- `CACHE_MAX_AGE_SECONDS`: Cache expiration time (default: 60)

### Filtering
- `EXCLUDE_INDIVIDUAL_OWNERS`: Exclude individual owners from results (default: false)
- `MIN_CONFIDENCE_LEVEL`: Minimum confidence level - 'low', 'medium', or 'high' (default: low)

### Regional Tracking
- `TRACKING_REGION`: Region to track - 'northeast', 'midwest', 'south', 'west', 'all', or leave empty for interactive selection

## Data Sources

- **FAA Aircraft Registration Database**: Publicly available aircraft registration data
- **OpenSky Network**: Real-time and historical flight tracking data

## Future Enhancements

- Flight pattern anomaly detection
- Notification system for unusual flight patterns
- Web dashboard for monitoring
- Historical flight pattern analysis
- Integration with emergency services databases

## License

This project is provided as-is for tracking EMS aircraft. Ensure compliance with OpenSky Network API terms of service and FAA data usage policies.

## Troubleshooting

### Authentication Issues

**Problem: Getting 401 Unauthorized errors**

1. **Verify your credentials are correct:**
   - Check that your username and password are spelled correctly
   - Ensure there are no extra spaces or special characters causing issues
   - Verify your account is activated (check email for activation link)

2. **Check your configuration:**
   - If using `.env`, ensure variables are set: `OPENSKY_USERNAME` and `OPENSKY_PASSWORD`
   - If using `credentials.json`, verify the format:
     ```json
     {
       "username": "your_username",
       "password": "your_password"
     }
     ```
   - Note: The old format with `clientId`/`clientSecret` is no longer supported

3. **Test authentication:**
   ```python
   from src.opensky_client import OpenSkyClient
   
   client = OpenSkyClient(
       username="your_username",
       password="your_password"
   )
   
   if client.test_authentication():
       print("✓ Authentication successful")
   else:
       print("✗ Authentication failed - check your credentials")
   ```

4. **Register for an account:**
   - If you don't have an account, register at: https://opensky-network.org/accounts/login
   - Free accounts are available for research and non-commercial use

**Problem: Rate limit errors (429)**

- Reduce `OPENSKY_RATE_LIMIT_CALLS` in your configuration
- Increase `OPENSKY_RATE_LIMIT_PERIOD` to slow down requests
- Enable caching to reduce API calls
- Consider authenticating for better rate limits

**Problem: No aircraft found**

- Aircraft may not be currently in flight
- Aircraft may not be transmitting ADS-B
- Mode S codes in your database may need verification
- Try querying without regional filtering first

## Contributing

Contributions are welcome! Please ensure any changes maintain accuracy in filtering EMS aircraft and respect API rate limits.
