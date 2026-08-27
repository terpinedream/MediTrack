"""
Filter EMS/Emergency Medical Service aircraft from FAA registration database.

Uses weighted scoring via the shared aircraft_filter base module.
"""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from aircraft_filter.base import (
    BaseAircraftFilter,
    FilteredAircraft,
    filtered_to_dict,
)


class EMSAircraftFilter(BaseAircraftFilter):
    """Filters FAA aircraft database for EMS/emergency medical service aircraft."""

    category = 'ems'

    def get_models_file(self) -> Path:
        return self.data_path / "ems_models.txt"

    def get_owner_keywords_file(self) -> Path:
        return self.data_path / "ems_owner_keywords.txt"

    def check_n_number_pattern(self, n_number: str) -> Tuple[bool, Optional[str]]:
        n_upper = n_number.upper()
        patterns = [
            (r'^N\d+DF$', "N-number pattern (CAL FIRE)"),
            (r'^N\d+FS$', "N-number pattern (USFS)"),
            (r'^N\d+BL$', "N-number pattern (BLM)"),
            (r'^N\d+DI$', "N-number pattern (DOI)"),
            (r'^N\d+NP$', "N-number pattern (NPS)"),
            (r'^N\d+FD$', "N-number pattern (Fire Department)"),
            (r'^N\d+(EM|MS)$', "N-number pattern (EMS)"),
        ]
        import re
        for pattern, reason in patterns:
            if re.match(pattern, n_upper):
                return True, reason
        return False, None


# Backward-compatible alias
EMSAircraft = FilteredAircraft


def save_to_json(aircraft_list: List[FilteredAircraft], output_path: Path) -> None:
    """Save filtered EMS aircraft to JSON with metadata wrapper."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'total_aircraft': len(aircraft_list),
            'description': 'Filtered EMS/Emergency Medical Service aircraft from FAA database',
            'category': 'ems',
        },
        'aircraft': [filtered_to_dict(ac) for ac in aircraft_list],
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(aircraft_list)} EMS aircraft to {output_path}")


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    output_file = project_root / "data" / "ems_aircraft.json"

    filter_obj = EMSAircraftFilter(project_root)
    ems_aircraft = filter_obj.run()
    save_to_json(ems_aircraft, output_file)

    print(f"\n✓ EMS filtering complete! Found {len(ems_aircraft)} aircraft")
    return ems_aircraft


if __name__ == "__main__":
    main()
