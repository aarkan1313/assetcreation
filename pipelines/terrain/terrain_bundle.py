"""Terrain v2: produce a complete Godot-ready terrain bundle from a heightmap.

Bundle output (per the SOTA report folder contract):
  world/terrain/<id>/
    height_16.png            -- 16-bit grayscale, 0..65535
    normal.png               -- tangent-space normal (OpenGL +Y)
    splat_rgba.png           -- 4-channel material splatmap
    biome.png                -- categorical biome (palette PNG)
    vegetation_density.png   -- grayscale 0..255
    water_mask.png           -- binary water occupancy
    flow.png                 -- log-scaled flow accumulation preview
    preview_hypsometric.png
    preview_hillshade.png
    terrain.json             -- metadata + provenance
    godot/
      terrain3d_import.json  -- importer hint for Terrain3D plugin
      heightmapshape3d.tres  -- ready-to-import collision resource

Inputs: a 0..1 float heightmap (synthetic via FBM or any PNG via --input).

Usage:
  python terrain_bundle.py --biome mountains --size 1024 --erosion 60 \
      --id alpine_a --erosion-mode thermal
  python terrain_bundle.py --input some_height.png --id real_dem_a

The Landlab erosion path is opt-in via --erosion-mode hydraulic. If Landlab is
not installed, we fall back to the local thermal erosion.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

# Reuse primitives from generate_heightmap.py
sys.path.insert(0, str(Path(__file__).parent))
from generate_heightmap import (
    fbm,
    shape_biome,
    thermal_erode,
    to_png_16bit,
    hypsometric_preview,
    normal_from_height,
)


# ---------------------------------------------------------------------------
# Optional Landlab hydraulic erosion
# ---------------------------------------------------------------------------
def hydraulic_erode_landlab(h: np.ndarray, n_steps: int = 200, K_sp: float = 5e-5) -> np.ndarray:
    """Stream-power hydraulic erosion via Landlab. Returns eroded heightmap.

    Falls back to thermal_erode if Landlab is missing.
    """
    try:
        from landlab import RasterModelGrid
        from landlab.components import FlowAccumulator, FastscapeEroder
    except ImportError:
        print("  [landlab] not installed; using thermal fallback")
        return thermal_erode(h, iterations=max(20, n_steps // 4))

    rows, cols = h.shape
    mg = RasterModelGrid((rows, cols), xy_spacing=1.0)
    z = mg.add_zeros("topographic__elevation", at="node")
    z[:] = h.flatten() * 100.0  # exaggerate so erosion has something to bite

    fa = FlowAccumulator(mg, flow_director="FlowDirectorD8")
    sp = FastscapeEroder(mg, K_sp=K_sp, m_sp=0.5, n_sp=1.0)
    for _ in range(n_steps):
        fa.run_one_step()
        sp.run_one_step(dt=1.0)

    eroded = z.reshape((rows, cols)).astype(np.float32)
    eroded -= eroded.min()
    eroded /= max(eroded.max(), 1e-9)
    return eroded


# ---------------------------------------------------------------------------
# Flow accumulation (cheap D8 fallback if no Landlab)
# ---------------------------------------------------------------------------
def flow_accumulation_d8(h: np.ndarray, iterations: int = 30) -> np.ndarray:
    """Cheap iterative flow accumulation. Returns log-scaled 0..1 array."""
    rows, cols = h.shape
    flow = np.ones_like(h, dtype=np.float32)
    pad = np.pad(h, 1, mode="edge")
    # find lowest neighbor offset for each cell
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    best_dy = np.zeros((rows, cols), dtype=np.int8)
    best_dx = np.zeros((rows, cols), dtype=np.int8)
    best_drop = np.zeros((rows, cols), dtype=np.float32)
    for dy, dx in offsets:
        n = pad[1 + dy:1 + dy + rows, 1 + dx:1 + dx + cols]
        drop = h - n
        better = drop > best_drop
        best_drop = np.where(better, drop, best_drop)
        best_dy = np.where(better, dy, best_dy)
        best_dx = np.where(better, dx, best_dx)

    for _ in range(iterations):
        new_flow = np.ones_like(flow)
        for dy, dx in offsets:
            mask_y = (best_dy == dy)
            mask_x = (best_dx == dx)
            mask = mask_y & mask_x
            # cells whose lowest neighbor is at (-dy,-dx) contribute upstream flow
            shifted = np.roll(np.roll(flow * mask.astype(np.float32), -dy, axis=0), -dx, axis=1)
            new_flow += shifted
        flow = new_flow

    flow_log = np.log1p(flow)
    flow_log /= max(flow_log.max(), 1e-9)
    return flow_log


# ---------------------------------------------------------------------------
# Biome / splat / vegetation / water derivation
# ---------------------------------------------------------------------------
BIOME_PALETTE = {
    "water":  (40, 80, 130),
    "beach":  (210, 190, 140),
    "grass":  (70, 140, 60),
    "forest": (40, 90, 35),
    "rock":   (110, 95, 80),
    "snow":   (240, 240, 250),
}


def slope_from_height(h: np.ndarray) -> np.ndarray:
    """Slope magnitude in 0..1."""
    pad = np.pad(h, 1, mode="edge")
    gx = pad[1:-1, 2:] - pad[1:-1, :-2]
    gy = pad[2:, 1:-1] - pad[:-2, 1:-1]
    s = np.sqrt(gx * gx + gy * gy)
    s /= max(s.max(), 1e-9)
    return s


def derive_biome(h: np.ndarray, slope: np.ndarray, sea_level: float = 0.32) -> tuple[np.ndarray, np.ndarray]:
    """Return (rgb biome image, integer label array)."""
    labels = np.zeros(h.shape, dtype=np.uint8)
    labels[h < sea_level] = 0  # water
    labels[(h >= sea_level) & (h < sea_level + 0.05)] = 1  # beach
    labels[(h >= sea_level + 0.05) & (h < 0.55) & (slope < 0.25)] = 2  # grass
    labels[(h >= sea_level + 0.05) & (h < 0.55) & (slope >= 0.25)] = 4  # rock
    labels[(h >= 0.55) & (h < 0.78) & (slope < 0.35)] = 3  # forest
    labels[(h >= 0.55) & (h < 0.78) & (slope >= 0.35)] = 4  # rock
    labels[h >= 0.78] = 5  # snow
    palette = list(BIOME_PALETTE.values())
    rgb = np.zeros((h.shape[0], h.shape[1], 3), dtype=np.uint8)
    for i, color in enumerate(palette):
        rgb[labels == i] = color
    return rgb, labels


def splat_rgba(labels: np.ndarray) -> np.ndarray:
    """4-channel splatmap. R=grass, G=rock, B=forest, A=snow.

    Beach/water are not in the splat (the height/water_mask handle them).
    """
    h, w = labels.shape
    splat = np.zeros((h, w, 4), dtype=np.uint8)
    splat[..., 0] = (labels == 2).astype(np.uint8) * 255  # grass
    splat[..., 1] = (labels == 4).astype(np.uint8) * 255  # rock
    splat[..., 2] = (labels == 3).astype(np.uint8) * 255  # forest
    splat[..., 3] = (labels == 5).astype(np.uint8) * 255  # snow
    return splat


def vegetation_density(labels: np.ndarray, slope: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Per-cell vegetation density 0..255."""
    density = np.zeros(labels.shape, dtype=np.float32)
    density[labels == 2] = 0.5   # grass: medium
    density[labels == 3] = 1.0   # forest: full
    density[labels == 1] = 0.05  # beach: sparse
    # reduce on slope and at altitude
    density *= (1.0 - np.clip(slope * 1.5, 0, 1))
    density *= (1.0 - np.clip((h - 0.65) * 4, 0, 1))
    return (density.clip(0, 1) * 255).astype(np.uint8)


