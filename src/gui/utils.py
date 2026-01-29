"""
Utility functions for GUI components.
"""

from typing import Dict


def is_helicopter(aircraft_info: Dict) -> bool:
    """
    Determine if an aircraft is a helicopter based on type and model.
    
    Args:
        aircraft_info: Dictionary containing aircraft information with keys:
            - type_aircraft: Aircraft type code ("6" for rotorcraft/helicopter)
            - model_name: Model name string
            - manufacturer: Manufacturer name
            - model_code: Model code (optional)
    
    Returns:
        True if helicopter, False if fixed-wing aircraft
    """
    if not aircraft_info:
        return False
    
    # Check type_aircraft field first (most reliable)
    # FAA type codes: 1=Glider, 2=Balloon, 3=Blimp, 4=Fixed Wing Single Engine, 
    # 5=Fixed Wing Multi Engine, 6=Rotorcraft (helicopter), 7=Weight-shift, 8=Powered Parachute, 9=Gyroplane
    type_aircraft = str(aircraft_info.get('type_aircraft', '')).strip()
    if type_aircraft == '6':  # Rotorcraft/helicopter
        return True
    
    # Get model information (check multiple fields)
    model_name = str(aircraft_info.get('model_name', '')).upper()
    manufacturer = str(aircraft_info.get('manufacturer', '')).upper()
    model_code = str(aircraft_info.get('model_code', '')).upper()
    
    # Treat "Unknown" as empty
    if model_name in ['UNKNOWN', 'N/A', '']:
        model_name = ''
    if manufacturer in ['UNKNOWN', 'N/A', '']:
        manufacturer = ''
    
    # Combine all model info for pattern matching
    combined_model = f"{model_name} {manufacturer} {model_code}".strip()
    
    # Common helicopter model patterns (expanded list)
    helicopter_patterns = [
        # Bell helicopters
        'BELL 206', 'BELL 407', 'BELL 429', 'BELL 412', 'BELL 505',
        'BELL 525', 'BELL 204', 'BELL 205', 'BELL 212', 'BELL 214',
        'JETRANGER', 'LONGRANGER', 'LONG RANGER',
        # Airbus/Eurocopter
        'EC135', 'EC145', 'EC130', 'EC155', 'EC225', 'EC635',
        'H135', 'H145', 'H160', 'H175', 'H215', 'H225',
        'AS350', 'AS355', 'AS365', 'ASTAR', 'ECUREUIL', 'DAUPHIN',
        'BO105', 'BK117', 'BK-117',
        # AgustaWestland/Leonardo
        'AW109', 'AW119', 'AW139', 'AW149', 'AW169', 'AW189',
        'A109', 'A119', 'A139', 'A149', 'A169', 'A189',
        # Sikorsky
        'S76', 'S-76', 'S92', 'S-92', 'S70', 'S-70', 'S64', 'S-64',
        'BLACK HAWK', 'SEAHAWK', 'SEA KING',
        # MD Helicopters
        'MD500', 'MD 500', 'MD530', 'MD 530', 'MD600', 'MD 600',
        'HUGHES 500', 'HUGHES 369',
        # Robinson
        'R22', 'R44', 'R66', 'ROBINSON R22', 'ROBINSON R44', 'ROBINSON R66',
        # Enstrom
        'ENSTROM', 'F28', 'F280', '480',
        # Other common helicopter indicators
        'HELICOPTER', 'COPTER', 'ROTORCRAFT', 'ROTOR'
    ]
    
    # Check if model name contains helicopter pattern
    for pattern in helicopter_patterns:
        if pattern in combined_model:
            return True
    
    # Check manufacturer for helicopter manufacturers
    helicopter_manufacturers = [
        'BELL', 'EUROCOPTER', 'AIRBUS HELICOPTERS', 'AIRBUS HELICOPTER',
        'AGUSTAWESTLAND', 'AGUSTA WESTLAND', 'LEONARDO',
        'SIKORSKY', 'ROBINSON', 'MD HELICOPTERS', 'MD HELICOPTER',
        'ENSTROM', 'HUGHES', 'KAMAN', 'BOEING VERTOL'
    ]
    
    for manufacturer_pattern in helicopter_manufacturers:
        if manufacturer_pattern in manufacturer:
            return True
    
    # Check model code patterns (some helicopter model codes start with specific patterns)
    if model_code:
        # Common helicopter model code patterns (this is heuristic)
        heli_code_patterns = ['H', 'R', 'B', 'S']  # Many helicopter codes start with these
        if len(model_code) >= 2 and model_code[0] in heli_code_patterns:
            # Additional check: if it's a short code and matches known patterns
            if any(code in model_code for code in ['206', '407', '429', '412', '135', '145', '109', '119', '76']):
                return True
    
    return False
