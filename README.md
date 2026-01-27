# MediTrack - EMS Aircraft Tracking System

A system for tracking and monitoring Emergency Medical Service (EMS) aircraft in the United States using the OpenSky Network API.

## Overview

MediTrack filters the FAA aircraft registration database to identify EMS/emergency medical service aircraft, then tracks them via the OpenSky Network API. The system is designed to:

- Accurately identify EMS aircraft from the FAA database
- Track active flights in real-time
- Flag unusual flight patterns that may indicate emergencies
- Provide rate-limited API access to minimize API usage

## Features

- **Multi-criteria filtering**: Identifies EMS aircraft by model type and owner name keywords
- **Confidence scoring**: Categorizes matches as high, medium, or low confidence
- **Multiple output formats**: Generates JSON, CSV, and SQLite databases
- **Rate-limited API client**: Respects OpenSky API rate limits with automatic retry logic
- **Response caching**: Reduces API calls by caching responses

## Project Structure

```
MediTrack/
├── data/                    # Generated databases and cache
│   ├── ems_aircraft.json    # JSON format database
│   ├── ems_aircraft.csv     # CSV format database
│   ├── ems_aircraft.db      # SQLite database
│   └── cache/               # API response cache
├── src/                     # Source code
│   ├── filter_ems_aircraft.py    # FAA database filtering
│   ├── create_ems_database.py    # Database generation
│   └── opensky_client.py          # OpenSky API client
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

3. **Set up environment variables (optional but recommended):**
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenSky credentials if you have them
   ```

## Usage

### Step 1: Generate EMS Aircraft Database

Filter the FAA database to create a filtered dataset of EMS aircraft:

```bash
cd src
python create_ems_database.py
```

This will:
- Parse the FAA MASTER.txt and ACFTREF.txt files
- Filter for EMS aircraft based on models and owner names
- Generate databases in JSON, CSV, and SQLite formats
- Output statistics about the filtering process

The filtered databases will be saved in the `data/` directory.

### Step 2: Track Aircraft with OpenSky API

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

## OpenSky API Rate Limits

- **Anonymous users**: Limited to recent state vectors only
- **Authenticated users**: Better rate limits and access to historical data

The client implements automatic rate limiting and retry logic. For production use, register for an OpenSky account at https://opensky-network.org/accounts/login and add your credentials to `.env`.

## Configuration

Edit `config.py` or set environment variables in `.env`:

- `OPENSKY_USERNAME`: OpenSky API username
- `OPENSKY_PASSWORD`: OpenSky API password
- `OPENSKY_RATE_LIMIT_CALLS`: Max API calls per period (default: 10)
- `OPENSKY_RATE_LIMIT_PERIOD`: Time period in seconds (default: 1.0)
- `CACHE_ENABLED`: Enable response caching (default: true)
- `CACHE_MAX_AGE_SECONDS`: Cache expiration time (default: 60)

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

## Contributing

Contributions are welcome! Please ensure any changes maintain accuracy in filtering EMS aircraft and respect API rate limits.
