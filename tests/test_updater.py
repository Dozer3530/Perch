"""Updater tests: version parsing, comparison, debounce, offline safety."""
from __future__ import annotations

import threading
from datetime import datetime, timedelta

import pytest

from perch import updater


# ---------------- parse_version ----------------

@pytest.mark.parametrize("text, expected", [
    ("v1.2.3",   (1, 2, 3)),
    ("1.2.3",    (1, 2, 3)),
    ("v0.7.0",   (0, 7, 0)),
    ("v10.0.1",  (10, 0, 1)),
    ("0.5.0rc1", (0, 5, 0)),
    ("v1",       (1,)),
    ("",         (0,)),
])
def test_parse_version(text, expected):
    assert updater.parse_version(text) == expected


# ---------------- is_newer ----------------

def test_is_newer_strict_inequality():
    assert updater.is_newer("v0.6.0", "0.5.0")
    assert updater.is_newer("v1.0.0", "0.99.99")
    assert not updater.is_newer("v0.5.0", "0.5.0")
    assert not updater.is_newer("v0.5.0", "0.6.0")


def test_is_newer_numeric_not_lexical():
    """The classic 0.10 > 0.9 bug — must compare ints, not strings."""
    assert updater.is_newer("v0.10.0", "0.9.0")
    assert updater.is_newer("v1.0.0", "0.10.0")


# ---------------- should_check (24h debounce) ----------------

def test_should_check_no_record():
    assert updater.should_check(None)
    assert updater.should_check("")
    assert updater.should_check("not-iso")


def test_should_check_within_window():
    just_now = datetime.now().isoformat()
    assert not updater.should_check(just_now)


def test_should_check_stale():
    yesterday = (datetime.now() - timedelta(hours=25)).isoformat()
    assert updater.should_check(yesterday)


def test_should_check_near_threshold():
    one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    assert not updater.should_check(one_hour_ago)


# ---------------- Offline safety ----------------

def test_fetch_returns_none_on_dns_error(monkeypatch):
    monkeypatch.setattr(updater, "GITHUB_API_URL", "http://does-not-resolve.invalid/x")
    assert updater.fetch_latest_release(timeout=0.5) is None


def test_check_async_callback_fires_once_on_error(monkeypatch):
    monkeypatch.setattr(updater, "GITHUB_API_URL", "http://does-not-resolve.invalid/x")
    done = threading.Event()
    results: list = []
    updater.check_async(lambda info: (results.append(info), done.set()))
    assert done.wait(timeout=10), "callback never fired"
    assert len(results) == 1
    assert results[0] is None
