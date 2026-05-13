"""EXIF preset auto-detect tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, TiffImagePlugin

from perch import exif


def _make_tiff_with_exif(path: Path, *, make: str = "", model: str = "") -> None:
    """Save a tiny TIFF with Make/Model EXIF tags."""
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (4, 4), color=(128, 128, 128))
    info = TiffImagePlugin.ImageFileDirectory_v2()
    if make:
        info[271] = make   # 271 = Make
    if model:
        info[272] = model  # 272 = Model
    im.save(path, tiffinfo=info)


def test_detects_altum_pt(tmp_path):
    src = tmp_path / "flight"
    _make_tiff_with_exif(src / "IMG_0001_1.tif", make="MicaSense", model="Altum-PT")
    assert exif.detect_sensor(src) == "altum_pt"


def test_detects_rededge_dual_when_red_and_blue_present(tmp_path):
    src = tmp_path / "flight"
    _make_tiff_with_exif(src / "RED" / "IMG_0001_1.tif", make="MicaSense", model="RedEdge-MX")
    # Need BLUE/ sibling to confirm Dual.
    (src / "BLUE").mkdir()
    assert exif.detect_sensor(src) == "rededge_mx_dual"


def test_rededge_without_blue_returns_none(tmp_path):
    """Single-cam RedEdge-MX isn't a supported preset yet — refuse to guess."""
    src = tmp_path / "flight"
    _make_tiff_with_exif(src / "RED" / "IMG_0001_1.tif", make="MicaSense", model="RedEdge-MX")
    assert exif.detect_sensor(src) is None


def test_unknown_model_returns_none(tmp_path):
    src = tmp_path / "flight"
    _make_tiff_with_exif(src / "IMG_0001_1.tif", make="SomeOtherCo", model="MysterySensor")
    assert exif.detect_sensor(src) is None


def test_no_tiff_returns_none(tmp_path):
    src = tmp_path / "flight"
    src.mkdir()
    assert exif.detect_sensor(src) is None


def test_nonexistent_source_returns_none(tmp_path):
    assert exif.detect_sensor(tmp_path / "does-not-exist") is None


def test_case_insensitive_model_matching(tmp_path):
    src = tmp_path / "flight"
    _make_tiff_with_exif(src / "IMG_0001_1.tif", make="MICASENSE", model="ALTUM-PT")
    assert exif.detect_sensor(src) == "altum_pt"


def test_only_first_band_tiff_is_probed(tmp_path):
    """detect_sensor finds the first IMG_NNNN_X.tif and uses its EXIF."""
    src = tmp_path / "flight"
    _make_tiff_with_exif(src / "IMG_0001_1.tif", make="MicaSense", model="Altum-PT")
    # A second TIFF without proper IMG_ naming shouldn't affect things.
    _make_tiff_with_exif(src / "random.tif", make="Foo", model="Bar")
    assert exif.detect_sensor(src) == "altum_pt"
