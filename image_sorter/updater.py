"""Check GitHub Releases for a newer version of Image Sorter.

The check runs in a background thread, fails silently on any error
(no network, GitHub down, rate-limited, etc.), and is cached for 24h
via the app's settings.json so we don't hit the API on every launch.
"""
from __future__ import annotations

import json
import threading
import urllib.request
from datetime import datetime, timedelta
from typing import Callable, Optional

from . import __version__

GITHUB_OWNER = "Dozer3530"
GITHUB_REPO = "Perch"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

CHECK_TIMEOUT_SEC = 5.0
CHECK_INTERVAL = timedelta(hours=24)


def parse_version(s: str) -> tuple[int, ...]:
    """Parse 'v1.2.3' or '1.2.3' (or '1.2.3a1') into a comparable tuple of ints.

    Non-numeric suffixes on each segment are ignored, so '0.5.0rc1' parses
    to (0, 5, 0). This is intentionally loose; we never need to compare
    pre-release ordering.
    """
    s = s.strip().lstrip("v").strip()
    if not s:
        return (0,)
    parts: list[int] = []
    for piece in s.split("."):
        digits = ""
        for c in piece:
            if c.isdigit():
                digits += c
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer(remote: str, local: str) -> bool:
    """Return True iff the remote version is strictly newer than local."""
    return parse_version(remote) > parse_version(local)


def fetch_latest_release(timeout: float = CHECK_TIMEOUT_SEC) -> Optional[dict]:
    """Fetch the latest non-prerelease info from GitHub. None on any error."""
    try:
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"ImageSorter/{__version__}",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        return {
            "tag_name": data.get("tag_name", "") or "",
            "html_url": data.get("html_url", "") or RELEASES_PAGE_URL,
            "name": data.get("name", "") or "",
        }
    except Exception:  # noqa: BLE001 — any failure is a silent no-op
        return None


def should_check(last_check_iso: str | None) -> bool:
    """True if a check is due (no prior check, or older than CHECK_INTERVAL)."""
    if not last_check_iso:
        return True
    try:
        last = datetime.fromisoformat(last_check_iso)
    except ValueError:
        return True
    return datetime.now() - last >= CHECK_INTERVAL


def check_async(callback: Callable[[Optional[dict]], None]) -> None:
    """Run an update check in a background thread.

    The callback is invoked exactly once with either:
      - a dict {tag_name, html_url, name} if a *newer* version is available, or
      - None for "no update needed" OR any error.

    The callback runs on the worker thread; if it touches Tk widgets it should
    schedule via root.after(0, ...).
    """
    def worker() -> None:
        info = fetch_latest_release()
        if info and info["tag_name"] and is_newer(info["tag_name"], __version__):
            callback(info)
        else:
            callback(None)

    threading.Thread(target=worker, daemon=True).start()
