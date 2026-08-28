"""
Worker thread for running MonitorService in background.
"""

from PyQt6.QtCore import QThread, pyqtSignal
from typing import Dict, List
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
src_path = Path(__file__).parent.parent.parent  # src directory
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from monitor_service import MonitorService

try:
    from gui.model_lookup import ModelLookup
except ImportError:
    class ModelLookup:
        def __init__(self, *args, **kwargs):
            pass

        def lookup(self, model_code):
            return None


class MonitorWorker(QThread):
    """Worker thread that runs MonitorService in background."""

    aircraft_updated = pyqtSignal(dict)
    anomaly_detected = pyqtSignal(dict)
    summary_updated = pyqtSignal(int, int, int)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(self,
                 region: str = None,
                 states: List[str] = None,
                 interval_seconds: int = 60,
                 credentials_file: Path = None,
                 database_type: str = 'ems'):
        super().__init__()
        self.region = region
        self.states = states
        self.interval_seconds = interval_seconds
        self.credentials_file = credentials_file
        self.database_type = database_type
        self.monitor_service = None
        self._should_pause = False
        self.model_lookup = ModelLookup()

    def run(self):
        """Run the monitoring service in this thread."""
        try:
            states_param = self.states if self.states is not None else []
            if self.region is None and self.states is None:
                states_param = []

            self.monitor_service = MonitorService(
                region=self.region,
                states=states_param,
                interval_seconds=self.interval_seconds,
                credentials_file=self.credentials_file,
                database_type=self.database_type,
                skip_interactive=True,
            )
            self.monitor_service.notifier.console_output = False

            self.status_changed.emit('running')
            self._run_monitoring_loop()

        except Exception as e:
            self.error_occurred.emit(str(e))
            self.status_changed.emit('stopped')

    def _run_monitoring_loop(self):
        """Run monitoring loop with signal emissions."""
        self.monitor_service.running = True
        self.monitor_service.paused = False

        try:
            while self.monitor_service.running and not self.isInterruptionRequested():
                while self._should_pause and self.monitor_service.running:
                    if self.isInterruptionRequested():
                        break
                    self.monitor_service.paused = True
                    self.status_changed.emit('paused')
                    self.msleep(500)

                if not self.monitor_service.running or self.isInterruptionRequested():
                    break

                self.monitor_service.paused = False
                self.status_changed.emit('running')
                self.monitor_service.poll_count += 1
                self.monitor_service._maybe_cleanup_state_db()

                try:
                    current_states = self.monitor_service.poll_aircraft_states()
                    self.monitor_service.current_states = current_states
                    self.aircraft_updated.emit(current_states)

                    previous_states = self.monitor_service.state_tracker.get_all_latest_states()
                    state_history = self.monitor_service.state_tracker.get_histories_batch(
                        list(current_states.keys()), limit=20
                    )

                    anomalies = self.monitor_service.process_state_changes(
                        current_states,
                        previous_states,
                        state_history,
                    )

                    if anomalies:
                        self.monitor_service.recent_anomalies.extend(anomalies)
                        if len(self.monitor_service.recent_anomalies) > 100:
                            self.monitor_service.recent_anomalies = (
                                self.monitor_service.recent_anomalies[-100:]
                            )

                        self.monitor_service.handle_anomalies(
                            anomalies,
                            current_states,
                            model_lookup=self.model_lookup,
                            notify=False,
                            add_detected_at=True,
                            on_anomaly=self.anomaly_detected.emit,
                        )

                    active_count = len(current_states) if current_states else 0
                    anomaly_count = len(anomalies) if anomalies else 0
                    self.summary_updated.emit(
                        self.monitor_service.poll_count,
                        active_count,
                        anomaly_count,
                    )

                except Exception as e:
                    self.error_occurred.emit(f"Error in monitoring loop: {e}")

                if self.monitor_service.running and not self.isInterruptionRequested():
                    for _ in range(self.interval_seconds * 10):
                        if not self.monitor_service.running or self.isInterruptionRequested():
                            break
                        self.msleep(100)

        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if self.monitor_service:
                self.monitor_service.stop()
            self.status_changed.emit('stopped')

    def stop_monitoring(self):
        """Stop the monitoring service cooperatively."""
        self._should_pause = False
        if self.monitor_service:
            self.monitor_service.running = False
        self.requestInterruption()

    def pause_monitoring(self):
        """Pause monitoring."""
        self._should_pause = True

    def resume_monitoring(self):
        """Resume monitoring."""
        self._should_pause = False

    def get_current_states(self) -> Dict:
        """Get current aircraft states."""
        if self.monitor_service:
            return self.monitor_service.get_current_states()
        return {}

    def get_recent_anomalies(self, limit: int = 50) -> List[Dict]:
        """Get recent anomalies."""
        if self.monitor_service:
            return self.monitor_service.get_recent_anomalies(limit)
        return []
