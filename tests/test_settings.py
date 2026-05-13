"""Settings load/save and legacy ImageSorter -> Perch migration tests."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def fake_localappdata(tmp_path, monkeypatch):
    """Point LOCALAPPDATA at a temp directory for the duration of the test."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


def test_load_returns_empty_dict_when_no_settings(fake_localappdata):
    from perch import settings
    assert settings.load() == {}


def test_save_then_load_roundtrip(fake_localappdata):
    from perch import settings
    payload = {"last_workers": 8, "last_preset": "altum_pt"}
    settings.save(payload)
    assert settings.load() == payload


def test_legacy_migration_from_ImageSorter(fake_localappdata):
    from perch import settings

    # Plant a settings file at the legacy ImageSorter location.
    legacy_dir = fake_localappdata / "ImageSorter"
    legacy_dir.mkdir()
    legacy_payload = {
        "last_source": "C:/old/source",
        "last_destination": "C:/old/dest",
        "last_workers": 6,
        "last_preset": "altum_pt",
    }
    (legacy_dir / "settings.json").write_text(json.dumps(legacy_payload), encoding="utf-8")

    # First load should migrate it forward.
    loaded = settings.load()
    assert loaded == legacy_payload

    # A second load reads from the new location even if the legacy is gone.
    import shutil
    shutil.rmtree(legacy_dir)
    again = settings.load()
    assert again == legacy_payload


def test_settings_dir_paths(fake_localappdata):
    from perch import settings
    new = settings._settings_dir()
    legacy = settings._legacy_settings_dir()
    assert new.name == "Perch"
    assert legacy.name == "ImageSorter"


def test_load_handles_corrupt_json(fake_localappdata):
    from perch import settings
    p = settings.settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not-json", encoding="utf-8")
    # Should fall through, find no legacy, return {}.
    assert settings.load() == {}
