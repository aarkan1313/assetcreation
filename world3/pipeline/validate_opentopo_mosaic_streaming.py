"""Validate a large OpenTopography mosaic using windowed reads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling

from build_opentopo_mosaic_streaming import NODATA, RunningStats, valid_mask


def raster_shape(path: Path) -> dict:
    with rasterio.open(path) as src:
        return {
            "crs": str(src.crs),
            "shape": [src.height, src.width],
            "bounds": [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top],
            "transform": list(src.transform)[:6],
            "nodata": src.nodata,
        }


def scan_core(mosaic_path: Path, coverage_path: Path, seam_path: Path, sample_stride: int) -> dict:
    mosaic_stats = RunningStats(sample_stride=sample_stride)
    seam_stats = RunningStats(thresholds=[0.5, 1.0, 2.0, 5.0, 10.0], sample_stride=sample_stride)
    coverage_valid = 0
    overlap_pixels = 0
    max_count = 0
    nodata_inside_coverage = 0

    with rasterio.open(mosaic_path) as mosaic, rasterio.open(coverage_path) as coverage, rasterio.open(seam_path) as seam:
        for _, window in mosaic.block_windows(1):
            m = mosaic.read(1, window=window)
            c = coverage.read(1, window=window)
            s = seam.read(1, window=window)
            m_valid = valid_mask(m)
            c_valid = c > 0
            coverage_valid += int(c_valid.sum())
            overlap_pixels += int((c > 1).sum())
            max_count = max(max_count, int(c.max()))
            nodata_inside_coverage += int((c_valid & ~m_valid).sum())
            mosaic_stats.update(m[m_valid])
            seam_stats.update(s[valid_mask(s)])

    return {
        "mosaic": mosaic_stats.to_dict(),
        "coverage": {
            "valid_pixels": coverage_valid,
            "overlap_pixels": overlap_pixels,
            "max_count": max_count,
        },
        "seam_delta": seam_stats.to_dict(),
        "nodata_inside_coverage": nodata_inside_coverage,
    }


def compare_source_windows(mosaic_path: Path, coverage_path: Path, source_paths: list[Path], sample_stride: int) -> dict:
    unique_stats = RunningStats(sample_stride=sample_stride)
    source_rows = []

    with rasterio.open(mosaic_path) as mosaic, rasterio.open(coverage_path) as coverage:
        for source_path in source_paths:
            with rasterio.open(source_path) as src:
                window = mosaic.window(*src.bounds).round_offsets().round_lengths()
                window = window.intersection(rasterio.windows.Window(0, 0, mosaic.width, mosaic.height))
                height = int(window.height)
                width = int(window.width)
                if width <= 0 or height <= 0:
                    source_rows.append({"file": source_path.name, "status": "no_overlap"})
                    continue
                m = mosaic.read(1, window=window)
                c = coverage.read(1, window=window)
                s = src.read(1, out_shape=(height, width), resampling=Resampling.bilinear)
                valid = valid_mask(m) & valid_mask(s, src.nodata if src.nodata is not None else NODATA) & (c == 1)
                delta = np.abs(m[valid].astype(np.float32) - s[valid].astype(np.float32))
                row_stats = RunningStats(sample_stride=sample_stride)
                row_stats.update(delta)
                unique_stats.update(delta)
                source_rows.append({
                    "file": source_path.name,
                    "window": {
                        "row_off": int(window.row_off),
                        "col_off": int(window.col_off),
                        "height": height,
                        "width": width,
                    },
                    "unique_area_abs_delta": row_stats.to_dict(),
                })

    return {
        "unique_area_abs_delta": unique_stats.to_dict(),
        "sources": source_rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mosaic-dir", required=True, type=Path)
    ap.add_argument("--raw-dir", type=Path)
    ap.add_argument("--glob", default="*.tif")
    ap.add_argument("--sample-stride", type=int, default=128)
    ap.add_argument("--max-seam-p99", type=float, default=0.05)
    ap.add_argument("--max-unique-p99", type=float, default=0.05)
    ap.add_argument("--skip-source-compare", action="store_true")
    args = ap.parse_args()

    report_path = args.mosaic_dir / "mosaic_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    mosaic_path = args.mosaic_dir / "mosaic.tif"
    coverage_path = args.mosaic_dir / "coverage_count.tif"
    seam_path = args.mosaic_dir / "seam_delta.tif"

    checks = []
    warnings = []
    mosaic_meta = raster_shape(mosaic_path)
    coverage_meta = raster_shape(coverage_path)
    seam_meta = raster_shape(seam_path)

    if mosaic_meta["shape"] == coverage_meta["shape"] == seam_meta["shape"]:
        checks.append({"name": "shape_consistency", "status": "pass"})
    else:
        checks.append({"name": "shape_consistency", "status": "fail"})

    if mosaic_meta["crs"] == report["target_crs"]:
        checks.append({"name": "target_crs", "status": "pass"})
    else:
        checks.append({"name": "target_crs", "status": "fail", "value": mosaic_meta["crs"]})

    scan = scan_core(mosaic_path, coverage_path, seam_path, args.sample_stride)
    if scan["nodata_inside_coverage"] == 0:
        checks.append({"name": "nodata_inside_coverage", "status": "pass"})
    else:
        checks.append({"name": "nodata_inside_coverage", "status": "fail", "pixels": scan["nodata_inside_coverage"]})

    if scan["mosaic"]["valid_pixels"] == int(report["mosaic"]["valid_pixels"]):
        checks.append({"name": "report_valid_pixel_count", "status": "pass"})
    else:
        checks.append({
            "name": "report_valid_pixel_count",
            "status": "fail",
            "report": int(report["mosaic"]["valid_pixels"]),
            "actual": scan["mosaic"]["valid_pixels"],
        })

    seam_p99 = float(scan["seam_delta"].get("p99", 0.0))
    if seam_p99 <= args.max_seam_p99:
        checks.append({"name": "seam_p99_limit", "status": "pass", "p99_m": seam_p99})
    else:
        checks.append({"name": "seam_p99_limit", "status": "warn", "p99_m": seam_p99, "limit_m": args.max_seam_p99})

    source_match = {"skipped": True}
    if args.raw_dir and not args.skip_source_compare:
        source_paths = sorted(args.raw_dir.glob(args.glob))
        source_match = compare_source_windows(mosaic_path, coverage_path, source_paths, args.sample_stride)
        unique_p99 = float(source_match["unique_area_abs_delta"].get("p99", 0.0))
        if unique_p99 <= args.max_unique_p99:
            checks.append({"name": "unique_area_source_match", "status": "pass", "p99_m": unique_p99})
        else:
            checks.append({"name": "unique_area_source_match", "status": "warn", "p99_m": unique_p99, "limit_m": args.max_unique_p99})

    width_m = float(report["target_bounds"]["right"] - report["target_bounds"]["left"])
    height_m = float(report["target_bounds"]["top"] - report["target_bounds"]["bottom"])
    aspect_ratio_error = abs(width_m - height_m) / min(width_m, height_m)
    if aspect_ratio_error > 0.001:
        warnings.append(
            "GeoTIFF grid is rectangular, but the exported Godot heightmap is square. "
            "Use rectangular terrain scaling or square AOIs for exact horizontal scale."
        )
    warnings.append("Vertical datum is not verified by this validator; keep datum provenance in the source audit.")

    status = "pass"
    if any(check["status"] == "fail" for check in checks):
        status = "fail"
    elif warnings or any(check["status"] == "warn" for check in checks):
        status = "pass_with_notes"

    validation = {
        "status": status,
        "mosaic_dir": str(args.mosaic_dir),
        "checks": checks,
        "warnings": warnings,
        "mosaic": {
            **scan["mosaic"],
            "shape": mosaic_meta["shape"],
            "crs": mosaic_meta["crs"],
            "width_m": width_m,
            "height_m": height_m,
            "aspect_ratio_error": aspect_ratio_error,
        },
        "coverage": scan["coverage"],
        "seam_delta": scan["seam_delta"],
        "source_match": source_match,
    }
    out = args.mosaic_dir / "validation_report.json"
    out.write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(out)
    print(json.dumps({"status": status, "checks": checks}, indent=2))
    return 0 if status in {"pass", "pass_with_notes"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
