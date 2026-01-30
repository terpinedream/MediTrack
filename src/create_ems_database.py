"""
Create filtered EMS aircraft database in multiple formats.

This script uses the EMSAircraftFilter to generate filtered datasets
in JSON, CSV, and SQLite formats for use with OpenSky API tracking.
"""

import json
import csv
import sqlite3
from pathlib import Path
from typing import List
from datetime import datetime

from filter_ems_aircraft import EMSAircraftFilter, EMSAircraft


class EMSDatabaseGenerator:
    """Generate EMS aircraft databases in multiple formats."""
    
    def __init__(self, data_dir: Path, output_dir: Path):
        """Initialize database generator."""
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def to_dict(self, aircraft: EMSAircraft) -> dict:
        """Convert EMSAircraft to dictionary."""
        return {
            'n_number': aircraft.n_number,
            'mode_s_hex': aircraft.mode_s_hex,
            'model_code': aircraft.model_code,
            'model_name': aircraft.model_name,
            'manufacturer': aircraft.manufacturer,
            'owner_name': aircraft.owner_name,
            'owner_city': aircraft.owner_city,
            'owner_state': aircraft.owner_state,
            'match_reasons': aircraft.match_reasons,
            'confidence': aircraft.confidence,
            'type_aircraft': aircraft.type_aircraft,
            'type_engine': aircraft.type_engine,
            'status_code': aircraft.status_code
        }
    
    def save_json(self, aircraft_list: List[EMSAircraft]) -> None:
        """Save aircraft data to JSON file."""
        output_file = self.output_dir / "ems_aircraft.json"
        
        data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_aircraft': len(aircraft_list),
                'description': 'Filtered EMS/Emergency Medical Service aircraft from FAA database'
            },
            'aircraft': [self.to_dict(ac) for ac in aircraft_list]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved JSON database: {output_file} ({len(aircraft_list)} aircraft)")
    
    def save_json_to_path(self, aircraft_list: List[EMSAircraft], file_path: Path) -> None:
        """Save aircraft data to a specific JSON file path (for custom database builds)."""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_aircraft': len(aircraft_list),
                'description': 'Filtered EMS/Emergency Medical Service aircraft from FAA database'
            },
            'aircraft': [self.to_dict(ac) for ac in aircraft_list]
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved JSON database: {file_path} ({len(aircraft_list)} aircraft)")
    
    def save_csv(self, aircraft_list: List[EMSAircraft]) -> None:
        """Save aircraft data to CSV file."""
        output_file = self.output_dir / "ems_aircraft.csv"
        
        if not aircraft_list:
            print("No aircraft to save to CSV")
            return
        
        fieldnames = [
            'n_number', 'mode_s_hex', 'model_code', 'model_name', 'manufacturer',
            'owner_name', 'owner_city', 'owner_state', 'match_reasons', 'confidence',
            'type_aircraft', 'type_engine', 'status_code'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for aircraft in aircraft_list:
                row = self.to_dict(aircraft)
                # Convert match_reasons list to string for CSV
                row['match_reasons'] = '; '.join(row['match_reasons'])
                writer.writerow(row)
        
        print(f"Saved CSV database: {output_file} ({len(aircraft_list)} aircraft)")
    
    def save_sqlite(self, aircraft_list: List[EMSAircraft]) -> None:
        """Save aircraft data to SQLite database."""
        output_file = self.output_dir / "ems_aircraft.db"
        
        # Remove existing database if it exists
        if output_file.exists():
            output_file.unlink()
        
        conn = sqlite3.connect(output_file)
        cursor = conn.cursor()
        
        # Create table
        cursor.execute("""
            CREATE TABLE ems_aircraft (
                n_number TEXT PRIMARY KEY,
                mode_s_hex TEXT,
                model_code TEXT,
                model_name TEXT,
                manufacturer TEXT,
                owner_name TEXT,
                owner_city TEXT,
                owner_state TEXT,
                match_reasons TEXT,
                confidence TEXT,
                type_aircraft TEXT,
                type_engine TEXT,
                status_code TEXT
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("CREATE INDEX idx_mode_s_hex ON ems_aircraft(mode_s_hex)")
        cursor.execute("CREATE INDEX idx_confidence ON ems_aircraft(confidence)")
        cursor.execute("CREATE INDEX idx_model_name ON ems_aircraft(model_name)")
        cursor.execute("CREATE INDEX idx_state ON ems_aircraft(owner_state)")
        
        # Insert data
        for aircraft in aircraft_list:
            cursor.execute("""
                INSERT INTO ems_aircraft (
                    n_number, mode_s_hex, model_code, model_name, manufacturer,
                    owner_name, owner_city, owner_state, match_reasons, confidence,
                    type_aircraft, type_engine, status_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                aircraft.n_number,
                aircraft.mode_s_hex,
                aircraft.model_code,
                aircraft.model_name,
                aircraft.manufacturer,
                aircraft.owner_name,
                aircraft.owner_city,
                aircraft.owner_state,
                '; '.join(aircraft.match_reasons),
                aircraft.confidence,
                aircraft.type_aircraft,
                aircraft.type_engine,
                aircraft.status_code
            ))
        
        conn.commit()
        conn.close()
        
        print(f"Saved SQLite database: {output_file} ({len(aircraft_list)} aircraft)")
    
    def generate(self, aircraft_list: List[EMSAircraft]) -> None:
        """Generate all database formats."""
        print("\nGenerating EMS aircraft databases...")
        
        if not aircraft_list:
            print("No aircraft to save")
            return
        
        self.save_json(aircraft_list)
        self.save_csv(aircraft_list)
        self.save_sqlite(aircraft_list)
        
        print("\nDatabase generation complete!")


def main():
    """Main entry point."""
    # Get project root directory
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "data"
    
    # Run filter
    print("=" * 60)
    print("EMS Aircraft Database Generator")
    print("=" * 60)
    
    filter_obj = EMSAircraftFilter(project_root)
    ems_aircraft = filter_obj.run()
    
    # Generate databases
    generator = EMSDatabaseGenerator(project_root, output_dir)
    generator.generate(ems_aircraft)
    
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Total EMS aircraft identified: {len(ems_aircraft)}")
    print(f"  Output directory: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
