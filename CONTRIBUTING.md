# Contributing to MediTrack

Thanks for helping improve MediTrack. This project tracks EMS and police aircraft from public FAA registry data and live OpenSky ADS-B states. Changes should keep false positives down — a missed agency aircraft is better than filling the list with flight schools and leasing companies.

## Development setup

Python 3.10+ is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

1. Download the [FAA Releasable Aircraft ZIP](https://registry.faa.gov/database/ReleasableAircraft.zip) and extract `ReleasableAircraft/` (with `MASTER.txt` and `ACFTREF.txt`) into the project root.
2. Optional: copy `.env.example` to `.env` and add OpenSky credentials.
3. Build databases, then run the GUI:

```bash
python3 src/create_ems_database.py
python3 src/filter_police_aircraft.py
python3 src/run_gui.py
```

Do not commit `ReleasableAircraft/`, generated files under `data/*.json`, `.env`, or `credentials.json`.

## Where to change things

| If you want to… | Edit |
|---|---|
| Add/remove EMS or police models | `data/ems_models.txt`, `data/police_models.txt` |
| Tune owner matching | `data/ems_owner_keywords.txt`, `data/police_owner_keywords.txt` |
| Exclude flight schools, tours, etc. | `data/negative_owner_keywords.txt` |
| Allowlist a known operator | `data/known_operators.json` |
| Change list-view owner tags | `src/owner_tags.py` |
| Change scoring / confidence | `src/aircraft_filter/base.py` |
| Change live monitoring or anomalies | `src/monitor_service.py`, `src/anomaly_detector.py` |
| Change the dashboard | `src/gui/` |

Keyword files use `#` comments. Owner keyword files are split into `[strong]` and `[weak]` sections.

After changing model or owner keyword files, rebuild the databases. Owner tags are computed at display time from names already in the filtered set, so a rebuild is not required for tag-only changes.

## Pull requests

- Prefer a focused change with a short explanation of *why*.
- Keep the existing code style (no unused imports or drive-by refactors).
- Update `CHANGELOG.md` under `[Unreleased]` for user-facing changes.
- If the GUI changed, say how you verified it (running `src/run_gui.py` is enough).

## Reporting issues

Include the database type (EMS or police), whether it is a false positive or a miss, the owner name / N-number / model if you have them, and a screenshot of the list row when it is a UI issue.

Please do not file issues that ask for help tracking a specific person or using the tool for anything other than public aircraft monitoring.
