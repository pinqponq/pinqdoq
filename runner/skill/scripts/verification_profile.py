#!/usr/bin/env python3
"""Moved to pinqdoq scripts/verification/verification_profile.py; this file keeps the runner's existing paths working."""
import runpy
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parents[3] / "scripts" / "verification" / "verification_profile.py"
sys.path.insert(0, str(TARGET.parent))
runpy.run_path(str(TARGET), run_name="__main__")
