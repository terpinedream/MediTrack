# Changelog

All notable changes to MediTrack are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-08-28

### Added

- Starred aircraft: click ☆ on an active flight to keep it in a persistent starred panel and on the map across database and region changes.
- Dark mode toggle (**Settings → Dark mode**).
- Map fullscreen view (**Fullscreen** on the map panel; **Esc** to exit).
- Sudden speed increase anomaly detection (compares recent poll history to current speed).
- Edit menu: show/hide table columns, reset column widths, reset layout.
- Keyboard shortcuts: `Ctrl+R` start/resume, `Ctrl+P` pause, `Ctrl+Shift+S` stop, `Ctrl+E` export active aircraft CSV.
- Session anomaly count in the sidebar status panel.
- Structured logging via `LOG_LEVEL` in `config.py` / `.env`.
- GitHub Actions CI workflow.
- Updated application logo and sidebar branding.

### Changed

- Dashboard UI refresh with card-based sidebar, updated theme, and a **Settings** button for monitoring configuration (database, region, states).
- **Setup data** moved to **Settings → Setup data (FAA download)...**; opens automatically on first run when no database exists.
- Throttled aircraft table updates to reduce UI freezing during rapid OpenSky polls.
- Monitor worker, state persistence, and OpenSky client polling improvements.
- README screenshots updated to match the current dashboard.

## [0.2.0] - 2026-08-27

### Added

- Owner-type tags in the main aircraft list and detail dialog. After filtering, registrant names are scanned for agency keywords so likely police/EMS matches are visible at a glance (Police, EMS, Hospital, Fire, Forest, Federal, City, County, Parish, State, Public Safety, CAP).
- Shared `aircraft_filter` module with word-boundary model matching, weighted scoring, confidence tiers (`low` / `medium` / `high`), and a score threshold of 3.
- Dedicated filter data files under `data/`: model patterns, strong/weak owner keywords, negative owner keywords, and known operators.
- Callsign boost at monitor time when a callsign looks like EMS/police activity (does not change which aircraft are in the database).
- `MIN_CONFIDENCE_LEVEL` applied when loading databases (default `medium`).

### Changed

- EMS and police filters now share the same scoring path instead of separate one-off matchers.
- Police JSON output uses the same metadata wrapper as EMS.
- GUI shows confidence, match score, and match reasons on aircraft rows and in the detail dialog.
- Database setup worker reports confidence counts after a rebuild.
- Geo context uses a spatial grid index; airport proximity suppression covers more approach/landing cases.

### Fixed

- Substring false positives in model matching (for example BELL matching LIBELLE, FLIGHT matching FLIGHTSTAR).
- Ambiguous common models (R44, C172, and similar) no longer pass on model match alone; they need an owner keyword, N-number pattern, or known operator.

## [0.1.0] - 2026-02-01

### Added

- EMS and Police aircraft databases built from the FAA releasable registry.
- OpenSky Network monitoring (GUI and CLI) with regional and state filters.
- Anomaly detection: high speed, rapid climb/descent, emergency squawks, erratic heading, multiple launches.
- Geographic context: suppress likely false positives near airports; enrich alerts with hospital proximity.
- PyQt6 monitoring dashboard with aircraft table, anomaly list, and interactive map.
- Export of active aircraft and anomalies.
