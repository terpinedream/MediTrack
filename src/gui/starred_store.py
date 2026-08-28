"""Persistent starred aircraft entries for the monitoring dashboard."""

from __future__ import annotations

import json
from typing import Dict, Optional, Set

from PyQt6.QtCore import QSettings


class StarredAircraftStore:
    """Keeps starred aircraft across region/database changes."""

    SETTINGS_KEY = "starred/aircraft"

    def __init__(self):
        self.entries: Dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        settings = QSettings("MediTrack", "MediTrack")
        raw = settings.value(self.SETTINGS_KEY, "[]")
        try:
            items = json.loads(raw) if isinstance(raw, str) else []
        except json.JSONDecodeError:
            items = []
        self.entries = {}
        for item in items:
            icao = (item.get("icao24") or "").strip().upper()
            if not icao:
                continue
            info = item.get("aircraft_info") or {}
            if not info.get("mode_s_hex"):
                info["mode_s_hex"] = icao
            self.entries[icao] = {
                "icao24": icao,
                "aircraft_info": info,
                "last_state": item.get("last_state") or {"icao24": icao},
                "database_type": item.get("database_type"),
            }

    def save(self) -> None:
        settings = QSettings("MediTrack", "MediTrack")
        settings.setValue(self.SETTINGS_KEY, json.dumps(list(self.entries.values())))

    def is_starred(self, icao24: str) -> bool:
        return icao24.upper() in self.entries

    def starred_icao24s(self) -> Set[str]:
        return set(self.entries.keys())

    def add(
        self,
        icao24: str,
        aircraft_info: Optional[dict],
        last_state: Optional[dict],
        database_type: Optional[str] = None,
    ) -> None:
        icao = icao24.upper()
        info = dict(aircraft_info or {})
        if not info.get("mode_s_hex"):
            info["mode_s_hex"] = icao
        self.entries[icao] = {
            "icao24": icao,
            "aircraft_info": info,
            "last_state": dict(last_state or {"icao24": icao}),
            "database_type": database_type,
        }
        self.save()

    def remove(self, icao24: str) -> None:
        self.entries.pop(icao24.upper(), None)
        self.save()

    def update_last_state(self, icao24: str, state: dict) -> None:
        entry = self.entries.get(icao24.upper())
        if entry is not None:
            entry["last_state"] = dict(state)
            self.save()

    def build_table_payload(self, current_states: Dict[str, dict]):
        """Return (states, db_list) for the starred table."""
        states = {}
        db_list = []
        for icao, entry in self.entries.items():
            info = entry.get("aircraft_info") or {"mode_s_hex": icao}
            db_list.append(info)
            if icao in current_states:
                states[icao] = current_states[icao]
                entry["last_state"] = current_states[icao]
            else:
                states[icao] = entry.get("last_state") or {"icao24": icao}
        return states, db_list
