"""Shared test setup: make code/dashboard.py importable as `dashboard`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))
