"""Tests for aircraft filter matching and scoring logic."""

import json
import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aircraft_filter.base import (
    model_matches_pattern,
    normalize_model_string,
    normalize_owner_name,
    owner_matches_keyword,
    score_to_confidence,
    apply_confidence_filter,
    load_model_patterns,
    load_owner_keywords,
    load_negative_keywords,
    is_ambiguous_model,
)
from callsign_utils import get_callsign_boost


class TestModelMatching:
    """Test word-boundary model pattern matching."""

    def test_bell_does_not_match_libelle(self):
        assert not model_matches_pattern(normalize_model_string("STANDARD LIBELLE"), "BELL")

    def test_bell_206_matches(self):
        assert model_matches_pattern(normalize_model_string("BELL 206B"), "BELL 206")

    def test_flight_does_not_match_flightstar(self):
        assert not model_matches_pattern(normalize_model_string("FLIGHTSTAR IISC"), "FLIGHT")

    def test_ec135_matches(self):
        assert model_matches_pattern(normalize_model_string("EC135 P3"), "EC135")

    def test_faa_code_be90(self):
        assert model_matches_pattern(normalize_model_string("BE90"), "BE90")

    def test_short_pattern_rejected(self):
        assert not model_matches_pattern(normalize_model_string("BELL 206"), "BE")

    def test_libelle_not_ambiguous_as_ems(self):
        assert not is_ambiguous_model(normalize_model_string("STANDARD LIBELLE"))

    def test_r44_is_ambiguous(self):
        assert is_ambiguous_model(normalize_model_string("R44 II"))


class TestOwnerKeywords:
    """Test owner keyword matching."""

    def test_flight_school_negative(self):
        negatives = load_negative_keywords(Path(__file__).parent.parent / "data" / "negative_owner_keywords.txt")
        owner = normalize_owner_name("FIRST FLIGHT AVIATION LLC")
        assert any(kw in owner for kw in negatives if "FLIGHT" in kw)

    def test_life_flight_strong_keyword(self):
        strong, weak = load_owner_keywords(Path(__file__).parent.parent / "data" / "ems_owner_keywords.txt")
        owner = normalize_owner_name("LIFE FLIGHT NETWORK INC")
        assert any(owner_matches_keyword(owner, kw) for kw in strong)

    def test_bare_flight_not_in_strong(self):
        strong, _ = load_owner_keywords(Path(__file__).parent.parent / "data" / "ems_owner_keywords.txt")
        assert "FLIGHT" not in strong

    def test_sheriff_police_keyword(self):
        strong, weak = load_owner_keywords(Path(__file__).parent.parent / "data" / "police_owner_keywords.txt")
        owner = normalize_owner_name("MARSHALL COUNTY SHERIFF DEPT")
        assert any(owner_matches_keyword(owner, kw) for kw in (strong | weak))


class TestScoring:
    """Test confidence mapping."""

    def test_high_confidence(self):
        assert score_to_confidence(5, True, True) == "high"

    def test_medium_confidence(self):
        assert score_to_confidence(3, True, False) == "medium"

    def test_low_confidence(self):
        assert score_to_confidence(2, False, False) == "low"


class TestConfidenceFilter:
    """Test MIN_CONFIDENCE_LEVEL filtering."""

    def test_medium_filter(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "MIN_CONFIDENCE_LEVEL", "medium")
        aircraft = [
            {"confidence": "low", "mode_s_hex": "A00001"},
            {"confidence": "medium", "mode_s_hex": "A00002"},
            {"confidence": "high", "mode_s_hex": "A00003"},
        ]
        result = apply_confidence_filter(aircraft)
        assert len(result) == 2
        assert all(a["confidence"] in ("medium", "high") for a in result)


class TestCallsignBoost:
    """Test runtime callsign boost detection."""

    def test_medevac_callsign(self):
        assert get_callsign_boost("MEDEVAC1") is not None

    def test_normal_callsign(self):
        assert get_callsign_boost("UAL123") is None

    def test_empty_callsign(self):
        assert get_callsign_boost(None) is None


class TestDataFiles:
    """Test that data files load correctly."""

    def test_ems_models_load(self):
        patterns = load_model_patterns(Path(__file__).parent.parent / "data" / "ems_models.txt")
        assert "EC135" in patterns
        assert "FLIGHT" not in patterns
        assert "BELL" not in patterns  # Only "BELL 206" etc.

    def test_police_models_load(self):
        patterns = load_model_patterns(Path(__file__).parent.parent / "data" / "police_models.txt")
        assert "BELL 206" in patterns

    def test_known_aircraft_fixture_valid(self):
        fixture = Path(__file__).parent / "fixtures" / "known_aircraft.json"
        with open(fixture) as f:
            cases = json.load(f)
        assert len(cases) >= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
