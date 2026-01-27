"""
Region selection utility for EMS aircraft tracking.

Handles region selection via .env configuration or interactive prompts.
"""

import os
from typing import Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv

from regions import Region, get_region, get_region_list, is_valid_region


def select_region(project_root: Optional[Path] = None) -> Optional[Region]:
    """
    Select tracking region from .env or interactive prompt.
    
    Args:
        project_root: Project root directory (for loading .env)
    
    Returns:
        Selected Region object, or None for "all US" (no filtering)
    """
    # Load .env if project root provided
    if project_root:
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    
    # Check .env first
    region_name = os.getenv("TRACKING_REGION")
    
    if region_name:
        region_name = region_name.strip().lower()
        if region_name == "all" or region_name == "none" or region_name == "":
            return None
        elif is_valid_region(region_name):
            return get_region(region_name)
        else:
            print(f"Warning: Invalid TRACKING_REGION '{region_name}' in .env")
            print("Falling back to interactive selection...\n")
    
    # Interactive selection
    return _interactive_region_selection()


def _interactive_region_selection() -> Optional[Region]:
    """
    Present interactive menu for region selection.
    
    Returns:
        Selected Region object, or None for "all US"
    """
    print("\n" + "=" * 60)
    print("Select Tracking Region")
    print("=" * 60)
    print("\nAvailable regions:")
    print("  1. Northeast")
    print("  2. Midwest")
    print("  3. South")
    print("  4. West")
    print("  5. All US (no regional filter)")
    print("\nNote: You can set TRACKING_REGION in .env to skip this prompt")
    print("      Valid values: 'northeast', 'midwest', 'south', 'west', 'all'")
    print("=" * 60)
    
    while True:
        try:
            choice = input("\nEnter choice (1-5): ").strip()
            
            if choice == "1":
                return get_region("northeast")
            elif choice == "2":
                return get_region("midwest")
            elif choice == "3":
                return get_region("south")
            elif choice == "4":
                return get_region("west")
            elif choice == "5":
                return None
            else:
                print("Invalid choice. Please enter 1, 2, 3, 4, or 5.")
        except (EOFError, KeyboardInterrupt):
            print("\n\nCancelled. Using 'All US' (no filter).")
            return None
        except Exception as e:
            print(f"Error: {e}. Please try again.")


def get_region_info(region: Optional[Region]) -> str:
    """
    Get formatted information string about a region.
    
    Args:
        region: Region object or None
    
    Returns:
        Formatted string with region information
    """
    if region is None:
        return "All US (no regional filter)"
    
    states_str = ", ".join(region.states)
    bbox = region.bbox
    return (f"{region.display_name} Region\n"
            f"  States: {states_str}\n"
            f"  Bounding Box: ({bbox[0]:.2f}, {bbox[1]:.2f}) to ({bbox[2]:.2f}, {bbox[3]:.2f})")


def filter_aircraft_by_region(aircraft_list: list, region: Optional[Region]) -> list:
    """
    Filter aircraft list by region based on owner_state.
    
    Args:
        aircraft_list: List of aircraft dictionaries
        region: Region object or None (for all)
    
    Returns:
        Filtered list of aircraft
    """
    if region is None:
        return aircraft_list
    
    region_states = set(state.upper() for state in region.states)
    
    filtered = [
        ac for ac in aircraft_list
        if ac.get('owner_state', '').strip().upper() in region_states
    ]
    
    return filtered
