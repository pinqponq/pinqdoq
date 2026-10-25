#!/usr/bin/env python3
"""Runs pinqdoq scripts/verification/ui_review_report.py from the runner's scripts folder."""
import runpy
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parents[3] / "scripts" / "verification" / "ui_review_report.py"
sys.path.insert(0, str(TARGET.parent))
runpy.run_path(str(TARGET), run_name="__main__")
