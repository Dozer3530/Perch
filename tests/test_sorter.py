"""Tests for scan, collision detection, parallel execution, MOVE, and misc routing."""
from __future__ import annotations

import filecmp
from pathlib import Path

from perch.bands import ALTUM_PT, REDEDGE_MX_DUAL
from perch.sorter import (
    auto_rename_for_uniqueness,
    dedupe_keep_first,
    execute_plan,
    find_collisions,
    scan_source,
)


# ---------------- Scan ----------------

def test_scan_routes_dual_bands_to_correct_folders(fake_flight):
    src = fake_flight(with_dual_bands=True)
    out = src.parent / "out"
    scan = scan_source(src, out, bands=REDEDGE_MX_DUAL.bands)
    assert len(scan.files) == 10
    assert not scan.unrecognized_tifs
    # Each suffix routes to its preset folder.
    targets = {pf.suffix: pf.target for pf in scan.files}
    for sfx, band in REDEDGE_MX_DUAL.bands.items():
        assert sfx in targets, f"missing suffix {sfx}"
        assert targets[sfx].parent.name == band.folder


def test_scan_logs_unrecognized_but_doesnt_route_them(fake_flight):
    src = fake_flight(with_dual_bands=True, with_unrecognized=True)
    out = src.parent / "out"
    scan = scan_source(src, out, bands=REDEDGE_MX_DUAL.bands)
    assert len(scan.unrecognized_tifs) == 2
    band_plans = [pf for pf in scan.files if pf.kind == "band"]
    assert len(band_plans) == 10


def test_scan_altum_rejects_suffixes_outside_range(fake_flight):
    src = fake_flight(with_dual_bands=True)
    out = src.parent / "out"
    scan = scan_source(src, out, bands=ALTUM_PT.bands)
    band_plans = [pf for pf in scan.files if pf.kind == "band"]
    assert len(band_plans) == 7  # suffixes 1-7 routed; 8/9/10 unrecognized
    assert len(scan.unrecognized_tifs) == 3


# ---------------- Collisions ----------------

def test_collision_detection(fake_flight):
    src = fake_flight(with_dual_bands=True, with_collision=True)
    out = src.parent / "out"
    scan = scan_source(src, out, bands=REDEDGE_MX_DUAL.bands)
    collisions = find_collisions(scan.files)
    assert len(collisions) == 5  # five RED suffixes collide between the two SYNC sets


def test_auto_rename_resolves_collisions(fake_flight):
    src = fake_flight(with_dual_bands=True, with_collision=True)
    out = src.parent / "out"
    scan = scan_source(src, out, bands=REDEDGE_MX_DUAL.bands)
    renamed = auto_rename_for_uniqueness(scan.files)
    assert renamed == 10  # 5 collisions, 2 files each
    assert not find_collisions(scan.files)


def test_dedupe_keep_first(fake_flight):
    src = fake_flight(with_dual_bands=True, with_collision=True)
    out = src.parent / "out"
    scan = scan_source(src, out, bands=REDEDGE_MX_DUAL.bands)
    kept, skipped = dedupe_keep_first(scan.files)
    assert len(kept) == 10   # 5 RED (deduped) + 5 BLUE
    assert len(skipped) == 5


# ---------------- Execute ----------------

def test_parallel_copy_byte_identical_to_serial(fake_flight):
    src = fake_flight(with_dual_bands=True, with_collision=True)

    out_serial = src.parent / "serial"
    scan_a = scan_source(src, out_serial, bands=REDEDGE_MX_DUAL.bands)
    auto_rename_for_uniqueness(scan_a.files)
    execute_plan(scan_a.files, move=False, workers=1)

    out_parallel = src.parent / "parallel"
    scan_b = scan_source(src, out_parallel, bands=REDEDGE_MX_DUAL.bands)
    auto_rename_for_uniqueness(scan_b.files)
    execute_plan(scan_b.files, move=False, workers=4)

    for band in REDEDGE_MX_DUAL.bands.values():
        a_dir = out_serial / band.folder
        b_dir = out_parallel / band.folder
        a_names = sorted(p.name for p in a_dir.glob("*.tif"))
        b_names = sorted(p.name for p in b_dir.glob("*.tif"))
        assert a_names == b_names, f"{band.folder} differs: {a_names} vs {b_names}"
        for name in a_names:
            assert filecmp.cmp(a_dir / name, b_dir / name, shallow=False)


