"""App-level tests: folder-name validator, ETA formatter, headless GUI smoke."""
from __future__ import annotations

import pytest

from perch.app import _format_eta, _validate_folder_name


# ---------------- folder name validator ----------------

@pytest.mark.parametrize("name", [
    "",
    "   ",
    "Foo/Bar",
    "Foo\\Bar",
    "CON",
    "nul",
    "COM1",
    "LPT9",
    "trailing.",
    "trailing ",
    "what?",
    "<weird>",
])
def test_validator_rejects(name):
    ok, err = _validate_folder_name(name)
    assert not ok, f"should have rejected {name!r}"
    assert err  # non-empty error message


@pytest.mark.parametrize("name", [
    "My Flight 2026-05-12",
    "Nisbet_W_Corn",
    "flight.day.one",
    "0708_RedEdge_Test",
])
def test_validator_accepts(name):
    ok, err = _validate_folder_name(name)
    assert ok, f"should have accepted {name!r}, got: {err}"


# ---------------- ETA formatter ----------------

@pytest.mark.parametrize("seconds, expected", [
    (-1,           "--"),
    (float("inf"), "--"),
    (0,            "0s"),
    (45,           "45s"),
    (59,           "59s"),
    (60,           "1m00s"),
    (125,          "2m05s"),
    (3599,         "59m59s"),
    (3600,         "1h00m"),
    (7325,         "2h02m"),
])
def test_format_eta(seconds, expected):
    assert _format_eta(seconds) == expected


# ---------------- Headless GUI construction ----------------

def test_app_constructs_headlessly():
    """Confirm the app object builds without raising — including the
    update banner, icon loading, theme apply, settings prefill, etc."""
    import customtkinter as ctk
    from perch.app import SorterApp

    root = ctk.CTk()
    root.withdraw()
    try:
        app = SorterApp(root)
        assert app.root is root
    finally:
        root.destroy()
