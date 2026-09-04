"""Assemble the frames from `Sheet2Play --smoke-gif` into the README demo GIF.

Kept in Python rather than C# on purpose: the app publishes as a single self-contained
executable, and it should not carry an image-encoding dependency that exists only to build
a documentation asset. Pillow is already present in the bridge's virtualenv.

    Bridge/.venv-homr-gpu/Scripts/python.exe scripts/make-demo-gif.py <frames-dir> <out.gif>

All frames share one palette, quantized from a frame in the middle of the clip. Per-frame
adaptive palettes would each be a little more accurate but make the colours crawl between
frames, which is very visible on flat UI panels.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

DEFAULT_WIDTH = 720
DEFAULT_FPS = 25
DEFAULT_COLORS = 48
# GitHub will serve a larger file, but a README that takes seconds to paint defeats the
# point of having a demo at the top of it.
WARN_BYTES = 8 * 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames", type=Path, help="directory of frame-XXXX.png files")
    parser.add_argument("output", type=Path, help="path of the .gif to write")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    parser.add_argument("--colors", type=int, default=DEFAULT_COLORS)
    args = parser.parse_args()

    paths = sorted(args.frames.glob("frame-*.png"))
    if not paths:
        print(f"No frame-*.png in {args.frames}", file=sys.stderr)
        return 1

    first = Image.open(paths[0])
    height = round(first.height * args.width / first.width)
    size = (args.width, height)

    frames: list[Image.Image] = []
    for path in paths:
        with Image.open(path) as source:
            frames.append(source.convert("RGB").resize(size, Image.LANCZOS))

    # A frame from the middle of the clip is a better palette source than the first one,
    # which on a falling-note view can still be half empty background.
    master = frames[len(frames) // 2].quantize(colors=args.colors, method=Image.MEDIANCUT)
    quantized = [frame.quantize(palette=master, dither=Image.Dither.FLOYDSTEINBERG) for frame in frames]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    quantized[0].save(
        args.output,
        save_all=True,
        append_images=quantized[1:],
        duration=round(1000 / args.fps),
        loop=0,
        optimize=True,
        disposal=2,
    )

    written = args.output.stat().st_size
    print(f"{args.output}  {len(quantized)} frames  {size[0]}x{size[1]}  {written / 1024 / 1024:.1f} MB")
    if written > WARN_BYTES:
        print(
            f"Larger than {WARN_BYTES // 1024 // 1024} MB. Reduce --width, --colors or the "
            "clip length passed to --smoke-gif.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
