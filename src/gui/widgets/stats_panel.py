"""
Statistics panel widget showing monitoring summary.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt
from gui.theme import COLORS, SPACING, FONT_SIZES, RADIUS


class StatsPanel(QWidget):
    """Panel displaying monitoring statistics."""
    
    def __init__(self, parent=None):
        """Initialize stats panel."""
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()
        layout.setContentsMargins(SPACING['md'], SPACING['md'], SPACING['md'], SPACING['md'])
        
        # Single unified label containing all stats
        self.stats_label = QLabel("Active Aircraft: 0 | Anomalies: 0 | Poll #0 | Status: Stopped")
        self.stats_label.setTextFormat(Qt.TextFormat.RichText)  # Enable HTML formatting
        self.stats_label.setStyleSheet(f"font-size: {FONT_SIZES['sm']}px; color: {COLORS['text_primary']};")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.stats_label.setWordWrap(False)
        
        # Store individual values for updating
        self.active_aircraft = 0
        self.anomalies = 0
        self.poll_count = 0
        self.status = 'Stopped'
        
        layout.addWidget(self.stats_label)
        self.setLayout(layout)
        self.setMinimumHeight(50)
        
        # Ensure the label can expand to show full text
        self.stats_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_panel']};
                border: 1px solid {COLORS['border']};
                border-radius: {RADIUS['md']}px;
                padding: {SPACING['sm']}px;
            }}
        """)
    
    def update_stats(self, active_aircraft: int, anomalies: int, poll_count: int):
        """Update statistics display."""
        self.active_aircraft = active_aircraft
        self.anomalies = anomalies
        self.poll_count = poll_count
        self._update_display()
    
    def update_status(self, status: str):
        """Update status display."""
        self.status = status.capitalize()
        self._update_display()
    
    def _update_display(self):
        """Update the unified stats label."""
        # Build the unified text
        text = f"Active Aircraft: {self.active_aircraft} | Anomalies: {self.anomalies} | Poll #{self.poll_count} | Status: {self.status}"
        
        # Determine status color
        if self.status.lower() == 'running':
            status_color = COLORS['success']
        elif self.status.lower() == 'paused':
            status_color = COLORS['warning']
        else:
            status_color = COLORS['text_muted']
        
        # Create rich text with colored status
        # Use HTML to color different parts
        html_text = (
            f"Active Aircraft: <b>{self.active_aircraft}</b> | "
            f"Anomalies: <b style='color: {COLORS['critical']}'>{self.anomalies}</b> | "
            f"Poll #<b>{self.poll_count}</b> | "
            f"Status: <b style='color: {status_color}'>{self.status}</b>"
        )
        
        self.stats_label.setText(html_text)
