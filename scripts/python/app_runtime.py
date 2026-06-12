from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "ValorantChecker"


def resource_path(name: str) -> Path:
    """Resolve a bundled PyInstaller resource or a source-tree file."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def executable_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def app_data_dir() -> Path:
    root = Path(os.getenv("APPDATA", Path.home())) / APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root

