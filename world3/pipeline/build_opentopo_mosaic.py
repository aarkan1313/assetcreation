"""Build a same-type raster mosaic with seam QA and optional Godot heightmap."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds


RESAMPLING = {
    "nearest": Resampling.nearest,
    "bilinear": Resampling.bilinear,
    "cubic": Resampling.cubic,
}
NODATA = -999999.0


def collect_inputs(args: argparse.Namespace) -> list[Path]:
    paths = list(args.inputs)
    if args.input_dir:
        paths.extend(sorted(args.input_dir.glob(args.glob)))
    seen = set()
    unique = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    if not unique:
        raise SystemExit("No input GeoTIFFs provided")
    return unique


def snap_bounds(bounds: tuple[float, float, float, float], cell: float) -> tuple[float, float, float, float]:
    left, bottom, right, top = bounds
    return (
        math.floor(left / cell) * cell,
        math.floor(bottom / cell) * cell,
        math.ceil(right / cell) * cell,
        math.ceil(top / cell) * cell,
    )


def target_grid(paths: list[Path], target_crs: str, cell_size: float, explicit_bounds: list[float] | None):
    if explicit_bounds is not None:
        left, bottom, right, top = explicit_bounds
    else:
        transformed = []
        for path in paths:
            with rasterio.open(path) as src:
                transformed.append(transform_bounds(src.crs, target_crs, *src.bounds, densify_pts=21))
        left = min(b[0] for b in transformed)
        bottom = min(b[1] for b in transformed)
        right = max(b[2] for b in transformed)
        top = max(b[3] for b in transformed)
    left, bottom, right, top = snap_bounds((left, bottom, right, top), cell_size)
    width = int(math.ceil((right - left) / cell_size))
    height = int(math.ceil((top - bottom) / cell_size))
    transform = from_origin(left, top, cell_size, cell_size)
    return (left, bottom, right, top), width, height, transform


def valid_mask(arr: np.ndarray) -> np.ndarray:
    return np.isfinite(arr) & (arr != NODATA)


def reproject_one(path: Path, target_crs: str, transform, shape: tuple[int, int], resampling: Resampling):
    dest = np.full(shape, NODATA, dtype=np.float32)
    with rasterio.open(path) as src:
        src_nodata = src.nodata
        bounds_wgs84 = None
        if src.crs:
            try:
                left, bottom, right, top = transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21)
                bounds_wgs84 = {"left": left, "bottom": bottom, "right": right, "top": top}
            except Exception:
                bounds_wgs84 = None
        reproject(
            source=rasterio.band(src, 1),
            destination=dest,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src_nodata,
            dst_transform=transform,
            dst_crs=target_crs,
            dst_nodata=NODATA,
            resampling=resampling,
        )
        src_info = {
            "path": str(path),
            "crs": str(src.crs),
            "bounds": {
                "left": src.bounds.left,
                "bottom": src.bounds.bottom,
                "right": src.bounds.right,
                "top": src.bounds.top,
            },
            "width": src.width,
            "height": src.height,
            "nodata": src.nodata,
        }
        if bounds_wgs84 is not None:
            src_info["bounds_wgs84"] = bounds_wgs84
    return dest, src_info


def reduce_arrays(paths: list[Path], args, bounds, width: int, height: int, transform):
    sum_arr = np.zeros((height, width), dtype=np.float64)
    count = np.zeros((height, width), dtype=np.uint16)
    min_arr = np.full((height, width), np.inf, dtype=np.float32)
    max_arr = np.full((height, width), -np.inf, dtype=np.float32)
    first = np.full((height, width), NODATA, dtype=np.float32)
    last = np.full((height, width), NODATA, dtype=np.float32)
    sources = []

    for path in paths:
        arr, info = reproject_one(path, args.target_crs, transform, (height, width), RESAMPLING[args.resampling])
        valid = valid_mask(arr)
        if valid.any():
            sum_arr[valid] += arr[valid]
            count[valid] += 1
            min_arr[valid] = np.minimum(min_arr[valid], arr[valid])
            max_arr[valid] = np.maximum(max_arr[valid], arr[valid])
            first[(first == NODATA) & valid] = arr[(first == NODATA) & valid]
            last[valid] = arr[valid]
        info["valid_pixels_on_target_grid"] = int(valid.sum())
        sources.append(info)
        print(f"aligned {path.name}: valid={int(valid.sum())}")

    valid_any = count > 0
    if args.reducer == "mean":
        mosaic = np.full((height, width), NODATA, dtype=np.float32)
        mosaic[valid_any] = (sum_arr[valid_any] / count[valid_any]).astype(np.float32)
    elif args.reducer == "min":
        mosaic = np.where(valid_any, min_arr, NODATA).astype(np.float32)
    elif args.reducer == "max":
        mosaic = np.where(valid_any, max_arr, NODATA).astype(np.float32)
    elif args.reducer == "first":
        mosaic = first
    elif args.reducer == "last":
        mosaic = last
    else:
        raise SystemExit(f"Unknown reducer {args.reducer}")

    seam_delta = np.full((height, width), NODATA, dtype=np.float32)
    overlap = count > 1
    seam_delta[overlap] = max_arr[overlap] - min_arr[overlap]
    return mosaic, count, seam_delta, sources


def write_tif(path: Path, arr: np.ndarray, target_crs: str, transform, dtype: str, nodata):
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": arr.shape[0],
        "width": arr.shape[1],
        "count": 1,
        "dtype": dtype,
        "crs": target_crs,
        "transform": transform,
        "compress": "deflate",
        "tiled": True,
        "nodata": nodata,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype(dtype), 1)


def preview_gray(path: Path, arr: np.ndarray, nodata=NODATA, max_value: float | None = None) -> None:
    if np.issubdtype(arr.dtype, np.floating):
        valid = np.isfinite(arr)
        if nodata is not None:
            valid &= arr != nodata
    elif nodata is not None:
        valid = arr != nodata
    else:
        valid = np.ones(arr.shape, dtype=bool)
    if not valid.any():
        Image.fromarray(np.zeros(arr.shape, dtype=np.uint8), mode="L").save(path)
        return
    lo = float(np.nanpercentile(arr[valid], 2))
    hi = float(max_value if max_value is not None else np.nanpercentile(arr[valid], 98))
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.zeros(arr.shape, dtype=np.float32)
    scaled[valid] = (arr[valid].astype(np.float32) - lo) / (hi - lo)
    out = np.clip(scaled * 255.0, 0, 255).astype(np.uint8)
    Image.fromarray(out, mode="L").save(path)


def hillshade(arr: np.ndarray, cell_size: float) -> np.ndarray:
    valid = valid_mask(arr)
    if not valid.any():
        return np.zeros(arr.shape, dtype=np.uint8)
    filled = arr.copy()
    filled[~valid] = float(arr[valid].min())
    gy, gx = np.gradient(filled.astype(np.float32), cell_size, cell_size)
    slope = np.pi / 2.0 - np.arctan(np.sqrt(gx * gx + gy * gy))
    aspect = np.arctan2(-gx, gy)
    azimuth = np.deg2rad(315.0)
    altitude = np.deg2rad(45.0)
    shaded = np.sin(altitude) * np.sin(slope) + np.cos(altitude) * np.cos(slope) * np.cos(azimuth - aspect)
    out = np.clip((shaded + 1.0) * 127.5, 0, 255).astype(np.uint8)
    out[~valid] = 0
    return out


def stats(arr: np.ndarray) -> dict:
    valid = valid_mask(arr)
    if not valid.any():
        return {"valid_pixels": 0}
    values = arr[valid]
    return {
        "valid_pixels": int(valid.sum()),
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
    }


def threshold_stats(arr: np.ndarray, thresholds: list[float]) -> dict:
    valid = valid_mask(arr)
    total = int(valid.sum())
    if total == 0:
        return {"valid_pixels": 0}
    values = arr[valid]
    result = {"valid_pixels": total}
    for threshold in thresholds:
        count = int((values > threshold).sum())
        key = f"gt_{threshold:g}m".replace(".", "_")
        result[key] = {
            "count": count,
            "percent": float(count * 100.0 / total),
        }
    return result


def polygon_from_bounds(bounds: dict) -> list[list[float]]:
    left = bounds["left"]
    bottom = bounds["bottom"]
    right = bounds["right"]
    top = bounds["top"]
    return [
        [left, bottom],
        [right, bottom],
        [right, top],
        [left, top],
        [left, bottom],
    ]


def write_tile_footprints(path: Path, sources: list[dict]) -> None:
    features = []
    for index, source in enumerate(sources):
        bounds = source.get("bounds_wgs84") or source["bounds"]
        features.append({
            "type": "Feature",
            "properties": {
                "index": index,
                "file": Path(source["path"]).name,
                "crs": source.get("crs"),
                "valid_pixels_on_target_grid": source.get("valid_pixels_on_target_grid"),
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon_from_bounds(bounds)],
            },
        })
    path.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": features,
    }, indent=2), encoding="utf-8")


def write_heightmap(out_dir: Path, mosaic: np.ndarray, args, bounds, target_crs: str):
    valid = valid_mask(mosaic)
    if not valid.any():
        raise SystemExit("Cannot export heightmap from empty mosaic")
    elev = mosaic.copy()
    elev[~valid] = float(elev[valid].min())
    h_min = float(elev.min())
    h_max = float(elev.max())
    h_range = max(h_max - h_min, 1.0)
    norm = (elev - h_min) / h_range
    img_f = Image.fromarray(norm.astype(np.float32), mode="F")
    img_f = img_f.resize((args.heightmap_size, args.heightmap_size), Image.Resampling.LANCZOS)
    arr16 = (np.asarray(img_f, dtype=np.float32) * 65535.0).clip(0, 65535).astype(np.uint16)
    Image.fromarray(arr16, mode="I;16").save(out_dir / "heightmap.png")
    world_size_m = float(min(bounds[2] - bounds[0], bounds[3] - bounds[1]))
    meta = {
        "source_dem": str(out_dir / "mosaic.tif"),
        "source_crs": target_crs,
        "source_bounds": {
            "left": bounds[0],
            "bottom": bounds[1],
            "right": bounds[2],
            "top": bounds[3],
        },
        "heightmap_size_px": args.heightmap_size,
        "elevation_min_m": h_min,
        "elevation_max_m": h_max,
        "elevation_range_m": h_range,
        "world_size_m": world_size_m,
        "material": args.material,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="*", type=Path)
    ap.add_argument("--input-dir", type=Path)
    ap.add_argument("--glob", default="*.tif")
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--target-crs", required=True, help="projected target CRS, e.g. EPSG:32612")
    ap.add_argument("--target-cell-size-m", type=float, required=True)
    ap.add_argument("--bounds", type=float, nargs=4, metavar=("LEFT", "BOTTOM", "RIGHT", "TOP"))
    ap.add_argument("--reducer", choices=["mean", "min", "max", "first", "last"], default="mean")
    ap.add_argument("--resampling", choices=sorted(RESAMPLING), default="bilinear")
    ap.add_argument("--heightmap-size", type=int, default=1024)
    ap.add_argument("--material", default="rock_light")
    ap.add_argument("--no-heightmap", action="store_true")
    args = ap.parse_args()

    paths = collect_inputs(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    qa_dir = args.output_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    bounds, width, height, transform = target_grid(paths, args.target_crs, args.target_cell_size_m, args.bounds)
    print(f"target grid {width}x{height} {args.target_crs} bounds={bounds}")
    mosaic, coverage, seam_delta, sources = reduce_arrays(paths, args, bounds, width, height, transform)

    write_tif(args.output_dir / "mosaic.tif", mosaic, args.target_crs, transform, "float32", NODATA)
    write_tif(args.output_dir / "coverage_count.tif", coverage, args.target_crs, transform, "uint16", 0)
    write_tif(args.output_dir / "seam_delta.tif", seam_delta, args.target_crs, transform, "float32", NODATA)
    write_tile_footprints(args.output_dir / "tile_footprints.geojson", sources)
    preview_gray(qa_dir / "mosaic_preview.png", mosaic)
    preview_gray(qa_dir / "coverage_count_preview.png", coverage.astype(np.float32), nodata=0, max_value=max(float(coverage.max()), 1.0))
    preview_gray(qa_dir / "seam_delta_preview.png", seam_delta, max_value=max(float(np.nanpercentile(seam_delta[valid_mask(seam_delta)], 99)) if valid_mask(seam_delta).any() else 1.0, 1.0))
    Image.fromarray(hillshade(mosaic, args.target_cell_size_m), mode="L").save(qa_dir / "hillshade_preview.png")

    seam_stats = stats(seam_delta)
    report = {
        "name": args.name,
        "target_crs": args.target_crs,
        "target_bounds": {
            "left": bounds[0],
            "bottom": bounds[1],
            "right": bounds[2],
            "top": bounds[3],
        },
        "target_cell_size_m": args.target_cell_size_m,
        "target_width": width,
        "target_height": height,
        "reducer": args.reducer,
        "resampling": args.resampling,
        "input_count": len(paths),
        "mosaic": stats(mosaic),
        "coverage": {
            "valid_pixels": int((coverage > 0).sum()),
            "overlap_pixels": int((coverage > 1).sum()),
            "max_count": int(coverage.max()),
        },
        "seam_delta": seam_stats,
        "seam_delta_thresholds": threshold_stats(seam_delta, [0.5, 1.0, 2.0, 5.0, 10.0]),
        "sources": sources,
        "outputs": {
            "mosaic": str(args.output_dir / "mosaic.tif"),
            "coverage_count": str(args.output_dir / "coverage_count.tif"),
            "seam_delta": str(args.output_dir / "seam_delta.tif"),
            "tile_footprints": str(args.output_dir / "tile_footprints.geojson"),
            "qa_dir": str(qa_dir),
        },
    }
    (args.output_dir / "mosaic_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.output_dir / "stack_manifest.json").write_text(json.dumps({
        "name": args.name,
        "target_crs": args.target_crs,
        "target_bounds": report["target_bounds"],
        "target_cell_size_m": args.target_cell_size_m,
        "target_width": width,
        "target_height": height,
        "vertical_datum": "unknown",
        "base_height_layer": "mosaic",
        "layers": [
            {"name": "mosaic", "path": "mosaic.tif", "role": "base_height"},
            {"name": "coverage_count", "path": "coverage_count.tif", "role": "qa"},
            {"name": "seam_delta", "path": "seam_delta.tif", "role": "qa"},
        ],
        "vectors": [
            {"name": "tile_footprints", "path": "tile_footprints.geojson", "role": "qa"},
        ],
    }, indent=2), encoding="utf-8")

    if not args.no_heightmap:
        write_heightmap(args.output_dir, mosaic, args, bounds, args.target_crs)

    print(args.output_dir / "mosaic_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
