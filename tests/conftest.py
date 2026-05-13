"""Shared pytest fixtures for the Perch test suite."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest


def _write_tiff(p: Path, content: bytes | None = None) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content if content is not None else (b"\x49\x49\x2a\x00" + p.name.encode()))


@pytest.fixture
def fake_flight(tmp_path: Path) -> Callable[..., Path]:
    """Build a synthetic MicaSense flight tree under tmp_path.

    Usage::

        src = fake_flight(
            with_dual_bands=True,           # IMG_NNNN_1..10.tif under RED/ + BLUE/
            with_collision=True,            # second SYNC set producing same names
            with_misc=True,                 # diag.dat, gpslog.csv, etc.
            with_unrecognized=False,        # BAD_NAME.tif at the top of RED/
        )

    Returns the path to the constructed flight root.
    """
    def _build(
        *,
        name: str = "flight",
        with_dual_bands: bool = True,
        with_collision: bool = False,
        with_misc: bool = False,
        with_unrecognized: bool = False,
    ) -> Path:
        src = tmp_path / name
        if with_dual_bands:
            for sfx in range(1, 6):
                _write_tiff(src / "RED" / "SYNC0001SET" / "000" / f"IMG_2400_{sfx}.tif")
            for sfx in range(6, 11):
                _write_tiff(src / "BLUE" / "SYNC0001SET" / "000" / f"IMG_2401_{sfx}.tif")
        if with_collision:
            # Same RED filenames in a second SYNC set -> deliberate collision.
            for sfx in range(1, 6):
                _write_tiff(src / "RED" / "SYNC0002SET" / "000" / f"IMG_2400_{sfx}.tif")
        if with_misc:
            (src / "RED" / "SYNC0001SET" / "diag.dat").parent.mkdir(parents=True, exist_ok=True)
            (src / "RED" / "SYNC0001SET" / "diag.dat").write_bytes(b"diag-red")
            (src / "RED" / "SYNC0001SET" / "gpslog.csv").write_bytes(b"gps,data")
            (src / "BLUE" / "SYNC0001SET").mkdir(parents=True, exist_ok=True)
            (src / "BLUE" / "SYNC0001SET" / "diag.dat").write_bytes(b"diag-blue")
            (src / "paramlog.tsv").write_bytes(b"params")
        if with_unrecognized:
            _write_tiff(src / "RED" / "BAD_NAME.tif")
            _write_tiff(src / "RED" / "IMG_2400_99.tif")  # invalid suffix
        return src

    return _build
