"""Core sort logic — scanning, collision detection, and (parallel) execution.

Kept free of any Tk imports so it can be unit-tested or driven from a CLI later.
"""
from __future__ import annotations

import re
import shutil
import threading
import time
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .bands import BANDS

FILENAME_RE = re.compile(r"^IMG_(\d+)_(\d+)\.tif$", re.IGNORECASE)

# Progress flush thresholds — fire at most every N completions or every T seconds.
_PROGRESS_FLUSH_EVERY_N = 25
_PROGRESS_FLUSH_EVERY_SEC = 0.15


@dataclass
class PlannedFile:
    source: Path
    suffix: int
    target: Path  # May be rewritten when resolving collisions.


@dataclass
class ScanResult:
    files: list[PlannedFile]
    unrecognized_tifs: list[Path]
    non_image_files: list[Path]
    total_seen: int


@dataclass
class CollisionGroup:
    target: Path
    sources: list[Path]


@dataclass
class ExecutionResult:
    written: int = 0
    skipped_existing: int = 0
    failed: list[tuple[Path, str]] = field(default_factory=list)
    cancelled: bool = False
    per_band: dict[int, int] = field(default_factory=dict)


# ---------------- Scan ----------------

def scan_source(
    source_root: Path,
    output_root: Path,
    *,
    progress_cb: Callable[[int], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> ScanResult:
    files: list[PlannedFile] = []
    unrecognized: list[Path] = []
    non_image: list[Path] = []
    count = 0
    for path in source_root.rglob("*"):
        if cancel_event is not None and cancel_event.is_set():
            break
        if not path.is_file():
            continue
        count += 1
        if progress_cb is not None and count % 250 == 0:
            progress_cb(count)
        ext = path.suffix.lower()
        if ext not in (".tif", ".tiff"):
            non_image.append(path)
            continue
        m = FILENAME_RE.match(path.name)
        if not m:
            unrecognized.append(path)
            continue
        sfx = int(m.group(2))
        band = BANDS.get(sfx)
        if band is None:
            unrecognized.append(path)
            continue
        target = output_root / band.folder / path.name
        files.append(PlannedFile(source=path, suffix=sfx, target=target))
    if progress_cb is not None:
        progress_cb(count)
    return ScanResult(
        files=files,
        unrecognized_tifs=unrecognized,
        non_image_files=non_image,
        total_seen=count,
    )


# ---------------- Collisions ----------------

def find_collisions(files: Iterable[PlannedFile]) -> list[CollisionGroup]:
    by_target: dict[Path, list[Path]] = {}
    for pf in files:
        by_target.setdefault(pf.target, []).append(pf.source)
    return [
        CollisionGroup(target=t, sources=srcs)
        for t, srcs in by_target.items()
        if len(srcs) > 1
    ]


def auto_rename_for_uniqueness(files: list[PlannedFile]) -> int:
    """For files sharing a target, append a parent-folder tag so each is unique.

    Returns the number of files renamed.
    """
    by_target: dict[Path, list[PlannedFile]] = {}
    for pf in files:
        by_target.setdefault(pf.target, []).append(pf)
    renamed = 0
    for target, group in by_target.items():
        if len(group) <= 1:
            continue
        for pf in group:
            disamb = _disambiguator(pf.source)
            new_name = f"{pf.target.stem}__{disamb}{pf.target.suffix}"
            pf.target = pf.target.with_name(new_name)
            renamed += 1
    return renamed


def _disambiguator(p: Path) -> str:
    """Build a short tag from the SYNC*SET\\NNN parent path.

    e.g. ...\\RED\\SYNC0004SET\\012\\IMG_2400_2.tif -> 'SYNC0004SET_012'.
    """
    grand = p.parent.parent.name if p.parent.parent != p.parent else ""
    parent = p.parent.name
    tag = f"{grand}_{parent}" if grand else parent
    return _sanitize_for_filename(tag)


def _sanitize_for_filename(s: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in s)


def dedupe_keep_first(files: list[PlannedFile]) -> tuple[list[PlannedFile], list[PlannedFile]]:
    """Return (kept, skipped) — keep only the first PlannedFile for each target path."""
    seen: set[Path] = set()
    kept: list[PlannedFile] = []
    skipped: list[PlannedFile] = []
    for pf in files:
        if pf.target in seen:
            skipped.append(pf)
        else:
            seen.add(pf.target)
            kept.append(pf)
    return kept, skipped


# ---------------- Execute ----------------

def execute_plan(
    plan: list[PlannedFile],
    *,
    move: bool,
    workers: int = 4,
    progress_cb: Callable[[int, int, Path], None] | None = None,
    log_cb: Callable[[str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> ExecutionResult:
    result = ExecutionResult()
    total = len(plan)
    if total == 0:
        return result

    op = shutil.move if move else shutil.copy2

    # Mkdir all distinct target parents up front — eliminates ~N stat calls in the hot loop
    # and avoids races between threads creating the same directory.
    for parent in {pf.target.parent for pf in plan}:
        parent.mkdir(parents=True, exist_ok=True)

    def do_one(pf: PlannedFile) -> tuple[PlannedFile, str, str | None]:
        """Returns (pf, status, detail). status in {'written','skipped','failed','cancelled'}."""
        if cancel_event is not None and cancel_event.is_set():
            return (pf, "cancelled", None)
        try:
            if pf.target.exists():
                return (pf, "skipped", None)
            op(str(pf.source), str(pf.target))
            return (pf, "written", None)
        except Exception as e:  # noqa: BLE001 — surface the message; we aggregate, not re-raise
            return (pf, "failed", str(e))

    completed = 0
    last_flush_count = 0
    last_flush_time = time.monotonic()

    def maybe_flush(force: bool, current: Path) -> None:
        nonlocal last_flush_count, last_flush_time
        if progress_cb is None:
            return
        now = time.monotonic()
        if (
            force
            or (completed - last_flush_count) >= _PROGRESS_FLUSH_EVERY_N
            or (now - last_flush_time) >= _PROGRESS_FLUSH_EVERY_SEC
        ):
            progress_cb(completed, total, current)
            last_flush_count = completed
            last_flush_time = now

    if workers <= 1:
        # Serial path — avoids ThreadPoolExecutor overhead for workers=1
        for pf in plan:
            if cancel_event is not None and cancel_event.is_set():
                result.cancelled = True
                break
            pf2, status, detail = do_one(pf)
            _aggregate(result, pf2, status, detail, log_cb)
            completed += 1
            maybe_flush(False, pf2.source)
    else:
        workers = max(1, min(workers, 32))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(do_one, pf) for pf in plan]
            cancelled_pending = False
            for fut in as_completed(futures):
                if cancel_event is not None and cancel_event.is_set():
                    result.cancelled = True
                    if not cancelled_pending:
                        for f in futures:
                            f.cancel()  # only cancels not-yet-started
                        cancelled_pending = True
                try:
                    pf2, status, detail = fut.result()
                except CancelledError:
                    continue
                _aggregate(result, pf2, status, detail, log_cb)
                completed += 1
                maybe_flush(False, pf2.source)

    # Final progress flush so the UI lands on 100%.
    if plan:
        maybe_flush(True, plan[-1].source)
    return result


def _aggregate(
    result: ExecutionResult,
    pf: PlannedFile,
    status: str,
    detail: str | None,
    log_cb: Callable[[str], None] | None,
) -> None:
    if status == "written":
        result.written += 1
        result.per_band[pf.suffix] = result.per_band.get(pf.suffix, 0) + 1
    elif status == "skipped":
        result.skipped_existing += 1
        if log_cb:
            log_cb(f"SKIP (already exists): {pf.target}")
    elif status == "failed":
        result.failed.append((pf.source, detail or ""))
        if log_cb:
            log_cb(f"ERROR: {pf.source} -> {pf.target}: {detail}")
    # "cancelled" -> no-op; the cancel flag is set on the result by the caller
