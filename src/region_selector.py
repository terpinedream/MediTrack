"""
Region selection utility for EMS aircraft tracking.

Handles region selection via .env configuration or interactive prompts.
"""

import os
from typing import Optional, Tuple, List
from pathlib import Path
from dotenv import load_dotenv

from regions import (
    Region, get_region, get_region_list, is_valid_region,
    is_valid_state_code, get_all_state_codes
)


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


def select_state(project_root: Optional[Path] = None) -> Optional[List[str]]:
    """
    Select state(s) for monitoring from .env or interactive prompt.
    
    Args:
        project_root: Project root directory (for loading .env)
    
    Returns:
        List of state codes (e.g., ['NJ'] or ['NJ', 'DE', 'PA']), or None for "all US"
    """
    # Load .env if project root provided
    if project_root:
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    
    # Check .env first
    state_str = os.getenv("MONITOR_STATE")
    
    if state_str:
        state_str = state_str.strip().upper()
        if state_str == "ALL" or state_str == "NONE" or state_str == "":
            return None
        
        # Parse comma-separated state codes
        state_codes = [s.strip().upper() for s in state_str.split(',')]
        
        # Validate all state codes
        invalid_states = [s for s in state_codes if not is_valid_state_code(s)]
        if invalid_states:
            print(f"Warning: Invalid state code(s) in MONITOR_STATE: {', '.join(invalid_states)}")
            print("Falling back to interactive selection...\n")
        else:
            return state_codes
    
    # Interactive selection
    return _interactive_state_selection()


def _interactive_state_selection() -> Optional[List[str]]:
    """
    Present interactive prompt for state selection.
    
    Returns:
        List of state codes, or None for "all US"
    """
    print("\n" + "=" * 60)
    print("Select State(s) for Monitoring")
    print("=" * 60)
    print("\nEnter state code(s) separated by commas (e.g., 'NJ' or 'NJ,DE,PA')")
    print("Or enter 'all' to monitor all US states")
    print("\nValid state codes: AL, AK, AZ, AR, CA, CO, CT, DE, DC, FL, GA,")
    print("  HI, ID, IL, IN, IA, KS, KY, LA, ME, MD, MA, MI, MN, MS, MO,")
    print("  MT, NE, NV, NH, NJ, NM, NY, NC, ND, OH, OK, OR, PA, RI, SC,")
    print("  SD, TN, TX, UT, VT, VA, WA, WV, WI, WY")
    print("=" * 60)
    
    while True:
        try:
            user_input = input("\nEnter state code(s) or 'all': ").strip()
            
            if not user_input:
                print("Please enter a state code or 'all'.")
                continue
            
            if user_input.upper() == "ALL":
                return None
            
            # Parse comma-separated state codes
            state_codes = [s.strip().upper() for s in user_input.split(',')]
            
            # Validate all state codes
            invalid_states = [s for s in state_codes if not is_valid_state_code(s)]
            if invalid_states:
                print(f"Invalid state code(s): {', '.join(invalid_states)}")
                print("Please enter valid two-letter state codes (e.g., NJ, DE, PA)")
                continue
            
            return state_codes
            
        except (EOFError, KeyboardInterrupt):
            print("\n\nCancelled. Using 'All US' (no filter).")
            return None
        except Exception as e:
            print(f"Error: {e}. Please try again.")


def select_region_or_state(project_root: Optional[Path] = None) -> Tuple[Optional[Region], Optional[List[str]]]:
    """
    Select between region or state-based monitoring.
    
    Args:
        project_root: Project root directory (for loading .env)
    
    Returns:
        Tuple of (region, states) where one will be None:
        - (Region, None) for region-based monitoring
        - (None, List[str]) for state-based monitoring
        - (None, None) for "all US" monitoring
    """
    # Load .env if project root provided
    if project_root:
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    
    # Check if region or state is specified in .env
    region_name = os.getenv("TRACKING_REGION") or os.getenv("MONITOR_REGION")
    state_str = os.getenv("MONITOR_STATE")
    
    # If both are specified, state takes precedence
    if state_str:
        states = select_state(project_root)
        return (None, states)
    elif region_name:
        region = select_region(project_root)
        return (region, None)
    
    # Interactive selection: choose between region or state
    print("\n" + "=" * 60)
    print("Select Monitoring Mode")
    print("=" * 60)
    print("\nChoose how you want to filter monitoring:")
    print("  1. By Region (Northeast, Midwest, South, West)")
    print("  2. By State (specific state code(s) like NJ, DE, PA)")
    print("  3. All US (no filtering)")
    print("=" * 60)
    
    while True:
        try:
            choice = input("\nEnter choice (1, 2, or 3): ").strip()
            
            if choice == "1":
                region = select_region(project_root)
                return (region, None)
            elif choice == "2":
                states = select_state(project_root)
                return (None, states)
            elif choice == "3":
                return (None, None)
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
        except (EOFError, KeyboardInterrupt):
            print("\n\nCancelled. Using 'All US' (no filter).")
            return (None, None)
        except Exception as e:
            print(f"Error: {e}. Please try again.")


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


def filter_aircraft_by_states(aircraft_list: list, states: Optional[List[str]]) -> list:
    """
    Filter aircraft list by state codes based on owner_state.
    
    Args:
        aircraft_list: List of aircraft dictionaries
        states: List of state codes or None (for all)
    
    Returns:
        Filtered list of aircraft
    """
    if states is None or not states:
        return aircraft_list
    
    state_set = set(state.upper() for state in states)
    
    filtered = [
        ac for ac in aircraft_list
        if ac.get('owner_state', '').strip().upper() in state_set
    ]
    
    return filtered
