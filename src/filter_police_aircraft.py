"""
Filter Police/Law Enforcement aircraft from FAA registration database.

This script parses the FAA MASTER and ACFTREF databases to identify aircraft
that are likely used for police/law enforcement based on:
1. Aircraft model matching (helicopters and fixed-wing commonly used by police)
2. Owner name keyword matching
3. N-number patterns (police-specific suffixes)
4. Exclusion rules (piston engines, airlines, inactive registrations, museums)
"""

import csv
import re
import os
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict


@dataclass
class PoliceAircraft:
    """Represents a filtered police aircraft with metadata."""
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


class PoliceAircraftFilter:
    """Filters FAA aircraft database for police/law enforcement aircraft."""
    
    def __init__(self, data_dir: Path):
        """Initialize filter with data directory paths."""
        self.data_dir = data_dir
        self.master_file = data_dir / "ReleasableAircraft" / "MASTER.txt"
        self.acftref_file = data_dir / "ReleasableAircraft" / "ACFTREF.txt"
        
        # Model code to model info mapping
        self.model_lookup: Dict[str, Dict[str, str]] = {}
        
        # Police model patterns (helicopters and fixed-wing commonly used by police)
        # Many police departments use similar helicopters to EMS
        self.police_model_patterns: Set[str] = {
            # Helicopters commonly used by police
            'BELL 206', 'BELL 407', 'BELL 429', 'BELL 412', 'BELL 505',
            'JETRANGER', 'LONGRANGER',
            'EC135', 'EC145', 'H135', 'H145', 'AS350', 'ASTAR', 'ECUREUIL',
            'AW109', 'AW119', 'A109', 'A139',
            'S76', 'S-76',
            'BO105', 'BK117',
            # Fixed-wing commonly used by police
            'CESSNA 182', 'CESSNA 206', 'CESSNA 210', 'CESSNA 172',
            'PIPER PA28', 'PIPER PA32', 'PIPER PA34',
            'BEECHCRAFT KING AIR', 'BE90', 'BE20', 'BE30', 'BE200',
            'PILATUS PC12', 'PC-12',
            # Police-specific models
            'MD500', 'MD 500', 'MD530', 'MD 530', 'HUGHES 500',
            'ENSTROM', 'R44', 'ROBINSON R44', 'R66', 'ROBINSON R66'
        }
        
        # Police/Law Enforcement owner name keywords
        self.police_keywords: Set[str] = {
            # Primary police keywords
            'POLICE', 'POLICE DEPARTMENT', 'POLICE DEPT', 'POLICE DEP',
            'SHERIFF', 'SHERIFFS OFFICE', 'SHERIFF OFFICE', 'SHERIFFS DEPT',
            'SHERIFF DEPARTMENT', 'COUNTY SHERIFF',
            'STATE POLICE', 'STATE PATROL', 'HIGHWAY PATROL',
            'TROOPER', 'TROOPERS',
            'LAW ENFORCEMENT', 'LAW ENFORCEMENT AGENCY',
            'MARSHAL', 'MARSHALS', 'US MARSHAL', 'US MARSHALS',
            'FBI', 'FEDERAL BUREAU OF INVESTIGATION',
            'DEA', 'DRUG ENFORCEMENT ADMINISTRATION',
            'ATF', 'BUREAU OF ALCOHOL TOBACCO FIREARMS',
            'CUSTOMS', 'BORDER PATROL', 'IMMIGRATION',
            'DHS', 'DEPARTMENT OF HOMELAND SECURITY',
            'TSA', 'TRANSPORTATION SECURITY ADMINISTRATION',
            # Abbreviations
            'PD',  # Police Department
            'SO',  # Sheriff's Office
            'SP',  # State Police
            'HP',  # Highway Patrol
            'LE',  # Law Enforcement
            # Federal agencies with law enforcement
            'FEDERAL', 'FEDERAL AGENCY',
            'DEPARTMENT OF JUSTICE', 'DOJ',
            'DEPARTMENT OF HOMELAND SECURITY', 'DHS',
            # State and local variations
            'PATROL', 'AERONAUTICS', 'AERONAUTICS DIVISION',
            'PUBLIC SAFETY', 'PUBLIC SAFETY DEPARTMENT',
            'CRIMINAL JUSTICE', 'JUSTICE DEPARTMENT'
        }
        
        # Museum exclusion keywords
        self.museum_keywords: Set[str] = {
            'MUSEUM', 'MUSEUMS', 'AVIATION MUSEUM', 'AIR MUSEUM',
            'FLIGHT MUSEUM', 'AEROSPACE MUSEUM', 'AIRSPACE MUSEUM',
            'MUSEUM OF', 'AIR & SPACE MUSEUM', 'AIR AND SPACE MUSEUM'
        }
        
        # Commercial cargo/logistics exclusion keywords
        self.commercial_exclusion_keywords: Set[str] = {
            'FEDERAL EXPRESS', 'FEDERAL EXPRESS CORP', 'FEDEX', 'FED EX',
            'FEDERAL EXPRESS CORPORATION', 'FEDEX EXPRESS', 'FEDEX CORP'
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
    
    def load_aircraft_reference(self) -> None:
        """Load aircraft reference database (ACFTREF.txt) to map codes to models."""
        if not self.acftref_file.exists():
            raise FileNotFoundError(f"ACFTREF file not found: {self.acftref_file}")
        
        with open(self.acftref_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            if not reader.fieldnames:
                raise ValueError("Could not read header from ACFTREF file")
            
            # Find the actual column keys
            code_key = None
            mfr_key = None
            model_key = None
            
            for key in reader.fieldnames:
                if key:
                    key_clean = key.strip().lstrip('\ufeff')
                    if key_clean == 'CODE':
                        code_key = key
                    elif key_clean == 'MFR':
                        mfr_key = key
                    elif key_clean == 'MODEL':
                        model_key = key
            
            # Fallback: use first few columns if standard names not found
            if not code_key:
                valid_keys = [k for k in reader.fieldnames if k and k.strip()]
                if len(valid_keys) >= 3:
                    code_key = valid_keys[0]
                    mfr_key = valid_keys[1] if not mfr_key else mfr_key
                    model_key = valid_keys[2] if not model_key else model_key
                    print(f"Warning: Using positional columns. Found: {valid_keys[:3]}")
                else:
                    raise ValueError(f"Could not find CODE column. Available: {reader.fieldnames[:5]}")
            
            for row in reader:
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
    
    def matches_police_model(self, model_code: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if model code matches any police model pattern.
        Returns: (matches, model_name, manufacturer)
        """
        if not model_code:
            return False, None, None
        
        if model_code not in self.model_lookup:
            return False, None, None
        
        model_info = self.model_lookup[model_code]
        model_normalized = model_info['model_normalized']
        model_name = model_info['model']
        manufacturer = model_info['manufacturer']
        
        # Check if normalized model matches any police pattern
        for pattern in self.police_model_patterns:
            # Use prefix matching and substring matching for flexibility
            if model_normalized.startswith(pattern) or pattern in model_normalized:
                return True, model_name, manufacturer
        
        return False, None, None
    
    def normalize_owner_name(self, owner_name: str) -> str:
        """
        Normalize owner name for better keyword matching.
        Removes common suffixes and normalizes spacing.
        """
        if not owner_name:
            return ""
        
        normalized = owner_name.upper()
        
        # Remove common business suffixes
        suffixes = [' LLC', ' INC', ' CORP', ' CORPORATION', ' LTD', ' LIMITED',
                   ' LP', ' LLP', ' PC', ' PLLC', ' LLC.', ' INC.', ' CORP.']
        for suffix in suffixes:
            normalized = re.sub(rf'{re.escape(suffix)}\s*$', '', normalized, flags=re.IGNORECASE)
        
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def matches_owner_keywords(self, owner_name: str) -> bool:
        """
        Check if owner name contains police keywords.
        Uses normalized owner name for better matching.
        """
        if not owner_name:
            return False
        
        owner_normalized = self.normalize_owner_name(owner_name)
        
        # Check for keywords in normalized name
        for keyword in self.police_keywords:
            # Use word boundary matching for short keywords
            if len(keyword) <= 3:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, owner_normalized):
                    return True
            else:
                if keyword in owner_normalized:
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
        
        # Exclude museum-owned aircraft
        owner_name = row.get('NAME', '').strip().upper()
        if owner_name:
            for museum_keyword in self.museum_keywords:
                if museum_keyword in owner_name:
                    return True, f"Museum-owned: {row.get('NAME', '').strip()[:50]}"
            
            # Exclude commercial cargo/logistics companies (FedEx, etc.)
            for exclusion_keyword in self.commercial_exclusion_keywords:
                if exclusion_keyword in owner_name:
                    return True, f"Commercial cargo: {row.get('NAME', '').strip()[:50]}"
        
        # Exclude airline aircraft by model
        model_code = row.get('MFR MDL CODE', '').strip()
        if model_code in self.model_lookup:
            model_name = self.model_lookup[model_code]['model']
            model_normalized = self.normalize_model_string(model_name)
            
            for airline_pattern in self.airline_patterns:
                if airline_pattern in model_normalized:
                    return True, f"Airline aircraft: {model_name}"
        
        # Exclude individual owners (TYPE REGISTRANT = 1)
        type_registrant = row.get('TYPE REGISTRANT', '').strip()
        if type_registrant == '1':
            return True, "Individual owner"
        
        # Exclude private LLCs that don't contain police/law enforcement keywords
        # This excludes generic private ownership but keeps legitimate police service LLCs
        if owner_name:
            # Check if it's an LLC
            is_llc = any(llc_indicator in owner_name for llc_indicator in 
                        [' LLC', ' LLC.', ' LIMITED LIABILITY', ' L.L.C.', ' L L C'])
            
            if is_llc:
                # Check if it contains any police/law enforcement keywords
                # If it's an LLC but has police keywords, keep it (e.g., "ABC Police Department LLC")
                has_police_keyword = any(keyword in owner_name for keyword in self.police_keywords)
                
                if not has_police_keyword:
                    return True, f"Private LLC (no police keywords): {row.get('NAME', '').strip()[:50]}"
        
        return False, ""
    
    def is_valid_mode_s_hex(self, mode_s_hex: str) -> bool:
        """Validate Mode S code format (must be exactly 6 hex characters)."""
        if not mode_s_hex:
            return False
        mode_s_hex_upper = mode_s_hex.upper().strip()
        return bool(re.match(r'^[0-9A-F]{6}$', mode_s_hex_upper))
    
    def filter_aircraft(self) -> List[PoliceAircraft]:
        """Filter FAA MASTER database for police aircraft."""
        if not self.master_file.exists():
            raise FileNotFoundError(f"MASTER file not found: {self.master_file}")
        
        police_aircraft = []
        excluded_count = 0
        excluded_reasons = {}
        model_match_count = 0
        owner_match_count = 0
        n_pattern_match_count = 0
        museum_excluded_count = 0
        commercial_excluded_count = 0
        individual_owner_excluded_count = 0
        private_llc_excluded_count = 0
        invalid_mode_s_count = 0
        
        print("Filtering aircraft database...")
        with open(self.master_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Find N-NUMBER column
            n_number_key = None
            if reader.fieldnames:
                for key in reader.fieldnames:
                    if key:
                        key_clean = key.strip().lstrip('\ufeff')
                        if key_clean == 'N-NUMBER' or key_clean == 'N NUMBER':
                            n_number_key = key
                            break
                if not n_number_key:
                    n_number_key = reader.fieldnames[0] if reader.fieldnames else 'N-NUMBER'
            
            for idx, row in enumerate(reader):
                if idx > 0 and idx % 10000 == 0:
                    print(f"  Processed {idx} aircraft... (Found {len(police_aircraft)} police, Excluded {excluded_count})")
                
                # Check exclusions
                should_exclude, exclude_reason = self.should_exclude(row)
                if should_exclude:
                    excluded_count += 1
                    excluded_reasons[exclude_reason] = excluded_reasons.get(exclude_reason, 0) + 1
                    if 'Museum' in exclude_reason:
                        museum_excluded_count += 1
                    # Track commercial exclusions separately
                    if 'Commercial cargo' in exclude_reason:
                        commercial_excluded_count += 1
                    # Track individual owner exclusions
                    if 'Individual owner' in exclude_reason:
                        individual_owner_excluded_count += 1
                    # Track private LLC exclusions
                    if 'Private LLC' in exclude_reason:
                        private_llc_excluded_count += 1
                    continue
                
                # Extract data
                n_number = (row.get('N-NUMBER', '') or 
                           (row.get(n_number_key, '') if n_number_key else '')).strip()
                
                if not n_number:
                    continue
                
                mode_s_hex = row.get('MODE S CODE HEX', '').strip()
                status_code = row.get('STATUS CODE', '').strip()
                
                # Validate Mode S code format
                if mode_s_hex:
                    mode_s_hex_upper = mode_s_hex.upper().strip()
                    if not self.is_valid_mode_s_hex(mode_s_hex_upper):
                        invalid_mode_s_count += 1
                        continue
                    mode_s_hex = mode_s_hex_upper
                else:
                    invalid_mode_s_count += 1
                    continue
                
                match_reasons = []
                model_code = row.get('MFR MDL CODE', '').strip()
                owner_name = row.get('NAME', '').strip()
                
                model_match, model_name, manufacturer = self.matches_police_model(model_code)
                owner_match = self.matches_owner_keywords(owner_name)
                
                if model_match:
                    model_match_count += 1
                if owner_match:
                    owner_match_count += 1
                
                # Check for police-specific N-number patterns
                n_number_pattern_match = False
                n_number_upper = n_number.upper() if n_number else ""
                
                if n_number_upper:
                    # Police Department pattern: N-numbers ending in "PD" (e.g., N123PD)
                    if re.match(r'^N\d+PD$', n_number_upper):
                        n_number_pattern_match = True
                        match_reasons.append("N-number pattern (Police Department)")
                    # Sheriff's Office pattern: N-numbers ending in "SO" (e.g., N123SO)
                    elif re.match(r'^N\d+SO$', n_number_upper):
                        n_number_pattern_match = True
                        match_reasons.append("N-number pattern (Sheriff's Office)")
                    # State Police pattern: N-numbers ending in "SP" (e.g., N123SP)
                    elif re.match(r'^N\d+SP$', n_number_upper):
                        n_number_pattern_match = True
                        match_reasons.append("N-number pattern (State Police)")
                    # Highway Patrol pattern: N-numbers ending in "HP" (e.g., N123HP)
                    elif re.match(r'^N\d+HP$', n_number_upper):
                        n_number_pattern_match = True
                        match_reasons.append("N-number pattern (Highway Patrol)")
                    # Law Enforcement pattern: N-numbers ending in "LE" (e.g., N123LE)
                    elif re.match(r'^N\d+LE$', n_number_upper):
                        n_number_pattern_match = True
                        match_reasons.append("N-number pattern (Law Enforcement)")
                    # State Patrol pattern: N-numbers ending in "ST" (e.g., N123ST)
                    elif re.match(r'^N\d+ST$', n_number_upper):
                        n_number_pattern_match = True
                        match_reasons.append("N-number pattern (State)")
                
                if n_number_pattern_match:
                    n_pattern_match_count += 1
                
                # Determine if this is a police/law enforcement aircraft
                is_police = False
                
                if model_match:
                    is_police = True
                    match_reasons.append(f"Model: {model_name}")
                
                if owner_match:
                    is_police = True
                    match_reasons.append("Owner name keyword")
                
                if n_number_pattern_match:
                    is_police = True
                
                if is_police:
                    # Determine confidence
                    # High: Model match + (owner match OR N-number pattern)
                    # Medium: Model match only, or N-number pattern + owner match
                    # Low: Owner match only, or N-number pattern only
                    if model_match and (owner_match or n_number_pattern_match):
                        confidence = 'high'
                    elif model_match or (n_number_pattern_match and owner_match):
                        confidence = 'medium'
                    else:
                        confidence = 'low'
                    
                    aircraft = PoliceAircraft(
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
                    
                    police_aircraft.append(aircraft)
        
        print(f"\nFiltering Statistics:")
        print(f"  Total processed: {idx + 1}")
        print(f"  Excluded: {excluded_count}")
        print(f"    - Museum-owned excluded: {museum_excluded_count}")
        print(f"    - Commercial cargo excluded: {commercial_excluded_count}")
        print(f"    - Individual owners excluded: {individual_owner_excluded_count}")
        print(f"    - Private LLCs excluded: {private_llc_excluded_count}")
        print(f"  Model matches found: {model_match_count}")
        print(f"  Owner keyword matches found: {owner_match_count}")
        print(f"  N-number pattern matches found: {n_pattern_match_count}")
        print(f"  Invalid/missing Mode S codes: {invalid_mode_s_count}")
        print(f"  Police aircraft found: {len(police_aircraft)}")
        
        if excluded_reasons:
            print(f"\nExclusion reasons:")
            for reason, count in sorted(excluded_reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  {reason}: {count}")
        
        return police_aircraft
    
    def run(self) -> List[PoliceAircraft]:
        """Run the complete filtering process."""
        print("Loading aircraft reference database...")
        self.load_aircraft_reference()
        
        # Build set of police model codes
        police_model_codes = set()
        print("Scanning all model references for police patterns...")
        for code, info in self.model_lookup.items():
            model_norm = info.get('model_normalized', '')
            model_name = info.get('model', '')
            
            for pattern in self.police_model_patterns:
                if (model_norm.startswith(pattern) or 
                    pattern in model_norm or
                    model_name.upper().startswith(pattern) or
                    pattern in model_name.upper()):
                    police_model_codes.add(code)
                    break
        
        self.police_model_codes = police_model_codes
        print(f"Found {len(police_model_codes)} potential police models in reference database")
        
        print("Filtering aircraft...")
        police_aircraft = self.filter_aircraft()
        
        # Print summary statistics
        confidence_counts = {}
        match_type_counts = {'model_only': 0, 'owner_only': 0, 'pattern_only': 0,
                            'model_owner': 0, 'model_pattern': 0, 'owner_pattern': 0,
                            'all_three': 0}
        
        for aircraft in police_aircraft:
            confidence_counts[aircraft.confidence] = confidence_counts.get(aircraft.confidence, 0) + 1
            
            has_model = any('Model:' in reason for reason in aircraft.match_reasons)
            has_owner = any('Owner name keyword' in reason for reason in aircraft.match_reasons)
            has_pattern = any('N-number pattern' in reason for reason in aircraft.match_reasons)
            
            if has_model and has_owner and has_pattern:
                match_type_counts['all_three'] += 1
            elif has_model and has_owner:
                match_type_counts['model_owner'] += 1
            elif has_model and has_pattern:
                match_type_counts['model_pattern'] += 1
            elif has_owner and has_pattern:
                match_type_counts['owner_pattern'] += 1
            elif has_model:
                match_type_counts['model_only'] += 1
            elif has_owner:
                match_type_counts['owner_only'] += 1
            elif has_pattern:
                match_type_counts['pattern_only'] += 1
        
        print("\nFiltering Summary:")
        print(f"  Total police aircraft found: {len(police_aircraft)}")
        print(f"\n  Confidence Distribution:")
        print(f"    High confidence: {confidence_counts.get('high', 0)}")
        print(f"    Medium confidence: {confidence_counts.get('medium', 0)}")
        print(f"    Low confidence: {confidence_counts.get('low', 0)}")
        print(f"\n  Match Type Distribution:")
        print(f"    Model + Owner + Pattern: {match_type_counts['all_three']}")
        print(f"    Model + Owner: {match_type_counts['model_owner']}")
        print(f"    Model + Pattern: {match_type_counts['model_pattern']}")
        print(f"    Owner + Pattern: {match_type_counts['owner_pattern']}")
        print(f"    Model only: {match_type_counts['model_only']}")
        print(f"    Owner only: {match_type_counts['owner_only']}")
        print(f"    Pattern only: {match_type_counts['pattern_only']}")
        
        return police_aircraft


def save_to_json(aircraft_list: List[PoliceAircraft], output_path: Path):
    """Save filtered aircraft to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    aircraft_dicts = [asdict(ac) for ac in aircraft_list]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(aircraft_dicts, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved {len(aircraft_list)} police aircraft to {output_path}")


def main():
    """Main entry point."""
    import sys
    
    # Get project root directory
    project_root = Path(__file__).parent.parent
    
    # Output file
    output_file = project_root / "data" / "police_aircraft.json"
    
    filter_obj = PoliceAircraftFilter(project_root)
    police_aircraft = filter_obj.run()
    
    # Save to JSON
    save_to_json(police_aircraft, output_file)
    
    print(f"\n✓ Filtering complete! Found {len(police_aircraft)} police aircraft")
    print(f"  Output saved to: {output_file}")
    
    return police_aircraft


if __name__ == "__main__":
    main()
