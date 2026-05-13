"""Per-user settings persistence — small JSON under %LOCALAPPDATA%\\Perch\\.

If a settings file exists at the legacy %LOCALAPPDATA%\\ImageSorter\\
location (pre-v0.7) but not at the new path, load() migrates it forward
on first call so users don't lose their last-used paths or preset.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def _settings_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "Perch"
    return Path.home() / ".config" / "Perch"


def _legacy_settings_dir() -> Path:
    """Pre-v0.7 location, when the tool was named 'Image Sorter'."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "ImageSorter"
    return Path.home() / ".config" / "ImageSorter"


def settings_path() -> Path:
    return _settings_dir() / "settings.json"


def load() -> dict[str, Any]:
    p = settings_path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    # Fall back to the pre-rebrand location and migrate forward.
    legacy = _legacy_settings_dir() / "settings.json"
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    save(data)  # Best-effort copy into the new location.
    return data


def save(data: dict[str, Any]) -> None:
    p = settings_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        # Best-effort: a settings write failure shouldn't break the app.
        pass
