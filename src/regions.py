"""
US Regional definitions for EMS aircraft tracking.

Defines the four US Census regions with their state lists and
geographic bounding boxes for OpenSky API queries.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Region:
    """Represents a US Census region."""
    name: str
    display_name: str
    states: List[str]  # Two-letter state codes
    bbox: Tuple[float, float, float, float]  # (min_lat, min_lon, max_lat, max_lon)


# US Census Regions with bounding boxes
# Bounding boxes are approximate and cover all states in each region
US_REGIONS: Dict[str, Region] = {
    'northeast': Region(
        name='northeast',
        display_name='Northeast',
        states=['ME', 'NH', 'VT', 'MA', 'RI', 'CT', 'NY', 'NJ', 'PA'],
        bbox=(39.0, -80.0, 48.0, -66.0)  # min_lat, min_lon, max_lat, max_lon
    ),
    'midwest': Region(
        name='midwest',
        display_name='Midwest',
        states=['OH', 'MI', 'IN', 'IL', 'WI', 'MN', 'IA', 'MO', 'ND', 'SD', 'NE', 'KS'],
        bbox=(36.0, -104.0, 50.0, -80.0)
    ),
    'south': Region(
        name='south',
        display_name='South',
        states=['DE', 'MD', 'DC', 'VA', 'WV', 'KY', 'TN', 'NC', 'SC', 'GA', 'FL', 
                'AL', 'MS', 'AR', 'LA', 'OK', 'TX'],
        bbox=(24.0, -110.0, 40.0, -75.0)
    ),
    'west': Region(
        name='west',
        display_name='West',
        states=['MT', 'ID', 'WY', 'CO', 'NM', 'AZ', 'UT', 'NV', 'CA', 'OR', 'WA', 'AK', 'HI'],
        bbox=(24.0, -125.0, 72.0, -102.0)
    )
}


def get_region(region_name: str) -> Optional[Region]:
    """
    Get region by name (case-insensitive).
    
    Args:
        region_name: Region name ('northeast', 'midwest', 'south', 'west')
    
    Returns:
        Region object or None if not found
    """
    return US_REGIONS.get(region_name.lower())


def get_all_regions() -> Dict[str, Region]:
    """Get all available regions."""
    return US_REGIONS.copy()


def get_region_list() -> List[Tuple[str, str]]:
    """
    Get list of regions as (key, display_name) tuples.
    
    Returns:
        List of (region_key, display_name) tuples
    """
    return [(key, region.display_name) for key, region in US_REGIONS.items()]


def is_valid_region(region_name: str) -> bool:
    """Check if region name is valid."""
    return region_name.lower() in US_REGIONS


def get_states_for_region(region_name: str) -> Optional[List[str]]:
    """
    Get list of state codes for a region.
    
    Args:
        region_name: Region name
    
    Returns:
        List of two-letter state codes or None if region not found
    """
    region = get_region(region_name)
    return region.states if region else None


def get_bbox_for_region(region_name: str) -> Optional[Tuple[float, float, float, float]]:
    """
    Get bounding box for a region.
    
    Args:
        region_name: Region name
    
    Returns:
        Tuple of (min_lat, min_lon, max_lat, max_lon) or None if region not found
    """
    region = get_region(region_name)
    return region.bbox if region else None


# US State bounding boxes (min_lat, min_lon, max_lat, max_lon)
# Approximate geographic bounding boxes for each state
US_STATES: Dict[str, Tuple[float, float, float, float]] = {
    'AL': (30.144, -88.473, 35.008, -84.889),  # Alabama
    'AK': (51.214, -179.148, 71.538, -129.979),  # Alaska
    'AZ': (31.332, -114.818, 37.004, -109.045),  # Arizona
    'AR': (33.004, -94.618, 36.500, -89.644),  # Arkansas
    'CA': (32.528, -124.482, 42.010, -114.131),  # California
    'CO': (36.993, -109.060, 41.003, -102.042),  # Colorado
    'CT': (40.950, -73.727, 42.050, -71.787),  # Connecticut
    'DE': (38.451, -75.789, 39.839, -75.048),  # Delaware
    'DC': (38.791, -77.120, 38.996, -76.909),  # District of Columbia
    'FL': (24.521, -87.635, 31.001, -80.031),  # Florida
    'GA': (30.356, -85.605, 35.001, -80.840),  # Georgia
    'HI': (18.911, -178.335, 28.402, -154.807),  # Hawaii
    'ID': (41.988, -117.243, 49.001, -111.043),  # Idaho
    'IL': (36.970, -91.513, 42.508, -87.495),  # Illinois
    'IN': (37.771, -88.098, 41.761, -84.785),  # Indiana
    'IA': (40.375, -96.639, 43.501, -90.140),  # Iowa
    'KS': (36.993, -102.052, 40.003, -94.588),  # Kansas
    'KY': (36.497, -89.571, 39.148, -81.964),  # Kentucky
    'LA': (28.928, -94.043, 33.019, -88.817),  # Louisiana
    'ME': (43.075, -71.084, 47.460, -66.949),  # Maine
    'MD': (37.886, -79.488, 39.723, -75.049),  # Maryland
    'MA': (41.187, -73.508, 42.887, -69.858),  # Massachusetts
    'MI': (41.696, -90.418, 48.303, -82.123),  # Michigan
    'MN': (43.499, -97.239, 49.384, -89.491),  # Minnesota
    'MS': (30.144, -91.655, 35.008, -88.098),  # Mississippi
    'MO': (35.996, -95.774, 40.614, -89.099),  # Missouri
    'MT': (44.358, -116.050, 49.001, -104.040),  # Montana
    'NE': (39.999, -104.053, 43.001, -95.309),  # Nebraska
    'NV': (35.002, -120.006, 42.002, -114.040),  # Nevada
    'NH': (42.697, -72.557, 45.305, -70.610),  # New Hampshire
    'NJ': (38.928, -75.559, 41.357, -73.885),  # New Jersey
    'NM': (31.332, -109.050, 37.000, -103.002),  # New Mexico
    'NY': (40.477, -79.762, 45.015, -71.856),  # New York
    'NC': (33.842, -84.322, 36.588, -75.460),  # North Carolina
    'ND': (45.935, -104.050, 49.001, -96.554),  # North Dakota
    'OH': (38.403, -84.820, 41.977, -80.518),  # Ohio
    'OK': (33.619, -103.002, 37.002, -94.431),  # Oklahoma
    'OR': (41.992, -124.566, 46.292, -116.463),  # Oregon
    'PA': (39.720, -80.520, 42.270, -74.689),  # Pennsylvania
    'RI': (41.146, -71.862, 42.019, -71.120),  # Rhode Island
    'SC': (32.035, -83.354, 35.215, -78.542),  # South Carolina
    'SD': (42.480, -104.058, 45.946, -96.436),  # South Dakota
    'TN': (34.983, -90.310, 36.678, -81.647),  # Tennessee
    'TX': (25.837, -106.646, 36.501, -93.508),  # Texas
    'UT': (36.998, -114.053, 42.001, -109.050),  # Utah
    'VT': (42.727, -73.344, 45.016, -71.465),  # Vermont
    'VA': (36.542, -83.675, 39.466, -75.242),  # Virginia
    'WA': (45.543, -124.763, 49.002, -116.916),  # Washington
    'WV': (37.201, -82.644, 40.639, -77.719),  # West Virginia
    'WI': (42.491, -92.889, 47.308, -86.249),  # Wisconsin
    'WY': (40.998, -111.055, 45.006, -104.053),  # Wyoming
}


def get_state_bbox(state_code: str) -> Optional[Tuple[float, float, float, float]]:
    """
    Get bounding box for a state.
    
    Args:
        state_code: Two-letter state code (e.g., 'CA', 'NY')
    
    Returns:
        Tuple of (min_lat, min_lon, max_lat, max_lon) or None if state not found
    """
    return US_STATES.get(state_code.upper())


def get_states_bbox(state_codes: List[str]) -> Optional[Tuple[float, float, float, float]]:
    """
    Get combined bounding box for multiple states.
    
    Args:
        state_codes: List of two-letter state codes (e.g., ['NJ', 'NY', 'PA'])
    
    Returns:
        Tuple of (min_lat, min_lon, max_lat, max_lon) or None if no valid states
    """
    if not state_codes:
        return None
    
    bboxes = []
    for state_code in state_codes:
        bbox = get_state_bbox(state_code)
        if bbox:
            bboxes.append(bbox)
    
    if not bboxes:
        return None
    
    # Combine bounding boxes: min of min_lats, min of min_lons, max of max_lats, max of max_lons
    min_lats = [bbox[0] for bbox in bboxes]
    min_lons = [bbox[1] for bbox in bboxes]
    max_lats = [bbox[2] for bbox in bboxes]
    max_lons = [bbox[3] for bbox in bboxes]
    
    return (min(min_lats), min(min_lons), max(max_lats), max(max_lons))


def is_valid_state_code(state_code: str) -> bool:
    """
    Check if state code is valid.
    
    Args:
        state_code: Two-letter state code
    
    Returns:
        True if valid, False otherwise
    """
    return state_code.upper() in US_STATES


def get_all_state_codes() -> List[str]:
    """
    Get list of all valid state codes.
    
    Returns:
        List of two-letter state codes
    """
    return sorted(US_STATES.keys())
