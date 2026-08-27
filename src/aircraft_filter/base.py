"""
Shared base module for EMS and Police aircraft filtering.

Provides FAA database loading, model/owner matching, weighted scoring,
and exclusion rules used by both filter implementations.
"""

import csv
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import config

# FAA model codes exempt from minimum pattern length
FAA_CODE_PATTERN = re.compile(r'^[A-Z0-9]{2,5}$')

# Models that require corroboration (owner keyword, N-number, or known operator)
AMBIGUOUS_MODEL_PATTERNS: Set[str] = {
    'R44', 'R66', 'ROBINSON R44', 'ROBINSON R66',
    'C172', 'C182', 'C206', 'C210', 'CESSNA 172', 'CESSNA 182', 'CESSNA 206', 'CESSNA 210',
    'PA28', 'PA32', 'PIPER PA28', 'PIPER PA32',
}

CONFIDENCE_ORDER = {'low': 0, 'medium': 1, 'high': 2}

BUSINESS_JET_PATTERNS = {
    'CITATION', 'LEARJET', 'GULFSTREAM', 'FALCON',
    'CHALLENGER', 'GLOBAL', 'LEGACY', 'PHENOM',
}

MUSEUM_KEYWORDS = {
    'MUSEUM', 'MUSEUMS', 'AVIATION MUSEUM', 'AIR MUSEUM',
    'FLIGHT MUSEUM', 'AEROSPACE MUSEUM', 'AIRSPACE MUSEUM',
    'MUSEUM OF', 'AIR & SPACE MUSEUM', 'AIR AND SPACE MUSEUM',
}

COMMERCIAL_EXCLUSION_KEYWORDS = {
    'FEDERAL EXPRESS', 'FEDERAL EXPRESS CORP', 'FEDEX', 'FED EX',
    'FEDERAL EXPRESS CORPORATION', 'FEDEX EXPRESS', 'FEDEX CORP',
}

AIRLINE_PATTERNS = {
    'A320', 'A321', 'A330', 'A350', 'A380',
    'B737', 'B747', 'B757', 'B767', 'B777', 'B787',
    'MD80', 'MD90', 'MD11', 'CRJ', 'ERJ', 'E170', 'E175',
}

GOVERNMENT_OWNER_BOOSTS = {
    'CITY OF', 'COUNTY OF', 'COUNTY', 'STATE OF', 'DEPARTMENT OF',
    'GOVERNMENT', 'AUTHORITY',
}


@dataclass
class FilteredAircraft:
    """Represents a filtered aircraft with metadata."""
    n_number: str
    mode_s_hex: str
    model_code: str
    model_name: str
    manufacturer: str
    owner_name: str
    owner_city: str
    owner_state: str
    match_reasons: List[str]
    confidence: str
    score: int
    category: str
    type_aircraft: str
    type_engine: str
    status_code: str


@dataclass
class FilterStats:
    """Summary statistics from a filter run."""
    total_processed: int = 0
    excluded: int = 0
    found: int = 0
    confidence_counts: Dict[str, int] = field(default_factory=dict)
    excluded_reasons: Dict[str, int] = field(default_factory=dict)


def normalize_model_string(model: str) -> str:
    """Normalize model string for matching: uppercase, strip punctuation."""
    if not model:
        return ""
    normalized = re.sub(r'[^\w\s]', '', model.upper())
    return re.sub(r'\s+', ' ', normalized).strip()


