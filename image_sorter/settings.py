"""Per-user settings persistence — small JSON under %LOCALAPPDATA%\\ImageSorter\\."""
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
            return Path(base) / "ImageSorter"
    return Path.home() / ".config" / "ImageSorter"


def settings_path() -> Path:
    return _settings_dir() / "settings.json"


def load() -> dict[str, Any]:
    p = settings_path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save(data: dict[str, Any]) -> None:
    p = settings_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        # Best-effort: a settings write failure shouldn't break the app.
        pass