def water_mask(h: np.ndarray, sea_level: float = 0.32) -> np.ndarray:
    return ((h < sea_level).astype(np.uint8) * 255)


def hillshade(h: np.ndarray, az_deg: float = 315.0, alt_deg: float = 45.0) -> np.ndarray:
    """Standard GDAL-style hillshade for visual QA."""
    az = np.radians(360.0 - az_deg + 90.0)
    alt = np.radians(alt_deg)
    pad = np.pad(h * 100.0, 1, mode="edge")
    dzdx = (pad[1:-1, 2:] - pad[1:-1, :-2]) / 2.0
    dzdy = (pad[2:, 1:-1] - pad[:-2, 1:-1]) / 2.0
    slope = np.arctan(np.sqrt(dzdx ** 2 + dzdy ** 2))
    aspect = np.arctan2(dzdy, -dzdx)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    shade = (shade.clip(0, 1) * 255).astype(np.uint8)
    return shade


# ---------------------------------------------------------------------------
# Godot import scaffolding
# ---------------------------------------------------------------------------
GODOT_TERRAIN3D_HINT = """\
{
  "_comment": "Terrain3D import hint. Open Godot, install Terrain3D plugin, drop these into a Terrain3D node.",
  "height_path": "../height_16.png",
  "splat_path":  "../splat_rgba.png",
  "biome_path":  "../biome.png",
  "vegetation_density_path": "../vegetation_density.png",
  "water_mask_path": "../water_mask.png",
  "y_scale_meters": 64.0,
  "horizontal_scale_meters_per_pixel": 1.0
}
"""


