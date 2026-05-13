"""Preset registry + suffix disambiguation tests."""
from __future__ import annotations

from perch.bands import (
    ALTUM_PT,
    BANDS,
    DEFAULT_PRESET_KEY,
    PRESETS,
    REDEDGE_MX_DUAL,
    preset_by_label,
)


def test_registry_contains_both_presets():
    assert "rededge_mx_dual" in PRESETS
    assert "altum_pt" in PRESETS
    assert DEFAULT_PRESET_KEY in PRESETS


def test_dual_preset_has_all_10_suffixes():
    keys = set(REDEDGE_MX_DUAL.bands.keys())
    assert keys == set(range(1, 11))


def test_altum_pt_preset_has_seven_suffixes():
    keys = set(ALTUM_PT.bands.keys())
    assert keys == set(range(1, 8))


def test_suffix_6_means_different_things_per_preset():
    """The whole reason the preset dropdown exists: suffix 6 routes to a
    different band depending on which sensor produced the file."""
    assert REDEDGE_MX_DUAL.bands[6].folder == "06_CoastalBlue_444"
    assert ALTUM_PT.bands[6].folder == "06_Panchro_634"


def test_suffix_7_means_different_things_per_preset():
    assert REDEDGE_MX_DUAL.bands[7].folder == "07_Green_531"
    assert ALTUM_PT.bands[7].folder == "07_LWIR_11um"


def test_preset_by_label_roundtrip():
    assert preset_by_label("MicaSense RedEdge-MX Dual").key == "rededge_mx_dual"
    assert preset_by_label("MicaSense Altum-PT").key == "altum_pt"


def test_preset_by_label_falls_back_to_default():
    fallback = preset_by_label("does not exist")
    assert fallback.key == DEFAULT_PRESET_KEY


def test_backcompat_BANDS_alias():
    """Older imports may still do `from perch.bands import BANDS`."""
    assert BANDS is REDEDGE_MX_DUAL.bands
