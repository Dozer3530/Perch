"""Sensor band presets — maps the IMG_NNNN_<suffix>.tif suffix to a band.

Each supported sensor has its own preset with its own suffix→band mapping. The
GUI exposes them via a dropdown; the sort pipeline reads the chosen preset's
``bands`` dict instead of relying on a global.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    suffix: int
    name: str
    folder: str
    center_nm: float
    bandwidth_nm: float
    camera: str  # informational only


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    bands: dict[int, Band]


# ----- MicaSense RedEdge-MX Dual (10 bands across RED + BLUE cameras) -----

_REDEDGE_MX_DUAL_BANDS: dict[int, Band] = {
    1:  Band(1,  "Blue",         "01_Blue_475",         475.0, 32.0, "RED"),
    2:  Band(2,  "Green",        "02_Green_560",        560.0, 27.0, "RED"),
    3:  Band(3,  "Red",          "03_Red_668",          668.0, 14.0, "RED"),
    4:  Band(4,  "NIR",          "04_NIR_842",          842.0, 57.0, "RED"),
    5:  Band(5,  "RedEdge_717",  "05_RedEdge_717",      717.0, 12.0, "RED"),
    6:  Band(6,  "CoastalBlue",  "06_CoastalBlue_444",  444.0, 28.0, "BLUE"),
    7:  Band(7,  "Green_531",    "07_Green_531",        531.0, 14.0, "BLUE"),
    8:  Band(8,  "Red_650",      "08_Red_650",          650.0, 16.0, "BLUE"),
    9:  Band(9,  "RedEdge_705",  "09_RedEdge_705",      705.0, 10.0, "BLUE"),
    10: Band(10, "RedEdge_740",  "10_RedEdge_740",      740.0, 18.0, "BLUE"),
}

REDEDGE_MX_DUAL = Preset(
    key="rededge_mx_dual",
    label="MicaSense RedEdge-MX Dual",
    bands=_REDEDGE_MX_DUAL_BANDS,
)


# ----- MicaSense Altum-PT (7 bands: 5 multispectral + panchromatic + LWIR) -----

_ALTUM_PT_BANDS: dict[int, Band] = {
    1: Band(1, "Blue",        "01_Blue_475",     475.0,    32.0,   "MS"),
    2: Band(2, "Green",       "02_Green_560",    560.0,    27.0,   "MS"),
    3: Band(3, "Red",         "03_Red_668",      668.0,    14.0,   "MS"),
    4: Band(4, "NIR",         "04_NIR_842",      842.0,    57.0,   "MS"),
    5: Band(5, "RedEdge_717", "05_RedEdge_717",  717.0,    12.0,   "MS"),
    6: Band(6, "Panchro",     "06_Panchro_634",  634.0,   463.0,   "PAN"),
    7: Band(7, "LWIR",        "07_LWIR_11um", 11000.0,  6000.0,   "LWIR"),
}

ALTUM_PT = Preset(
    key="altum_pt",
    label="MicaSense Altum-PT",
    bands=_ALTUM_PT_BANDS,
)


# Registry. Order here is the order the dropdown shows.
PRESETS: dict[str, Preset] = {
    REDEDGE_MX_DUAL.key: REDEDGE_MX_DUAL,
    ALTUM_PT.key:        ALTUM_PT,
}

DEFAULT_PRESET_KEY = REDEDGE_MX_DUAL.key


def preset_by_label(label: str) -> Preset:
    """Look up a preset by its human-readable label; falls back to the default."""
    for p in PRESETS.values():
        if p.label == label:
            return p
    return PRESETS[DEFAULT_PRESET_KEY]


# Back-compat alias for any consumer that imported BANDS directly. Always
# points at the default preset's map; new code should accept a preset's
# .bands dict as a parameter instead.
BANDS = REDEDGE_MX_DUAL.bands
