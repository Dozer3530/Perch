"""Regenerate derived art assets from assets/perch.png.

Run this whenever the source logo changes:

    python tools/build_assets.py

It produces:
  • assets/perch.ico  — multi-resolution Windows icon (16, 24, 32, 48, 64, 128, 256)
                        used by PyInstaller's --icon flag.

The source PNG is kept as-is; the in-app GUI loads it directly and does a
square crop / resize in memory.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

SRC = Path(__file__).resolve().parent.parent / "assets" / "perch.png"
ICO = Path(__file__).resolve().parent.parent / "assets" / "perch.ico"
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def square_crop(im: Image.Image) -> Image.Image:
    """Center-crop to the largest possible square."""
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return im.crop((left, top, left + side, top + side))


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: {SRC} not found", flush=True)
        return 1

    im = Image.open(SRC).convert("RGBA")
    print(f"loaded {SRC.name}  {im.size}  {im.mode}")

    square = square_crop(im)
    print(f"square-cropped to {square.size}")

    square.save(ICO, format="ICO", sizes=ICO_SIZES)
    print(f"wrote {ICO} with sizes {ICO_SIZES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
