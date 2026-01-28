"""
Location utilities for reverse geocoding and generating radio broadcast links.
"""

import requests
from typing import Optional, Dict
import time
from pathlib import Path

# Rate limiting for Nominatim API (max 1 request per second)
_last_geocode_time = 0

# County code mapping cache
_county_code_map: Optional[Dict[tuple, int]] = None

# State name to abbreviation mapping
_STATE_NAME_TO_ABBR = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
    'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
    'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
    'wisconsin': 'WI', 'wyoming': 'WY', 'district of columbia': 'DC'
}


def _load_county_codes() -> Dict[tuple, int]:
    """
    Load county codes from counties.txt file.
    
    Returns:
        Dictionary mapping (county_name_lower, state_abbr) -> county_code
    """
    global _county_code_map
    
    if _county_code_map is not None:
        return _county_code_map
    
    _county_code_map = {}
    
    # Find counties.txt file - try current directory and parent directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    counties_file = project_root / 'counties.txt'
    
    if not counties_file.exists():
        # Try current directory
        counties_file = Path('counties.txt')
    
    if not counties_file.exists():
        # Return empty dict if file not found
        return _county_code_map
    
    try:
        with open(counties_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Format: code\tcounty_name\tstate_abbr
                parts = line.split('\t')
                if len(parts) >= 3:
                    try:
                        code = int(parts[0])
                        county_name = parts[1].strip()
                        state_abbr = parts[2].strip().upper()
                        
                        # Normalize county name (remove common suffixes, lowercase)
                        county_normalized = county_name.lower()
                        # Remove " County", " Parish", etc. for matching
                        for suffix in [' county', ' parish', ' borough', ' municipality']:
                            if county_normalized.endswith(suffix):
                                county_normalized = county_normalized[:-len(suffix)]
                        
                        # Store both with and without suffix for flexible matching
                        key = (county_normalized, state_abbr)
                        _county_code_map[key] = code
                        
                        # Also store with original county name
                        key_original = (county_name.lower(), state_abbr)
                        _county_code_map[key_original] = code
                        
                    except (ValueError, IndexError):
                        # Skip malformed lines
                        continue
    except Exception:
        # If file can't be read, return empty dict
        pass
    
    return _county_code_map


def _normalize_state(state: str) -> str:
    """
    Convert state name to abbreviation.
    
    Args:
        state: State name or abbreviation
        
    Returns:
        Two-letter state abbreviation (uppercase)
    """
    if not state:
        return ''
    
    state_upper = state.upper().strip()
    
    # If already a 2-letter abbreviation, return it
    if len(state_upper) == 2:
        return state_upper
    
    # Try to find abbreviation from full name
    state_lower = state.lower().strip()
    return _STATE_NAME_TO_ABBR.get(state_lower, state_upper)


def _normalize_county(county: str) -> str:
    """
    Normalize county name for matching.
    
    Args:
        county: County name
        
    Returns:
        Normalized county name (lowercase, without common suffixes)
    """
    if not county:
        return ''
    
    county_lower = county.lower().strip()
    
    # Remove common suffixes
    for suffix in [' county', ' parish', ' borough', ' municipality']:
        if county_lower.endswith(suffix):
            county_lower = county_lower[:-len(suffix)].strip()
    
    return county_lower


def get_county_from_coordinates(latitude: float, longitude: float) -> Optional[Dict[str, str]]:
    """
    Get county name and state from latitude/longitude using Nominatim (OpenStreetMap).
    
    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        
    Returns:
        Dictionary with 'county' and 'state' keys, or None if lookup fails
    """
    global _last_geocode_time
    
    if latitude is None or longitude is None:
        return None
    
    try:
        # Rate limiting: Nominatim allows max 1 request per second
        # But don't block for too long - cap the delay at 1 second
        current_time = time.time()
        time_since_last = current_time - _last_geocode_time
        if time_since_last < 1.0:
            sleep_time = min(1.0 - time_since_last, 1.0)  # Cap at 1 second
            time.sleep(sleep_time)
        _last_geocode_time = time.time()
        
        # Use Nominatim (OpenStreetMap) reverse geocoding API
        # Free, no API key required, but has rate limits
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            'lat': latitude,
            'lon': longitude,
            'format': 'json',
            'addressdetails': 1
        }
        headers = {
            'User-Agent': 'MediTrack-Aircraft-Monitor/1.0'  # Required by Nominatim
        }
        
        # Use shorter timeout to avoid blocking
        response = requests.get(url, params=params, headers=headers, timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            address = data.get('address', {})
            
            # Extract county (may be called 'county' or 'municipality' in different regions)
            county = address.get('county') or address.get('municipality') or address.get('city')
            
            # Extract state
            state = address.get('state') or address.get('region')
            
            if county and state:
                return {
                    'county': county,
                    'state': state
                }
        
        return None
        
    except Exception as e:
        # Silently fail - we don't want to break the monitoring service
        # if geocoding is unavailable
        return None


def get_location_name_from_coordinates(latitude: float, longitude: float, skip_rate_limit: bool = False) -> Optional[Dict[str, str]]:
    """
    Get location name (city, county, state) from coordinates.
    
    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        skip_rate_limit: If True, skip rate limiting sleep (for async calls)
        
    Returns:
        Dictionary with 'city', 'county', 'state' keys, or None if lookup fails
    """
    global _last_geocode_time
    
    if latitude is None or longitude is None:
        return None
    
    try:
        # Rate limiting: Nominatim allows max 1 request per second
        # Only sleep if not skipping (for async/threaded calls)
        if not skip_rate_limit:
            current_time = time.time()
            time_since_last = current_time - _last_geocode_time
            if time_since_last < 1.0:
                sleep_time = min(1.0 - time_since_last, 1.0)
                time.sleep(sleep_time)
            _last_geocode_time = time.time()
        else:
            # Still update timestamp for rate limiting tracking
            _last_geocode_time = time.time()
        
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            'lat': latitude,
            'lon': longitude,
            'format': 'json',
            'addressdetails': 1
        }
        headers = {
            'User-Agent': 'MediTrack-Aircraft-Monitor/1.0'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            address = data.get('address', {})
            
            # Extract city, county, state
            city = address.get('city') or address.get('town') or address.get('village')
            county = address.get('county') or address.get('municipality')
            state = address.get('state') or address.get('region')
            
            # Build location name
            location_parts = []
            if city:
                location_parts.append(city)
            if county and county != city:  # Don't duplicate if same
                location_parts.append(county)
            if state:
                location_parts.append(state)
            
            if location_parts:
                return {
                    'city': city,
                    'county': county,
                    'state': state,
                    'display': ', '.join(location_parts)
                }
        
        return None
        
    except Exception:
        return None


def get_broadcastify_url(latitude: float, longitude: float) -> Optional[str]:
    """
    Generate a Broadcastify search URL for the nearest county's PD radio feed.
    
    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        
    Returns:
        Broadcastify search URL, or None if county lookup fails
    """
    location_info = get_county_from_coordinates(latitude, longitude)
    
    if not location_info:
        return None
    
    county = location_info.get('county', '')
    state = location_info.get('state', '')
    
    if not county or not state:
        return None
    
    # Generate Broadcastify search URL
    # Format: https://www.broadcastify.com/listen/?ctid={county_id}
    # Since we don't have county IDs, we'll use a search URL with county and state
    # This will let users find the appropriate feed
    county_clean = county.replace(' ', '-').replace("'", '').lower()
    state_clean = state.replace(' ', '-').lower()
    
    # Broadcastify search URL - users can search by county/state
    # Alternative: direct search URL
    search_query = f"{county} {state} police"
    url = f"https://www.broadcastify.com/listen/?q={search_query.replace(' ', '+')}"
    
    return url


def _try_get_broadcastify_ctid(county: str, state: str) -> Optional[int]:
    """
    Get Broadcastify county ID (ctid) from counties.txt mapping.
    
    Args:
        county: County name (e.g., "Kern" or "Kern County")
        state: State name or abbreviation (e.g., "California" or "CA")
        
    Returns:
        ctid (county code) if found, None otherwise
    """
    if not county or not state:
        return None
    
    # Load county codes
    county_map = _load_county_codes()
    if not county_map:
        return None
    
    # Normalize state to abbreviation
    state_abbr = _normalize_state(state)
    if not state_abbr:
        return None
    
    # Normalize county name
    county_normalized = _normalize_county(county)
    
    # Try exact match first
    key = (county_normalized, state_abbr)
    if key in county_map:
        return county_map[key]
    
    # Try with original county name (in case it had a suffix we removed)
    county_original = county.lower().strip()
    key_original = (county_original, state_abbr)
    if key_original in county_map:
        return county_map[key_original]
    
    # No match found
    return None


def get_broadcastify_url_simple(latitude: float, longitude: float) -> Optional[str]:
    """
    Generate a Broadcastify URL for the nearest county's PD radio feed.
    
    Broadcastify uses county IDs (ctid) in URLs like: /listen/ctid/197
    This function uses the counties.txt mapping to find the correct ctid
    and generate a direct link. If no mapping is found, falls back to a search URL.
    
    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        
    Returns:
        Broadcastify URL with ctid if found, search URL otherwise, or None on error
    """
    try:
        location_info = get_county_from_coordinates(latitude, longitude)
        
        if location_info:
            county = location_info.get('county', '')
            state = location_info.get('state', '')
            if county and state:
                # Try to get ctid first
                ctid = _try_get_broadcastify_ctid(county, state)
                if ctid:
                    # Use direct ctid URL if we have it
                    return f"https://www.broadcastify.com/listen/ctid/{ctid}"
                
                # Otherwise, use search URL
                # Clean county name (remove "County" suffix if present)
                county_clean = county.replace(' County', '').replace(' Parish', '').strip()
                
                # Use a search URL that's more likely to find the county page
                # Format: /listen/?q=county+state (Broadcastify search)
                search_query = f"{county_clean} {state}"
                # URL encode the search query
                from urllib.parse import quote_plus
                encoded_query = quote_plus(search_query)
                return f"https://www.broadcastify.com/listen/?q={encoded_query}"
        
        # Fallback: general police radio search
        return "https://www.broadcastify.com/listen/"
    except Exception:
        # Return None on any error - let the caller handle it
        return None
