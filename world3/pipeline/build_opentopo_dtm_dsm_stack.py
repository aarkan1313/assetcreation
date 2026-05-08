"""Build a Godot-ready OpenTopo stack from matched DTM and DSM rasters.

The stack uses DTM as terrain height and DSM-DTM as a surface-height signal for
forest/canopy/material masks. It intentionally does not require real color.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image, ImageFilter
from rasterio.fill import fillnodata
from rasterio.warp import Resampling, reproject

try:
    from scipy import ndimage
except Exception:  # pragma: no cover - optional fallback
    ndimage = None


@dataclass
class Raster:
    arr: np.ndarray
    valid: np.ndarray
    transform: Any
    crs: Any
    bounds: Any
    nodata: float | None
    path: Path


def read_primary(path: Path) -> Raster:
    with rasterio.open(path) as src:
        arr = src.read(1).astype(np.float32)
        valid = np.isfinite(arr)
        if src.nodata is not None and np.isfinite(src.nodata):
            valid &= arr != float(src.nodata)
        return Raster(
            arr=arr,
            valid=valid,
            transform=src.transform,
            crs=src.crs,
            bounds=src.bounds,
            nodata=float(src.nodata) if src.nodata is not None else None,
            path=path,
        )


def read_aligned(path: Path, reference: Raster) -> Raster:
    with rasterio.open(path) as src:
        same_grid = (
            src.shape == reference.arr.shape
            and src.crs == reference.crs
            and src.transform.almost_equals(reference.transform)
        )
        if same_grid:
            arr = src.read(1).astype(np.float32)
        else:
            arr = np.full(reference.arr.shape, np.nan, dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=arr,
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=src.nodata,
                dst_transform=reference.transform,
                dst_crs=reference.crs,
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
        nodata = float(src.nodata) if src.nodata is not None else None
    valid = np.isfinite(arr)
    if nodata is not None and np.isfinite(nodata):
        valid &= arr != nodata
    return Raster(
        arr=arr,
        valid=valid,
        transform=reference.transform,
        crs=reference.crs,
        bounds=reference.bounds,
        nodata=nodata,
        path=path,
    )


def repair_nodata(arr: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    invalid = ~valid
    report: dict[str, Any] = {
        "method": "none",
        "source_valid_pixels": int(valid.sum()),
        "source_invalid_pixels": int(invalid.sum()),
        "fill_pixels": int(invalid.sum()),
    }
    if not invalid.any():
        return arr.astype(np.float32), report
    if not valid.any():
        raise ValueError("Cannot repair raster with no valid cells")

    valid_values = arr[valid]
    work = arr.copy()
    work[invalid] = float(np.nanmedian(valid_values))
    filled = fillnodata(work, mask=valid.astype(np.uint8), max_search_distance=2048.0, smoothing_iterations=2)
    repaired = arr.copy()
    repaired[invalid] = filled[invalid]
    bad = ~np.isfinite(repaired)
    if bad.any() and ndimage is not None:
        indices = ndimage.distance_transform_edt(invalid, return_distances=False, return_indices=True)
        nearest = arr[tuple(indices)]
        repaired[bad] = nearest[bad]
        report["fallback"] = "nearest_valid"
    elif bad.any():
        repaired[bad] = float(np.nanmedian(valid_values))
        report["fallback"] = "median_valid"
    report["method"] = "rasterio.fill.fillnodata"
    return repaired.astype(np.float32), report


def resize_float(values: np.ndarray, size: int, resampling: Image.Resampling = Image.Resampling.LANCZOS) -> np.ndarray:
    img = Image.fromarray(values.astype(np.float32), mode="F")
    if img.size != (size, size):
        img = img.resize((size, size), resampling)
    return np.asarray(img, dtype=np.float32)


def save_gray(values: np.ndarray, path: Path, size: int, low: float = 2.0, high: float = 98.0) -> tuple[float, float]:
    finite = np.isfinite(values)
    if finite.any():
        lo, hi = np.nanpercentile(values[finite], [low, high])
        if not np.isfinite(lo):
            lo = float(values[finite].min())
        if not np.isfinite(hi) or hi <= lo:
            hi = lo + 1.0
    else:
        lo, hi = 0.0, 1.0
    scaled = np.clip((values - float(lo)) / float(hi - lo), 0.0, 1.0)
    out = resize_float(scaled, size, Image.Resampling.BILINEAR)
    Image.fromarray((out * 255.0).clip(0, 255).astype(np.uint8), mode="L").save(path)
    return float(lo), float(hi)


def save_unit(values: np.ndarray, path: Path, size: int, resampling: Image.Resampling = Image.Resampling.BILINEAR) -> None:
    out = resize_float(np.clip(values, 0.0, 1.0), size, resampling)
    Image.fromarray((out * 255.0).clip(0, 255).astype(np.uint8), mode="L").save(path)


def save_mask(mask: np.ndarray, path: Path, size: int) -> None:
    img = Image.fromarray(mask.astype(np.uint8) * 255, mode="L")
    if img.size != (size, size):
        img = img.resize((size, size), Image.Resampling.NEAREST)
    img.save(path)


def cell_sizes_m(raster: Raster) -> tuple[float, float]:
    if raster.crs and raster.crs.is_geographic:
        lat_mid = (raster.bounds.top + raster.bounds.bottom) * 0.5
        meters_per_deg_lat = 111_320.0
        meters_per_deg_lon = 111_320.0 * np.cos(np.radians(lat_mid))
        return abs(raster.transform.a) * meters_per_deg_lon, abs(raster.transform.e) * meters_per_deg_lat
    return abs(raster.transform.a), abs(raster.transform.e)


def world_sizes_m(raster: Raster) -> tuple[float, float]:
    if raster.crs and raster.crs.is_geographic:
        lat_mid = (raster.bounds.top + raster.bounds.bottom) * 0.5
        meters_per_deg_lat = 111_320.0
        meters_per_deg_lon = 111_320.0 * np.cos(np.radians(lat_mid))
        return (
            float((raster.bounds.right - raster.bounds.left) * meters_per_deg_lon),
            float((raster.bounds.top - raster.bounds.bottom) * meters_per_deg_lat),
        )
    return float(raster.bounds.right - raster.bounds.left), float(raster.bounds.top - raster.bounds.bottom)


def slope_hillshade_roughness(elev: np.ndarray, cell_x: float, cell_y: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    gy, gx = np.gradient(elev.astype(np.float32), cell_y, cell_x)
    slope_rad = np.arctan(np.sqrt(gx * gx + gy * gy))
    slope_deg = np.degrees(slope_rad).astype(np.float32)
    aspect = np.arctan2(-gx, gy)
    azimuth = np.deg2rad(315.0)
    altitude = np.deg2rad(45.0)
    shaded = (
        np.sin(altitude) * np.cos(slope_rad)
        + np.cos(altitude) * np.sin(slope_rad) * np.cos(azimuth - aspect)
    )
    hillshade = np.clip(shaded, 0.0, 1.0).astype(np.float32)
    slope_y, slope_x = np.gradient(slope_deg, cell_y, cell_x)
    roughness = np.sqrt(slope_x * slope_x + slope_y * slope_y).astype(np.float32)
    return slope_deg, hillshade, roughness


def normalize_percentile(values: np.ndarray, low: float = 2.0, high: float = 98.0) -> np.ndarray:
    finite = np.isfinite(values)
    if not finite.any():
        return np.zeros(values.shape, dtype=np.float32)
    lo, hi = np.nanpercentile(values[finite], [low, high])
    if not np.isfinite(hi) or hi <= lo:
        hi = lo + 1.0
    return np.clip((values.astype(np.float32) - float(lo)) / float(hi - lo), 0.0, 1.0)


def ramp_color(values: np.ndarray, ramp: np.ndarray) -> np.ndarray:
    values = np.clip(values, 0.0, 1.0)
    pos = values * (len(ramp) - 1)
    lo = np.floor(pos).astype(np.int32)
    hi = np.clip(lo + 1, 0, len(ramp) - 1)
    t = (pos - lo)[..., None]
    return ramp[lo] * (1.0 - t) + ramp[hi] * t


def make_terrain_texture(
    elev_norm: np.ndarray,
    hillshade: np.ndarray,
    slope_deg: np.ndarray,
    rough_norm: np.ndarray,
    surface_norm: np.ndarray,
    wetness: np.ndarray,
    size: int,
) -> np.ndarray:
    elev = resize_float(elev_norm, size, Image.Resampling.BILINEAR)
    shade = resize_float(hillshade, size, Image.Resampling.BILINEAR)
    slope = resize_float(slope_deg / 70.0, size, Image.Resampling.BILINEAR)
    rough = resize_float(rough_norm, size, Image.Resampling.BILINEAR)
    surface = resize_float(surface_norm, size, Image.Resampling.BILINEAR)
    wet = resize_float(wetness, size, Image.Resampling.BILINEAR)

    ramp = np.array(
        [
            [34, 55, 45],
            [45, 78, 51],
            [68, 95, 59],
            [103, 112, 78],
            [128, 126, 96],
            [128, 132, 123],
            [178, 184, 176],
            [224, 226, 216],
        ],
        dtype=np.float32,
    ) / 255.0
    color = ramp_color(elev, ramp)

    forest = np.clip(np.sqrt(surface), 0.0, 1.0)
    rock = np.clip((slope - 0.42) / 0.40, 0.0, 1.0) ** 1.15
    high_alpine = np.clip((elev - 0.78) / 0.18, 0.0, 1.0)
    forest_color = np.array([0.10, 0.24, 0.15], dtype=np.float32)
    rock_color = np.array([0.47, 0.49, 0.46], dtype=np.float32)
    wet_color = np.array([0.08, 0.20, 0.19], dtype=np.float32)
    snow_rock = np.array([0.76, 0.78, 0.74], dtype=np.float32)

    color = color * (1.0 - wet[..., None] * 0.18) + wet_color * wet[..., None] * 0.18
    color = color * (1.0 - forest[..., None] * 0.42) + forest_color * forest[..., None] * 0.42
    color = color * (1.0 - rock[..., None] * 0.50) + rock_color * rock[..., None] * 0.50
    color = color * (1.0 - high_alpine[..., None] * 0.30) + snow_rock * high_alpine[..., None] * 0.30

    shade_factor = 0.52 + shade[..., None] * 0.72
    micro = (rough - 0.5)[..., None] * 0.10
    return np.clip(color * shade_factor + micro, 0.0, 1.0)


def stats(values: np.ndarray, valid: np.ndarray | None = None) -> dict[str, float | int]:
    mask = np.isfinite(values)
    if valid is not None:
        mask &= valid
    if not mask.any():
        return {"valid": 0}
    data = values[mask]
    return {
        "valid": int(data.size),
        "min": round(float(data.min()), 3),
        "max": round(float(data.max()), 3),
        "mean": round(float(data.mean()), 3),
        "p05": round(float(np.percentile(data, 5)), 3),
        "p95": round(float(np.percentile(data, 95)), 3),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dtm", required=True, type=Path, help="bare-earth DTM GeoTIFF")
    ap.add_argument("--dsm", required=True, type=Path, help="surface DSM GeoTIFF")
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--name", default="OpenTopo DTM/DSM Stack")
    ap.add_argument("--size", type=int, default=4096, help="square Godot heightmap/layer export size")
    ap.add_argument("--surface-max-m", type=float, default=45.0, help="surface-height value that maps to white")
    args = ap.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    layers_dir = args.output_dir / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)

    dtm = read_primary(args.dtm)
    dsm = read_aligned(args.dsm, dtm)
    source_valid = dtm.valid.copy()
    surface_valid = dtm.valid & dsm.valid
    dtm_repaired, repair_report = repair_nodata(dtm.arr, dtm.valid)
    dsm_repaired, dsm_repair_report = repair_nodata(dsm.arr, dsm.valid)

    surface_height = np.zeros(dtm_repaired.shape, dtype=np.float32)
    surface_height[surface_valid] = np.maximum(dsm_repaired[surface_valid] - dtm_repaired[surface_valid], 0.0)
    surface_norm = np.clip(surface_height / max(args.surface_max_m, 1.0), 0.0, 1.0)

    h_min = float(np.nanmin(dtm_repaired))
    h_max = float(np.nanmax(dtm_repaired))
    h_range = max(h_max - h_min, 1.0)
    height_norm = np.clip((dtm_repaired - h_min) / h_range, 0.0, 1.0)
    height_resized = resize_float(height_norm, args.size, Image.Resampling.LANCZOS)
    Image.fromarray((height_resized * 65535.0).clip(0, 65535).astype(np.uint16), mode="I;16").save(args.output_dir / "heightmap.png")

    cell_x, cell_y = cell_sizes_m(dtm)
    slope_deg, hillshade, roughness = slope_hillshade_roughness(dtm_repaired, cell_x, cell_y)
    rough_norm = normalize_percentile(roughness, 1.0, 99.0)
    wetness = np.clip((1.0 - normalize_percentile(dtm_repaired, 5.0, 95.0)) * 0.55 + (1.0 - slope_deg / 28.0) * 0.45, 0.0, 1.0)
    forest = np.clip(np.sqrt(surface_norm), 0.0, 1.0)
    rock = np.clip((slope_deg - 28.0) / 32.0, 0.0, 1.0) * (0.65 + rough_norm * 0.35)
    alpine = np.clip((height_norm - 0.78) / 0.18, 0.0, 1.0)

    save_gray(dtm_repaired, layers_dir / "dtm_gray.png", args.size)
    save_gray(dsm_repaired, layers_dir / "dsm_gray.png", args.size)
    save_unit(height_norm, layers_dir / "elevation_gray.png", args.size)
    save_unit(hillshade, layers_dir / "hillshade.png", args.size)
    save_unit(np.clip(slope_deg / 70.0, 0.0, 1.0), layers_dir / "slope_deg.png", args.size)
    save_gray(roughness, layers_dir / "roughness.png", args.size, 1.0, 99.0)
    save_unit(surface_norm, layers_dir / "surface_height.png", args.size)
    save_unit(forest, layers_dir / "forest_surface_mask.png", args.size)
    save_unit(rock, layers_dir / "rock_slope_mask.png", args.size)
    save_unit(wetness, layers_dir / "wetness_valley_mask.png", args.size)
    save_mask(source_valid, layers_dir / "source_valid_mask.png", args.size)
    save_mask(surface_valid, layers_dir / "surface_valid_mask.png", args.size)

    material_rgba = np.dstack(
        [
            resize_float(np.clip(rock, 0.0, 1.0), args.size, Image.Resampling.BILINEAR),
            resize_float(np.clip(forest, 0.0, 1.0), args.size, Image.Resampling.BILINEAR),
            resize_float(np.clip(wetness, 0.0, 1.0), args.size, Image.Resampling.BILINEAR),
            resize_float(np.clip(alpine, 0.0, 1.0), args.size, Image.Resampling.BILINEAR),
        ]
    )
    Image.fromarray((material_rgba * 255.0).clip(0, 255).astype(np.uint8), mode="RGBA").save(layers_dir / "material_mask_rgba.png")

    texture = make_terrain_texture(height_norm, hillshade, slope_deg, rough_norm, surface_norm, wetness, args.size)
    Image.fromarray((texture * 255.0).astype(np.uint8), mode="RGB").save(layers_dir / "terrain_texture.png")

    world_x, world_z = world_sizes_m(dtm)
    meta = {
        "name": args.name,
        "source_dtm": str(args.dtm),
        "source_dsm": str(args.dsm),
        "source_crs": str(dtm.crs),
        "source_bounds": {
            "left": float(dtm.bounds.left),
            "right": float(dtm.bounds.right),
            "bottom": float(dtm.bounds.bottom),
            "top": float(dtm.bounds.top),
        },
        "source_shape": [int(dtm.arr.shape[1]), int(dtm.arr.shape[0])],
        "source_cell_size_m": [float(cell_x), float(cell_y)],
        "heightmap_size_px": int(args.size),
        "elevation_min_m": h_min,
        "elevation_max_m": h_max,
        "elevation_range_m": h_range,
        "world_size_m": float(min(world_x, world_z)),
        "world_size_x_m": float(world_x),
        "world_size_z_m": float(world_z),
        "material": "opentopo_dtm_dsm_no_color",
        "nodata_repair": repair_report,
        "dsm_nodata_repair": dsm_repair_report,
        "surface_max_m": float(args.surface_max_m),
    }
    (args.output_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    layers = [
        "terrain_texture",
        "dtm_gray",
        "dsm_gray",
        "surface_height",
        "forest_surface_mask",
        "rock_slope_mask",
        "wetness_valley_mask",
        "material_mask_rgba",
        "hillshade",
        "elevation_gray",
        "slope_deg",
        "roughness",
        "source_valid_mask",
        "surface_valid_mask",
    ]
    manifest = {
        "name": args.name,
        "mode": "dtm_dsm_no_color_stack",
        "dtm": str(args.dtm),
        "dsm": str(args.dsm),
        "output_dir": str(args.output_dir),
        "layers": [{"name": name, "path": f"layers/{name}.png"} for name in layers],
        "stats": {
            "dtm": stats(dtm_repaired, source_valid),
            "dsm": stats(dsm_repaired, dsm.valid),
            "surface_height_m": stats(surface_height, surface_valid),
            "slope_deg": stats(slope_deg, source_valid),
        },
        "compression_policy": {
            "source": "raw GeoTIFFs untouched",
            "review": "16-bit height PNG plus 8-bit PNG layers",
            "master_recommendation": "write aligned float32 tiled GeoTIFF/Zarr before destructive compression when this stack grows",
        },
    }
    (args.output_dir / "stack_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"OK {args.output_dir} size={args.size} source={dtm.arr.shape[1]}x{dtm.arr.shape[0]} world={world_x/1000:.2f}x{world_z/1000:.2f}km")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
