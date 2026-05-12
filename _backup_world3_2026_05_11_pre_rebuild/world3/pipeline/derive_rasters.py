"""Generate basic derived rasters from a single-band elevation GeoTIFF.

Outputs:
    hillshade.tif  uint8, 0..255
    slope_deg.tif  float32 degrees
    roughness.tif  float32 local 3x3 max-min

Usage:
    python derive_rasters.py <input.tif> <output_dir>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio


def cellsize_m(src: rasterio.DatasetReader) -> tuple[float, float]:
    transform = src.transform
    dx = abs(transform.a)
    dy = abs(transform.e)
    if src.crs and src.crs.is_geographic:
        lat_mid = (src.bounds.top + src.bounds.bottom) * 0.5
        meters_per_deg_lat = 111_320.0
        meters_per_deg_lon = 111_320.0 * np.cos(np.radians(lat_mid))
        return dx * meters_per_deg_lon, dy * meters_per_deg_lat
    return dx, dy


def local_roughness(elev: np.ndarray) -> np.ndarray:
    padded = np.pad(elev, 1, mode="edge")
    windows = []
    for y in range(3):
        for x in range(3):
            windows.append(padded[y:y + elev.shape[0], x:x + elev.shape[1]])
    stack = np.stack(windows)
    return stack.max(axis=0) - stack.min(axis=0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.input) as src:
        elev = src.read(1, masked=True).astype("float32")
        profile = src.profile.copy()
        dx, dy = cellsize_m(src)

    fill_value = float(elev.mean()) if np.ma.is_masked(elev) else float(np.nanmean(elev))
    arr = np.asarray(elev.filled(fill_value), dtype=np.float32)
    dzdy, dzdx = np.gradient(arr, dy, dx)
    slope_rad = np.arctan(np.sqrt(dzdx * dzdx + dzdy * dzdy))
    slope_deg = np.degrees(slope_rad).astype(np.float32)

    azimuth = np.radians(315.0)
    altitude = np.radians(45.0)
    aspect = np.arctan2(dzdy, -dzdx)
    shaded = (
        np.sin(altitude) * np.cos(slope_rad)
        + np.cos(altitude) * np.sin(slope_rad) * np.cos(azimuth - aspect)
    )
    hillshade = (np.clip(shaded, 0.0, 1.0) * 255.0).astype(np.uint8)
    roughness = local_roughness(arr).astype(np.float32)

    base_profile = profile.copy()
    base_profile.update(driver="GTiff", count=1, compress="deflate", tiled=True)
    # Some source rasters carry odd block sizes; GeoTIFF tile blocks must be
    # multiples of 16.
    base_profile.pop("blockxsize", None)
    base_profile.pop("blockysize", None)
    base_profile.update(blockxsize=256, blockysize=256)

    hs_profile = base_profile.copy()
    hs_profile.update(dtype="uint8", nodata=None)
    with rasterio.open(args.output / "hillshade.tif", "w", **hs_profile) as dst:
        dst.write(hillshade, 1)

    f_profile = base_profile.copy()
    f_profile.update(dtype="float32", nodata=None)
    with rasterio.open(args.output / "slope_deg.tif", "w", **f_profile) as dst:
        dst.write(slope_deg, 1)
    with rasterio.open(args.output / "roughness.tif", "w", **f_profile) as dst:
        dst.write(roughness, 1)

    print(
        f"OK {args.output} slope={float(slope_deg.min()):.2f}..{float(slope_deg.max()):.2f} "
        f"rough={float(roughness.min()):.2f}..{float(roughness.max()):.2f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