def normalize_owner_name(owner_name: str) -> str:
    """Normalize owner name for keyword matching."""
    if not owner_name:
        return ""
    normalized = owner_name.upper()
    suffixes = [
        ' LLC', ' INC', ' CORP', ' CORPORATION', ' LTD', ' LIMITED',
        ' LP', ' LLP', ' PC', ' PLLC', ' LLC.', ' INC.', ' CORP.',
    ]
    for suffix in suffixes:
        normalized = re.sub(rf'{re.escape(suffix)}\s*$', '', normalized, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', normalized).strip()


def model_matches_pattern(model_normalized: str, pattern: str) -> bool:
    """
    Match model name against pattern using token boundaries.

    FAA codes match exactly. Longer patterns use prefix-at-boundary matching
    to avoid false positives (e.g. BELL must not match LIBELLE).
    """
    if not model_normalized or not pattern:
        return False

    pattern = pattern.upper().strip()
    model_normalized = model_normalized.upper()

    if FAA_CODE_PATTERN.match(pattern) and len(pattern) <= 5:
        if model_normalized == pattern:
            return True
        if model_normalized.startswith(pattern + ' ') or model_normalized.startswith(pattern):
            rest = model_normalized[len(pattern):]
            if rest and (rest[0].isspace() or rest[0].isdigit()):
                return True
        return False

    if len(pattern) < 4:
        return False

    if model_normalized == pattern:
        return True

    if model_normalized.startswith(pattern):
        rest = model_normalized[len(pattern):]
        if not rest:
            return True
        if rest[0].isspace():
            return True
        if pattern[-1].isdigit() and rest[0].isalnum():
            return True
        return False

    pattern_re = r'\b' + re.escape(pattern) + r'(?:\s|$)'
    if re.search(pattern_re, model_normalized):
        return True
    if pattern[-1].isdigit():
        pattern_re = r'\b' + re.escape(pattern) + r'[A-Z0-9]'
        return bool(re.search(pattern_re, model_normalized))
    return False


def is_ambiguous_model(model_normalized: str) -> bool:
    """Return True if model requires corroborating signals beyond model match alone."""
    if not model_normalized:
        return False
    for pattern in AMBIGUOUS_MODEL_PATTERNS:
        if model_matches_pattern(model_normalized, pattern):
            return True
    return False


def is_valid_mode_s_hex(mode_s_hex: str) -> bool:
    """Validate Mode S code format (exactly 6 hex characters)."""
    if not mode_s_hex:
        return False
    return bool(re.match(r'^[0-9A-F]{6}$', mode_s_hex.upper().strip()))


def load_model_patterns(path: Path) -> Set[str]:
    """Load model patterns from a text file (one per line, # comments)."""
    patterns: Set[str] = set()
    if not path.exists():
        raise FileNotFoundError(f"Model patterns file not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            line = re.sub(r'\([^)]*\)', '', line).strip()
            normalized = normalize_model_string(line)
            if not normalized:
                continue
            if len(normalized) < 4 and not FAA_CODE_PATTERN.match(normalized):
                continue
            if normalized.isupper() and ' ' not in normalized and len(normalized) > 15:
                continue
            patterns.add(normalized)

    return patterns


def load_owner_keywords(path: Path) -> Tuple[Set[str], Set[str]]:
    """Load owner keywords grouped by [strong] and [weak] sections."""
    strong: Set[str] = set()
    weak: Set[str] = set()
    section = 'strong'

    if not path.exists():
        raise FileNotFoundError(f"Owner keywords file not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('[strong]'):
                section = 'strong'
                continue
            if line.startswith('[weak]'):
                section = 'weak'
                continue
            keyword = line.upper()
            if section == 'strong':
                strong.add(keyword)
            else:
                weak.add(keyword)

    return strong, weak


def load_negative_keywords(path: Path) -> Set[str]:
    """Load negative owner keywords from file."""
    keywords: Set[str] = set()
    if not path.exists():
        return keywords
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                keywords.add(line.upper())
    return keywords


def load_known_operators(path: Path) -> Dict[str, Set[str]]:
    """Load known operator allowlist from JSON."""
    result: Dict[str, Set[str]] = {'ems': set(), 'police': set(), 'both': set()}
    if not path.exists():
        return result
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for category in ('ems', 'police', 'both'):
        result[category] = {op.upper() for op in data.get(category, [])}
    return result


def owner_matches_keyword(owner_normalized: str, keyword: str) -> bool:
    """Check if normalized owner name matches a keyword."""
    if not owner_normalized or not keyword:
        return False
    if len(keyword) <= 3:
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', owner_normalized))
    return keyword in owner_normalized


def score_to_confidence(score: int, has_model: bool, has_strong_owner: bool) -> str:
    """Map score to confidence tier."""
    if score >= 5 or (has_model and has_strong_owner):
        return 'high'
    if score >= 3:
        return 'medium'
    return 'low'


class BaseAircraftFilter(ABC):
    """Base class for FAA aircraft filtering with weighted scoring."""

    category: str = 'unknown'

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.master_file = data_dir / "ReleasableAircraft" / "MASTER.txt"
        self.acftref_file = data_dir / "ReleasableAircraft" / "ACFTREF.txt"
        self.data_path = data_dir / "data"

        self.model_lookup: Dict[str, Dict[str, str]] = {}
        self.model_patterns: Set[str] = set()
        self.model_codes: Set[str] = set()
        self.strong_keywords: Set[str] = set()
        self.weak_keywords: Set[str] = set()
        self.negative_keywords: Set[str] = set()
        self.known_operators: Dict[str, Set[str]] = {'ems': set(), 'police': set(), 'both': set()}
        self.stats = FilterStats()

    @abstractmethod
    def get_models_file(self) -> Path:
        """Return path to model patterns file."""

    @abstractmethod
    def get_owner_keywords_file(self) -> Path:
        """Return path to owner keywords file."""

    @abstractmethod
    def check_n_number_pattern(self, n_number: str) -> Tuple[bool, Optional[str]]:
        """Check N-number suffix patterns. Returns (matched, reason)."""

    def load_resources(self) -> None:
        """Load all filter configuration and FAA reference data."""
        self.model_patterns = load_model_patterns(self.get_models_file())
        self.strong_keywords, self.weak_keywords = load_owner_keywords(self.get_owner_keywords_file())
        self.negative_keywords = load_negative_keywords(self.data_path / "negative_owner_keywords.txt")
        self.known_operators = load_known_operators(self.data_path / "known_operators.json")
        self.load_aircraft_reference()
        self._build_model_codes()
        print(f"Loaded {len(self.model_patterns)} model patterns, "
              f"{len(self.strong_keywords)} strong / {len(self.weak_keywords)} weak owner keywords")

    def load_aircraft_reference(self) -> None:
        """Load aircraft reference database (ACFTREF.txt)."""
        if not self.acftref_file.exists():
            raise FileNotFoundError(f"ACFTREF file not found: {self.acftref_file}")

        with open(self.acftref_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("Could not read header from ACFTREF file")

            code_key = mfr_key = model_key = None
            for key in reader.fieldnames:
                if not key:
                    continue
                key_clean = key.strip().lstrip('\ufeff')
                if key_clean == 'CODE':
                    code_key = key
                elif key_clean == 'MFR':
                    mfr_key = key
                elif key_clean == 'MODEL':
                    model_key = key

            if not code_key:
                valid_keys = [k for k in reader.fieldnames if k and k.strip()]
                if len(valid_keys) >= 3:
                    code_key, mfr_key, model_key = valid_keys[0], valid_keys[1], valid_keys[2]
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
                    'model_normalized': normalize_model_string(model),
                }

        print(f"Loaded {len(self.model_lookup)} aircraft model references")

    def _build_model_codes(self) -> None:
        """Precompute FAA model codes matching our patterns."""
        self.model_codes = set()
        for code, info in self.model_lookup.items():
            model_norm = info.get('model_normalized', '')
            for pattern in self.model_patterns:
                if model_matches_pattern(model_norm, pattern):
                    self.model_codes.add(code)
                    break
        print(f"Found {len(self.model_codes)} matching model codes in reference database")

    def matches_model(self, model_code: str) -> Tuple[bool, Optional[str], Optional[str], bool]:
        """
        Check if model code matches filter patterns.
        Returns: (matches, model_name, manufacturer, is_ambiguous)
        """
        if not model_code or model_code not in self.model_lookup:
            return False, None, None, False

        model_info = self.model_lookup[model_code]
        model_norm = model_info['model_normalized']
        model_name = model_info['model']
        manufacturer = model_info['manufacturer']

        if model_code in self.model_codes:
            return True, model_name, manufacturer, is_ambiguous_model(model_norm)

        for pattern in self.model_patterns:
            if model_matches_pattern(model_norm, pattern):
                return True, model_name, manufacturer, is_ambiguous_model(model_norm)

        return False, None, None, False

    def matches_owner_keywords(self, owner_name: str) -> Tuple[bool, bool, List[str]]:
        """
        Check owner keywords. Returns (matched, is_strong, matched_keywords).
        """
        if not owner_name:
            return False, False, []

        owner_norm = normalize_owner_name(owner_name)
        matched: List[str] = []
        is_strong = False

        for keyword in self.strong_keywords:
            if owner_matches_keyword(owner_norm, keyword):
                matched.append(keyword)
                is_strong = True

        for keyword in self.weak_keywords:
            if owner_matches_keyword(owner_norm, keyword):
                matched.append(keyword)

        return bool(matched), is_strong, matched

    def matches_negative_keywords(self, owner_name: str) -> Tuple[bool, List[str]]:
        """Check negative owner keywords."""
        if not owner_name:
            return False, []
        owner_norm = normalize_owner_name(owner_name)
        owner_raw = owner_name.upper()
        matched = []
        for keyword in self.negative_keywords:
            if keyword in owner_norm or keyword in owner_raw:
                matched.append(keyword)
        return bool(matched), matched

    def matches_known_operator(self, owner_name: str) -> bool:
        """Check if owner matches known operator allowlist."""
        if not owner_name:
            return False
        owner_norm = normalize_owner_name(owner_name)
        for op in self.known_operators.get('both', set()):
            if op in owner_norm:
                return True
        for op in self.known_operators.get(self.category, set()):
            if op in owner_norm:
                return True
        return False

    def is_business_jet_model(self, model_normalized: str) -> bool:
        """Check if model is a business jet pattern."""
        for pattern in BUSINESS_JET_PATTERNS:
            if model_matches_pattern(model_normalized, pattern):
                return True
        return False

    def has_government_boost(self, owner_name: str, type_registrant: str) -> bool:
        """Check for government registrant signals."""
        if type_registrant == '6':
            return True
        if not owner_name:
            return False
        owner_norm = normalize_owner_name(owner_name)
        return any(boost in owner_norm for boost in GOVERNMENT_OWNER_BOOSTS)

    def _all_positive_keywords(self) -> Set[str]:
        return self.strong_keywords | self.weak_keywords

    def should_exclude(self, row: Dict[str, str]) -> Tuple[bool, str]:
        """Check if aircraft should be excluded before scoring."""
        status_code = row.get('STATUS CODE', '').strip()
        if status_code != 'V':
            return True, f"Status code: {status_code}"

        owner_name = row.get('NAME', '').strip().upper()
        if owner_name:
            for museum_keyword in MUSEUM_KEYWORDS:
                if museum_keyword in owner_name:
                    return True, f"Museum-owned: {row.get('NAME', '').strip()[:50]}"

            for exclusion_keyword in COMMERCIAL_EXCLUSION_KEYWORDS:
                if exclusion_keyword in owner_name:
                    return True, f"Commercial cargo: {row.get('NAME', '').strip()[:50]}"

            neg_match, _ = self.matches_negative_keywords(row.get('NAME', ''))
            if neg_match:
                return True, f"Negative keyword: {row.get('NAME', '').strip()[:50]}"

        type_aircraft = row.get('TYPE AIRCRAFT', '').strip()
        type_engine = row.get('TYPE ENGINE', '').strip()
        if type_aircraft == '4' and type_engine == '1':
            return True, "Piston engine aircraft"

        model_code = row.get('MFR MDL CODE', '').strip()
        if model_code in self.model_lookup:
            model_name = self.model_lookup[model_code]['model']
            model_normalized = normalize_model_string(model_name)
            for airline_pattern in AIRLINE_PATTERNS:
                if airline_pattern in model_normalized:
                    return True, f"Airline aircraft: {model_name}"

        type_registrant = row.get('TYPE REGISTRANT', '').strip()
        if config.EXCLUDE_INDIVIDUAL_OWNERS and type_registrant == '1':
            return True, "Individual owner"

        if owner_name:
            is_llc = any(ind in owner_name for ind in
                         [' LLC', ' LLC.', ' LIMITED LIABILITY', ' L.L.C.', ' L L C'])
            if is_llc:
                owner_norm = normalize_owner_name(row.get('NAME', ''))
                has_keyword = any(owner_matches_keyword(owner_norm, kw) for kw in self._all_positive_keywords())
                if not has_keyword and not self.matches_known_operator(row.get('NAME', '')):
                    return True, f"Private LLC (no keywords): {row.get('NAME', '').strip()[:50]}"

        return False, ""

    def score_aircraft(
        self,
        row: Dict[str, str],
        model_match: bool,
        model_name: str,
        is_ambiguous: bool,
        owner_match: bool,
        owner_strong: bool,
        owner_keywords: List[str],
        n_pattern_match: bool,
        n_pattern_reason: Optional[str],
        known_operator: bool,
        model_normalized: str,
    ) -> Tuple[int, List[str], str]:
        """
        Compute weighted score for an aircraft.
        Returns: (score, match_reasons, confidence)
        """
        score = 0
        reasons: List[str] = []

        if known_operator:
            score += 3
            reasons.append("Known operator")

        if model_match and not is_ambiguous:
            score += 2
            reasons.append(f"Model: {model_name}")

        if owner_match:
            kw_label = ', '.join(owner_keywords[:3])
            if owner_strong:
                score += 2
                reasons.append(f"Strong owner keyword ({kw_label})")
            else:
                score += 1
                reasons.append(f"Weak owner keyword ({kw_label})")

        if n_pattern_match and n_pattern_reason:
            score += 2
            reasons.append(n_pattern_reason)

        if model_match and is_ambiguous and (owner_match or n_pattern_match or known_operator):
            score += 2
            reasons.append(f"Ambiguous model corroborated: {model_name}")
        elif model_match and is_ambiguous:
            score += 0
            reasons.append(f"Ambiguous model (needs corroboration): {model_name}")

        type_registrant = row.get('TYPE REGISTRANT', '').strip()
        if self.has_government_boost(row.get('NAME', ''), type_registrant):
            score += 1
            reasons.append("Government registrant")

        if (self.is_business_jet_model(model_normalized) and model_match
                and not owner_strong and not known_operator and not n_pattern_match):
            score -= 2
            reasons.append("Business jet penalty")

        confidence = score_to_confidence(score, model_match and not is_ambiguous, owner_strong or known_operator)
        return score, reasons, confidence

    def filter_aircraft(self) -> List[FilteredAircraft]:
        """Filter FAA MASTER database using weighted scoring."""
        if not self.master_file.exists():
            raise FileNotFoundError(f"MASTER file not found: {self.master_file}")

        results: List[FilteredAircraft] = []
        excluded_count = 0
        excluded_reasons: Dict[str, int] = {}
        idx = 0

        print("Filtering aircraft database...")
        with open(self.master_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            n_number_key = self._find_n_number_key(reader.fieldnames)

            for idx, row in enumerate(reader):
                if idx > 0 and idx % 10000 == 0:
                    print(f"  Processed {idx} aircraft... (Found {len(results)}, Excluded {excluded_count})")

                should_exclude, exclude_reason = self.should_exclude(row)
                if should_exclude:
                    excluded_count += 1
                    excluded_reasons[exclude_reason] = excluded_reasons.get(exclude_reason, 0) + 1
                    continue

                n_number = (row.get('N-NUMBER', '') or row.get(n_number_key, '')).strip()
                if not n_number:
                    continue

                mode_s_hex = row.get('MODE S CODE HEX', '').strip().upper()
                if not is_valid_mode_s_hex(mode_s_hex):
                    continue

                model_code = row.get('MFR MDL CODE', '').strip()
                owner_name = row.get('NAME', '').strip()

                model_match, model_name, manufacturer, ambiguous = self.matches_model(model_code)
                if not model_name and model_code in self.model_lookup:
                    info = self.model_lookup[model_code]
                    model_name = info.get('model', '')
                    manufacturer = info.get('manufacturer', '')

                model_normalized = normalize_model_string(model_name or '')
                owner_match, owner_strong, owner_kws = self.matches_owner_keywords(owner_name)
                known_operator = self.matches_known_operator(owner_name)
                n_pattern_match, n_pattern_reason = self.check_n_number_pattern(n_number)

                score, reasons, confidence = self.score_aircraft(
                    row=row,
                    model_match=model_match,
                    model_name=model_name or "Unknown",
                    is_ambiguous=ambiguous,
                    owner_match=owner_match,
                    owner_strong=owner_strong,
                    owner_keywords=owner_kws,
                    n_pattern_match=n_pattern_match,
                    n_pattern_reason=n_pattern_reason,
                    known_operator=known_operator,
                    model_normalized=model_normalized,
                )

                if score < 3:
                    continue

                results.append(FilteredAircraft(
                    n_number=n_number,
                    mode_s_hex=mode_s_hex,
                    model_code=model_code,
                    model_name=model_name or "Unknown",
                    manufacturer=manufacturer or "Unknown",
                    owner_name=owner_name,
                    owner_city=row.get('CITY', '').strip(),
                    owner_state=row.get('STATE', '').strip(),
                    match_reasons=reasons,
                    confidence=confidence,
                    score=score,
                    category=self.category,
                    type_aircraft=row.get('TYPE AIRCRAFT', '').strip(),
                    type_engine=row.get('TYPE ENGINE', '').strip(),
                    status_code=row.get('STATUS CODE', '').strip(),
                ))

        self.stats = FilterStats(
            total_processed=idx + 1,
            excluded=excluded_count,
            found=len(results),
            excluded_reasons=excluded_reasons,
            confidence_counts=_count_confidence(results),
        )

        self._print_stats(results, excluded_count, excluded_reasons, idx + 1)
        return results

    def _find_n_number_key(self, fieldnames) -> str:
        if not fieldnames:
            return 'N-NUMBER'
        for key in fieldnames:
            if key:
                key_clean = key.strip().lstrip('\ufeff')
                if key_clean in ('N-NUMBER', 'N NUMBER'):
                    return key
        return fieldnames[0]

    def _print_stats(self, results, excluded_count, excluded_reasons, total) -> None:
        print(f"\nFiltering Statistics:")
        print(f"  Total processed: {total}")
        print(f"  Excluded: {excluded_count}")
        print(f"  {self.category.upper()} aircraft found: {len(results)}")
        conf = _count_confidence(results)
        print(f"  Confidence: high={conf.get('high', 0)}, medium={conf.get('medium', 0)}, low={conf.get('low', 0)}")
        if excluded_reasons:
            print("  Top exclusion reasons:")
            for reason, count in sorted(excluded_reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"    {reason}: {count}")

    def run(self) -> List[FilteredAircraft]:
        """Run the complete filtering process."""
        self.load_resources()
        return self.filter_aircraft()


def _count_confidence(results: List[FilteredAircraft]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for ac in results:
        counts[ac.confidence] = counts.get(ac.confidence, 0) + 1
    return counts


def filtered_to_dict(ac: FilteredAircraft) -> dict:
    """Convert FilteredAircraft to a plain dict for JSON export."""
    return {
        'n_number': ac.n_number,
        'mode_s_hex': ac.mode_s_hex,
        'model_code': ac.model_code,
        'model_name': ac.model_name,
        'manufacturer': ac.manufacturer,
        'owner_name': ac.owner_name,
        'owner_city': ac.owner_city,
        'owner_state': ac.owner_state,
        'match_reasons': ac.match_reasons,
        'confidence': ac.confidence,
        'score': ac.score,
        'category': ac.category,
        'type_aircraft': ac.type_aircraft,
        'type_engine': ac.type_engine,
        'status_code': ac.status_code,
    }


def apply_confidence_filter(aircraft: List[dict], min_level: Optional[str] = None) -> List[dict]:
    """Filter aircraft list by minimum confidence level."""
    min_level = min_level or config.MIN_CONFIDENCE_LEVEL
    threshold = CONFIDENCE_ORDER.get(min_level, 0)
    return [a for a in aircraft if CONFIDENCE_ORDER.get(a.get('confidence', 'low'), 0) >= threshold]
