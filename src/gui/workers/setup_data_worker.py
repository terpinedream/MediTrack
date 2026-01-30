"""
Worker for building EMS and Police aircraft databases in a background thread.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal


class SetupDataWorker(QObject):
    """Builds EMS then Police databases; emits progress and finished signals."""

    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)  # 0–100
    finished_success = pyqtSignal()
    finished_error = pyqtSignal(str)

    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = Path(project_root)
        self.data_dir = self.project_root / "data"

    def run(self):
        """Run EMS then Police build in this thread. Emit progress and finished."""
        try:
            self.progress_percent.emit(0)
            # Ensure imports can find project modules
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))
            src_path = self.project_root / "src"
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))

            # EMS: filter then generate
            self.progress.emit("Building EMS...")
            from filter_ems_aircraft import EMSAircraftFilter
            from create_ems_database import EMSDatabaseGenerator

            filter_ems = EMSAircraftFilter(self.project_root)
            ems_aircraft = filter_ems.run()
            self.progress.emit(f"EMS: {len(ems_aircraft)} aircraft")

            generator = EMSDatabaseGenerator(self.project_root, self.data_dir)
            generator.generate(ems_aircraft)
            self.progress.emit("EMS databases written (JSON, CSV, SQLite).")
            self.progress_percent.emit(50)

            # Police: filter then save JSON
            self.progress.emit("Building Police...")
            from filter_police_aircraft import PoliceAircraftFilter, save_to_json

            filter_police = PoliceAircraftFilter(self.project_root)
            police_aircraft = filter_police.run()
            self.progress.emit(f"Police: {len(police_aircraft)} aircraft")

            police_json = self.data_dir / "police_aircraft.json"
            save_to_json(police_aircraft, police_json)
            self.progress.emit("Police database written (JSON).")
            self.progress_percent.emit(100)

            self.finished_success.emit()
        except FileNotFoundError as e:
            self.progress.emit(str(e))
            self.finished_error.emit(str(e))
        except Exception as e:
            self.progress.emit(str(e))
            self.finished_error.emit(str(e))
