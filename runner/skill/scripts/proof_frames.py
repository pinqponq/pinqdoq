#!/usr/bin/env python3
"""Runs pinqdoq scripts/verification/proof_frames.py from the runner's scripts folder."""
import runpy
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parents[3] / "scripts" / "verification" / "proof_frames.py"
sys.path.insert(0, str(TARGET.parent))
runpy.run_path(str(TARGET), run_name="__main__")
