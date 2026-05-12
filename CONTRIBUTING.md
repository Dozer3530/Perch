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

- `image_sorter/bands.py` — sensor band metadata (active preset).
- `image_sorter/sorter.py` — pure scan / collision / parallel copy logic. No Tk imports.
- `image_sorter/settings.py` — JSON persistence for last-used paths.
- `image_sorter/app.py` — CustomTkinter GUI on top.
- `run.py` — entry point used by both `python run.py` and PyInstaller.

The core sort logic in `sorter.py` is intentionally GUI-agnostic, so a CLI
front-end or alternative GUI can be added without touching it.

## Adding a band preset

The current `BANDS` dict in `bands.py` is the RedEdge-MX Dual preset. A
preset/profile system (dropdown + custom JSON) is on the roadmap; if you
want to land it ahead of the maintainer, please open an issue first to
align on the schema.

## Building the Windows EXE

```
build_exe.bat
```

Output is `dist\ImageSorter.exe`. The bundled GitHub Actions workflow
(`.github/workflows/release.yml`) builds and attaches an EXE to a GitHub
Release whenever a `v*` tag is pushed.

## Style

- Match the existing code; no formatter pinned.
- Keep `sorter.py` Tk-free.
- Don't add runtime dependencies without discussion.
