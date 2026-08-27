"""
Filter Police/Law Enforcement aircraft from FAA registration database.

Uses weighted scoring via the shared aircraft_filter base module.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from aircraft_filter.base import (
    BaseAircraftFilter,
    FilteredAircraft,
    filtered_to_dict,
)


class PoliceAircraftFilter(BaseAircraftFilter):
    """Filters FAA aircraft database for police/law enforcement aircraft."""

    category = 'police'

    def get_models_file(self) -> Path:
        return self.data_path / "police_models.txt"

    def get_owner_keywords_file(self) -> Path:
        return self.data_path / "police_owner_keywords.txt"

    def check_n_number_pattern(self, n_number: str) -> Tuple[bool, Optional[str]]:
        import re
        n_upper = n_number.upper()
        patterns = [
            (r'^N\d+PD$', "N-number pattern (Police Department)"),
            (r'^N\d+SO$', "N-number pattern (Sheriff's Office)"),
            (r'^N\d+SP$', "N-number pattern (State Police)"),
            (r'^N\d+HP$', "N-number pattern (Highway Patrol)"),
            (r'^N\d+LE$', "N-number pattern (Law Enforcement)"),
        ]
        for pattern, reason in patterns:
            if re.match(pattern, n_upper):
                return True, reason
        return False, None


# Backward-compatible alias
PoliceAircraft = FilteredAircraft


def save_to_json(aircraft_list: List[FilteredAircraft], output_path: Path) -> None:
    """Save filtered police aircraft to JSON with metadata wrapper."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'total_aircraft': len(aircraft_list),
            'description': 'Filtered Police/Law Enforcement aircraft from FAA database',
            'category': 'police',
        },
        'aircraft': [filtered_to_dict(ac) for ac in aircraft_list],
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(aircraft_list)} police aircraft to {output_path}")


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    output_file = project_root / "data" / "police_aircraft.json"

    filter_obj = PoliceAircraftFilter(project_root)
    police_aircraft = filter_obj.run()
    save_to_json(police_aircraft, output_file)

    print(f"\n✓ Police filtering complete! Found {len(police_aircraft)} aircraft")
    print(f"  Output saved to: {output_file}")
    return police_aircraft


if __name__ == "__main__":
    main()