def heightmapshape3d_tres(height_relative: str) -> str:
    return f"""[gd_resource type=\"HeightMapShape3D\" load_steps=2 format=3]

[ext_resource type=\"Texture2D\" path=\"{height_relative}\" id=\"1\"]

[resource]
map_data = ExtResource(\"1\")
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="terrain id (folder name)")
    ap.add_argument("--mode", choices=["synthetic", "image"], default="synthetic")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--octaves", type=int, default=6)
    ap.add_argument("--biome", default="custom",
                    choices=["mountains", "plains", "islands", "canyon", "custom"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--erosion", type=int, default=40, help="erosion iterations")
    ap.add_argument("--erosion-mode", choices=["thermal", "hydraulic", "none"], default="thermal")
    ap.add_argument("--sea-level", type=float, default=0.32)
    ap.add_argument("--input", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=Path(__file__).parent / "output")
    args = ap.parse_args()

    out_dir = args.out_root / args.id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "godot").mkdir(parents=True, exist_ok=True)

    if args.mode == "image":
        if not args.input or not args.input.exists():
            raise SystemExit("--input required for image mode")
        im = Image.open(args.input).convert("L")
        if im.size != (args.size, args.size):
            im = im.resize((args.size, args.size), Image.LANCZOS)
        h = np.asarray(im, dtype=np.float32) / 255.0
    else:
        print(f"[1/8] FBM {args.size}x{args.size} biome={args.biome} seed={args.seed}")
        base_scale = max(2, int(4 / args.scale))
        h = fbm(args.size, base_scale=base_scale, octaves=args.octaves, seed=args.seed)
        h = (h - h.min()) / (h.max() - h.min() + 1e-9)
        h = shape_biome(h, args.biome)

    if args.erosion_mode == "hydraulic":
        print(f"[2/8] Hydraulic erosion (Landlab) x{args.erosion}")
        h = hydraulic_erode_landlab(h, n_steps=args.erosion)
    elif args.erosion_mode == "thermal":
        print(f"[2/8] Thermal erosion x{args.erosion}")
        h = thermal_erode(h, iterations=args.erosion)
    else:
        print("[2/8] No erosion")

    print("[3/8] Slope + flow accumulation")
    slope = slope_from_height(h)
    flow = flow_accumulation_d8(h, iterations=20)

    print("[4/8] Biome / splat / vegetation / water")
    biome_rgb, labels = derive_biome(h, slope, sea_level=args.sea_level)
    splat = splat_rgba(labels)
    veg = vegetation_density(labels, slope, h)
    water = water_mask(h, sea_level=args.sea_level)

    print("[5/8] Writing height + normal")
    to_png_16bit(h, out_dir / "height_16.png")
    normal_from_height(h).save(out_dir / "normal.png")

    print("[6/8] Writing splat / biome / veg / water / flow")
    Image.fromarray(splat, mode="RGBA").save(out_dir / "splat_rgba.png")
    Image.fromarray(biome_rgb, mode="RGB").save(out_dir / "biome.png")
    Image.fromarray(veg, mode="L").save(out_dir / "vegetation_density.png")
    Image.fromarray(water, mode="L").save(out_dir / "water_mask.png")
    Image.fromarray((flow * 255).astype(np.uint8), mode="L").save(out_dir / "flow.png")

    print("[7/8] Previews (hypsometric + hillshade)")
    hypsometric_preview(h).save(out_dir / "preview_hypsometric.png")
    Image.fromarray(hillshade(h), mode="L").save(out_dir / "preview_hillshade.png")

    print("[8/8] Godot scaffolding + terrain.json")
    (out_dir / "godot" / "terrain3d_import.json").write_text(GODOT_TERRAIN3D_HINT, encoding="utf-8")
    (out_dir / "godot" / "heightmapshape3d.tres").write_text(
        heightmapshape3d_tres("../height_16.png"), encoding="utf-8"
    )

    metadata = {
        "id": args.id,
        "created": datetime.now(timezone.utc).isoformat(),
        "source": "synthetic" if args.mode == "synthetic" else f"image:{args.input.name}",
        "size": args.size,
        "biome_preset": args.biome,
        "seed": args.seed,
        "erosion_mode": args.erosion_mode,
        "erosion_iterations": args.erosion,
        "sea_level": args.sea_level,
        "files": {
            "height": "height_16.png",
            "normal": "normal.png",
            "splat": "splat_rgba.png",
            "biome": "biome.png",
            "vegetation_density": "vegetation_density.png",
            "water_mask": "water_mask.png",
            "flow": "flow.png",
            "preview_hypsometric": "preview_hypsometric.png",
            "preview_hillshade": "preview_hillshade.png",
            "godot_import_hint": "godot/terrain3d_import.json",
            "godot_heightmapshape3d": "godot/heightmapshape3d.tres",
        },
    }
    (out_dir / "terrain.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"\ndone: {out_dir}")


if __name__ == "__main__":
    main()
