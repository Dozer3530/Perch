"""Asset path resolution + logo loading.

Handles both ``python run.py`` (assets/ is alongside the package) and the
PyInstaller --onefile build (assets are extracted to ``sys._MEIPASS`` at
runtime). All loaders return ``None`` on any error so the GUI degrades
gracefully when assets are missing.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
    _PIL_OK = True
except ImportError:  # Pillow is a hard runtime dep, but degrade rather than crash.
    Image = None  # type: ignore
    _PIL_OK = False


def asset_path(name: str) -> Path:
    """Return the absolute path of an asset shipped with the app."""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS) / "assets"
    else:
        base = Path(__file__).resolve().parent.parent / "assets"
    return base / name


def _square_crop(im: "Image.Image") -> "Image.Image":
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return im.crop((left, top, left + side, top + side))


def load_logo_square(size: int = 256) -> Optional["Image.Image"]:
    """Load and square-crop assets/perch.png, resized to ``size`` x ``size``.

    Returns None if Pillow isn't installed, the file is missing, or the read
    fails.
    """
    if not _PIL_OK:
        return None
    p = asset_path("perch.png")
    if not p.exists():
        return None
    try:
        im = Image.open(p).convert("RGBA")
        im = _square_crop(im)
        if im.size != (size, size):
            im = im.resize((size, size), Image.LANCZOS)
        return im
    except Exception:  # noqa: BLE001
        return None


def ico_path() -> Optional[Path]:
    """Return the path to assets/perch.ico if it exists, else None."""
    p = asset_path("perch.ico")
    return p if p.exists() else None
