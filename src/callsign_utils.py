"""Callsign-based confidence boost helpers for runtime monitoring."""

import re
from typing import Optional

CALLSIGN_BOOST_PATTERNS = [
    'MEDEVAC', 'MEDVAC', 'LIFEGUARD', 'RESCUE', 'HEMS',
    'AIR1', 'AIR2', 'MED', 'EMS', 'LIFE',
]

CALLSIGN_AGENCY_SUFFIX = re.compile(r'^N\d+(PD|SO|SP|HP|LE|FD|DF|FS|EM|MS)$')


def get_callsign_boost(callsign: Optional[str]) -> Optional[str]:
    """
    Return boost reason if callsign suggests EMS/police activity.

    Does not filter aircraft — only enriches runtime state for display/alerts.
    """
    if not callsign:
        return None
    cs = callsign.strip().upper()
    if not cs:
        return None
    for pattern in CALLSIGN_BOOST_PATTERNS:
        if pattern in cs:
            return f"Callsign contains {pattern}"
    if CALLSIGN_AGENCY_SUFFIX.match(cs):
        return "Callsign matches agency N-number pattern"
    return None
