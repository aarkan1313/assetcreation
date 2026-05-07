"""world3 build pipeline — DEM TIFF -> 16-bit heightmap PNG + meta.json.

One job, one source DEM, one output bundle. No state, no caching, no biomes.

Usage:
    python build_world.py <dem.tif> <out_dir> [--size 1024] [--material rock_dark]

Inputs:
    DEM    — single-band float32 GeoTIFF in meters (OpenTopography product).
    size   — target heightmap resolution (square). Default 1024.
    material — name of folder under world3/textures/ to bind. Default rock_dark.

Outputs (in <out_dir>):
    heightmap.png   16-bit grayscale, square, mip-friendly.
    meta.json       elevation range, mesh dimensions, source bbox, material id.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dem", type=Path, help="path to DEM GeoTIFF")
    ap.add_argument("out", type=Path, help="output dir for heightmap + meta")
    ap.add_argument("--size", type=int, default=1024, help="heightmap edge length px")
    ap.add_argument("--material", default="rock_dark", help="texture set name")
    ap.add_argument("--world-size-m", type=float, default=None,
                    help="override world XZ size in meters; default from DEM bounds")
    ap.add_argument("--bbox", type=float, nargs=4, default=None,
                    metavar=("LEFT", "BOTTOM", "RIGHT", "TOP"),
                    help="crop sub-window in lon/lat (EPSG:4326); cuts before resample")
    ap.add_argument("--center", type=float, nargs=2, default=None,
                    metavar=("LON", "LAT"),
                    help="crop centered here, used with --extent-km")
    ap.add_argument("--extent-km", type=float, default=None,
                    help="square crop edge length in kilometers (used with --center)")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.dem) as src:
        # Resolve crop bbox.
        crop_window = None
        bounds = src.bounds
        if args.bbox is not None:
            l, b, r, t = args.bbox
            crop_window = rasterio.windows.from_bounds(l, b, r, t, transform=src.transform)
        elif args.center is not None and args.extent_km is not None:
            lon, lat = args.center
            half_km = args.extent_km * 0.5
            half_deg_lat = half_km / 111.32
            half_deg_lon = half_km / (111.32 * float(np.cos(np.radians(lat))))
            l = lon - half_deg_lon; r = lon + half_deg_lon
            b = lat - half_deg_lat; t = lat + half_deg_lat
            crop_window = rasterio.windows.from_bounds(l, b, r, t, transform=src.transform)

        if crop_window is not None:
            elev = src.read(1, window=crop_window).astype(np.float32)
            wt = src.window_transform(crop_window)
            cb = rasterio.windows.bounds(crop_window, src.transform)
            from collections import namedtuple
            BB = namedtuple("BB", "left bottom right top")
            bounds = BB(*cb)
        else:
            elev = src.read(1).astype(np.float32)
        crs = str(src.crs)
        nodata = src.nodata
        is_geographic = bool(src.crs and src.crs.is_geographic)

    # Replace nodata / extreme negatives with the local minimum so we don't
    # blow up the dynamic range.
    finite = np.isfinite(elev)
    if nodata is not None and np.isfinite(nodata):
        finite &= elev != float(nodata)
    if not finite.any():
        raise SystemExit(f"No valid elevation pixels found in {args.dem}")
    if not finite.all():
        elev[~finite] = elev[finite].min()

    h_min = float(elev.min())
    h_max = float(elev.max())
    h_range = max(h_max - h_min, 1.0)

    # Resample to square `size` using PIL's high-quality LANCZOS in float space,
    # then quantize to 16-bit. (PIL's I;16 mode does not support LANCZOS directly.)
    norm = (elev - h_min) / h_range  # 0..1
    img_f = Image.fromarray(norm.astype(np.float32), mode="F")
    img_f = img_f.resize((args.size, args.size), Image.Resampling.LANCZOS)
    arr16 = (np.asarray(img_f, dtype=np.float32) * 65535.0).clip(0, 65535).astype(np.uint16)
    Image.fromarray(arr16, mode="I;16").save(args.out / "heightmap.png")

    # World XZ size in meters: rough geographic-degree -> meters at this lat.
    # 1 deg lat ≈ 111_320 m; 1 deg lon ≈ 111_320 * cos(lat).
    if args.world_size_m is None and is_geographic:
        lat_mid = (bounds.top + bounds.bottom) * 0.5
        dx_deg = bounds.right - bounds.left
        dy_deg = bounds.top - bounds.bottom
        meters_per_deg_lat = 111_320.0
        meters_per_deg_lon = 111_320.0 * np.cos(np.radians(lat_mid))
        size_x_m = float(dx_deg * meters_per_deg_lon)
        size_z_m = float(dy_deg * meters_per_deg_lat)
        # MVP: square XZ so the heightmap maps 1:1. Use the smaller axis.
        world_size_m = float(min(size_x_m, size_z_m))
    elif args.world_size_m is None:
        world_size_m = float(min(abs(bounds.right - bounds.left), abs(bounds.top - bounds.bottom)))
    else:
        world_size_m = float(args.world_size_m)

    meta = {
        "source_dem": str(args.dem),
        "source_crs": crs,
        "source_bounds": {
            "left": bounds.left, "right": bounds.right,
            "bottom": bounds.bottom, "top": bounds.top,
        },
        "heightmap_size_px": args.size,
        "elevation_min_m": h_min,
        "elevation_max_m": h_max,
        "elevation_range_m": h_range,
        "world_size_m": world_size_m,
        "material": args.material,
    }
    (args.out / "meta.json").write_text(json.dumps(meta, indent=2))

    print(f"OK heightmap.png ({args.size}x{args.size} u16) elev {h_min:.0f}..{h_max:.0f}m "
          f"world {world_size_m:.0f}m material={args.material}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
