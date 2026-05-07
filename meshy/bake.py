"""User-facing wrapper for the headless Blender sprite bake.

Usage:
    python bake.py <input.fbx|glb|obj> [<out_dir>] [options]

If <out_dir> is omitted, output goes to:
    D:\\assets\\meshy\\sprites\\<input-stem>\\

Options pass through to bake_sprites.py:
    --angles N           number of azimuth angles (default 8)
    --frames N           number of animation frames to sample (default 16)
    --res N              square resolution (default 512)
    --ortho              orthographic camera (sprite-friendly, no perspective)
    --padding F          framing padding multiplier (default 1.15)
    --elevation D        camera tilt above horizon, degrees (0=side, 30=3/4 view)
    --no-alpha           disable transparent background (white instead)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text())
SPRITE_DIR = ROOT / "sprites"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("out_dir", type=Path, nargs="?", default=None)
    ap.add_argument("--angles", type=int, default=8)
    ap.add_argument("--frames", type=int, default=16)
    ap.add_argument("--res", type=int, default=512)
    ap.add_argument("--ortho", action="store_true")
    ap.add_argument("--padding", type=float, default=1.15)
    ap.add_argument("--elevation", type=float, default=0.0)
    ap.add_argument("--no-alpha", action="store_true")
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")

    if args.out_dir is None:
        SPRITE_DIR.mkdir(parents=True, exist_ok=True)
        args.out_dir = SPRITE_DIR / args.input.stem

    blender_args = [
        CONFIG["blender_exe"],
        "-b",
        "-P",
        str(ROOT / "bake_sprites.py"),
        "--",
        str(args.input),
        str(args.out_dir),
        "--angles", str(args.angles),
        "--frames", str(args.frames),
        "--res", str(args.res),
        "--padding", str(args.padding),
        "--elevation", str(args.elevation),
    ]
    if args.ortho:
        blender_args.append("--ortho")
    if args.no_alpha:
        blender_args.append("--no-alpha")

    print(f"$ {' '.join(blender_args)}")
    r = subprocess.run(blender_args)
    if r.returncode != 0:
        sys.exit(r.returncode)

    print(f"\noutput: {args.out_dir}")


if __name__ == "__main__":
    main()
