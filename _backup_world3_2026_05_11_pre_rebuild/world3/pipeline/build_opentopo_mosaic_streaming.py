"""Build a large same-CRS OpenTopography raster mosaic without full-array RAM use."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds


NODATA = -999999.0
RESAMPLING = {
    "nearest": Resampling.nearest,
    "bilinear": Resampling.bilinear,
    "cubic": Resampling.cubic,
}


def collect_inputs(args: argparse.Namespace) -> list[Path]:
    paths = list(args.inputs)
    if args.input_dir:
        paths.extend(sorted(args.input_dir.glob(args.glob)))
    unique = []
    seen = set()
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
    source_crs = []
    if explicit_bounds is not None:
        left, bottom, right, top = explicit_bounds
    else:
        transformed = []
        for path in paths:
            with rasterio.open(path) as src:
                source_crs.append(str(src.crs))
                transformed.append(transform_bounds(src.crs, target_crs, *src.bounds, densify_pts=21))
        left = min(b[0] for b in transformed)
        bottom = min(b[1] for b in transformed)
        right = max(b[2] for b in transformed)
        top = max(b[3] for b in transformed)
    if source_crs and any(crs != target_crs for crs in source_crs):
        raise SystemExit(
            "Streaming mosaic only supports same-CRS inputs. "
            "Use the non-streaming builder for small reprojection jobs."
        )
    left, bottom, right, top = snap_bounds((left, bottom, right, top), cell_size)
    width = int(math.ceil((right - left) / cell_size))
    height = int(math.ceil((top - bottom) / cell_size))
    transform = from_origin(left, top, cell_size, cell_size)
    return (left, bottom, right, top), width, height, transform


def gtiff_profile(crs: str, dtype: str, nodata) -> dict:
    return {
        "driver": "GTiff",
        "count": 1,
        "dtype": dtype,
        "crs": crs,
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "nodata": nodata,
        "BIGTIFF": "IF_SAFER",
    }


def merge_to_file(
    paths: list[Path],
    out: Path,
    bounds: tuple[float, float, float, float],
    cell_size: float,
    target_crs: str,
    method: str,
    dtype: str,
    nodata,
    resampling: Resampling,
    mem_limit: int,
) -> None:
    datasets = [rasterio.open(path) for path in paths]
    try:
        merge(
            datasets,
            bounds=bounds,
            res=(cell_size, cell_size),
            nodata=nodata,
            dtype=dtype,
            resampling=resampling,
            method=method,
            target_aligned_pixels=True,
            mem_limit=mem_limit,
            dst_path=str(out),
            dst_kwds=gtiff_profile(target_crs, dtype, nodata),
        )
    finally:
        for ds in datasets:
            ds.close()


def valid_mask(arr: np.ndarray, nodata=NODATA) -> np.ndarray:
    return np.isfinite(arr) & (arr != nodata)


def write_seam_delta(min_path: Path, max_path: Path, count_path: Path, out_path: Path) -> None:
    with rasterio.open(min_path) as min_src, rasterio.open(max_path) as max_src, rasterio.open(count_path) as count_src:
        profile = min_src.profile.copy()
        profile.update(gtiff_profile(str(min_src.crs), "float32", NODATA))
        profile.update({
            "height": min_src.height,
            "width": min_src.width,
            "transform": min_src.transform,
        })
        with rasterio.open(out_path, "w", **profile) as dst:
            for _, window in min_src.block_windows(1):
                min_arr = min_src.read(1, window=window)
                max_arr = max_src.read(1, window=window)
                count = count_src.read(1, window=window)
                seam = np.full(min_arr.shape, NODATA, dtype=np.float32)
                overlap = count > 1
                valid = overlap & valid_mask(min_arr) & valid_mask(max_arr)
                seam[valid] = max_arr[valid] - min_arr[valid]
                dst.write(seam, 1, window=window)


class RunningStats:
    def __init__(self, thresholds: list[float] | None = None, sample_stride: int = 128):
        self.count = 0
        self.min = math.inf
        self.max = -math.inf
        self.sum = 0.0
        self.thresholds = thresholds or []
        self.threshold_counts = {threshold: 0 for threshold in self.thresholds}
        self.sample_stride = max(sample_stride, 1)
        self.samples: list[np.ndarray] = []

    def update(self, values: np.ndarray) -> None:
        if values.size == 0:
            return
        values = values.astype(np.float64, copy=False)
        self.count += int(values.size)
        self.min = min(self.min, float(values.min()))
        self.max = max(self.max, float(values.max()))
        self.sum += float(values.sum())
        for threshold in self.thresholds:
            self.threshold_counts[threshold] += int((values > threshold).sum())
        sample = values.ravel()[:: self.sample_stride]
        if sample.size:
            self.samples.append(sample.astype(np.float32, copy=True))

    def to_dict(self) -> dict:
        if self.count == 0:
            return {"valid_pixels": 0}
        sample = np.concatenate(self.samples) if self.samples else np.array([], dtype=np.float32)
        result = {
            "valid_pixels": self.count,
            "min": self.min,
            "max": self.max,
            "mean": self.sum / self.count,
            "percentiles": "sampled",
        }
        if sample.size:
            result.update({
                "p50": float(np.percentile(sample, 50)),
                "p95": float(np.percentile(sample, 95)),
                "p99": float(np.percentile(sample, 99)),
                "sample_count": int(sample.size),
            })
        if self.thresholds:
            thresholds = {}
            for threshold, count in self.threshold_counts.items():
                key = f"gt_{threshold:g}m".replace(".", "_")
                thresholds[key] = {"count": count, "percent": float(count * 100.0 / self.count)}
            result["thresholds"] = thresholds
        return result


def raster_stats(path: Path, nodata, thresholds: list[float] | None = None, sample_stride: int = 128) -> dict:
    stats = RunningStats(thresholds=thresholds, sample_stride=sample_stride)
    with rasterio.open(path) as src:
        for _, window in src.block_windows(1):
            arr = src.read(1, window=window)
            stats.update(arr[valid_mask(arr, nodata)])
    return stats.to_dict()


def count_stats(path: Path) -> dict:
    valid = 0
    overlap = 0
    max_count = 0
    with rasterio.open(path) as src:
        for _, window in src.block_windows(1):
            arr = src.read(1, window=window)
            valid += int((arr > 0).sum())
            overlap += int((arr > 1).sum())
            max_count = max(max_count, int(arr.max()))
    return {"valid_pixels": valid, "overlap_pixels": overlap, "max_count": max_count}


def write_preview(path: Path, raster_path: Path, nodata, size: int = 2048, max_value: float | None = None) -> None:
    with rasterio.open(raster_path) as src:
        aspect = src.width / src.height
        if aspect >= 1.0:
            width = size
            height = max(1, int(size / aspect))
        else:
            height = size
            width = max(1, int(size * aspect))
        arr = src.read(1, out_shape=(height, width), resampling=Resampling.bilinear)
    valid = valid_mask(arr, nodata)
    if not valid.any():
        Image.fromarray(np.zeros(arr.shape, dtype=np.uint8), mode="L").save(path)
        return
    lo = float(np.nanpercentile(arr[valid], 2))
    hi = float(max_value if max_value is not None else np.nanpercentile(arr[valid], 98))
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.zeros(arr.shape, dtype=np.float32)
    scaled[valid] = (arr[valid].astype(np.float32) - lo) / (hi - lo)
    Image.fromarray(np.clip(scaled * 255.0, 0, 255).astype(np.uint8), mode="L").save(path)


def write_hillshade_preview(path: Path, raster_path: Path, cell_size: float, size: int = 2048) -> None:
    with rasterio.open(raster_path) as src:
        aspect = src.width / src.height
        if aspect >= 1.0:
            width = size
            height = max(1, int(size / aspect))
        else:
            height = size
            width = max(1, int(size * aspect))
        arr = src.read(1, out_shape=(height, width), resampling=Resampling.bilinear)
        preview_cell = cell_size * max(src.width / width, src.height / height)
    valid = valid_mask(arr)
    if not valid.any():
        Image.fromarray(np.zeros(arr.shape, dtype=np.uint8), mode="L").save(path)
        return
    filled = arr.astype(np.float32, copy=True)
    filled[~valid] = float(filled[valid].min())
    gy, gx = np.gradient(filled, preview_cell, preview_cell)
    slope = np.pi / 2.0 - np.arctan(np.sqrt(gx * gx + gy * gy))
    aspect = np.arctan2(-gx, gy)
    azimuth = np.deg2rad(315.0)
    altitude = np.deg2rad(45.0)
    shaded = np.sin(altitude) * np.sin(slope) + np.cos(altitude) * np.cos(slope) * np.cos(azimuth - aspect)
    out = np.clip((shaded + 1.0) * 127.5, 0, 255).astype(np.uint8)
    out[~valid] = 0
    Image.fromarray(out, mode="L").save(path)


def write_heightmap(out_dir: Path, mosaic_path: Path, args, bounds, target_crs: str, mosaic_stats: dict) -> None:
    Image.MAX_IMAGE_PIXELS = None
    with rasterio.open(mosaic_path) as src:
        arr = src.read(1, out_shape=(args.heightmap_size, args.heightmap_size), resampling=Resampling.bilinear)
    valid = valid_mask(arr)
    if not valid.any():
        raise SystemExit("Cannot export heightmap from empty mosaic")
    h_min = float(mosaic_stats["min"])
    h_max = float(mosaic_stats["max"])
    h_range = max(h_max - h_min, 1.0)
    arr = arr.astype(np.float32, copy=False)
    arr[~valid] = h_min
    norm = (arr - h_min) / h_range
    arr16 = (norm * 65535.0).clip(0, 65535).astype(np.uint16)
    Image.fromarray(arr16, mode="I;16").save(out_dir / "heightmap.png")
    world_size_x_m = float(bounds[2] - bounds[0])
    world_size_z_m = float(bounds[3] - bounds[1])
    world_size_m = float(min(world_size_x_m, world_size_z_m))
    meta = {
        "source_dem": str(mosaic_path),
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
        "world_size_x_m": world_size_x_m,
        "world_size_z_m": world_size_z_m,
        "material": args.material,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def source_infos(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        with rasterio.open(path) as src:
            bounds_wgs84 = transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21)
            rows.append({
                "path": str(path),
                "crs": str(src.crs),
                "width": src.width,
                "height": src.height,
                "nodata": src.nodata,
                "bounds": {
                    "left": src.bounds.left,
                    "bottom": src.bounds.bottom,
                    "right": src.bounds.right,
                    "top": src.bounds.top,
                },
                "bounds_wgs84": {
                    "left": bounds_wgs84[0],
                    "bottom": bounds_wgs84[1],
                    "right": bounds_wgs84[2],
                    "top": bounds_wgs84[3],
                },
            })
    return rows


def polygon_from_bounds(bounds: dict) -> list[list[float]]:
    left = bounds["left"]
    bottom = bounds["bottom"]
    right = bounds["right"]
    top = bounds["top"]
    return [[left, bottom], [right, bottom], [right, top], [left, top], [left, bottom]]


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
            },
            "geometry": {"type": "Polygon", "coordinates": [polygon_from_bounds(bounds)]},
        })
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="*", type=Path)
    ap.add_argument("--input-dir", type=Path)
    ap.add_argument("--glob", default="*.tif")
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--target-crs", required=True)
    ap.add_argument("--target-cell-size-m", type=float, required=True)
    ap.add_argument("--bounds", type=float, nargs=4, metavar=("LEFT", "BOTTOM", "RIGHT", "TOP"))
    ap.add_argument("--reducer", choices=["first", "last", "min", "max"], default="first")
    ap.add_argument("--resampling", choices=sorted(RESAMPLING), default="bilinear")
    ap.add_argument("--heightmap-size", type=int, default=8192)
    ap.add_argument("--material", default="forest_floor")
    ap.add_argument("--mem-limit", type=int, default=256)
    ap.add_argument("--preview-size", type=int, default=2048)
    ap.add_argument("--sample-stride", type=int, default=128)
    ap.add_argument("--keep-min-max", action="store_true")
    ap.add_argument("--no-heightmap", action="store_true")
    args = ap.parse_args()

    paths = collect_inputs(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    qa_dir = args.output_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    bounds, width, height, transform = target_grid(paths, args.target_crs, args.target_cell_size_m, args.bounds)
    print(f"target grid {width}x{height} {args.target_crs} bounds={bounds}")

    mosaic_path = args.output_dir / "mosaic.tif"
    coverage_path = args.output_dir / "coverage_count.tif"
    min_path = args.output_dir / "_min_for_seam.tif"
    max_path = args.output_dir / "_max_for_seam.tif"
    seam_path = args.output_dir / "seam_delta.tif"

    print("writing mosaic")
    merge_to_file(paths, mosaic_path, bounds, args.target_cell_size_m, args.target_crs, args.reducer, "float32", NODATA, RESAMPLING[args.resampling], args.mem_limit)
    print("writing coverage")
    merge_to_file(paths, coverage_path, bounds, args.target_cell_size_m, args.target_crs, "count", "uint16", 0, RESAMPLING[args.resampling], args.mem_limit)
    print("writing min/max seam inputs")
    merge_to_file(paths, min_path, bounds, args.target_cell_size_m, args.target_crs, "min", "float32", NODATA, RESAMPLING[args.resampling], args.mem_limit)
    merge_to_file(paths, max_path, bounds, args.target_cell_size_m, args.target_crs, "max", "float32", NODATA, RESAMPLING[args.resampling], args.mem_limit)
    print("writing seam delta")
    write_seam_delta(min_path, max_path, coverage_path, seam_path)

    print("writing QA previews")
    write_preview(qa_dir / "mosaic_preview.png", mosaic_path, NODATA, size=args.preview_size)
    write_preview(qa_dir / "coverage_count_preview.png", coverage_path, 0, size=args.preview_size, max_value=4.0)
    write_preview(qa_dir / "seam_delta_preview.png", seam_path, NODATA, size=args.preview_size, max_value=1.0)
    write_hillshade_preview(qa_dir / "hillshade_preview.png", mosaic_path, args.target_cell_size_m, size=args.preview_size)

    print("calculating block stats")
    mosaic_stats = raster_stats(mosaic_path, NODATA, sample_stride=args.sample_stride)
    coverage_stats = count_stats(coverage_path)
    seam_stats = raster_stats(seam_path, NODATA, thresholds=[0.5, 1.0, 2.0, 5.0, 10.0], sample_stride=args.sample_stride)
    sources = source_infos(paths)
    write_tile_footprints(args.output_dir / "tile_footprints.geojson", sources)

    report = {
        "name": args.name,
        "builder": "build_opentopo_mosaic_streaming.py",
        "stats_note": "counts/min/max/mean are exact; percentiles are sampled",
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
        "mosaic": mosaic_stats,
        "coverage": coverage_stats,
        "seam_delta": seam_stats,
        "sources": sources,
        "outputs": {
            "mosaic": str(mosaic_path),
            "coverage_count": str(coverage_path),
            "seam_delta": str(seam_path),
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
        print("writing Godot heightmap")
        write_heightmap(args.output_dir, mosaic_path, args, bounds, args.target_crs, mosaic_stats)

    if not args.keep_min_max:
        min_path.unlink(missing_ok=True)
        max_path.unlink(missing_ok=True)

    print(args.output_dir / "mosaic_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
