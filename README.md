# Image Sorter

[![Build & Release Windows EXE](https://github.com/Dozer3530/Perch/actions/workflows/release.yml/badge.svg)](https://github.com/Dozer3530/Perch/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Windows GUI for reorganizing multi-band drone imagery into a flat,
band-per-folder layout. It walks a source flight folder, identifies each TIFF
by its filename suffix, and copies (or moves) it into the matching band folder
under a destination of your choosing.

Two sensor presets are built in: **MicaSense RedEdge-MX Dual** and
**MicaSense Altum-PT**. Pick from the dropdown at the top of the Input card.
More presets (single-camera RedEdge-MX, custom JSON) are on the roadmap.

## Download

Grab the latest `ImageSorter.exe` from the [Releases](https://github.com/Dozer3530/Perch/releases) page.
Single file, no installer, no Python required on the target machine.

## Preset 1 — MicaSense RedEdge-MX Dual

10 bands across two cameras (RED + BLUE). Applies to RedEdge-MX (serial RX02+)
and Altum (AL05+) in the Dual configuration.

| Suffix | Camera | Band            | Center (nm) | Bandwidth (nm) | Folder              |
|:------:|:------:|-----------------|:-----------:|:--------------:|---------------------|
| 1      | RED    | Blue            | 475         | 32             | `01_Blue_475`       |
| 2      | RED    | Green           | 560         | 27             | `02_Green_560`      |
| 3      | RED    | Red             | 668         | 14             | `03_Red_668`        |
| 4      | RED    | Near IR         | 842         | 57             | `04_NIR_842`        |
| 5      | RED    | Red Edge        | 717         | 12             | `05_RedEdge_717`    |
| 6      | BLUE   | Coastal Blue    | 444         | 28             | `06_CoastalBlue_444`|
| 7      | BLUE   | Green           | 531         | 14             | `07_Green_531`      |
| 8      | BLUE   | Red             | 650         | 16             | `08_Red_650`        |
| 9      | BLUE   | Red Edge        | 705         | 10             | `09_RedEdge_705`    |
| 10     | BLUE   | Red Edge        | 740         | 18             | `10_RedEdge_740`    |

## Preset 2 — MicaSense Altum-PT

7 bands: 5 multispectral + panchromatic + LWIR (thermal). Single integrated
sensor unit.

| Suffix | Band      | Center      | Bandwidth | Folder            |
|:------:|-----------|:-----------:|:---------:|-------------------|
| 1      | Blue      | 475 nm      | 32 nm     | `01_Blue_475`     |
| 2      | Green     | 560 nm      | 27 nm     | `02_Green_560`    |
| 3      | Red       | 668 nm      | 14 nm     | `03_Red_668`      |
| 4      | NIR       | 842 nm      | 57 nm     | `04_NIR_842`      |
| 5      | Red Edge  | 717 nm      | 12 nm     | `05_RedEdge_717`  |
| 6      | Panchro   | 634 nm      | 463 nm    | `06_Panchro_634`  |
| 7      | LWIR      | 11 µm       | 6 µm      | `07_LWIR_11um`    |

Note: suffix `6` means **Coastal Blue** on the Dual but **Panchro** on Altum-PT.
Suffix `7` means **Green-531** on the Dual but **LWIR thermal** on Altum-PT —
so picking the right preset matters. The app remembers your last choice
between launches.

## What you get for each run

```
<output_parent>\<your-folder-name>\
  01_Blue_475\         IMG_2400_1.tif  ...
  02_Green_560\        IMG_2400_2.tif  ...
  ...
  10_RedEdge_740\      IMG_2400_10.tif ...
  sort_log_<timestamp>.txt
```

The output folder name is whatever you type — no forced prefix.

## Features

- **Sensor presets** — RedEdge-MX Dual or Altum-PT from a dropdown.
- **Misc folder** — everything that isn't a band TIFF (GPS logs, .dat files,
  parameter logs, etc.) is captured into a `Misc/` sibling folder with the
  source layout preserved. Especially important for MOVE mode so nothing gets
  stranded. Toggle off if you only want the band TIFFs.
- **Auto-update check** — on launch, quietly checks GitHub Releases. If a
  newer version is available, a yellow banner appears at the top of the
  window with a Download button (opens the Releases page in your browser).
  Checked at most once every 24 hours; "Dismiss" remembers the version so
  it won't bother you again for that release.
- Modern UI with light / dark / system theme (CustomTkinter).
- Recursive scan — source layout doesn't have to match exactly.
- **Copy** by default; **Move** is an opt-in checkbox with confirmation.
- **Parallel copy** with configurable worker count (default 4) — typically
  2-3x faster than serial on cross-drive runs, much more on network shares.
- Filename collisions detected up front; choose auto-rename, skip duplicates,
  or cancel for the whole run.
- Existing destination files are never overwritten — counted as skipped.
- Live progress with files/sec and ETA.
- Cancel button works mid-run, even with parallel workers.
- Per-band file counts and a full log written into the output folder.
- Source / destination / worker count / appearance remembered between runs
  (stored at `%LOCALAPPDATA%\ImageSorter\settings.json`).
- "Open output folder" button after a successful run.

## Run from source

Requires Python 3.10+ on Windows.

```
pip install -r requirements.txt
python run.py
```

or double-click `run.bat` (after the pip install).

## Build a single-file EXE

```
pip install -r requirements.txt -r requirements-dev.txt
build_exe.bat
```

Output: `dist\ImageSorter.exe`.

You can also push a `v*` tag to GitHub — the bundled workflow builds the EXE
on `windows-latest` and attaches it to a GitHub Release automatically:

```
git tag v0.3.0
git push origin v0.3.0
```

## Tuning copy workers

| Source ↔ Destination                                  | Workers   |
|-------------------------------------------------------|-----------|
| Two different SSDs / different physical drives        | **4-8**   |
| Same SSD                                              | 2-4       |
| Same HDD                                              | **1** (parallel head seeks slow it down) |
| SD card / USB stick → internal drive                  | 4         |
| Network share → local                                 | **8** (often the biggest win)            |

Change the count any time from the **Run** card in the GUI.

## Project layout

```
image_sorter/
  __init__.py
  __main__.py        # `python -m image_sorter`
  bands.py           # suffix -> band metadata (active preset)
  sorter.py          # scan / collision / parallel copy-move (Tk-free)
  settings.py        # tiny JSON persistence
  app.py             # CustomTkinter GUI
run.py               # entry point for source + PyInstaller
run.bat              # convenience launcher
build_exe.bat        # PyInstaller build script
requirements.txt     # runtime: customtkinter
requirements-dev.txt # build-only: pyinstaller
.github/workflows/release.yml  # CI: build + attach EXE on tag push
```

## License

MIT — see [LICENSE](LICENSE).
