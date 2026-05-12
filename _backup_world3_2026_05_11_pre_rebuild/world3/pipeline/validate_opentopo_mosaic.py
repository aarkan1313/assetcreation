"""Validate a same-type OpenTopography raster mosaic bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject


NODATA = -999999.0


def valid_float(arr: np.ndarray, nodata: float = NODATA) -> np.ndarray:
    return np.isfinite(arr) & (arr != nodata)


def stats(values: np.ndarray) -> dict:
    if values.size == 0:
        return {"valid_pixels": 0}
    values = values.astype(np.float64, copy=False)
    return {
        "valid_pixels": int(values.size),
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
    }


def threshold_stats(values: np.ndarray, thresholds: list[float]) -> dict:
    result = {"valid_pixels": int(values.size)}
    if values.size == 0:
        return result
    for threshold in thresholds:
        count = int((values > threshold).sum())
        key = f"gt_{threshold:g}m".replace(".", "_")
        result[key] = {"count": count, "percent": float(count * 100.0 / values.size)}
    return result


def read_band(path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as src:
        arr = src.read(1)
        meta = {
            "crs": str(src.crs),
            "transform": src.transform,
            "shape": [src.height, src.width],
            "bounds": [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top],
            "nodata": src.nodata,
        }
    return arr, meta


def reproject_source(path: Path, target_meta: dict) -> np.ndarray:
    dest = np.full(tuple(target_meta["shape"]), NODATA, dtype=np.float32)
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=dest,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=target_meta["transform"],
            dst_crs=target_meta["crs"],
            dst_nodata=NODATA,
            resampling=Resampling.bilinear,
        )
    return dest


def slope_stats(mosaic: np.ndarray, cell_size: float) -> dict:
    valid = valid_float(mosaic)
    if not valid.any():
        return {"valid_pixels": 0}
    filled = mosaic.copy()
    filled[~valid] = float(mosaic[valid].min())
    gy, gx = np.gradient(filled.astype(np.float32), cell_size, cell_size)
    slope = np.degrees(np.arctan(np.sqrt(gx * gx + gy * gy)))
    return stats(slope[valid])


def validate(args: argparse.Namespace) -> dict:
    mosaic_dir = args.mosaic_dir
    report_path = mosaic_dir / "mosaic_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))

    mosaic, mosaic_meta = read_band(mosaic_dir / "mosaic.tif")
    coverage, coverage_meta = read_band(mosaic_dir / "coverage_count.tif")
    seam_delta, seam_meta = read_band(mosaic_dir / "seam_delta.tif")

    checks = []
    warnings = []
    if mosaic_meta["shape"] != coverage_meta["shape"] or mosaic_meta["shape"] != seam_meta["shape"]:
        checks.append({"name": "shape_consistency", "status": "fail"})
    else:
        checks.append({"name": "shape_consistency", "status": "pass"})

    if mosaic_meta["crs"] == report["target_crs"]:
        checks.append({"name": "target_crs", "status": "pass"})
    else:
        checks.append({"name": "target_crs", "status": "fail", "value": mosaic_meta["crs"]})

    valid = valid_float(mosaic)
    coverage_valid = coverage > 0
    missing_inside_coverage = int((coverage_valid & ~valid).sum())
    if missing_inside_coverage == 0:
        checks.append({"name": "nodata_inside_coverage", "status": "pass"})
    else:
        checks.append({"name": "nodata_inside_coverage", "status": "fail", "pixels": missing_inside_coverage})

    report_valid = int(report["mosaic"]["valid_pixels"])
    actual_valid = int(valid.sum())
    if actual_valid == report_valid:
        checks.append({"name": "report_valid_pixel_count", "status": "pass"})
    else:
        checks.append({
            "name": "report_valid_pixel_count",
            "status": "fail",
            "report": report_valid,
            "actual": actual_valid,
        })

    overlap = coverage > 1
    seam_values = seam_delta[valid_float(seam_delta)]
    if seam_values.size and float(np.percentile(seam_values, 99)) <= args.max_seam_p99:
        checks.append({"name": "seam_p99_limit", "status": "pass"})
    else:
        checks.append({"name": "seam_p99_limit", "status": "warn", "limit_m": args.max_seam_p99})

    source_paths = [Path(src["path"]) for src in report["sources"]]
    if args.raw_dir:
        source_paths = sorted(args.raw_dir.glob(args.glob))
    source_checks = []
    unique_deltas = []
    overlap_deltas = []
    for source_path in source_paths:
        source = reproject_source(source_path, mosaic_meta)
        source_valid = valid_float(source)
        compare_valid = valid & source_valid
        unique_mask = compare_valid & (coverage == 1)
        overlap_mask = compare_valid & overlap
        unique_abs = np.abs(mosaic[unique_mask] - source[unique_mask])
        overlap_abs = np.abs(mosaic[overlap_mask] - source[overlap_mask])
        if unique_abs.size:
            unique_deltas.append(unique_abs)
        if overlap_abs.size:
            overlap_deltas.append(overlap_abs)
        source_checks.append({
            "file": source_path.name,
            "valid_pixels_on_target_grid": int(source_valid.sum()),
            "unique_area_abs_delta": stats(unique_abs),
            "overlap_area_abs_delta": stats(overlap_abs),
        })

    unique_all = np.concatenate(unique_deltas) if unique_deltas else np.array([], dtype=np.float32)
    overlap_all = np.concatenate(overlap_deltas) if overlap_deltas else np.array([], dtype=np.float32)
    unique_stats = stats(unique_all)
    overlap_stats = stats(overlap_all)
    if unique_all.size and float(np.percentile(unique_all, 99)) <= args.max_unique_p99:
        checks.append({"name": "unique_area_source_match", "status": "pass"})
    else:
        checks.append({"name": "unique_area_source_match", "status": "warn", "limit_m": args.max_unique_p99})

    width_m = float(report["target_bounds"]["right"] - report["target_bounds"]["left"])
    height_m = float(report["target_bounds"]["top"] - report["target_bounds"]["bottom"])
    aspect_ratio_error = abs(width_m - height_m) / min(width_m, height_m)
    if aspect_ratio_error > 0.001:
        warnings.append(
            "GeoTIFF grid is rectangular, but the exported Godot heightmap is square. "
            "Use rectangular terrain scaling or square AOIs for exact horizontal scale."
        )

    if report.get("vertical_datum") == "unknown":
        warnings.append("Vertical datum is unknown in the current manifest/report.")

    status = "pass"
    if any(check["status"] == "fail" for check in checks):
        status = "fail"
    elif warnings or any(check["status"] == "warn" for check in checks):
        status = "pass_with_notes"

    return {
        "status": status,
        "mosaic_dir": str(mosaic_dir),
        "checks": checks,
        "warnings": warnings,
        "mosaic": {
            "valid_pixels": actual_valid,
            "shape": mosaic_meta["shape"],
            "crs": mosaic_meta["crs"],
            "width_m": width_m,
            "height_m": height_m,
            "aspect_ratio_error": aspect_ratio_error,
        },
        "coverage": {
            "valid_pixels": int(coverage_valid.sum()),
            "overlap_pixels": int(overlap.sum()),
            "max_count": int(coverage.max()),
        },
        "seam_delta": {
            "stats": stats(seam_values),
            "thresholds": threshold_stats(seam_values, [0.5, 1.0, 2.0, 5.0, 10.0]),
        },
        "source_match": {
            "unique_area_abs_delta": unique_stats,
            "overlap_area_abs_delta": overlap_stats,
            "sources": source_checks,
        },
        "terrain_slope_degrees": slope_stats(mosaic, float(report["target_cell_size_m"])),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mosaic-dir", required=True, type=Path)
    ap.add_argument("--raw-dir", type=Path)
    ap.add_argument("--glob", default="*.tif")
    ap.add_argument("--max-seam-p99", type=float, default=2.0)
    ap.add_argument("--max-unique-p99", type=float, default=0.01)
    args = ap.parse_args()

    report = validate(args)
    out = args.mosaic_dir / "validation_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(out)
    print(json.dumps({"status": report["status"], "warnings": report["warnings"]}, indent=2))
    return 0 if report["status"] in {"pass", "pass_with_notes"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
