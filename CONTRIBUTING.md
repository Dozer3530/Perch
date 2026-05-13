# Contributing

Thanks for your interest. This is a small focused tool — keep PRs focused
similarly.

## Dev setup

```
pip install -r requirements.txt -r requirements-dev.txt
python run.py
```

No build step is needed for development; the GUI runs directly from source.

## Project layout

- `perch/bands.py` — sensor band metadata (preset registry).
- `perch/sorter.py` — pure scan / collision / parallel copy logic. No Tk imports.
- `perch/settings.py` — JSON persistence for last-used paths (with legacy migration).
- `perch/updater.py` — GitHub Releases auto-update check.
- `perch/app.py` — CustomTkinter GUI on top.
- `run.py` — entry point used by both `python run.py` and PyInstaller.

The core sort logic in `sorter.py` is intentionally GUI-agnostic, so a CLI
front-end or alternative GUI can be added without touching it.

## Adding a band preset

Open `perch/bands.py`, define a new `Preset` (suffix → `Band` dict), add it
to the `PRESETS` registry. The GUI dropdown picks it up automatically.

## Updating the logo

The source-of-truth is `assets/perch.png`. The `.ico` used by PyInstaller
is derived from it via:

```
python tools/build_assets.py
```

That regenerates `assets/perch.ico` at sizes 16/24/32/48/64/128/256. Commit
both files together.

## Building the Windows EXE

```
build_exe.bat
```

Output is `dist\Perch.exe`. The bundled GitHub Actions workflow
(`.github/workflows/release.yml`) builds and attaches an EXE to a GitHub
Release whenever a `v*` tag is pushed. The workflow refuses to build if the
tag doesn't match `perch.__version__` — bump the version in
`perch/__init__.py` before tagging.

## Style

- Match the existing code; no formatter pinned.
- Keep `sorter.py` Tk-free.
- Don't add runtime dependencies without discussion.
