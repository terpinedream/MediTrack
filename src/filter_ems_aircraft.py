"""
Filter EMS/Emergency Medical Service aircraft from FAA registration database.

This script parses the FAA MASTER and ACFTREF databases to identify aircraft
that are likely used for EMS/emergency medical services based on:
1. Aircraft model matching
2. Owner name keyword matching
3. Exclusion rules (piston engines, airlines, inactive registrations)
"""

import csv
import re
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass


@dataclass
class EMSAircraft:
    """Represents a filtered EMS aircraft with metadata."""
    n_number: str
    mode_s_hex: str
    model_code: str
    model_name: str
    manufacturer: str
    owner_name: str
    owner_city: str
    owner_state: str
    match_reasons: List[str]
    confidence: str  # 'high', 'medium', 'low'
    type_aircraft: str
    type_engine: str
    status_code: str


class EMSAircraftFilter:
    """Filters FAA aircraft database for EMS/emergency medical service aircraft."""
    
    def __init__(self, data_dir: Path):
        """Initialize filter with data directory paths."""
        self.data_dir = data_dir
        self.master_file = data_dir / "ReleasableAircraft" / "MASTER.txt"
        self.acftref_file = data_dir / "ReleasableAircraft" / "ACFTREF.txt"
        self.models_file = data_dir / "mediModels.txt"
        
        # Model code to model info mapping
        self.model_lookup: Dict[str, Dict[str, str]] = {}
        
        # EMS model patterns (normalized)
        self.ems_model_patterns: Set[str] = set()
        
        # EMS owner name keywords
        self.ems_keywords: Set[str] = {
            'LIFE', 'MED', 'AIRMED', 'CARE', 'ANGEL', 'EMS', 
            'HEALTH', 'HOSPITAL', 'FLIGHT', 'AEROMED', 'MEDICAL',
            'AMBULANCE', 'RESCUE', 'EMERGENCY'
        }
        
        # Exclusion patterns
        self.airline_patterns = {'A320', 'A321', 'A330', 'A350', 'A380',
                                 'B737', 'B747', 'B757', 'B767', 'B777', 'B787',
                                 'MD80', 'MD90', 'MD11', 'CRJ', 'ERJ', 'E170', 'E175'}
        
    def normalize_model_string(self, model: str) -> str:
        """Normalize model string for matching: uppercase, strip punctuation."""
        if not model:
            return ""
        # Remove punctuation and extra spaces
        normalized = re.sub(r'[^\w\s]', '', model.upper())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def load_ems_models(self) -> None:
        """Load EMS model patterns from mediModels.txt."""
        if not self.models_file.exists():
            raise FileNotFoundError(f"Models file not found: {self.models_file}")
        
        current_section = None
        with open(self.models_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('[') or line.startswith('**'):
                    if line.startswith('['):
                        current_section = line
                    continue
                
                # Skip exclusion notes and other metadata
                if line.startswith('What to Exclude') or line.startswith('Strongly'):
                    break
                
                # Skip section headers
                if line.isupper() and len(line) > 10:
                    continue
                
                # Extract model names
                # Remove parenthetical notes like "(JetRanger / LongRanger)"
                model = re.sub(r'\([^)]*\)', '', line).strip()
                
                if model and current_section != '[Common substrings:]':
                    normalized = self.normalize_model_string(model)
                    if normalized:
                        self.ems_model_patterns.add(normalized)
        
        # Add FAA model codes for King Air
        self.ems_model_patterns.update(['BE90', 'BE20', 'BE30'])
        
        print(f"Loaded {len(self.ems_model_patterns)} EMS model patterns")
        print(f"Sample patterns: {list(self.ems_model_patterns)[:10]}")
    
    def load_aircraft_reference(self) -> None:
        """Load aircraft reference database (ACFTREF.txt) to map codes to models."""
        if not self.acftref_file.exists():
            raise FileNotFoundError(f"ACFTREF file not found: {self.acftref_file}")
        
        with open(self.acftref_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Get fieldnames - handle trailing comma by filtering out None/empty
            if not reader.fieldnames:
                raise ValueError("Could not read header from ACFTREF file")
            
            # Find the actual column keys (handle trailing comma that creates empty key)
            # Also handle BOM (Byte Order Mark) in CSV files
            code_key = None
            mfr_key = None
            model_key = None
            
            for key in reader.fieldnames:
                if key:
                    key_clean = key.strip().lstrip('\ufeff')  # Remove BOM and whitespace
                    if key_clean == 'CODE':
                        code_key = key
                    elif key_clean == 'MFR':
                        mfr_key = key
                    elif key_clean == 'MODEL':
                        model_key = key
            
            # Fallback: use first few columns if standard names not found
            if not code_key:
                # Try to use first non-empty column
                valid_keys = [k for k in reader.fieldnames if k and k.strip()]
                if len(valid_keys) >= 3:
                    code_key = valid_keys[0]
                    mfr_key = valid_keys[1] if not mfr_key else mfr_key
                    model_key = valid_keys[2] if not model_key else model_key
                    print(f"Warning: Using positional columns. Found: {valid_keys[:3]}")
                else:
                    raise ValueError(f"Could not find CODE column. Available: {reader.fieldnames[:5]}")
            
            for row in reader:
                # Use .get() to safely access columns (handles missing keys)
                code = row.get(code_key, '').strip() if code_key else ''
                if not code:
                    continue
                
                mfr = row.get(mfr_key, '').strip() if mfr_key else ''
                model = row.get(model_key, '').strip() if model_key else ''
                
                self.model_lookup[code] = {
                    'manufacturer': mfr,
                    'model': model,
                    'model_normalized': self.normalize_model_string(model)
                }
        
        print(f"Loaded {len(self.model_lookup)} aircraft model references")
    
    def matches_ems_model(self, model_code: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if model code matches any EMS model pattern.
        Returns: (matches, model_name, manufacturer)
        """
        if not model_code:
            return False, None, None
        
        # First check if this is a known EMS model code
        if hasattr(self, 'ems_model_codes') and model_code in self.ems_model_codes:
            model_info = self.model_lookup[model_code]
            return True, model_info['model'], model_info['manufacturer']
        
        # Fallback: check if model code exists and matches patterns
        if model_code not in self.model_lookup:
            return False, None, None
        
        model_info = self.model_lookup[model_code]
        model_normalized = model_info['model_normalized']
        model_name = model_info['model']
        manufacturer = model_info['manufacturer']
        
        # Check if normalized model matches any EMS pattern
        for pattern in self.ems_model_patterns:
            # Use prefix matching for flexibility
            if model_normalized.startswith(pattern) or pattern in model_normalized:
                return True, model_name, manufacturer
        
        return False, None, None
    
    def matches_owner_keywords(self, owner_name: str) -> bool:
        """Check if owner name contains EMS keywords."""
        if not owner_name:
            return False
        
        owner_upper = owner_name.upper()
        for keyword in self.ems_keywords:
            if keyword in owner_upper:
                return True
        return False
    
    def should_exclude(self, row: Dict[str, str]) -> Tuple[bool, str]:
        """
        Check if aircraft should be excluded.
        Returns: (should_exclude, reason)
        """
        # Exclude inactive registrations
        status_code = row.get('STATUS CODE', '').strip()
        if status_code != 'V':
            return True, f"Status code: {status_code}"
        
        # Exclude piston aircraft (TYPE AIRCRAFT = 4, TYPE ENGINE = 1)
        type_aircraft = row.get('TYPE AIRCRAFT', '').strip()
        type_engine = row.get('TYPE ENGINE', '').strip()
        
        if type_aircraft == '4' and type_engine == '1':
            return True, "Piston engine aircraft"
        
        # Exclude airline aircraft by model
        model_code = row.get('MFR MDL CODE', '').strip()
        if model_code in self.model_lookup:
            model_name = self.model_lookup[model_code]['model']
            model_normalized = self.normalize_model_string(model_name)
            
            for airline_pattern in self.airline_patterns:
                if airline_pattern in model_normalized:
                    return True, f"Airline aircraft: {model_name}"
        
        # Optionally exclude individual owners (TYPE REGISTRANT = 1)
        # Commented out as per plan - can be enabled if needed
        # type_registrant = row.get('TYPE REGISTRANT', '').strip()
        # if type_registrant == '1':
        #     return True, "Individual owner"
        
        return False, ""
    
    def filter_aircraft(self) -> List[EMSAircraft]:
        """Filter FAA MASTER database for EMS aircraft."""
        if not self.master_file.exists():
            raise FileNotFoundError(f"MASTER file not found: {self.master_file}")
        
        ems_aircraft = []
        excluded_count = 0
        excluded_reasons = {}
        model_match_count = 0
        owner_match_count = 0
        sample_models = []
        sample_owners = []
        first_few_rows = []
        
        print("Filtering aircraft database...")
        with open(self.master_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Debug: Check what columns we actually have
            if reader.fieldnames:
                print(f"  CSV columns found: {list(reader.fieldnames)[:10]}")
                # Find N-NUMBER column (handle BOM and variations)
                n_number_key = None
                for key in reader.fieldnames:
                    if key:
                        key_clean = key.strip().lstrip('\ufeff')
                        if key_clean == 'N-NUMBER' or key_clean == 'N NUMBER':
                            n_number_key = key
                            break
                if not n_number_key:
                    # Try first column
                    n_number_key = reader.fieldnames[0] if reader.fieldnames else 'N-NUMBER'
                    print(f"  Warning: Using first column as N-NUMBER: {n_number_key}")
                else:
                    print(f"  Using N-NUMBER column: '{n_number_key}'")
            
            for idx, row in enumerate(reader):
                # Collect first few rows for debugging (before any processing)
                if idx < 5:
                    # Try multiple ways to get N-number
                    n_num = row.get('N-NUMBER', '') or row.get(n_number_key, '') if 'n_number_key' in locals() else row.get('N-NUMBER', '')
                    first_few_rows.append({
                        'n_number': n_num.strip() if n_num else '',
                        'model_code': row.get('MFR MDL CODE', '').strip(),
                        'owner': row.get('NAME', '').strip()[:30],
                        'status': row.get('STATUS CODE', '').strip(),
                        'type_acft': row.get('TYPE AIRCRAFT', '').strip(),
                        'type_eng': row.get('TYPE ENGINE', '').strip()
                    })
                
                # Extract data early for sample collection - handle N-number column variations
                n_number = (row.get('N-NUMBER', '') or 
                           (row.get(n_number_key, '') if 'n_number_key' in locals() else '')).strip()
                model_code = row.get('MFR MDL CODE', '').strip()
                owner_name = row.get('NAME', '').strip()
                
                # Collect samples for debugging - collect from ALL rows to see what we have
                if len(sample_models) < 200 and model_code:
                    in_lookup = model_code in self.model_lookup
                    is_ems_code = hasattr(self, 'ems_model_codes') and model_code in self.ems_model_codes
                    sample_models.append((model_code, in_lookup, is_ems_code, n_number))
                    # If we find an EMS code, print it immediately for debugging with full row info
                    if is_ems_code:
                        status = row.get('STATUS CODE', '').strip()
                        type_acft = row.get('TYPE AIRCRAFT', '').strip()
                        type_eng = row.get('TYPE ENGINE', '').strip()
                        print(f"  *** FOUND EMS CODE: {model_code} (N:{n_number or 'EMPTY'}) Status:{status} Type:{type_acft}/{type_eng} Owner:{owner_name[:40]} ***")
                if len(sample_owners) < 200 and owner_name:
                    sample_owners.append(owner_name[:50])
                
                if idx > 0 and idx % 10000 == 0:
                    print(f"  Processed {idx} aircraft... (Found {len(ems_aircraft)} EMS, Excluded {excluded_count})")
                
                # Check exclusions
                should_exclude, exclude_reason = self.should_exclude(row)
                if should_exclude:
                    excluded_count += 1
                    excluded_reasons[exclude_reason] = excluded_reasons.get(exclude_reason, 0) + 1
                    # Debug: If this is an EMS code that got excluded, note it
                    if hasattr(self, 'ems_model_codes') and model_code in self.ems_model_codes:
                        print(f"  *** EMS CODE EXCLUDED: {model_code} (N:{n_number or 'EMPTY'}) Reason: {exclude_reason} ***")
                    continue
                
                # Skip if no N-number
                if not n_number:
                    # Debug: If this is an EMS code with no N-number, note it
                    if hasattr(self, 'ems_model_codes') and model_code in self.ems_model_codes:
                        print(f"  *** EMS CODE SKIPPED (no N-number): {model_code} -> {self.model_lookup.get(model_code, {}).get('model', 'N/A')} ***")
                    continue
                
                mode_s_hex = row.get('MODE S CODE HEX', '').strip()
                status_code = row.get('STATUS CODE', '').strip()
                
                match_reasons = []
                model_match, model_name, manufacturer = self.matches_ems_model(model_code)
                owner_match = self.matches_owner_keywords(owner_name)
                
                # Debug: If we have an EMS code and it matches, print it
                if model_match and hasattr(self, 'ems_model_codes') and model_code in self.ems_model_codes:
                    print(f"  *** EMS CODE MATCHED: {model_code} (N:{n_number}) Model:{model_name} Owner:{owner_name[:40]} ***")
                
                if model_match:
                    model_match_count += 1
                if owner_match:
                    owner_match_count += 1
                
                # Determine if this is an EMS aircraft
                is_ems = False
                
                if model_match:
                    is_ems = True
                    match_reasons.append(f"Model: {model_name}")
                
                if owner_match:
                    is_ems = True
                    match_reasons.append("Owner name keyword")
                
                if is_ems:
                    # Determine confidence
                    if model_match and owner_match:
                        confidence = 'high'
                    elif model_match:
                        confidence = 'medium'
                    else:
                        confidence = 'low'
                    
                    aircraft = EMSAircraft(
                        n_number=n_number,
                        mode_s_hex=mode_s_hex,
                        model_code=model_code,
                        model_name=model_name or "Unknown",
                        manufacturer=manufacturer or "Unknown",
                        owner_name=owner_name,
                        owner_city=row.get('CITY', '').strip(),
                        owner_state=row.get('STATE', '').strip(),
                        match_reasons=match_reasons,
                        confidence=confidence,
                        type_aircraft=row.get('TYPE AIRCRAFT', '').strip(),
                        type_engine=row.get('TYPE ENGINE', '').strip(),
                        status_code=status_code
                    )
                    
                    ems_aircraft.append(aircraft)
        
        print(f"\nFiltering Statistics:")
        print(f"  Total processed: {idx + 1}")
        print(f"  Excluded: {excluded_count}")
        print(f"  Model matches found: {model_match_count}")
        print(f"  Owner keyword matches found: {owner_match_count}")
        print(f"  EMS aircraft found: {len(ems_aircraft)}")
        
        # Show first few rows for debugging
        if first_few_rows:
            print(f"\nFirst 5 rows from MASTER.txt:")
            for i, r in enumerate(first_few_rows):
                print(f"  Row {i+1}: N={r['n_number']}, Code={r['model_code']}, Status={r['status']}, Type={r['type_acft']}/{r['type_eng']}, Owner={r['owner']}")
        
        if excluded_reasons:
            print(f"\nExclusion reasons:")
            for reason, count in sorted(excluded_reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  {reason}: {count}")
        
        if sample_models:
            print(f"\nSample model codes from MASTER.txt (first 30):")
            ems_found_in_samples = 0
            in_lookup_count = 0
            for code, in_lookup, is_ems, n_num in sample_models[:30]:
                if in_lookup:
                    in_lookup_count += 1
                    model_info = self.model_lookup.get(code, {})
                    ems_status = " [EMS CODE!]" if is_ems else ""
                    if is_ems:
                        ems_found_in_samples += 1
                    print(f"  {code} (N:{n_num}) -> {model_info.get('model', 'N/A')} (in lookup{ems_status})")
                else:
                    print(f"  {code} (N:{n_num}) -> NOT in lookup")
            print(f"\n  Summary: {in_lookup_count}/{len(sample_models)} in lookup, {ems_found_in_samples} EMS codes")
        
        # Show some sample owners with keywords
        if sample_owners:
            print(f"\nSample owner names (first 5):")
            for owner in sample_owners[:5]:
                print(f"  {owner}")
        
        print(f"Found {len(ems_aircraft)} EMS aircraft")
        return ems_aircraft
    
    def run(self) -> List[EMSAircraft]:
        """Run the complete filtering process."""
        print("Loading EMS model patterns...")
        self.load_ems_models()
        
        print("Loading aircraft reference database...")
        self.load_aircraft_reference()
        
        # Build set of EMS model codes by checking ALL entries in lookup
        ems_in_lookup = 0
        sample_ems_models = []
        ems_model_codes = set()  # Track which codes are EMS models
        
        print("Scanning all model references for EMS patterns...")
        for code, info in self.model_lookup.items():
            model_norm = info.get('model_normalized', '')
            model_name = info.get('model', '')
            
            # Check if normalized model matches any EMS pattern
            for pattern in self.ems_model_patterns:
                # Use both prefix and substring matching
                if (model_norm.startswith(pattern) or 
                    pattern in model_norm or
                    model_name.upper().startswith(pattern) or
                    pattern in model_name.upper()):
                    ems_in_lookup += 1
                    ems_model_codes.add(code)
                    if len(sample_ems_models) < 10:
                        sample_ems_models.append((code, model_name, pattern))
                    break
        
        self.ems_model_codes = ems_model_codes  # Store for use in filtering
        print(f"Found {ems_in_lookup} potential EMS models in reference database")
        print(f"Total unique EMS model codes: {len(ems_model_codes)}")
        if sample_ems_models:
            print("Sample EMS models in lookup:")
            for code, model, pattern in sample_ems_models[:10]:
                print(f"  Code {code}: {model} (matched pattern: {pattern})")
        
        # Debug: Check a few sample codes from ems_model_codes to see what they look like
        print(f"\nSample EMS model codes (first 10): {list(ems_model_codes)[:10]}")
        
        print("Filtering aircraft...")
        ems_aircraft = self.filter_aircraft()
        
        # Print summary statistics
        confidence_counts = {}
        for aircraft in ems_aircraft:
            confidence_counts[aircraft.confidence] = confidence_counts.get(aircraft.confidence, 0) + 1
        
        print("\nFiltering Summary:")
        print(f"  Total EMS aircraft found: {len(ems_aircraft)}")
        print(f"  High confidence: {confidence_counts.get('high', 0)}")
        print(f"  Medium confidence: {confidence_counts.get('medium', 0)}")
        print(f"  Low confidence: {confidence_counts.get('low', 0)}")
        
        return ems_aircraft


def main():
    """Main entry point."""
    # Get project root directory
    project_root = Path(__file__).parent.parent
    
    filter_obj = EMSAircraftFilter(project_root)
    ems_aircraft = filter_obj.run()
    
    return ems_aircraft


if __name__ == "__main__":
    main()
