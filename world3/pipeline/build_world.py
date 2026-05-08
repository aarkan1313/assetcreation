"""world3 build pipeline — DEM TIFF -> 16-bit heightmap PNG + meta.json.

One job, one source DEM, one output bundle. No state, no caching, no biomes.

Usage:
    python build_world.py <dem.tif> <out_dir> [--size 1024] [--material rock_dark]

Inputs:
    DEM    — single-band float32 GeoTIFF in meters (OpenTopography product).
    size   — target heightmap resolution (square). Default 1024.
    material — name of folder under world3/textures/ to bind. Default rock_dark.

Outputs (in <out_dir>):
    heightmap.png   16-bit grayscale, square, mip-friendly render heightmap.
    meta.json       elevation range, mesh dimensions, source bbox, material id.
    layers/source_valid_mask.png   original source-valid pixels.
    layers/render_fill_mask.png    pixels repaired for render height.
    layers/render_fill_buffer.png  softened buffer around repaired pixels.
    layers/cliff_mask.png          slope mask for cliff/material blending.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageFilter
from rasterio.fill import fillnodata

try:
    from scipy import ndimage
except Exception:  # pragma: no cover - optional fallback
    ndimage = None


def quantize_height(elev: np.ndarray, h_min: float, h_range: float, size: int) -> np.ndarray:
    norm = (elev - h_min) / h_range
    img_f = Image.fromarray(norm.astype(np.float32), mode="F")
    img_f = img_f.resize((size, size), Image.Resampling.LANCZOS)
    return (np.asarray(img_f, dtype=np.float32) * 65535.0).clip(0, 65535).astype(np.uint16)


def save_mask_layer(mask: np.ndarray, path: Path, size: int, sidecar: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = (mask.astype(np.uint8) * 255)
    img = Image.fromarray(arr, mode="L")
    if img.size != (size, size):
        img = img.resize((size, size), Image.Resampling.NEAREST)
    img.save(path)
    sidecar = dict(sidecar)
    sidecar.update({
        "output": str(path),
        "size": [size, size],
        "valid_pixels": int(np.count_nonzero(mask)),
    })
    path.with_suffix(path.suffix + ".json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")


def save_weight_layer(weight: np.ndarray, path: Path, size: int, sidecar: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = (weight.clip(0.0, 1.0) * 255.0).astype(np.uint8)
    img = Image.fromarray(arr, mode="L")
    if img.size != (size, size):
        img = img.resize((size, size), Image.Resampling.BILINEAR)
    img.save(path)
    sidecar = dict(sidecar)
    sidecar.update({
        "output": str(path),
        "size": [size, size],
        "nonzero_pixels": int(np.count_nonzero(arr)),
    })
    path.with_suffix(path.suffix + ".json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")


def dilate_mask(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0 or not mask.any():
        return mask.copy()
    size = radius * 2 + 1
    img = Image.fromarray(mask.astype(np.uint8) * 255, mode="L")
    img = img.filter(ImageFilter.MaxFilter(size))
    return np.asarray(img) > 0


def repair_nodata(
    elev: np.ndarray,
    valid: np.ndarray,
    max_search_distance: float,
    smoothing_iterations: int,
) -> tuple[np.ndarray, dict]:
    repaired = elev.copy()
    invalid = ~valid
    valid_values = elev[valid]
    report = {
        "method": "none",
        "source_valid_pixels": int(valid.sum()),
        "source_invalid_pixels": int(invalid.sum()),
        "fill_pixels": int(invalid.sum()),
        "fill_max_search_distance_px": float(max_search_distance),
        "fill_smoothing_iterations": int(smoothing_iterations),
        "fallback": None,
    }
    if not invalid.any():
        return repaired, report

    valid_min = float(valid_values.min())
    valid_max = float(valid_values.max())
    work = repaired.copy()
    work[invalid] = valid_min
    filled = fillnodata(
        work,
        mask=valid.astype(np.uint8),
        max_search_distance=max_search_distance,
        smoothing_iterations=smoothing_iterations,
    ).astype(np.float32)
    repaired[invalid] = filled[invalid]
    report["method"] = "rasterio.fill.fillnodata"

    # If fillnodata leaves values outside the valid source range, fall back to a
    # nearest-valid seed for those pixels. This avoids artificial pits/curtains.
    bad = ~np.isfinite(repaired)
    invalid_values = repaired[invalid]
    if invalid_values.size:
        invalid_bad = (invalid_values < valid_min) | (invalid_values > valid_max)
        if invalid_bad.any():
            bad_invalid = np.zeros_like(invalid, dtype=bool)
            bad_invalid[invalid] = invalid_bad
            bad |= bad_invalid
    if bad.any():
        if ndimage is not None:
            indices = ndimage.distance_transform_edt(invalid, return_distances=False, return_indices=True)
            nearest = elev[tuple(indices)]
            repaired[bad] = nearest[bad]
            report["fallback"] = "scipy.ndimage.distance_transform_edt nearest valid"
        else:
            repaired[bad] = float(np.median(valid_values))
            report["fallback"] = "median valid elevation"

    # Smooth only repaired pixels, and restore original valid source elevations
    # after each pass. This softens fill patches without changing real data.
    if smoothing_iterations > 0 and ndimage is not None:
        for _ in range(smoothing_iterations):
            blurred = ndimage.gaussian_filter(repaired, sigma=1.0)
            repaired[invalid] = blurred[invalid]
            repaired[valid] = elev[valid]
        report["post_smoothing"] = "gaussian sigma=1 on repaired pixels only"

    return repaired.astype(np.float32), report


def cell_sizes_m(transform, crs, bounds) -> tuple[float, float]:
    if crs and crs.is_geographic:
        lat_mid = (bounds.top + bounds.bottom) * 0.5
        meters_per_deg_lat = 111_320.0
        meters_per_deg_lon = 111_320.0 * np.cos(np.radians(lat_mid))
        return abs(transform.a) * meters_per_deg_lon, abs(transform.e) * meters_per_deg_lat
    return abs(transform.a), abs(transform.e)


def slope_degrees(elev: np.ndarray, cell_x_m: float, cell_y_m: float) -> np.ndarray:
    gy, gx = np.gradient(elev.astype(np.float32), cell_y_m, cell_x_m)
    return np.degrees(np.arctan(np.sqrt(gx * gx + gy * gy))).astype(np.float32)


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
    ap.add_argument("--no-repair-nodata", action="store_true",
                    help="preserve old behavior by replacing invalid cells with source min")
    ap.add_argument("--fill-max-search-distance", type=float, default=2048.0,
                    help="max pixel search distance for render no-data fill")
    ap.add_argument("--fill-smoothing-iterations", type=int, default=2,
                    help="smoothing passes for repaired pixels only")
    ap.add_argument("--repair-buffer-px", type=int, default=12,
                    help="source-pixel dilation radius for render_fill_buffer mask")
    ap.add_argument("--cliff-start-deg", type=float, default=35.0,
                    help="slope angle where cliff mask begins")
    ap.add_argument("--cliff-full-deg", type=float, default=55.0,
                    help="slope angle where cliff mask reaches full weight")
    ap.add_argument("--invalid-below", type=float, default=None,
                    help="optional source elevation lower sanity cutoff")
    ap.add_argument("--invalid-above", type=float, default=None,
                    help="optional source elevation upper sanity cutoff")
    ap.add_argument("--no-repair-layers", action="store_true",
                    help="do not write source_valid/fill/cliff mask layers")
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
            wt = src.transform
        crs = str(src.crs)
        crs_obj = src.crs
        nodata = src.nodata
        is_geographic = bool(src.crs and src.crs.is_geographic)

    # Build a source-valid mask before any render repair. This mask is preserved
    # as a layer so downstream scenes know which pixels are real measurements.
    valid = np.isfinite(elev)
    if nodata is not None and np.isfinite(nodata):
        valid &= elev != float(nodata)
    if args.invalid_below is not None:
        valid &= elev >= float(args.invalid_below)
    if args.invalid_above is not None:
        valid &= elev <= float(args.invalid_above)
    if not valid.any():
        raise SystemExit(f"No valid elevation pixels found in {args.dem}")
    source_valid = valid.copy()
    source_invalid = ~source_valid
    raw_valid_min = float(elev[source_valid].min())
    raw_valid_max = float(elev[source_valid].max())

    if args.no_repair_nodata:
        elev = elev.copy()
        elev[source_invalid] = raw_valid_min
        repair_report = {
            "method": "legacy_min_fill",
            "source_valid_pixels": int(source_valid.sum()),
            "source_invalid_pixels": int(source_invalid.sum()),
            "fill_pixels": int(source_invalid.sum()),
        }
    else:
        elev, repair_report = repair_nodata(
            elev,
            source_valid,
            max_search_distance=args.fill_max_search_distance,
            smoothing_iterations=args.fill_smoothing_iterations,
        )

    h_min = float(elev.min())
    h_max = float(elev.max())
    h_range = max(h_max - h_min, 1.0)

    # Resample to square `size` using PIL's high-quality LANCZOS in float space,
    # then quantize to 16-bit. (PIL's I;16 mode does not support LANCZOS directly.)
    arr16 = quantize_height(elev, h_min, h_range, args.size)
    Image.fromarray(arr16, mode="I;16").save(args.out / "heightmap.png")

    cell_x_m, cell_y_m = cell_sizes_m(wt, crs_obj, bounds)
    slope = slope_degrees(elev, cell_x_m, cell_y_m)
    denom = max(args.cliff_full_deg - args.cliff_start_deg, 0.001)
    cliff_weight = ((slope - args.cliff_start_deg) / denom).clip(0.0, 1.0)
    fill_buffer = dilate_mask(source_invalid, args.repair_buffer_px)
    if not args.no_repair_layers:
        layer_dir = args.out / "layers"
        base_sidecar = {
            "input": str(args.dem),
            "source_bounds": {
                "left": bounds.left, "right": bounds.right,
                "bottom": bounds.bottom, "top": bounds.top,
            },
            "source_shape": [int(elev.shape[1]), int(elev.shape[0])],
        }
        save_mask_layer(source_valid, layer_dir / "source_valid_mask.png", args.size, {
            **base_sidecar,
            "kind": "source_valid_mask",
            "description": "255 where the source DEM had valid original data before render repair.",
        })
        save_mask_layer(source_invalid, layer_dir / "render_fill_mask.png", args.size, {
            **base_sidecar,
            "kind": "render_fill_mask",
            "description": "255 where height was procedurally repaired for render use.",
        })
        save_mask_layer(fill_buffer, layer_dir / "render_fill_buffer.png", args.size, {
            **base_sidecar,
            "kind": "render_fill_buffer",
            "description": "Dilated render fill mask for material blending around repaired pixels.",
            "buffer_px_source": int(args.repair_buffer_px),
        })
        save_weight_layer(cliff_weight, layer_dir / "cliff_mask.png", args.size, {
            **base_sidecar,
            "kind": "cliff_mask",
            "description": "0..255 slope-derived mask for blending away from top-down orthophoto on steep terrain.",
            "cliff_start_deg": float(args.cliff_start_deg),
            "cliff_full_deg": float(args.cliff_full_deg),
            "source_slope_max_deg": float(np.nanmax(slope)),
        })

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
        "raw_valid_elevation_min_m": raw_valid_min,
        "raw_valid_elevation_max_m": raw_valid_max,
        "world_size_m": world_size_m,
        "material": args.material,
        "nodata_repair": repair_report,
        "render_masks": {
            "source_valid_mask": "layers/source_valid_mask.png",
            "render_fill_mask": "layers/render_fill_mask.png",
            "render_fill_buffer": "layers/render_fill_buffer.png",
            "cliff_mask": "layers/cliff_mask.png",
        } if not args.no_repair_layers else {},
    }
    (args.out / "meta.json").write_text(json.dumps(meta, indent=2))

    print(f"OK heightmap.png ({args.size}x{args.size} u16) elev {h_min:.0f}..{h_max:.0f}m "
          f"world {world_size_m:.0f}m material={args.material}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
