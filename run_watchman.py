#!/usr/bin/env python3
"""
PM Watchman Runner Script

Convenience script to run PM Watchman with proper Python path setup.
"""

import os
import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# Import and run main application
if __name__ == "__main__":
    from main import main
    sys.exit(main())