def test_target_exists_is_skipped_not_overwritten(fake_flight):
    src = fake_flight(with_dual_bands=True)
    out = src.parent / "out"
    scan_a = scan_source(src, out, bands=REDEDGE_MX_DUAL.bands)
    r1 = execute_plan(scan_a.files, move=False, workers=2)
    assert r1.written == 10
    # second pass: everything exists -> all skipped, nothing overwritten
    scan_b = scan_source(src, out, bands=REDEDGE_MX_DUAL.bands)
    r2 = execute_plan(scan_b.files, move=False, workers=2)
    assert r2.written == 0
    assert r2.skipped_existing == 10


def test_move_drains_source(fake_flight):
    src = fake_flight(with_dual_bands=True)
    out = src.parent / "out"
    scan = scan_source(src, out, bands=REDEDGE_MX_DUAL.bands)
    r = execute_plan(scan.files, move=True, workers=2)
    assert r.written == 10
    assert not list(src.rglob("IMG_*.tif"))


# ---------------- Misc routing ----------------

def test_misc_files_route_to_Misc_folder(fake_flight):
    src = fake_flight(with_dual_bands=True, with_misc=True)
    out = src.parent / "out"
    scan = scan_source(src, out, bands=REDEDGE_MX_DUAL.bands, include_misc=True)
    misc = [pf for pf in scan.files if pf.kind == "misc"]
    assert len(misc) == 4
    targets = sorted(str(pf.target.relative_to(out)) for pf in misc)
    expected = sorted([
        str(Path("Misc") / "RED" / "SYNC0001SET" / "diag.dat"),
        str(Path("Misc") / "RED" / "SYNC0001SET" / "gpslog.csv"),
        str(Path("Misc") / "BLUE" / "SYNC0001SET" / "diag.dat"),
        str(Path("Misc") / "paramlog.tsv"),
    ])
    assert targets == expected


def test_misc_files_dont_collide_across_red_blue(fake_flight):
    src = fake_flight(with_dual_bands=True, with_misc=True)
    out = src.parent / "out"
    scan = scan_source(src, out, bands=REDEDGE_MX_DUAL.bands, include_misc=True)
    # The two diag.dat files live under different parents -> no collision.
    assert not find_collisions(scan.files)
    r = execute_plan(scan.files, move=False, workers=2)
    assert (out / "Misc" / "RED" / "SYNC0001SET" / "diag.dat").exists()
    assert (out / "Misc" / "BLUE" / "SYNC0001SET" / "diag.dat").exists()
    assert r.misc_written == 4


def test_include_misc_false_preserves_v04_behavior(fake_flight):
    src = fake_flight(with_dual_bands=True, with_misc=True)
    out = src.parent / "out"
    scan = scan_source(src, out, bands=REDEDGE_MX_DUAL.bands, include_misc=False)
    assert all(pf.kind == "band" for pf in scan.files)
    assert len(scan.files) == 10
    # non_image_files still tracked for the summary, just not routed.
    assert len(scan.non_image_files) == 4
    r = execute_plan(scan.files, move=False, workers=2)
    assert r.misc_written == 0
    assert not (out / "Misc").exists()


def test_per_band_counts_in_result(fake_flight):
    src = fake_flight(with_dual_bands=True)
    out = src.parent / "out"
    scan = scan_source(src, out, bands=REDEDGE_MX_DUAL.bands)
    r = execute_plan(scan.files, move=False, workers=2)
    for sfx in range(1, 11):
        assert r.per_band[sfx] == 1
