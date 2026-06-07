"""Pytest configuration: add project root and dashboard to sys.path so tests can import src and app."""
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_dashboard_root = _project_root / "dashboard"
if str(_dashboard_root) not in sys.path:
    sys.path.insert(0, str(_dashboard_root))
