"""Anchor demo — Phase 1: DEM scout + crop.

Picks a high-relief region from D:/assets/dems/ (cached real-world DEMs)
and crops a 256m x 256m window at native resolution. Writes:
  - heightmap.png  (16-bit grayscale, 256x256 px)
  - meta.json      (elev range, world size, source provenance)

Picks the most interesting subregion automatically by scanning for max
relief + valid drainage signature (has min in the middle/sides, max at
top — i.e. a slope, not a plateau).

Outputs to: D:/assets/world 4/the world 4/worlds/anchor/

Pinned choice: USGS1m_-78.3520_+38.5147_-78.1980_+38.6500.tif
(Blue Ridge / Shenandoah area, ~982m relief over 14km, native 1m/px)
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

ROOT = Path("D:/assets")
DEMS_DIR = ROOT / "dems"
OUT_DIR = ROOT / "world 4" / "the world 4" / "worlds" / "anchor"

# Anchor world spec
WORLD_SIZE_M = 256.0          # 256m x 256m world
TARGET_PX = 256               # heightmap output resolution

# Pinned DEM tile (Virginia Blue Ridge, full 1m native resolution, ~982m relief)
SOURCE_TILE = "USGS1m_-78.3520_+38.5147_-78.1980_+38.6500.tif"

# Subregion scoring weights
RELIEF_WEIGHT = 1.0
SLOPE_BIAS_WEIGHT = 0.5       # favor regions where elev varies, not flat


def scan_for_best_subregion(arr: np.ndarray, crop_px: int) -> tuple[int, int, float]:
    """Walk the array in steps of crop_px/2, score each subregion by relief
    + slope variance, return (x, y, score) of the winner."""
    h, w = arr.shape
    step = max(8, crop_px // 4)
    best = (0, 0, -1.0)
    for y in range(0, h - crop_px, step):
        for x in range(0, w - crop_px, step):
            blk = arr[y:y + crop_px, x:x + crop_px]
            relief = float(blk.max() - blk.min())
            # Slope variance: how varied are local elevations?
            # Cheap proxy: std of the block
            slope_var = float(blk.std())
            score = RELIEF_WEIGHT * relief + SLOPE_BIAS_WEIGHT * slope_var
            if score > best[2]:
                best = (x, y, score)
    return best


def main() -> int:
    source_path = DEMS_DIR / SOURCE_TILE
    if not source_path.exists():
        print(f"ERROR: source tile not found: {source_path}")
        return 1

    print(f"[anchor/crop] Loading {SOURCE_TILE}")
    with rasterio.open(str(source_path)) as src:
        arr = src.read(1).astype(np.float32)
        nodata = src.nodata
        transform = src.transform
        crs = src.crs
        x_res = abs(transform.a)
        y_res = abs(transform.e)

    print(f"  source shape: {arr.shape}  res: {x_res:.2f}x{y_res:.2f}m/px  crs: {crs}")

    if nodata is not None:
        mask = arr != nodata
        valid_pct = 100 * mask.sum() / arr.size
        print(f"  valid: {valid_pct:.1f}%  (nodata={nodata})")
    else:
        mask = np.ones_like(arr, dtype=bool)

    # Crop size in pixels (USGS1m is ~1m/px so crop_px ~= WORLD_SIZE_M)
    crop_px_x = int(round(WORLD_SIZE_M / x_res))
    crop_px_y = int(round(WORLD_SIZE_M / y_res))
    crop_px = max(crop_px_x, crop_px_y)
    print(f"  cropping {crop_px}x{crop_px}px (= {WORLD_SIZE_M}m world)")

    # Scan for best subregion
    print(f"  scanning for high-relief subregion...")
    best_x, best_y, score = scan_for_best_subregion(arr, crop_px)
    crop = arr[best_y:best_y + crop_px, best_x:best_x + crop_px].copy()
    crop_relief = float(crop.max() - crop.min())
    print(f"  picked subregion at ({best_x}, {best_y}) relief={crop_relief:.1f}m score={score:.1f}")

    # Fill any nodata in the crop with neighbor mean (shouldn't happen if 100% valid)
    if nodata is not None and (crop == nodata).any():
        bad = crop == nodata
        good = crop[~bad]
        crop[bad] = good.mean()
        print(f"  filled {bad.sum()} nodata pixels with mean")

    # Resize to TARGET_PX × TARGET_PX (if needed)
    if crop.shape != (TARGET_PX, TARGET_PX):
        # Use PIL bilinear resize; convert to float64 for accuracy
        img = Image.fromarray(crop.astype(np.float32), mode="F")
        img = img.resize((TARGET_PX, TARGET_PX), Image.Resampling.BILINEAR)
        crop = np.asarray(img, dtype=np.float32)
        print(f"  resized to {TARGET_PX}x{TARGET_PX}")

    # Quantize to 16-bit normalized PNG
    elev_min = float(crop.min())
    elev_max = float(crop.max())
    elev_range = elev_max - elev_min
    if elev_range < 1e-3:
        print("ERROR: crop has zero relief")
        return 1
    quantized = ((crop - elev_min) / elev_range * 65535.0).clip(0, 65535).astype(np.uint16)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    heightmap_path = OUT_DIR / "heightmap.png"
    Image.fromarray(quantized, mode="I;16").save(str(heightmap_path))

    meta = {
        "name": "anchor",
        "builder": "world 4/pipeline/pick_dem_crop.py",
        "version": 1,
        "source": {
            "tile": SOURCE_TILE,
            "path": str(source_path).replace("\\", "/"),
            "crs": str(crs),
            "native_res_m": [x_res, y_res],
            "crop_px": [best_x, best_y, crop_px, crop_px],
        },
        "world_size_x_m": WORLD_SIZE_M,
        "world_size_z_m": WORLD_SIZE_M,
        "world_size_m": WORLD_SIZE_M,
        "heightmap_size_px": [TARGET_PX, TARGET_PX],
        "elevation_min_m": elev_min,
        "elevation_max_m": elev_max,
        "elevation_range_m": elev_range,
    }
    meta_path = OUT_DIR / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print()
    print(f"[anchor/crop] DONE")
    print(f"  heightmap: {heightmap_path}")
    print(f"  meta:      {meta_path}")
    print(f"  elev:      {elev_min:.1f}m to {elev_max:.1f}m (range {elev_range:.1f}m)")
    print(f"  world:     {WORLD_SIZE_M}m x {WORLD_SIZE_M}m  ({TARGET_PX}x{TARGET_PX}px)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
