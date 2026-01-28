#!/usr/bin/env python3
"""
GUI entry point script for MediTrack.

Run this script to launch the graphical interface.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
# Also add src directory to path
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from gui.main import main

if __name__ == "__main__":
    main()
