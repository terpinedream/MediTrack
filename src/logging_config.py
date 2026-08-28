"""
Logging setup for MediTrack.
"""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger from config LOG_LEVEL."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
        force=True,
    )
