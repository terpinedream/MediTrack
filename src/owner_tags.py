"""
Classify filtered aircraft owner names into glanceable agency tags.

Tags are derived after filtering, from the registered owner name.
They do not change scoring — they only make likely police/EMS matches
easier to spot in the list view.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from aircraft_filter.base import normalize_owner_name

# Alphanumeric boundaries so FIRE does not match FIREDANCER, PD does not match SPEED.
_PHRASE_BOUNDARY = r'(?<![A-Z0-9]){phrase}(?![A-Z0-9])'


@dataclass(frozen=True)
class OwnerTag:
    """A single owner-type indicator for list-view display."""
    id: str
    label: str
    bg: str
    fg: str = '#ffffff'
    matched: Tuple[str, ...] = ()


@dataclass(frozen=True)
class _TagRule:
    id: str
    label: str
    bg: str
    keywords: Tuple[str, ...]


# Dark fills so white label text stays readable on the chips.
_RULES: Tuple[_TagRule, ...] = (
    _TagRule(
        id='police',
        label='Police',
        bg='#1d4ed8',
        keywords=(
            'POLICE DEPARTMENT', 'POLICE DEPT', 'POLICE DEP',
            'SHERIFFS OFFICE', 'SHERIFF OFFICE', 'SHERIFFS DEPT', 'SHERIFF DEPT',
            'SHERIFF DEPARTMENT', 'COUNTY SHERIFF',
            'STATE POLICE', 'STATE PATROL', 'HIGHWAY PATROL',
            'LAW ENFORCEMENT', 'PUBLIC SAFETY DEPARTMENT',
            'POLICE', 'SHERIFFS', 'SHERIFF', 'TROOPERS', 'TROOPER',
            'MARSHALS', 'MARSHAL',
        ),
    ),
    _TagRule(
        id='federal',
        label='Federal',
        bg='#5b21b6',
        keywords=(
            'DEPARTMENT OF HOMELAND SECURITY', 'HOMELAND SECURITY',
            'FEDERAL BUREAU OF INVESTIGATION', 'DRUG ENFORCEMENT ADMINISTRATION',
            'BUREAU OF ALCOHOL TOBACCO FIREARMS', 'BUREAU OF ALCOHOL',
            'CUSTOMS AND BORDER', 'BORDER PATROL',
            'UNITED STATES MARSHALS', 'UNITED STATES MARSHAL',
            'US MARSHALS', 'US MARSHAL',
            'DEPARTMENT OF JUSTICE',
            'FBI', 'DEA', 'ATF', 'DHS', 'CBP',
        ),
    ),
    _TagRule(
        id='ems',
        label='EMS',
        bg='#b91c1c',
        keywords=(
            'LIFE FLIGHT', 'AIR FLIGHT', 'MED FLIGHT', 'GUARDIAN FLIGHT',
            'RESCUE FLIGHT', 'MERCY FLIGHT', 'ANGEL FLIGHT',
            'AIR EVAC', 'AIREVAC', 'AIR METHODS', 'REACH AIR',
            'PHI HEALTH', 'PHI AIR', 'PHI INC', 'PHI HELICOPTER',
            'METRO AVIATION', 'CRITICAL CARE',
            'MED TRANS', 'MEDTRANS', 'CALSTAR',
            'HEALTHNET', 'HEALTH NET', 'STARS AIR',
            'AIR MEDICAL', 'AIRMEDICAL', 'AEROMEDICAL', 'AERO MEDICAL',
            'AIRMED', 'AEROMED', 'AERO MED',
            'MEDICAL TRANSPORT', 'AMBULANCE', 'MEDEVAC', 'MED EVAC',
            'LIFE NET', 'LIFENET', 'JETCARE', 'AIR RESCUE',
            'SEARCH AND RESCUE', 'EMS',
        ),
    ),
    _TagRule(
        id='hospital',
        label='Hospital',
        bg='#0f766e',
        keywords=(
            'MEDICAL CENTER', 'MEDICAL CENTERS', 'REGIONAL MEDICAL',
            'HEALTH SYSTEM', 'HEALTHCARE', 'HEALTH CARE',
            'HOSPITALS', 'HOSPITAL',
        ),
    ),
    _TagRule(
        id='fire',
        label='Fire',
        bg='#c2410c',
        keywords=(
            'FIRE DEPARTMENT', 'FIRE DEPT', 'FIRE DEP', 'FIRE DISTRICT',
            'FIRE AUTHORITY', 'FIRE RESCUE', 'FIREFIGHTING', 'FIREFIGHT',
            'CAL FIRE', 'CALFIRE', 'FIRE',
        ),
    ),
    _TagRule(
        id='forest',
        label='Forest',
        bg='#15803d',
        keywords=(
            'FOREST SERVICE', 'DEPARTMENT OF FORESTRY', 'FORESTRY',
            'FISH AND WILDLIFE', 'FISH WILDLIFE',
            'NATIONAL PARK SERVICE', 'NATIONAL PARK',
            'BUREAU OF LAND MANAGEMENT',
            'DEPARTMENT OF THE INTERIOR', 'DEPARTMENT OF INTERIOR',
            'USDA FOREST', 'USFS', 'BLM', 'NPS', 'USFWS',
        ),
    ),
    _TagRule(
        id='public_safety',
        label='Public Safety',
        bg='#0369a1',
        keywords=(
            'DEPARTMENT OF PUBLIC SAFETY', 'DEPT OF PUBLIC SAFETY',
            'PUBLIC SAFETY',
        ),
    ),
    _TagRule(
        id='city',
        label='City',
        bg='#475569',
        keywords=(
            'CITY OF', 'TOWN OF', 'VILLAGE OF', 'MUNICIPALITY OF',
        ),
    ),
    _TagRule(
        id='county',
        label='County',
        bg='#57534e',
        keywords=(
            'COUNTY OF', 'COUNTY',
        ),
    ),
    _TagRule(
        id='parish',
        label='Parish',
        bg='#57534e',
        keywords=('PARISH',),
    ),
    _TagRule(
        id='state',
        label='State',
        bg='#334155',
        keywords=(
            'STATE OF', 'COMMONWEALTH OF',
        ),
    ),
    _TagRule(
        id='cap',
        label='CAP',
        bg='#6b7280',
        keywords=('CIVIL AIR PATROL',),
    ),
)


def prepare_owner_text(owner_name: Optional[str]) -> str:
    """Normalize owner name for keyword matching."""
    if not owner_name:
        return ''
    text = normalize_owner_name(owner_name)
    text = text.replace('&', ' AND ')
    text = re.sub(r'[^A-Z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _phrase_in_text(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    pattern = _PHRASE_BOUNDARY.format(phrase=re.escape(phrase))
    return bool(re.search(pattern, text))


def classify_owner_tags(
    owner_name: Optional[str] = None,
    n_number: Optional[str] = None,
) -> List[OwnerTag]:
    """
    Return owner-type tags for a filtered aircraft.

    Tags are inferred from the FAA registrant name. n_number is accepted
    for call-site compatibility and is not used for classification.
    """
    del n_number
    owner_text = prepare_owner_text(owner_name)
    tags: List[OwnerTag] = []

    for rule in _RULES:
        matched: List[str] = []
        if owner_text:
            for keyword in rule.keywords:
                if _phrase_in_text(owner_text, keyword):
                    matched.append(keyword)
        if matched:
            tags.append(OwnerTag(
                id=rule.id,
                label=rule.label,
                bg=rule.bg,
                fg='#ffffff',
                matched=tuple(matched),
            ))
    return tags


def tags_as_dicts(tags: Sequence[OwnerTag]) -> List[Dict[str, str]]:
    """Serialize tags for Qt item roles and tooltips."""
    return [
        {
            'id': tag.id,
            'label': tag.label,
            'bg': tag.bg,
            'fg': tag.fg,
        }
        for tag in tags
    ]


def format_tag_labels(tags: Sequence[OwnerTag]) -> str:
    """Comma-separated labels for sorting, export, and plain-text display."""
    return ', '.join(tag.label for tag in tags)


def tag_tooltip(owner_name: Optional[str], tags: Sequence[OwnerTag]) -> str:
    """Hover text: owner name plus which keywords produced each tag."""
    lines: List[str] = []
    owner = (owner_name or '').strip()
    if owner and owner.upper() != 'N/A':
        lines.append(owner)
    for tag in tags:
        if tag.matched:
            lines.append(f"{tag.label}: {', '.join(tag.matched)}")
        else:
            lines.append(tag.label)
    return '\n'.join(lines)


def classify_from_aircraft(aircraft_info: Optional[Dict], n_number: Optional[str] = None) -> List[OwnerTag]:
    """Classify tags from an aircraft database/info dict."""
    if not aircraft_info:
        aircraft_info = {}
    owner = aircraft_info.get('owner_name')
    n_val = n_number if n_number is not None else aircraft_info.get('n_number')
    if owner in (None, '', 'N/A'):
        owner = None
    if n_val in (None, '', 'N/A'):
        n_val = None
    return classify_owner_tags(owner, n_val)
