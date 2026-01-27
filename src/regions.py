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
