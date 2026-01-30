"""
Geographic context for anomaly detection: airports and hospitals.

Loads US airports (OurAirports CSV) and hospitals CSV; provides distance
and "within radius" queries for suppressing false positives (e.g. landing
near airport) and enriching anomalies with hospital proximity.
"""

import csv
import math
from pathlib import Path
from typing import List, Optional, Tuple

# Lazy-loaded data; None until first use
_airports: Optional[List[Tuple[float, float, str]]] = None
_hospitals: Optional[List[Tuple[float, float, str]]] = None
_airports_path: Optional[Path] = None
_hospitals_path: Optional[Path] = None
_load_warned_airports: bool = False
_load_warned_hospitals: bool = False


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between (lat1, lon1) and (lat2, lon2)."""
    R = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _load_airports(path: Path) -> List[Tuple[float, float, str]]:
    """Load OurAirports CSV; return list of (lat, lon, name). Skip invalid rows."""
    global _load_warned_airports
    result: List[Tuple[float, float, str]] = []
    if not path.exists():
        if not _load_warned_airports:
            _load_warned_airports = True
            import logging
            logging.getLogger(__name__).warning("Airports CSV not found: %s", path)
        return result
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    lat_s = row.get("latitude_deg", "").strip()
                    lon_s = row.get("longitude_deg", "").strip()
                    if not lat_s or not lon_s:
                        continue
                    lat = float(lat_s)
                    lon = float(lon_s)
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        continue
                    name = (row.get("name") or "").strip() or "Unknown"
                    result.append((lat, lon, name))
                except (ValueError, TypeError):
                    continue
    except Exception as e:
        if not _load_warned_airports:
            _load_warned_airports = True
            import logging
            logging.getLogger(__name__).warning("Failed to load airports CSV: %s", e)
        return result
    return result


def _load_hospitals(path: Path) -> List[Tuple[float, float, str]]:
    """Load hospitals CSV; expect LATITUDE, LONGITUDE, NAME. Skip invalid rows."""
    global _load_warned_hospitals
    result: List[Tuple[float, float, str]] = []
    if not path.exists():
        if not _load_warned_hospitals:
            _load_warned_hospitals = True
            import logging
            logging.getLogger(__name__).warning("Hospitals CSV not found: %s", path)
        return result
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    lat_s = (row.get("LATITUDE") or row.get("latitude") or "").strip()
                    lon_s = (row.get("LONGITUDE") or row.get("longitude") or "").strip()
                    if not lat_s or not lon_s:
                        continue
                    lat = float(lat_s)
                    lon = float(lon_s)
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        continue
                    name = (row.get("NAME") or row.get("name") or "").strip() or "Unknown"
                    result.append((lat, lon, name))
                except (ValueError, TypeError):
                    continue
    except Exception as e:
        if not _load_warned_hospitals:
            _load_warned_hospitals = True
            import logging
            logging.getLogger(__name__).warning("Failed to load hospitals CSV: %s", e)
        return result
    return result


class GeoContext:
    """
    Lazy-loading geographic context: airports and hospitals.
    Exposes distance and is_near queries for anomaly suppression and enrichment.
    """

    def __init__(self, airports_path: Path, hospitals_path: Path):
        self.airports_path = Path(airports_path)
        self.hospitals_path = Path(hospitals_path)
        self._airports: Optional[List[Tuple[float, float, str]]] = None
        self._hospitals: Optional[List[Tuple[float, float, str]]] = None

    def _ensure_airports(self) -> List[Tuple[float, float, str]]:
        if self._airports is None:
            self._airports = _load_airports(self.airports_path)
        return self._airports

    def _ensure_hospitals(self) -> List[Tuple[float, float, str]]:
        if self._hospitals is None:
            self._hospitals = _load_hospitals(self.hospitals_path)
        return self._hospitals

    def distance_to_nearest_airport(self, lat: float, lon: float) -> Tuple[float, Optional[str]]:
        """Return (distance_km, name or None). Returns (inf, None) if no data or invalid input."""
        if lat is None or lon is None:
            return (float("inf"), None)
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            return (float("inf"), None)
        points = self._ensure_airports()
        if not points:
            return (float("inf"), None)
        best_km = float("inf")
        best_name: Optional[str] = None
        for plat, plon, name in points:
            d = haversine_km(lat_f, lon_f, plat, plon)
            if d < best_km:
                best_km = d
                best_name = name
        return (best_km, best_name)

    def distance_to_nearest_hospital(self, lat: float, lon: float) -> Tuple[float, Optional[str]]:
        """Return (distance_km, name or None). Returns (inf, None) if no data or invalid input."""
        if lat is None or lon is None:
            return (float("inf"), None)
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            return (float("inf"), None)
        points = self._ensure_hospitals()
        if not points:
            return (float("inf"), None)
        best_km = float("inf")
        best_name: Optional[str] = None
        for plat, plon, name in points:
            d = haversine_km(lat_f, lon_f, plat, plon)
            if d < best_km:
                best_km = d
                best_name = name
        return (best_km, best_name)

    def is_near_airport(self, lat: float, lon: float, radius_km: float) -> bool:
        """True if (lat, lon) is within radius_km of any airport."""
        dist, _ = self.distance_to_nearest_airport(lat, lon)
        return dist <= radius_km

    def is_near_hospital(self, lat: float, lon: float, radius_km: float) -> bool:
        """True if (lat, lon) is within radius_km of any hospital."""
        dist, _ = self.distance_to_nearest_hospital(lat, lon)
        return dist <= radius_km
