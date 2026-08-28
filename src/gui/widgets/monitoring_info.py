"""
Monitoring information widget displaying search parameters and statistics.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from gui.theme import COLORS, SPACING, FONT_SIZES, apply_card_style, SIDEBAR_CARD_MARGINS


class MonitoringInfo(QWidget):
    """Widget displaying monitoring configuration and statistics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.region = None
        self.states = None
        self.database_type = None
        self.active_flights = 0
        self.total_aircraft_in_db = 0
        self.poll_count = 0
        self.anomaly_count = 0
        self.is_fetching = False

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QWidget()
        apply_card_style(card)
        main_layout = QVBoxLayout(card)
        main_layout.setContentsMargins(*SIDEBAR_CARD_MARGINS)
        main_layout.setSpacing(SPACING['sm'])

        content_layout = QVBoxLayout()
        content_layout.setSpacing(SPACING['sm'])
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("Status: Stopped")
        self.status_label.setAccessibleName("Monitoring status")
        self.status_label.setStyleSheet(
            f"font-size: {FONT_SIZES['sm']}px; font-weight: 600; color: {COLORS['status_stopped']}; "
            f"background: transparent;"
        )
        content_layout.addWidget(self.status_label)

        label_style = f"font-size: {FONT_SIZES['sm']}px; color: {COLORS['text_primary']}; background: transparent;"
        muted_style = f"font-size: {FONT_SIZES['sm']}px; color: {COLORS['text_secondary']}; background: transparent;"

        self.db_label = QLabel("Database: N/A")
        self.db_label.setStyleSheet(label_style)
        content_layout.addWidget(self.db_label)

        self.region_label = QLabel("Region/State: N/A")
        self.region_label.setStyleSheet(label_style)
        content_layout.addWidget(self.region_label)

        self.total_aircraft_label = QLabel("Aircraft in DB: 0")
        self.total_aircraft_label.setStyleSheet(muted_style)
        content_layout.addWidget(self.total_aircraft_label)

        self.active_flights_label = QLabel("Active Flights: 0")
        self.active_flights_label.setStyleSheet(
            f"font-size: {FONT_SIZES['sm']}px; font-weight: 600; color: {COLORS['text_primary']}; "
            f"background: transparent;"
        )
        content_layout.addWidget(self.active_flights_label)

        self.anomaly_label = QLabel("Session Anomalies: 0")
        self.anomaly_label.setStyleSheet(muted_style)
        content_layout.addWidget(self.anomaly_label)

        self.poll_label = QLabel("Poll Count: 0")
        self.poll_label.setStyleSheet(muted_style)
        content_layout.addWidget(self.poll_label)

        self.fetching_label = QLabel("")
        self.fetching_label.setStyleSheet(
            f"font-size: {FONT_SIZES['xs']}px; color: {COLORS['primary']}; font-style: italic; "
            f"background: transparent;"
        )
        content_layout.addWidget(self.fetching_label)

        main_layout.addLayout(content_layout)
        root.addWidget(card)
        self._card = card
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    def refresh_theme(self):
        """Re-apply styles after theme change."""
        apply_card_style(self._card)
        self._update_display()
        self.set_status(getattr(self, '_last_status', 'stopped'))

    def set_config(self, region=None, states=None, database_type=None, total_aircraft=0):
        self.region = region
        self.states = states
        self.database_type = database_type
        self.total_aircraft_in_db = total_aircraft
        self._update_display()

    def update_active_flights(self, count: int):
        self.active_flights = count
        self._update_display()

    def update_poll_count(self, count: int):
        self.poll_count = count
        if count == 0:
            self.is_fetching = False
        self._update_display()

    def update_anomaly_count(self, count: int):
        self.anomaly_count = count
        self._update_display()

    def set_fetching(self, fetching: bool):
        self.is_fetching = fetching
        self._update_display()

    def set_status(self, status: str):
        """Update status pill: running, paused, stopped."""
        status = (status or 'stopped').lower()
        self._last_status = status
        color_map = {
            'running': COLORS['success'],
            'paused': COLORS['warning'],
            'stopped': COLORS['status_stopped'],
        }
        label_map = {
            'running': 'Running',
            'paused': 'Paused',
            'stopped': 'Stopped',
        }
        color = color_map.get(status, COLORS['status_stopped'])
        label = label_map.get(status, 'Stopped')
        self.status_label.setText(f"Status: {label}")
        self.status_label.setStyleSheet(
            f"font-size: {FONT_SIZES['sm']}px; font-weight: 600; color: {color}; background: transparent;"
        )

    def _update_display(self):
        db_text = self.database_type.upper() if self.database_type else "N/A"
        self.db_label.setText(f"Database: {db_text}")

        if self.states:
            states_text = ", ".join(self.states) if isinstance(self.states, list) else str(self.states)
            self.region_label.setText(f"State(s): {states_text}")
        elif self.region:
            self.region_label.setText(f"Region: {self.region}")
        else:
            self.region_label.setText("Region/State: All")

        self.total_aircraft_label.setText(f"Aircraft in DB: {self.total_aircraft_in_db}")
        self.active_flights_label.setText(f"Active Flights: {self.active_flights}")
        self.anomaly_label.setText(f"Session Anomalies: {self.anomaly_count}")
        self.poll_label.setText(f"Poll Count: {self.poll_count}")

        if self.is_fetching and self.poll_count == 0:
            self.fetching_label.setText("Fetching data…")
        else:
            self.fetching_label.setText("")
