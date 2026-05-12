"""Render kernel composer output as preview PNGs.

Outputs:
- <out>/height.png       — grayscale heightmap (16-bit; normalized to [0..1])
- <out>/biome_dominant.png — RGB with each biome shown in a distinct color
- <out>/meta.json        — params used + min/max height

Usage:
    python build_kernel_preview.py \\
        --catalog ".../worlds/scale_v2/biome_catalog.json" \\
        --out "preview/" --resolution 512 --extent-m 4096 --seed 42
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from kernels import build_builtin_registry
from kernel_composer import KernelComposer


BIOME_PALETTE = [
    (240, 240, 250),  # alpine — pale icy
    (220, 180, 90),   # desert — tan
    (50, 140, 60),    # forest — green
    (160, 140, 130),  # rocky — mid-grey-brown
    (40, 60, 80),     # wetland — dark blue-grey
    (200, 50, 50),
    (50, 200, 200),
    (200, 50, 200),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--resolution", type=int, default=512,
                    help="Output PNG resolution (px).")
    ap.add_argument("--extent-m", type=float, default=4096.0,
                    help="World extent covered by the preview, in meters.")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cat_raw = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    comp = KernelComposer(catalog=cat_raw, registry=build_builtin_registry())

    res = args.resolution
    half = args.extent_m * 0.5
    xs = np.linspace(-half, half, res, dtype=np.float64)
    zs = np.linspace(-half, half, res, dtype=np.float64)

    height = np.zeros((res, res), dtype=np.float64)
    dominant = np.zeros((res, res), dtype=np.int32)
    biome_names = comp.biome_names()
    biome_index = {n: i for i, n in enumerate(biome_names)}

    for ri, z in enumerate(zs):
        for ci, x in enumerate(xs):
            height[ri, ci] = comp.sample_height(float(x), float(z), args.seed)
            weights = comp.sample_biome_weights(float(x), float(z), args.seed)
            dominant_biome = max(weights, key=weights.get)
            dominant[ri, ci] = biome_index[dominant_biome]

    h_min = float(height.min())
    h_max = float(height.max())
    h_norm = (height - h_min) / max(h_max - h_min, 1e-6)
    h_u16 = (h_norm * 65535).astype(np.uint16)
    Image.fromarray(h_u16, mode="I;16").save(out_dir / "height.png")

    rgb = np.zeros((res, res, 3), dtype=np.uint8)
    for i, name in enumerate(biome_names):
        color = BIOME_PALETTE[i % len(BIOME_PALETTE)]
        mask = (dominant == i)
        for c in range(3):
            rgb[mask, c] = color[c]
    Image.fromarray(rgb, mode="RGB").save(out_dir / "biome_dominant.png")

    meta = {
        "catalog": str(args.catalog),
        "seed": args.seed,
        "extent_m": args.extent_m,
        "resolution_px": res,
        "biomes": biome_names,
        "biome_palette": {n: list(BIOME_PALETTE[i % len(BIOME_PALETTE)])
                          for i, n in enumerate(biome_names)},
        "height_min_m": h_min,
        "height_max_m": h_max,
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote preview to {out_dir} (height {h_min:.1f}m..{h_max:.1f}m)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
