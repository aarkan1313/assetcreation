"""Scale demo — Phase 1b: slice 1024m heightmap into 16 x 256m tiles.

Reads _source_1024.png + _source_1024_meta.json from scale_demo/, slices
the heightmap into 4x4 = 16 tiles of 256x256 px each, writes per-tile
heightmap + meta files. Also writes a world-level meta.json describing
the grid layout.

CRITICAL: all 16 tiles share the SAME elev_min and elev_range (the
world's). Each tile heightmap is re-quantized against the world range,
not its own local range. This is what guarantees seam continuity.

Re-merges the tiles and diffs against the source as a sanity check.

Output structure:
  worlds/scale_demo/
    meta.json                       (world-level)
    tiles/
      tile_0_0/heightmap.png + meta.json
      tile_0_1/heightmap.png + meta.json
      ... (16 total)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

W4_ROOT = Path("D:/assets/world 4/the world 4")
SCALE_DIR = W4_ROOT / "worlds" / "scale_demo"

TILE_SIZE_M = 256.0
TILE_PX_PER_M = 1  # base pixel density before upsample
GRID_N = 4  # 4x4 grid
WORLD_SIZE_M = TILE_SIZE_M * GRID_N  # 1024

# Gaussian smoothing sigma in pixels applied to the heightmap before slicing.
# USGS1m LiDAR DEMs carry visible flight-line scan striping (sub-meter elev
# oscillations parallel to the collection-flight direction) that's masked
# by real relief in high-feature areas (like the anchor's crop) but dominates
# the slope field in flatter regions. Lambertian shading on those striped
# normals produces dark/light banding in the rendered terrain. A small
# gaussian removes the noise while preserving real features down to ~2-3m
# scale. 0 = no smoothing (raw DEM data).
SMOOTH_SIGMA_PX = 1.0

# Upsample factor turned out NOT to help when mesh density divides
# evenly into heightmap density — vertices land at exact pixel positions
# regardless, and bilinear interpolation never engages. Disabled here;
# real smoothness comes from a larger SMOOTH_SIGMA_PX.
UPSAMPLE_FACTOR = 1


def main() -> int:
    src_png = SCALE_DIR / "_source_1024.png"
    src_meta_path = SCALE_DIR / "_source_1024_meta.json"
    if not src_png.exists() or not src_meta_path.exists():
        print(f"ERROR: source missing. Run pick_dem_crop_scale.py first.")
        return 1

    src_meta = json.loads(src_meta_path.read_text(encoding="utf-8"))
    elev_min = float(src_meta["elevation_min_m"])
    elev_range = float(src_meta["elevation_range_m"])
    elev_max = elev_min + elev_range

    # Read the source as raw 16-bit values. PIL may return mode "I;16" or
    # "I" (32-bit signed int container holding 16-bit data) depending on
    # version; both decode the same data, so just normalize via numpy.
    src_img = Image.open(str(src_png))
    if src_img.mode not in ("I;16", "I"):
        print(f"ERROR: source PNG not 16-bit, mode={src_img.mode}")
        return 1
    src_arr = np.asarray(src_img, dtype=np.int32).astype(np.uint16)
    if src_arr.shape != (1024, 1024):
        print(f"ERROR: source shape != (1024, 1024), got {src_arr.shape}")
        return 1

    print(f"[scale/slice] source: 1024x1024px, elev {elev_min:.1f}..{elev_max:.1f}m")

    if SMOOTH_SIGMA_PX > 0:
        # Smooth in float space then re-quantize. mode='nearest' avoids
        # darkening the edges.
        smoothed = gaussian_filter(src_arr.astype(np.float32), sigma=SMOOTH_SIGMA_PX, mode="nearest")
        src_arr = smoothed.clip(0, 65535).astype(np.uint16)
        print(f"  applied gaussian smooth sigma={SMOOTH_SIGMA_PX}px to suppress LiDAR scan-line noise")

    # Upsample for sub-pixel mesh-vertex height sampling. Bilinear upsample
    # in float space; result has 4× the pixels but every pixel-to-pixel
    # height delta is half as steep, so adjacent mesh vertices land on a
    # gradually-changing height field instead of discrete pixel steps.
    if UPSAMPLE_FACTOR > 1:
        upsampled_px = src_arr.shape[0] * UPSAMPLE_FACTOR
        src_img_f = Image.fromarray(src_arr.astype(np.float32), mode="F")
        src_img_f = src_img_f.resize((upsampled_px, upsampled_px), Image.Resampling.BILINEAR)
        src_arr = np.asarray(src_img_f, dtype=np.float32).clip(0, 65535).astype(np.uint16)
        print(f"  upsampled {UPSAMPLE_FACTOR}x to {upsampled_px}x{upsampled_px}px ({UPSAMPLE_FACTOR} px/m)")

    # Final heightmap dims (after smoothing + upsampling)
    world_px: int = src_arr.shape[0]
    tile_px: int = world_px // GRID_N

    # Write the world heightmap as a permanent artifact. Godot loads this
    # to do cross-tile height sampling (so finite-difference normals at
    # tile edges don't collapse against a clamped tile boundary).
    smoothed_path = SCALE_DIR / "world_heightmap.png"
    Image.fromarray(src_arr, mode="I;16").save(str(smoothed_path))
    print(f"  wrote world heightmap: {smoothed_path}  ({world_px}x{world_px})")

    tiles_dir = SCALE_DIR / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)

    # Slice into 4x4 tiles
    # tile_x = column index (world X axis), tile_z = row index (world Z axis)
    # Source array indexing: src_arr[row, col] = src_arr[z, x]
    n_tiles = 0
    for tile_z in range(GRID_N):
        for tile_x in range(GRID_N):
            x0 = tile_x * tile_px
            z0 = tile_z * tile_px
            tile_arr = src_arr[z0:z0 + tile_px, x0:x0 + tile_px]
            if tile_arr.shape != (tile_px, tile_px):
                print(f"ERROR: tile ({tile_x},{tile_z}) wrong shape {tile_arr.shape}")
                return 1

            tile_dir = tiles_dir / f"tile_{tile_x}_{tile_z}"
            tile_dir.mkdir(exist_ok=True)
            Image.fromarray(tile_arr, mode="I;16").save(str(tile_dir / "heightmap.png"))

            tile_meta = {
                "tile_x": tile_x,
                "tile_z": tile_z,
                "tile_size_m": TILE_SIZE_M,
                "heightmap_size_px": [tile_px, tile_px],
                # WORLD-shared range — every tile uses these same numbers.
                # This is what makes heights continuous across tile borders.
                "elevation_min_m": elev_min,
                "elevation_range_m": elev_range,
                "elevation_max_m": elev_max,
                # World position of this tile's (0,0) corner, with world
                # centered on origin: tile_x=0 sits at -512..−256 in world X.
                "world_origin_x_m": tile_x * TILE_SIZE_M - WORLD_SIZE_M * 0.5,
                "world_origin_z_m": tile_z * TILE_SIZE_M - WORLD_SIZE_M * 0.5,
            }
            (tile_dir / "meta.json").write_text(
                json.dumps(tile_meta, indent=2), encoding="utf-8")
            n_tiles += 1

    print(f"  wrote {n_tiles} tiles to {tiles_dir}")

    # Lossless slicing check: re-merge tiles and diff
    merged = np.zeros((world_px, world_px), dtype=np.uint16)
    for tile_z in range(GRID_N):
        for tile_x in range(GRID_N):
            tile_dir = tiles_dir / f"tile_{tile_x}_{tile_z}"
            tile_arr = np.asarray(Image.open(str(tile_dir / "heightmap.png")), dtype=np.uint16)
            x0 = tile_x * tile_px
            z0 = tile_z * tile_px
            merged[z0:z0 + tile_px, x0:x0 + tile_px] = tile_arr
    diff = (merged.astype(np.int32) - src_arr.astype(np.int32))
    max_diff = int(np.abs(diff).max())
    if max_diff != 0:
        print(f"ERROR: merge-back diff != 0, max={max_diff}")
        return 1
    print(f"  lossless check: PASS (max diff = 0)")

    # World meta
    world_meta = {
        "name": "scale_demo",
        "builder": "world 4/pipeline/slice_to_tiles.py",
        "version": 1,
        "source": src_meta["source"],
        "world_size_x_m": WORLD_SIZE_M,
        "world_size_z_m": WORLD_SIZE_M,
        "world_size_m": WORLD_SIZE_M,
        "grid_n": GRID_N,
        "tile_size_m": TILE_SIZE_M,
        "tile_size_px": tile_px,
        "upsample_factor": UPSAMPLE_FACTOR,
        "smooth_sigma_px": SMOOTH_SIGMA_PX,
        "elevation_min_m": elev_min,
        "elevation_max_m": elev_max,
        "elevation_range_m": elev_range,
    }
    world_meta_path = SCALE_DIR / "meta.json"
    world_meta_path.write_text(json.dumps(world_meta, indent=2), encoding="utf-8")
    print(f"  world meta: {world_meta_path}")

    print()
    print(f"[scale/slice] DONE")
    print(f"  {GRID_N}x{GRID_N}={n_tiles} tiles, each {tile_px}x{tile_px}px = {TILE_SIZE_M}m")
    print(f"  world: {WORLD_SIZE_M}m x {WORLD_SIZE_M}m")
    print(f"  elev shared across tiles: {elev_min:.1f}m to {elev_max:.1f}m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
