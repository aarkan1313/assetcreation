"""Wrap a WorldEngine output into the terrain bundle contract.

WorldEngine emits world-scale PNGs (heightmap, biome, precip, temp, rivers).
We pick the grayscale heightmap and the biome map, resample to --size, and
run them through the same downstream stages as terrain_bundle.py so the
output folder matches the rest of the pipeline.

Usage:
  python worldengine_to_bundle.py --we-dir D:/assets/pipelines/terrain/output/worldengine_smoketest --id world_a
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

from terrain_bundle import (
    slope_from_height, flow_accumulation_d8, derive_biome, splat_rgba,
    vegetation_density, water_mask, hillshade, hypsometric_preview,
    normal_from_height, to_png_16bit, GODOT_TERRAIN3D_HINT,
    heightmapshape3d_tres,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--we-dir", type=Path, required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--size", type=int, default=1024)
    args = ap.parse_args()

    grayscale = args.we_dir / [p.name for p in args.we_dir.glob("*_grayscale.png")][0]
    we_biome = args.we_dir / [p.name for p in args.we_dir.glob("*_biome.png")][0]

    h_im = Image.open(grayscale).convert("L").resize((args.size, args.size), Image.LANCZOS)
    h = np.asarray(h_im, dtype=np.float32) / 255.0

    out_dir = Path(__file__).parent / "output" / args.id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "godot").mkdir(parents=True, exist_ok=True)

    slope = slope_from_height(h)
    flow = flow_accumulation_d8(h, iterations=20)
    biome_rgb, labels = derive_biome(h, slope)
    splat = splat_rgba(labels)
    veg = vegetation_density(labels, slope, h)
    water = water_mask(h)

    to_png_16bit(h, out_dir / "height_16.png")
    normal_from_height(h).save(out_dir / "normal.png")
    Image.fromarray(splat, mode="RGBA").save(out_dir / "splat_rgba.png")
    Image.fromarray(biome_rgb, mode="RGB").save(out_dir / "biome.png")
    # Also keep WorldEngine's authoritative biome map for reference
    Image.open(we_biome).resize((args.size, args.size), Image.NEAREST).save(out_dir / "biome_worldengine.png")
    Image.fromarray(veg, mode="L").save(out_dir / "vegetation_density.png")
    Image.fromarray(water, mode="L").save(out_dir / "water_mask.png")
    Image.fromarray((flow * 255).astype(np.uint8), mode="L").save(out_dir / "flow.png")
    hypsometric_preview(h).save(out_dir / "preview_hypsometric.png")
    Image.fromarray(hillshade(h), mode="L").save(out_dir / "preview_hillshade.png")
    (out_dir / "godot" / "terrain3d_import.json").write_text(GODOT_TERRAIN3D_HINT, encoding="utf-8")
    (out_dir / "godot" / "heightmapshape3d.tres").write_text(
        heightmapshape3d_tres("../height_16.png"), encoding="utf-8"
    )

    metadata = {
        "id": args.id,
        "created": datetime.now(timezone.utc).isoformat(),
        "source": "worldengine",
        "we_dir": str(args.we_dir),
        "size": args.size,
    }
    (out_dir / "terrain.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"done: {out_dir}")


if __name__ == "__main__":
    main()
