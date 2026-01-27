"""
OpenSky API client with rate limiting for tracking EMS aircraft.

This module provides a rate-limited interface to the OpenSky Network API
for tracking EMS/emergency medical service aircraft.
"""

import time
import json
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from functools import wraps
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""
    
    def __init__(self, max_calls: int, period: float):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed
            period: Time period in seconds
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = []
    
    def __call__(self, func):
        """Decorator for rate limiting."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            # Remove calls outside the time window
            self.calls = [call_time for call_time in self.calls 
                         if now - call_time < self.period]
            
            # Wait if we've hit the limit
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0]) + 0.1
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    # Recalculate after sleep
                    now = time.time()
                    self.calls = [call_time for call_time in self.calls 
                                 if now - call_time < self.period]
            
            # Record this call
            self.calls.append(now)
            
            return func(*args, **kwargs)
        
        return wrapper


class OpenSkyClient:
    """
    OpenSky Network API client with rate limiting and error handling.
    
    Supports both Basic Auth (username/password) and OAuth2 client credentials.
    OpenSky API documentation: https://openskynetwork.github.io/opensky-api/
    """
    
    BASE_URL = "https://opensky-network.org/api"
    TOKEN_URL = "https://opensky-network.org/api/oauth/token"
    
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None,
                 client_id: Optional[str] = None, client_secret: Optional[str] = None,
                 credentials_file: Optional[Path] = None,
                 rate_limit_calls: int = 10, rate_limit_period: float = 1.0,
                 cache_dir: Optional[Path] = None):
        """
        Initialize OpenSky client.
        
        Args:
            username: OpenSky username (optional, for Basic Auth)
            password: OpenSky password (optional, for Basic Auth)
            client_id: OAuth2 client ID (optional, for OAuth2)
            client_secret: OAuth2 client secret (optional, for OAuth2)
            credentials_file: Path to credentials.json file (optional)
            rate_limit_calls: Max API calls per period
            rate_limit_period: Time period in seconds for rate limiting
            cache_dir: Directory for caching API responses
        """
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        
        # Load OAuth2/client credentials from file if provided
        use_client_creds_for_basic = False
        if credentials_file and credentials_file.exists():
            try:
                with open(credentials_file, 'r') as f:
                    creds = json.load(f)
                    self.client_id = creds.get('clientId') or creds.get('client_id')
                    self.client_secret = creds.get('clientSecret') or creds.get('client_secret')
                    # If we have client credentials but no username/password, use them for Basic Auth
                    if self.client_id and self.client_secret and not username and not password:
                        username = self.client_id
                        password = self.client_secret
                        use_client_creds_for_basic = True
            except Exception as e:
                print(f"Warning: Could not load credentials from {credentials_file}: {e}")
        
        # Update username/password if we set them from client credentials
        if use_client_creds_for_basic:
            self.username = username
            self.password = password
        
        # Determine authentication method
        self.use_basic_auth = (self.username is not None and self.password is not None) or use_client_creds_for_basic
        self.use_oauth2 = self.client_id is not None and self.client_secret is not None and not self.use_basic_auth
        self.authenticated = self.use_oauth2 or self.use_basic_auth
        
        # OAuth2 token management
        self.access_token = None
        self.token_expires_at = 0
        
        # Rate limiter
        self.rate_limiter = RateLimiter(rate_limit_calls, rate_limit_period)
        
        # Cache directory
        self.cache_dir = cache_dir
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup requests session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        
        # Auth for authenticated requests
        if self.use_basic_auth:
            self.session.auth = (username, password)
        # OAuth2 token will be added in _get_access_token()
    
    def _get_access_token(self) -> Optional[str]:
        """
        Get OAuth2 access token using client credentials flow.
        
        Returns:
            Access token string or None if failed
        """
        if not self.use_oauth2:
            return None
        
        # Check if we have a valid cached token
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token
        
        # Request new token
        try:
            response = requests.post(
                self.TOKEN_URL,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                },
                timeout=10
            )
            response.raise_for_status()
            token_data = response.json()
            
            self.access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 3600)  # Default 1 hour
            self.token_expires_at = time.time() + expires_in - 60  # Refresh 1 min early
            
            return self.access_token
        except Exception as e:
            print(f"Error getting OAuth2 token: {e}")
            return None
    
    def test_authentication(self) -> bool:
        """
        Test if authentication credentials are valid.
        
        Returns:
            True if authentication works, False otherwise
        """
        if not self.authenticated:
            return False
        
        try:
            # For OAuth2, get token first
            if self.use_oauth2:
                token = self._get_access_token()
                if not token:
                    return False
            
            # Try a simple endpoint that requires auth
            # Using a minimal request to test auth
            test_url = f"{self.BASE_URL}/states/all"
            response = self.session.get(test_url, params={'time': 0}, timeout=5)
            # 200 or 400 (bad time) means auth worked, 401 means auth failed
            return response.status_code != 401
        except:
            return False
    
    def _get_cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate cache key for endpoint and parameters."""
        key = f"{endpoint}_{json.dumps(params, sort_keys=True)}"
        # Sanitize for filename
        key = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in key)
        return key[:100]  # Limit length
    
    def _get_cached_response(self, cache_key: str, max_age_seconds: int = 60) -> Optional[Dict]:
        """Get cached response if available and not expired."""
        if not self.cache_dir:
            return None
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        if not cache_file.exists():
            return None
        
        # Check age
        file_age = time.time() - cache_file.stat().st_mtime
        if file_age > max_age_seconds:
            return None
        
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    
    def _cache_response(self, cache_key: str, data: Dict) -> None:
        """Cache API response."""
        if not self.cache_dir:
            return
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass  # Ignore cache errors
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None, 
                     use_cache: bool = True, cache_max_age: int = 60) -> Dict:
        """
        Make API request with rate limiting and caching.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters
            use_cache: Whether to use cached responses
            cache_max_age: Maximum age of cached response in seconds
        
        Returns:
            JSON response as dictionary
        """
        # Check cache first (before rate limiting)
        cache_key = None
        if use_cache:
            cache_key = self._get_cache_key(endpoint, params)
            cached = self._get_cached_response(cache_key, cache_max_age)
            if cached:
                return cached
        
        # Apply rate limiting only for actual API requests
        @self.rate_limiter
        def _do_request():
            url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
            
            # Add OAuth2 Bearer token if using OAuth2
            headers = {}
            if self.use_oauth2:
                token = self._get_access_token()
                if token:
                    headers['Authorization'] = f'Bearer {token}'
            
            try:
                response = self.session.get(url, params=params, headers=headers, timeout=10)
                
                # Handle authentication errors with more detail
                if response.status_code == 401:
                    error_msg = "Authentication failed (401 Unauthorized)"
                    if self.authenticated:
                        error_msg += f"\n  Username: {self.username}"
                        error_msg += "\n  The provided credentials appear to be incorrect or invalid"
                        error_msg += "\n  Please verify your OpenSky credentials in .env file"
                        error_msg += "\n  Register or check your account at: https://opensky-network.org/accounts/login"
                        error_msg += "\n\n  Common issues:"
                        error_msg += "\n    - Username or password may be incorrect"
                        error_msg += "\n    - Account may not be activated"
                        error_msg += "\n    - Special characters in password may need URL encoding"
                    else:
                        error_msg += "\n  This endpoint requires authentication"
                        error_msg += "\n  Set OPENSKY_USERNAME and OPENSKY_PASSWORD in .env"
                        error_msg += "\n  Register at: https://opensky-network.org/accounts/login"
                    
                    # Try to get error details from response
                    try:
                        error_data = response.json()
                        if 'message' in error_data:
                            error_msg += f"\n  API message: {error_data['message']}"
                    except:
                        pass
                    
                    raise Exception(error_msg)
                
                response.raise_for_status()
                data = response.json()
                
                # Cache successful response
                if use_cache and response.status_code == 200:
                    # Use the cache_key from outer scope, or compute if needed
                    cache_key_to_use = cache_key if cache_key else self._get_cache_key(endpoint, params)
                    self._cache_response(cache_key_to_use, data)
                
                return data
            
            except requests.exceptions.HTTPError as e:
                # Re-raise our custom 401 error
                if "Authentication failed" in str(e):
                    raise
                raise Exception(f"OpenSky API HTTP error: {e}")
            except requests.exceptions.RequestException as e:
                raise Exception(f"OpenSky API request failed: {e}")
        
        return _do_request()
    
    def get_states(self, icao24: Optional[List[str]] = None, 
                   bbox: Optional[tuple] = None) -> Dict:
        """
        Get current state vectors of aircraft.
        
        Args:
            icao24: List of ICAO24 addresses (Mode S hex codes)
            bbox: Bounding box (min_latitude, min_longitude, max_latitude, max_longitude)
        
        Returns:
            Dictionary with 'time' and 'states' (list of state vectors)
        """
        params = {}
        
        if icao24:
            params['icao24'] = ','.join(icao24)
        
        if bbox:
            params['lamin'] = bbox[0]
            params['lomin'] = bbox[1]
            params['lamax'] = bbox[2]
            params['lomax'] = bbox[3]
        
        return self._make_request("states/all", params=params, cache_max_age=5)
    
    def get_regional_states(self, bbox: tuple, icao24: Optional[List[str]] = None) -> Dict:
        """
        Get current state vectors for aircraft in a specific geographic region.
        
        Args:
            bbox: Bounding box (min_latitude, min_longitude, max_latitude, max_longitude)
            icao24: Optional list of specific ICAO24 addresses to filter
                   Note: If provided, filtering is done client-side after query
        
        Returns:
            Dictionary with 'time' and 'states' (list of state vectors)
        """
        # If icao24 is provided, we can't combine with bbox in API call
        # So query by bbox only to get all aircraft in region
        if icao24:
            # For specific aircraft, query by icao24 and filter client-side
            # This is handled by get_aircraft_states with region_bbox parameter
            raise ValueError("Use get_aircraft_states() with region_bbox parameter for specific aircraft")
        
        # Query all aircraft in bbox
        return self.get_states(icao24=None, bbox=bbox)
    
    def get_aircraft_states(self, mode_s_codes: List[str], region_bbox: Optional[tuple] = None) -> Dict[str, Optional[Dict]]:
        """
        Get current states for specific aircraft by Mode S codes.
        
        Args:
            mode_s_codes: List of Mode S hex codes (ICAO24)
            region_bbox: Optional bounding box tuple (min_lat, min_lon, max_lat, max_lon) for regional filtering
                       Note: OpenSky API doesn't support combining icao24 and bbox, so filtering is done client-side
        
        Returns:
            Dictionary mapping Mode S code to state vector (or None if not found)
        """
        # OpenSky expects uppercase ICAO24 codes
        icao24_list = [code.upper().strip() for code in mode_s_codes if code.strip()]
        
        if not icao24_list:
            return {}
        
        # OpenSky limits to 1000 aircraft per request
        # Note: OpenSky API doesn't allow combining icao24 and bbox parameters
        # So we query by icao24 only, then filter by bbox client-side
        results = {}
        batch_size = 1000
        
        for i in range(0, len(icao24_list), batch_size):
            batch = icao24_list[i:i + batch_size]
            # Query by icao24 only (bbox filtering done client-side)
            response = self.get_states(icao24=batch, bbox=None)
            
            # Handle response - check if it's valid
            if not response:
                # Mark all as not found
                for code in batch:
                    results[code.upper()] = None
                continue
            
            # Parse state vectors - handle None or missing 'states' key
            # OpenSky API returns {'time': ..., 'states': [...]} or {'time': ..., 'states': None}
            states = response.get('states') if response else None
            
            # Handle different cases: None, empty list, or actual list
            if states is None:
                # Check if there's an error message in the response
                if response and 'error' in response:
                    print(f"API Error: {response.get('error')}")
                # If 'states' is None, that's normal - no aircraft currently in range
                # (This is different from missing key - None means valid response with no data)
                states = []
            elif not isinstance(states, list):
                # If states is not a list, something went wrong
                print(f"Warning: Unexpected response format. States type: {type(states)}, value: {states}")
                states = []
            # If states is already a list (even if empty), use it as-is
            
            for state in states:
                if state and len(state) >= 1:
                    icao24 = state[0].upper()
                    latitude = state[6] if len(state) > 6 and state[6] else None
                    longitude = state[5] if len(state) > 5 and state[5] else None
                    
                    # Filter by bbox if provided (client-side filtering)
                    if region_bbox:
                        min_lat, min_lon, max_lat, max_lon = region_bbox
                        # Only include if coordinates are within bbox
                        if latitude is None or longitude is None:
                            # No position data, exclude from results
                            continue
                        if not (min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon):
                            # Outside bbox, exclude from results
                            continue
                    
                    results[icao24] = {
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
                        'position_source': state[16] if len(state) > 16 and state[16] else None
                    }
            
            # Mark missing aircraft (only those we queried for, not filtered out by bbox)
            for code in batch:
                if code.upper() not in results:
                    results[code.upper()] = None
        
        return results
    
    def track_aircraft(self, mode_s_code: str) -> Optional[Dict]:
        """
        Track a specific aircraft by Mode S code.
        
        Args:
            mode_s_code: ICAO24 hex code
        
        Returns:
            State vector dictionary or None if not found
        """
        results = self.get_aircraft_states([mode_s_code])
        return results.get(mode_s_code.upper())
    
    def get_flights_by_aircraft(self, icao24: str, begin: int, end: int) -> List[Dict]:
        """
        Get flights for a specific aircraft within a time range.
        
        Args:
            icao24: ICAO24 address
            begin: Start time as Unix timestamp
            end: End time as Unix timestamp
        
        Returns:
            List of flight dictionaries
        """
        if not self.authenticated:
            raise Exception("Historical flight data requires authentication")
        
        params = {
            'icao24': icao24.upper(),
            'begin': begin,
            'end': end
        }
        
        response = self._make_request("flights/aircraft", params=params, 
                                     use_cache=True, cache_max_age=3600)
        return response.get('data', [])
    
    def get_arrivals_by_airport(self, airport: str, begin: int, end: int) -> List[Dict]:
        """
        Get arrivals at an airport within a time range.
        
        Args:
            airport: ICAO airport code
            begin: Start time as Unix timestamp
            end: End time as Unix timestamp
        
        Returns:
            List of arrival flight dictionaries
        """
        if not self.authenticated:
            raise Exception("Airport data requires authentication")
        
        params = {
            'airport': airport.upper(),
            'begin': begin,
            'end': end
        }
        
        response = self._make_request("flights/arrival", params=params,
                                     use_cache=True, cache_max_age=3600)
        return response.get('data', [])
    
    def get_departures_by_airport(self, airport: str, begin: int, end: int) -> List[Dict]:
        """
        Get departures from an airport within a time range.
        
        Args:
            airport: ICAO airport code
            begin: Start time as Unix timestamp
            end: End time as Unix timestamp
        
        Returns:
            List of departure flight dictionaries
        """
        if not self.authenticated:
            raise Exception("Airport data requires authentication")
        
        params = {
            'airport': airport.upper(),
            'begin': begin,
            'end': end
        }
        
        response = self._make_request("flights/departure", params=params,
                                     use_cache=True, cache_max_age=3600)
        return response.get('data', [])


