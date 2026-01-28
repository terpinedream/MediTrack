"""
Location utilities for reverse geocoding and generating radio broadcast links.
"""

import requests
from typing import Optional, Dict
import time

# Rate limiting for Nominatim API (max 1 request per second)
_last_geocode_time = 0


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
    Try to get Broadcastify county ID (ctid) by searching.
    
    Note: This is a placeholder. Without an API or database mapping,
    we can't reliably get ctid values. This could be enhanced with:
    - A static mapping file of county names to ctid values
    - Scraping RadioReference/Broadcastify
    - Using a third-party API if available
    
    Args:
        county: County name
        state: State name or abbreviation
        
    Returns:
        ctid if found, None otherwise
    """
    # TODO: Implement county-to-ctid mapping
    # For now, return None to use search URL instead
    return None


def get_broadcastify_url_simple(latitude: float, longitude: float) -> Optional[str]:
    """
    Generate a Broadcastify URL for the nearest county's PD radio feed.
    
    Broadcastify uses county IDs (ctid) in URLs like: /listen/ctid/1792
    Since we don't have a mapping of county names to ctid values, we'll use
    a search URL that should help users find the right county feed.
    
    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        
    Returns:
        Broadcastify URL, or None on error
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
