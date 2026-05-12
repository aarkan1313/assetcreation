"""Upscale a biome's PBR texture set in-place by N× via PIL Lanczos.

Quick quality knob 'B' for the worldgen workflow. Lanczos is not as sharp as
Real-ESRGAN/SwinIR but is a no-install baseline that doubles or quadruples
texel resolution — meaningful improvement when the iso/topdown character cam
zooms in and the original 1024² source starts showing pixel-grid.

Backs up the originals to <set_dir>/_original_<map>.png so the upscale can be
reverted by deleting the upscaled files.

Usage:
  python pipelines/textures/upscale_biome_set.py \\
      --set biome_mana_crystal --factor 4
  # Or upscale every biome set:
  python pipelines/textures/upscale_biome_set.py --all --factor 4

For higher quality, swap PIL.Image.resize for Real-ESRGAN once a model is
installed in animators/ComfyUI/models/upscale_models/. The single-call API is
identical (input PNG → output PNG); see commit 2026-05-06 for the workflow
that wires ComfyUI's UpscaleModelLoader into a node graph.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

from PIL import Image

LIBRARY = Path(r"D:\assets\world\textures\library")
PBR_CHANNELS = ("albedo", "normal", "roughness", "ao", "metallic", "height")


def upscale_one(set_dir: Path, factor: int) -> dict:
    """Upscale every <set_id>_<channel>.png in set_dir by factor× in place."""
    set_id = set_dir.name
    if not set_dir.is_dir():
        raise SystemExit(f"set dir not found: {set_dir}")

    info = {"set_id": set_id, "upscaled": [], "skipped": []}
    for ch in PBR_CHANNELS:
        path = set_dir / f"{set_id}_{ch}.png"
        if not path.exists():
            info["skipped"].append(ch)
            continue
        backup = set_dir / f"_original_{ch}.png"
        if not backup.exists():
            shutil.copy2(path, backup)

        t0 = time.time()
        im = Image.open(backup)  # always read original to avoid double-upscale
        new_w = im.width * factor
        new_h = im.height * factor
        # Normal maps prefer LANCZOS too; bicubic would produce softer normals
        # but most pipeline downstream uses normals directly so Lanczos is fine.
        upscaled = im.resize((new_w, new_h), Image.LANCZOS)
        upscaled.save(path, optimize=True)
        info["upscaled"].append({
            "channel": ch,
            "from": f"{im.width}×{im.height}",
            "to": f"{new_w}×{new_h}",
            "ms": int((time.time() - t0) * 1000),
        })

    return info


def revert_one(set_dir: Path) -> None:
    """Restore originals from _original_<channel>.png backups."""
    set_id = set_dir.name
    for ch in PBR_CHANNELS:
        backup = set_dir / f"_original_{ch}.png"
        target = set_dir / f"{set_id}_{ch}.png"
        if backup.exists():
            shutil.copy2(backup, target)
            print(f"  reverted {target.name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=None,
                    help="single set_id under world/textures/library/")
    ap.add_argument("--all", action="store_true",
                    help="upscale every biome_* set in the library")
    ap.add_argument("--factor", type=int, default=4)
    ap.add_argument("--revert", action="store_true",
                    help="restore originals from _original_*.png backups")
    args = ap.parse_args()

    if args.all:
        targets = [d for d in LIBRARY.iterdir() if d.is_dir() and d.name.startswith("biome_")]
    elif args.set:
        targets = [LIBRARY / args.set]
    else:
        ap.error("pass --set <id> or --all")

    print(f"{'reverting' if args.revert else f'upscaling {args.factor}×'}: "
          f"{len(targets)} set(s)")
    for t in targets:
        if args.revert:
            print(f"\n--- {t.name} ---")
            revert_one(t)
        else:
            try:
                info = upscale_one(t, args.factor)
                print(f"\n--- {info['set_id']} ---")
                for u in info["upscaled"]:
                    print(f"  {u['channel']:10} {u['from']:>11} -> {u['to']:>11}  ({u['ms']}ms)")
                if info["skipped"]:
                    print(f"  skipped: {info['skipped']}")
            except Exception as e:
                print(f"\nFAIL {t.name}: {e}")
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
