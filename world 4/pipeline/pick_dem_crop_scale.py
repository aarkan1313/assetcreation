"""Scale demo — Phase 1a: DEM scout + crop for 1024m region.

Picks the highest-relief 1024m x 1024m region from the same Blue Ridge USGS
tile the anchor uses. Writes a 1024x1024 px heightmap (1m/px) + world meta.

This is the input to slice_to_tiles.py which will cut it into 16 tiles.

Output: D:/assets/world 4/the world 4/worlds/scale_demo/_source_1024.png
        D:/assets/world 4/the world 4/worlds/scale_demo/_source_1024_meta.json

(Underscore prefix = intermediate artifact, not the final per-tile data.)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

ROOT = Path("D:/assets")
DEMS_DIR = ROOT / "dems"
OUT_DIR = ROOT / "world 4" / "the world 4" / "worlds" / "scale_demo"

WORLD_SIZE_M = 1024.0
TARGET_PX = 1024

SOURCE_TILE = "USGS1m_-78.3520_+38.5147_-78.1980_+38.6500.tif"

RELIEF_WEIGHT = 1.0
SLOPE_BIAS_WEIGHT = 0.5
# Penalty for directional ridging (striated terrain). Some USGS1m crops
# show baked-in contour-parallel ridging that renders as terraces — either
# real geology or a hillshade-bake-into-elevation processing artifact.
# An FFT of the crop reveals a strong directional component when present;
# we measure ridging as the ratio between the dominant directional band's
# power and the average non-DC power. Lower = more isotropic = better.
#
# Set to 0 to disable the penalty (and reproduce the original striated
# crop at 1280, 5888 for diagnostic work).
RIDGE_PENALTY_WEIGHT = 1500.0
ALLOW_RIDGED_OVERRIDE = True
RIDGED_OVERRIDE_XY = (1280, 5888)  # the original striated crop


def directional_anisotropy(blk: np.ndarray) -> float:
    """Return a score in [0..1] where higher = more striated/anisotropic.
    Computes the 2D FFT of the (mean-subtracted) crop and measures the
    ratio between the strongest directional band power and the average
    power. Isotropic terrain ~ 0.15; strongly ridged terrain ~ 0.4+."""
    # Downsample for speed on a 1024px crop
    s = blk[::4, ::4].astype(np.float64)
    s = s - s.mean()
    f = np.fft.fftshift(np.fft.fft2(s))
    p = np.abs(f) ** 2
    h, w = p.shape
    cy, cx = h // 2, w // 2
    # Mask out DC and very-low-frequency content
    yy, xx = np.indices(p.shape)
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    band = (r > 4) & (r < min(h, w) // 3)
    if band.sum() == 0:
        return 0.0
    # Compute angular histogram (16 bins, 0..pi). For each pixel in the
    # band, its angle determines which bin its power lands in.
    ang = np.arctan2(yy - cy, xx - cx) % np.pi
    bins = (ang / np.pi * 16).astype(np.int32).clip(0, 15)
    bin_power = np.zeros(16, dtype=np.float64)
    for b in range(16):
        m = band & (bins == b)
        if m.any():
            bin_power[b] = p[m].mean()
    if bin_power.max() == 0:
        return 0.0
    return float((bin_power.max() - bin_power.mean()) / bin_power.max())


def scan_for_best_subregion(arr: np.ndarray, crop_px: int) -> tuple[int, int, float]:
    h, w = arr.shape
    step = max(16, crop_px // 4)
    best = (0, 0, -1e9)
    for y in range(0, h - crop_px, step):
        for x in range(0, w - crop_px, step):
            blk = arr[y:y + crop_px, x:x + crop_px]
            relief = float(blk.max() - blk.min())
            slope_var = float(blk.std())
            ridge = directional_anisotropy(blk)
            score = (RELIEF_WEIGHT * relief
                     + SLOPE_BIAS_WEIGHT * slope_var
                     - RIDGE_PENALTY_WEIGHT * ridge)
            if score > best[2]:
                best = (x, y, score)
    return best


def main() -> int:
    source_path = DEMS_DIR / SOURCE_TILE
    if not source_path.exists():
        print(f"ERROR: source tile not found: {source_path}")
        return 1

    print(f"[scale/crop] Loading {SOURCE_TILE}")
    with rasterio.open(str(source_path)) as src:
        arr = src.read(1).astype(np.float32)
        nodata = src.nodata
        transform = src.transform
        crs = src.crs
        x_res = abs(transform.a)
        y_res = abs(transform.e)

    print(f"  source shape: {arr.shape}  res: {x_res:.2f}x{y_res:.2f}m/px")

    crop_px_x = int(round(WORLD_SIZE_M / x_res))
    crop_px_y = int(round(WORLD_SIZE_M / y_res))
    crop_px = max(crop_px_x, crop_px_y)
    print(f"  cropping {crop_px}x{crop_px}px (= {WORLD_SIZE_M}m world)")

    if ALLOW_RIDGED_OVERRIDE:
        best_x, best_y = RIDGED_OVERRIDE_XY
        score = 0.0
        print(f"  USING RIDGED OVERRIDE: forcing crop at ({best_x}, {best_y}) — original striated region for diagnostic work")
    else:
        print(f"  scanning for high-relief subregion...")
        best_x, best_y, score = scan_for_best_subregion(arr, crop_px)
    crop = arr[best_y:best_y + crop_px, best_x:best_x + crop_px].copy()
    crop_relief = float(crop.max() - crop.min())
    print(f"  picked subregion at ({best_x}, {best_y}) relief={crop_relief:.1f}m score={score:.1f}")

    if nodata is not None and (crop == nodata).any():
        bad = crop == nodata
        good = crop[~bad]
        crop[bad] = good.mean()
        print(f"  filled {bad.sum()} nodata pixels with mean")

    if crop.shape != (TARGET_PX, TARGET_PX):
        img = Image.fromarray(crop.astype(np.float32), mode="F")
        img = img.resize((TARGET_PX, TARGET_PX), Image.Resampling.BILINEAR)
        crop = np.asarray(img, dtype=np.float32)
        print(f"  resized to {TARGET_PX}x{TARGET_PX}")

    elev_min = float(crop.min())
    elev_max = float(crop.max())
    elev_range = elev_max - elev_min
    if elev_range < 1e-3:
        print("ERROR: crop has zero relief")
        return 1
    quantized = ((crop - elev_min) / elev_range * 65535.0).clip(0, 65535).astype(np.uint16)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    heightmap_path = OUT_DIR / "_source_1024.png"
    Image.fromarray(quantized, mode="I;16").save(str(heightmap_path))

    meta = {
        "name": "scale_demo_source",
        "builder": "world 4/pipeline/pick_dem_crop_scale.py",
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
    meta_path = OUT_DIR / "_source_1024_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print()
    print(f"[scale/crop] DONE")
    print(f"  heightmap: {heightmap_path}")
    print(f"  meta:      {meta_path}")
    print(f"  elev:      {elev_min:.1f}m to {elev_max:.1f}m (range {elev_range:.1f}m)")
    print(f"  world:     {WORLD_SIZE_M}m x {WORLD_SIZE_M}m  ({TARGET_PX}x{TARGET_PX}px)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
