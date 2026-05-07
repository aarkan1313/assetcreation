"""FastNoiseLite-based heightmap generator (faster + more interesting noise types).

The numpy/value-noise generator in generate_heightmap.py is fine for prototyping
but slow and limited to FBM. FastNoiseLite gives us:
  - OpenSimplex2/2S, Perlin, Cellular/Worley, ValueCubic
  - DomainWarp transforms
  - Ridged / Ping-Pong / FBM fractal types

Outputs feed straight into terrain_bundle's downstream stages.

Usage:
  python fastnoise_height.py --id ridged_a --noise OpenSimplex2 --fractal Ridged --warp Domain
  python fastnoise_height.py --id cellular_a --noise Cellular --fractal FBm
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image
from pyfastnoiselite.pyfastnoiselite import (
    FastNoiseLite, NoiseType, FractalType, DomainWarpType, CellularDistanceFunction,
)

sys.path.insert(0, str(Path(__file__).parent))
from terrain_bundle import (
    slope_from_height, flow_accumulation_d8, derive_biome, splat_rgba,
    vegetation_density, water_mask, hillshade, hypsometric_preview,
    normal_from_height, to_png_16bit, GODOT_TERRAIN3D_HINT,
    heightmapshape3d_tres, hydraulic_erode_landlab, thermal_erode,
)


NOISE_TYPES = {
    "OpenSimplex2":  NoiseType.NoiseType_OpenSimplex2,
    "OpenSimplex2S": NoiseType.NoiseType_OpenSimplex2S,
    "Cellular":      NoiseType.NoiseType_Cellular,
    "Perlin":        NoiseType.NoiseType_Perlin,
    "ValueCubic":    NoiseType.NoiseType_ValueCubic,
    "Value":         NoiseType.NoiseType_Value,
}

FRACTAL_TYPES = {
    "None":     FractalType.FractalType_None,
    "FBm":      FractalType.FractalType_FBm,
    "Ridged":   FractalType.FractalType_Ridged,
    "PingPong": FractalType.FractalType_PingPong,
}

WARP_TYPES = {
    "None":          None,
    "OpenSimplex2":  DomainWarpType.DomainWarpType_OpenSimplex2,
    "OpenSimplex2R": DomainWarpType.DomainWarpType_OpenSimplex2Reduced,
    "BasicGrid":     DomainWarpType.DomainWarpType_BasicGrid,
}


def build_noise(args) -> np.ndarray:
    n = FastNoiseLite(seed=args.seed)
    n.noise_type = NOISE_TYPES[args.noise]
    n.frequency = args.frequency
    n.fractal_type = FRACTAL_TYPES[args.fractal]
    n.fractal_octaves = args.octaves
    n.fractal_lacunarity = args.lacunarity
    n.fractal_gain = args.gain
    if args.noise == "Cellular":
        n.cellular_distance_function = CellularDistanceFunction.CellularDistanceFunction_EuclideanSq

    # Note: pyfastnoiselite 0.0.7 does not expose domain_warp() as a method,
    # only the type/amp settings. We get most of the shape benefit from the
    # fractal types alone (Ridged + OpenSimplex2 is the report's recommendation).
    if args.warp != "None":
        print(f"  [warning] --warp is a no-op in this binding version; ignoring")

    out = np.zeros((args.size, args.size), dtype=np.float32)
    half = args.size / 2
    for y in range(args.size):
        for x in range(args.size):
            xf = (x - half) * 1.0
            yf = (y - half) * 1.0
            out[y, x] = n.get_noise(xf, yf)
    out = (out - out.min()) / (out.max() - out.min() + 1e-9)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--noise", default="OpenSimplex2", choices=list(NOISE_TYPES.keys()))
    ap.add_argument("--fractal", default="FBm", choices=list(FRACTAL_TYPES.keys()))
    ap.add_argument("--warp", default="None", choices=list(WARP_TYPES.keys()))
    ap.add_argument("--frequency", type=float, default=0.005)
    ap.add_argument("--octaves", type=int, default=5)
    ap.add_argument("--lacunarity", type=float, default=2.0)
    ap.add_argument("--gain", type=float, default=0.5)
    ap.add_argument("--warp-amp", type=float, default=30.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--erosion", type=int, default=40)
    ap.add_argument("--erosion-mode", choices=["thermal", "hydraulic", "none"], default="thermal")
    args = ap.parse_args()

    print(f"[fastnoise] {args.size}x{args.size} {args.noise}/{args.fractal} warp={args.warp}")
    h = build_noise(args)

    if args.erosion_mode == "hydraulic":
        h = hydraulic_erode_landlab(h, n_steps=args.erosion)
    elif args.erosion_mode == "thermal":
        h = thermal_erode(h, iterations=args.erosion)

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
    Image.fromarray(veg, mode="L").save(out_dir / "vegetation_density.png")
    Image.fromarray(water, mode="L").save(out_dir / "water_mask.png")
    Image.fromarray((flow * 255).astype(np.uint8), mode="L").save(out_dir / "flow.png")
    hypsometric_preview(h).save(out_dir / "preview_hypsometric.png")
    Image.fromarray(hillshade(h), mode="L").save(out_dir / "preview_hillshade.png")
    (out_dir / "godot" / "terrain3d_import.json").write_text(GODOT_TERRAIN3D_HINT, encoding="utf-8")
    (out_dir / "godot" / "heightmapshape3d.tres").write_text(
        heightmapshape3d_tres("../height_16.png"), encoding="utf-8"
    )
    (out_dir / "terrain.json").write_text(json.dumps({
        "id": args.id, "created": datetime.now(timezone.utc).isoformat(),
        "source": "fastnoiselite",
        "noise_type": args.noise, "fractal_type": args.fractal, "warp": args.warp,
        "frequency": args.frequency, "octaves": args.octaves,
        "lacunarity": args.lacunarity, "gain": args.gain, "warp_amp": args.warp_amp,
        "size": args.size, "seed": args.seed,
        "erosion_mode": args.erosion_mode, "erosion": args.erosion,
    }, indent=2), encoding="utf-8")
    print(f"done: {out_dir}")


if __name__ == "__main__":
    main()
