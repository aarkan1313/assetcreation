"""Region zoom — extract a chunk of a coherent multi-biome world and re-generate it
at higher detail for playable use.

Workflow:
  1. Load a world from `world/worlds/<world_id>/` (made by world_biome_engine.py)
  2. Pick a region by bbox in world-pixel coords OR by landmark name
  3. Read the dominant biome(s) at that region
  4. Re-generate the heightmap at higher detail (more octaves of FBM, finer
     features) seeded by the original heightmap's mid-frequencies
  5. Per-biome carve features at full playable scale
  6. Emit a standard terrain bundle at <region_size> px (defaults 1024)

This is what bridges "world overview" to "player walks here." The output bundle
is a drop-in replacement for any pipelines/terrain/output/<id>/ — feeds
straight into the Godot exporter, biome dressing, etc.

Usage:
  # By bbox (world-pixel coords):
  python region_zoom.py --world mythos_world --bbox 200 300 600 700 --id mythos_region_a --size 1024

  # By landmark (uses world's landmarks.json from generate_world_map if available):
  python region_zoom.py --world mythos_world --landmark "Sundered Pass" --radius 200 --id sundered --size 1024
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(r"D:\assets\pipelines\terrain")))
sys.path.insert(0, str(Path(r"D:\assets\art_lab\biomes\tools")))

from generate_heightmap import fbm, thermal_erode, normal_from_height, hypsometric_preview
from terrain_bundle import (
    slope_from_height, flow_accumulation_d8,
    vegetation_density, water_mask, hillshade, to_png_16bit,
    GODOT_TERRAIN3D_HINT, heightmapshape3d_tres,
)
from world_biome_engine import (
    apply_biome_features, render_regional_view, render_local_view,
    render_world_view, OCEAN_COLOR_DEEP, OCEAN_COLOR_SHALLOW,
)


WORLDS_ROOT = Path(r"D:\assets\world\worlds")
KITS_DIR = Path(r"D:\assets\art_lab\biomes\world_kits")
OUT_ROOT = Path(r"D:\assets\world\regions")


def upsample_with_detail(world_h_chunk: np.ndarray, target_size: int, seed: int) -> np.ndarray:
    """Take a low-res world heightmap chunk and upsample to target_size with
    added high-frequency detail.

    The world heightmap supplies the LARGE-SCALE shape; we add fresh fine FBM
    on top so the region looks playable rather than blurry-upsampled.
    """
    src_h, src_w = world_h_chunk.shape
    # Bicubic upsample — preserves the macro shape
    macro = np.asarray(
        Image.fromarray((world_h_chunk * 255).astype(np.uint8), mode="L")
             .resize((target_size, target_size), Image.BICUBIC),
        dtype=np.float32,
    ) / 255.0

    # Add high-frequency detail
    # base_scale should reflect target_size / src_chunk_size ratio so the new
    # detail lives at frequencies the source didn't capture.
    detail_scale = max(8, target_size // 32)
    detail = fbm(target_size, base_scale=detail_scale, octaves=5, persistence=0.5, seed=seed + 1)
    detail = (detail - detail.min()) / (detail.max() - detail.min() + 1e-9)

    # Mid-frequency variation: add some 3-octave FBM at medium scale
    mid_scale = max(4, target_size // 64)
    mid = fbm(target_size, base_scale=mid_scale, octaves=3, persistence=0.6, seed=seed + 2)
    mid = (mid - mid.min()) / (mid.max() - mid.min() + 1e-9)

    # Combine: 70% macro shape from source, 20% mid-freq variation, 10% fine detail
    combined = macro * 0.70 + (mid - 0.5) * 0.20 + (detail - 0.5) * 0.10
    return np.clip(combined, 0, 1).astype(np.float32)


def upsample_labels(labels_chunk: np.ndarray, target_size: int) -> np.ndarray:
    """Nearest-neighbour upsample of biome labels (categorical, must not blur)."""
    return np.asarray(
        Image.fromarray(labels_chunk, mode="L")
             .resize((target_size, target_size), Image.NEAREST),
        dtype=np.uint8,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", required=True, help="world_id under world/worlds/")
    ap.add_argument("--bbox", nargs=4, type=int, metavar=("X0", "Y0", "X1", "Y1"),
                    help="region bbox in world-pixel coords")
    ap.add_argument("--landmark", help="landmark name (uses world's landmarks.json)")
    ap.add_argument("--radius", type=int, default=200,
                    help="(--landmark mode) world-pixel radius around landmark")
    ap.add_argument("--id", required=True, help="output region id")
    ap.add_argument("--size", type=int, default=1024,
                    help="region resolution in pixels")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--erosion", type=int, default=20)
    args = ap.parse_args()

    # Load source world
    world_dir = WORLDS_ROOT / args.world
    if not world_dir.exists():
        raise SystemExit(f"world not found: {world_dir}")

    world_h = np.asarray(Image.open(world_dir / "height_16.png"), dtype=np.float32) / 65535.0
    world_labels = np.asarray(Image.open(world_dir / "biome_labels.png"), dtype=np.uint8)
    world_meta = json.loads((world_dir / "world.json").read_text(encoding="utf-8"))

    print(f"[zoom] source world: {args.world} ({world_h.shape[0]}x{world_h.shape[1]})")

    # Resolve region bbox
    if args.bbox:
        x0, y0, x1, y1 = args.bbox
    elif args.landmark:
        # Map's landmarks.json was generated by generate_world_map; we don't have it here.
        # Use a quick fallback: pick coords from the user
        raise SystemExit("--landmark not yet implemented for world_biome_engine outputs; pass --bbox")
    else:
        ap.error("provide --bbox or --landmark")

    x0 = max(0, x0); y0 = max(0, y0)
    x1 = min(world_h.shape[1], x1); y1 = min(world_h.shape[0], y1)
    if x1 <= x0 or y1 <= y0:
        raise SystemExit(f"bbox is degenerate: {x0},{y0},{x1},{y1}")

    print(f"[zoom] bbox: ({x0},{y0}) -> ({x1},{y1}) = {x1-x0}x{y1-y0}px world")

    # Extract chunks
    h_chunk = world_h[y0:y1, x0:x1].copy()
    labels_chunk = world_labels[y0:y1, x0:x1].copy()

    # Show what biomes are present in this region
    biome_ids = world_meta["biomes"]
    biome_kits = []
    for bid in biome_ids:
        kit_path = KITS_DIR / f"{bid}.json"
        if kit_path.exists():
            biome_kits.append(json.loads(kit_path.read_text(encoding="utf-8")))
        else:
            biome_kits.append(None)
    print(f"[zoom] biome composition of region:")
    total = labels_chunk.size
    for bi, kit in enumerate(biome_kits):
        n = (labels_chunk == bi).sum()
        if n > 0 and kit:
            print(f"  {kit['display_name']:25s} {n/total:5.1%}")
    n_ocean = (labels_chunk == 255).sum()
    if n_ocean > 0:
        print(f"  {'Ocean':25s} {n_ocean/total:5.1%}")

    # Upsample to target size with added detail
    print(f"[zoom] upsample heightmap to {args.size}x{args.size} with new fine detail")
    h = upsample_with_detail(h_chunk, args.size, args.seed)
    labels = upsample_labels(labels_chunk, args.size)

    # Re-apply per-biome carving at the higher resolution
    print(f"[zoom] re-carve features at full playable scale")
    for bi, kit in enumerate(biome_kits):
        if kit is None:
            continue
        mask = labels == bi
        if not mask.any():
            continue
        features = kit["terrain"].get("carve_features", [])
        if features:
            h = apply_biome_features(h, mask, features, args.seed + bi * 17)

    if args.erosion > 0:
        print(f"[zoom] erosion x{args.erosion}")
        h = thermal_erode(h, iterations=args.erosion)

    # Re-derive everything from the upsampled heightmap
    print(f"[zoom] re-derive bundle layers")
    slope = slope_from_height(h)
    flow = flow_accumulation_d8(h, iterations=15)
    biome_rgb = np.zeros((args.size, args.size, 3), dtype=np.uint8)
    for bi, kit in enumerate(biome_kits):
        if kit:
            biome_rgb[labels == bi] = kit["identity"]["world_color"]

    splat = np.zeros((args.size, args.size, 4), dtype=np.uint8)
    for bi in range(min(4, len(biome_kits))):
        splat[..., bi] = (labels == bi).astype(np.uint8) * 255

    veg = vegetation_density(labels, slope, h)
    water = water_mask(h, sea_level=0.32)

    # Write bundle
    out_dir = OUT_ROOT / args.id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "godot").mkdir(parents=True, exist_ok=True)

    to_png_16bit(h, out_dir / "height_16.png")
    normal_from_height(h).save(out_dir / "normal.png")
    Image.fromarray(splat, mode="RGBA").save(out_dir / "splat_rgba.png")
    Image.fromarray(biome_rgb, mode="RGB").save(out_dir / "biome.png")
    Image.fromarray(labels, mode="L").save(out_dir / "biome_labels.png")
    label_rgb = np.zeros((args.size, args.size, 3), dtype=np.uint8)
    for bi, kit in enumerate(biome_kits):
        if kit:
            label_rgb[labels == bi] = kit["identity"]["world_color"]
    Image.fromarray(label_rgb, mode="RGB").save(out_dir / "biome_labels_colored.png")
    Image.fromarray(veg, mode="L").save(out_dir / "vegetation_density.png")
    Image.fromarray(water, mode="L").save(out_dir / "water_mask.png")
    Image.fromarray((flow * 255).astype(np.uint8), mode="L").save(out_dir / "flow.png")
    hypsometric_preview(h).save(out_dir / "preview_hypsometric.png")
    Image.fromarray(hillshade(h), mode="L").save(out_dir / "preview_hillshade.png")

    # Three-tier views
    valid_kits = [k for k in biome_kits if k is not None]
    render_world_view(labels, valid_kits, h, target_px=128).save(out_dir / "world_view.png")
    render_regional_view(labels, h, valid_kits, target_px=512).save(out_dir / "regional_view.png")
    render_local_view(h, labels, valid_kits).save(out_dir / "local_view.png")

    # Godot scaffolding
    (out_dir / "godot" / "terrain3d_import.json").write_text(GODOT_TERRAIN3D_HINT, encoding="utf-8")
    (out_dir / "godot" / "heightmapshape3d.tres").write_text(
        heightmapshape3d_tres("../height_16.png"), encoding="utf-8"
    )

    # Manifest
    manifest = {
        "id": args.id,
        "created": datetime.now(timezone.utc).isoformat(),
        "source": "region_zoom",
        "source_world": args.world,
        "source_bbox": [x0, y0, x1, y1],
        "size": args.size,
        "seed": args.seed,
        "erosion": args.erosion,
        "biome_pixel_counts": {
            (biome_kits[bi]["id"] if biome_kits[bi] else f"unknown_{bi}"): int((labels == bi).sum())
            for bi in range(len(biome_kits))
        },
        "ocean_pixel_count": int((labels == 255).sum()),
    }
    (out_dir / "region.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"REGION: {args.id}")
    print(f"  source:  {args.world} bbox=({x0},{y0})-({x1},{y1})")
    print(f"  size:    {args.size}x{args.size}")
    print(f"  out:     {out_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
