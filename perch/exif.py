"""Best-effort sensor detection from EXIF.

Reads the EXIF Make/Model tags from the first ``IMG_*_*.tif`` found under a
source directory and maps the result to a Perch preset key. Any failure
(no Pillow, no TIFF, no EXIF, unknown sensor) returns ``None`` — the GUI
just doesn't change the preset selection.

The RedEdge-MX shows up as "RedEdge-M" or "RedEdge-MX" in EXIF regardless of
whether it's single-cam or Dual; we additionally check for sibling ``RED/``
and ``BLUE/`` directories under the source root to confirm Dual.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


_MAX_FILES_TO_PROBE = 50  # don't walk an entire 22K-file source if the first probe fails


def _first_band_tiff(source_root: Path) -> Optional[Path]:
    """Return the first IMG_NNNN_<digit>.tif under source_root, or None."""
    import re
    pat = re.compile(r"^IMG_\d+_\d+\.tif$", re.IGNORECASE)
    seen = 0
    for p in source_root.rglob("IMG_*.tif"):
        seen += 1
        if seen > _MAX_FILES_TO_PROBE:
            break
        if pat.match(p.name):
            return p
    return None


def _read_make_model(path: Path) -> tuple[str, str]:
    """Read EXIF Make/Model from a TIFF. Returns ('', '') on any failure."""
    if not _PIL_OK:
        return ("", "")
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            if not exif:
                return ("", "")
            data: dict[str, str] = {}
            for tag_id, value in exif.items():
                name = TAGS.get(tag_id, "")
                if name in ("Make", "Model") and isinstance(value, str):
                    data[name] = value.strip()
            return (data.get("Make", ""), data.get("Model", ""))
    except Exception:  # noqa: BLE001
        return ("", "")


def detect_sensor(source_root: Path) -> Optional[str]:
    """Return the matching preset key, or None if no confident match.

    Recognized today:
      - "altum_pt"        — EXIF Model contains "Altum-PT" (case-insensitive).
      - "rededge_mx_dual" — EXIF Model contains "RedEdge-M" or "RedEdge-MX"
                            AND the source has both RED/ and BLUE/ siblings.
    """
    if not source_root.exists() or not source_root.is_dir():
        return None
    sample = _first_band_tiff(source_root)
    if sample is None:
        return None
    make, model = _read_make_model(sample)
    model_lc = model.lower()
    if "altum-pt" in model_lc:
        return "altum_pt"
    if "rededge-m" in model_lc or "rededge-mx" in model_lc:
        # Dual = both RED/ and BLUE/ subdirs present at the source root.
        if (source_root / "RED").is_dir() and (source_root / "BLUE").is_dir():
            return "rededge_mx_dual"
        return None
    return None
