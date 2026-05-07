"""Convert a GLB to a Mixamo-ready FBX.

Mixamo requires:
  - FBX/OBJ format (not GLB)
  - Single mesh
  - ~human-scale (1-2 meters)
  - Y-up axis (FBX default)
  - Feet at world origin (character standing on the ground plane)

Usage:
    python glb_to_fbx.py <input.glb> [<output.fbx>]

If <output.fbx> is omitted, writes to:
    D:\\assets\\meshy\\mixamo_ready\\<input-stem>.fbx

After conversion:
  1. Go to https://www.mixamo.com (free Adobe account required)
  2. Click "Upload Character", drop the FBX
  3. Place markers (chin / wrists / elbows / knees / groin) — Mixamo guides you
  4. Wait ~30 sec for auto-rig
  5. Browse animations; pick walk/run/idle/attack/etc.
  6. Click "Download" → choose FBX with Skin → save back into the project
  7. Bake to sprites with bake.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text())
MIXAMO_DIR = ROOT / "mixamo_ready"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path, nargs="?", default=None)
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")

    if args.output is None:
        MIXAMO_DIR.mkdir(parents=True, exist_ok=True)
        # Strip "_p" suffix that preprocess.py adds, and handle Meshy's <name>/model.glb pattern
        stem = args.input.stem
        if stem == "model" and args.input.parent.name not in ("", "/", "\\"):
            stem = args.input.parent.name
        if stem.endswith("_p"):
            stem = stem[:-2]
        args.output = MIXAMO_DIR / f"{stem}.fbx"

    blender_args = [
        CONFIG["blender_exe"],
        "-b",
        "-P",
        str(ROOT / "glb_to_fbx_blender.py"),
        "--",
        str(args.input),
        str(args.output),
    ]
    print(f"$ {' '.join(blender_args)}")
    r = subprocess.run(blender_args)
    if r.returncode != 0:
        sys.exit(r.returncode)

    print(f"\noutput: {args.output}")
    print(f"upload to: https://www.mixamo.com")


if __name__ == "__main__":
    main()
