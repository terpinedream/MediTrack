"""
Initial setup walkthrough: download FAA registry and build EMS + Police databases.
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QGroupBox, QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices

from gui.theme import COLORS, SPACING, FONT_SIZES, RADIUS, get_button_style

# Project root (setup_data_dialog.py is in src/gui/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

FAA_DOWNLOAD_URL = "https://registry.faa.gov/database/ReleasableAircraft.zip"
FAA_DOWNLOAD_PAGE_URL = "https://www.faa.gov/licenses_certificates/aircraft_certification/aircraft_registry/releasable_aircraft_download"


def _faa_files_ready(project_root: Path) -> bool:
    """Return True if ReleasableAircraft/MASTER.txt and ACFTREF.txt exist."""
    master = project_root / "ReleasableAircraft" / "MASTER.txt"
    acftref = project_root / "ReleasableAircraft" / "ACFTREF.txt"
    return master.exists() and acftref.exists()


class SetupDataDialog(QDialog):
    """Dialog for initial setup: FAA download instructions and build both databases."""

    databases_built = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._thread = None
        self.init_ui()
        self._update_faa_status()

    def init_ui(self):
        self.setWindowTitle("MediTrack – Setup data")
        self.setMinimumSize(520, 480)
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING['lg'])
        layout.setContentsMargins(SPACING['xl'], SPACING['xl'], SPACING['xl'], SPACING['xl'])

        # Step 1 – Download FAA registry
        step1 = QGroupBox("Step 1: Download FAA registry")
        step1.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: {RADIUS['md']}px;
                margin-top: {SPACING['sm']}px;
                padding-top: {SPACING['md']}px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {SPACING['md']}px;
                padding: 0 {SPACING['xs']}px;
            }}
        """)
        step1_layout = QVBoxLayout()
        instructions = QLabel(
            "Download the FAA Releasable Aircraft database (~60 MB ZIP). "
            "Extract the archive so that the ReleasableAircraft folder (containing MASTER.txt and ACFTREF.txt) "
            "is inside your MediTrack project folder (the same folder that contains data/ and src/)."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: {FONT_SIZES['sm']}px;")
        step1_layout.addWidget(instructions)
        self.faa_status_label = QLabel()
        self.faa_status_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: {FONT_SIZES['xs']}px;")
        step1_layout.addWidget(self.faa_status_label)
        open_faa_btn = QPushButton("Open FAA download page")
        open_faa_btn.setStyleSheet(get_button_style('primary'))
        open_faa_btn.clicked.connect(self._open_faa_download)
        step1_layout.addWidget(open_faa_btn)
        step1.setLayout(step1_layout)
        layout.addWidget(step1)

        # Step 2 – Build databases
        step2 = QGroupBox("Step 2: Build EMS & Police databases")
        step2.setStyleSheet(step1.styleSheet())
        step2_layout = QVBoxLayout()
        build_instructions = QLabel(
            "When the FAA files are in place, click below to build both the EMS and Police aircraft databases. "
            "This may take a minute."
        )
        build_instructions.setWordWrap(True)
        build_instructions.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: {FONT_SIZES['sm']}px;")
        step2_layout.addWidget(build_instructions)
        self.build_btn = QPushButton("Build EMS & Police databases")
        self.build_btn.setStyleSheet(get_button_style('primary'))
        self.build_btn.clicked.connect(self._start_build)
        step2_layout.addWidget(self.build_btn)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {COLORS['border']};
                border-radius: {RADIUS['sm']}px;
                text-align: center;
                background: {COLORS['bg_panel']};
            }}
            QProgressBar::chunk {{
                background: {COLORS['primary']};
                border-radius: {RADIUS['sm'] - 1}px;
            }}
        """)
        step2_layout.addWidget(self.progress_bar)
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Progress will appear here when you run the build.")
        self.log_output.setMinimumHeight(120)
        self.log_output.setStyleSheet(f"""
            QPlainTextEdit {{
                font-family: monospace;
                font-size: {FONT_SIZES['xs']}px;
                background-color: {COLORS['bg_panel']};
                border: 1px solid {COLORS['border']};
                border-radius: {RADIUS['sm']}px;
                padding: {SPACING['sm']}px;
            }}
        """)
        step2_layout.addWidget(self.log_output)
        step2.setLayout(step2_layout)
        layout.addWidget(step2)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(get_button_style('primary'))
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _update_faa_status(self):
        if _faa_files_ready(_PROJECT_ROOT):
            self.faa_status_label.setText("FAA files found (ReleasableAircraft/MASTER.txt and ACFTREF.txt).")
        else:
            self.faa_status_label.setText(
                "FAA files not found. Download and extract the FAA registry into the project folder first."
            )

    def _open_faa_download(self):
        QDesktopServices.openUrl(QUrl(FAA_DOWNLOAD_PAGE_URL))

    def _start_build(self):
        from gui.workers.setup_data_worker import SetupDataWorker
        from PyQt6.QtCore import QThread

        self.build_btn.setEnabled(False)
        self.log_output.clear()
        self.progress_bar.setValue(0)
        self._append_log("Starting build…")

        self._thread = QThread()
        self._worker = SetupDataWorker(_PROJECT_ROOT)
        self._worker.moveToThread(self._thread)
        self._worker.progress.connect(self._on_progress)
        self._worker.progress_percent.connect(self._on_progress_percent)
        self._worker.finished_success.connect(self._on_build_success)
        self._worker.finished_error.connect(self._on_build_error)
        self._thread.started.connect(self._worker.run)
        self._worker.finished_success.connect(self._thread.quit)
        self._worker.finished_error.connect(self._thread.quit)
        self._thread.finished.connect(self._on_build_thread_finished)
        self._thread.start()

    def _append_log(self, text: str):
        self.log_output.appendPlainText(text)
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def _on_progress(self, message: str):
        self._append_log(message)

    def _on_progress_percent(self, value: int):
        self.progress_bar.setValue(value)

    def _on_build_success(self):
        self._append_log("Done.")
        self.progress_bar.setValue(100)
        self.databases_built.emit()

    def _on_build_error(self, message: str):
        self._append_log(f"Error: {message}")

    def _on_build_thread_finished(self):
        """Called when the worker thread has fully stopped. Safe to clear references."""
        self.build_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self._worker = None
        if self._thread:
            self._thread.deleteLater()
            self._thread = None