def load_ems_aircraft_db(db_path: Path) -> List[Dict]:
    """
    Load EMS aircraft from generated database.
    
    Args:
        db_path: Path to SQLite database or JSON file
    
    Returns:
        List of aircraft dictionaries
    """
    if db_path.suffix == '.json':
        with open(db_path, 'r') as f:
            data = json.load(f)
            return data.get('aircraft', [])
    elif db_path.suffix == '.db':
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ems_aircraft")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    else:
        raise ValueError(f"Unsupported database format: {db_path.suffix}")


def main():
    """Example usage of OpenSky client with regional filtering."""
    from pathlib import Path
    from region_selector import select_region, get_region_info, filter_aircraft_by_region
    
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "ems_aircraft.json"
    
    # Load EMS aircraft
    if db_path.exists():
        aircraft_list = load_ems_aircraft_db(db_path)
        print(f"Loaded {len(aircraft_list)} EMS aircraft from database")
        
        # Select region (from .env or interactive)
        region = select_region(project_root)
        
        # Filter aircraft by region (state-based pre-filtering)
        if region:
            aircraft_list = filter_aircraft_by_region(aircraft_list, region)
            print(f"\nFiltered to {len(aircraft_list)} aircraft in {region.display_name} region")
            print(f"  States: {', '.join(region.states)}")
        
        # Get Mode S codes
        mode_s_codes = [ac['mode_s_hex'] for ac in aircraft_list 
                       if ac.get('mode_s_hex') and ac['mode_s_hex'].strip()]
        mode_s_codes = [code for code in mode_s_codes if code.strip()]
        
        print(f"Found {len(mode_s_codes)} aircraft with Mode S codes")
        
        # Initialize client (try credentials.json first, then .env username/password)
        import os
        credentials_file = project_root / "credentials.json"
        
        # Try credentials.json first (client credentials)
        if credentials_file.exists():
            client = OpenSkyClient(
                credentials_file=credentials_file,
                cache_dir=project_root / "data" / "cache"
            )
            if client.authenticated:
                if client.use_basic_auth:
                    print("Using Basic Auth with client credentials (from credentials.json)")
                elif client.use_oauth2:
                    print("Using OAuth2 authentication (from credentials.json)")
                # Test authentication
                if not client.test_authentication():
                    print("Warning: Authentication test failed.")
                    print("  Please verify your credentials.json file is correct.")
                else:
                    print("✓ Authentication successful")
        else:
            # Fall back to username/password from .env
            username = os.getenv('OPENSKY_USERNAME')
            password = os.getenv('OPENSKY_PASSWORD')
            
            client = OpenSkyClient(
                username=username,
                password=password,
                cache_dir=project_root / "data" / "cache"
            )
            
            if username:
                print(f"Using Basic Auth (username: {username})")
                # Test authentication
                if not client.test_authentication():
                    print("Warning: Authentication test failed. Credentials may be incorrect.")
                    print("  The API may still work, but you may encounter 401 errors.")
                    print("  Please verify your credentials at https://opensky-network.org/accounts/login")
            else:
                print("Using anonymous access (register at https://openskynetwork.org for better rate limits)")
                print("Note: Some endpoints may require authentication")
        
        # Get bounding box for region (if region selected)
        region_bbox = region.bbox if region else None
        
        # Track a sample of aircraft (limit to avoid rate limits)
        sample_codes = mode_s_codes[:20] if len(mode_s_codes) > 20 else mode_s_codes
        print(f"\nTracking {len(sample_codes)} aircraft" + (f" in {region.display_name} region" if region else "") + "...")
        
        # Use regional bbox filtering if region is selected
        states = client.get_aircraft_states(sample_codes, region_bbox=region_bbox)
        
        active_count = sum(1 for state in states.values() if state is not None)
        print(f"Found {active_count} active aircraft" + (f" in {region.display_name} region" if region else ""))
        
        # Print active aircraft
        if active_count > 0:
            print("\nActive EMS Aircraft:")
            print("-" * 80)
            for code, state in states.items():
                if state:
                    # Find aircraft info
                    aircraft_info = next((ac for ac in aircraft_list if ac.get('mode_s_hex', '').strip().upper() == code.upper()), None)
                    n_number = aircraft_info.get('n_number', 'N/A') if aircraft_info else 'N/A'
                    model = aircraft_info.get('model_name', 'N/A') if aircraft_info else 'N/A'
                    owner = aircraft_info.get('owner_name', 'N/A')[:40] if aircraft_info else 'N/A'
                    
                    print(f"\nN-{n_number} ({code}) - {model}")
                    print(f"  Owner: {owner}")
                    print(f"  Callsign: {state.get('callsign', 'N/A')}")
                    if state.get('latitude') and state.get('longitude'):
                        print(f"  Position: {state.get('latitude'):.4f}, {state.get('longitude'):.4f}")
                    if state.get('baro_altitude'):
                        print(f"  Altitude: {state.get('baro_altitude')} m ({state.get('baro_altitude') * 3.28084:.0f} ft)")
                    if state.get('velocity'):
                        print(f"  Velocity: {state.get('velocity')} m/s ({state.get('velocity') * 1.94384:.1f} knots)")
                    if state.get('on_ground') is not None:
                        print(f"  On Ground: {state.get('on_ground')}")
                    if state.get('origin_country'):
                        print(f"  Country: {state.get('origin_country')}")
        else:
            print("\nNo active aircraft found in this sample.")
            if region:
                print(f"This could mean no EMS aircraft are currently flying in the {region.display_name} region.")
            else:
                print("This could mean:")
                print("  - The aircraft are not currently in flight")
                print("  - They're not transmitting ADS-B")
                print("  - The Mode S codes might need verification")
    else:
        print(f"EMS aircraft database not found at {db_path}")
        print("Run create_ems_database.py first to generate the database")


if __name__ == "__main__":
    main()
