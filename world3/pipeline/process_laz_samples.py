"""Process downloaded LAS/LAZ samples into summaries and raster products.

Outputs per sample:
    summary.json
    points_sample.csv
    dtm_ground.tif                  ground-class minimum elevation grid
    dsm_surface.tif                 non-noise maximum elevation grid
    surface_minus_ground_raw.tif    DSM minus classified-ground DTM, if possible
    chm_vegetation.tif              class 3/4/5 vegetation height, if possible
    surface_minus_external_dtm.tif  DSM minus matching external DTM, if found
    canopy_like_external_dtm.tif    gated DSM minus external DTM
    rgb_topdown.tif/png             RGB from highest point per cell, if present
    nir_topdown.tif                 true LAS NIR from highest point per cell, if present

Requires:
    pip install laspy lazrs pyproj pillow
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import laspy
import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject


ROOT = Path(__file__).resolve().parents[1]
POINT_ROOT = ROOT / "opentopo" / "raw" / "pointcloud"
DATASPACE_ROOT = ROOT / "opentopo" / "raw" / "dataspace"
OUT_ROOT = ROOT / "opentopo" / "processed" / "pointcloud"

CLASS_NAMES = {
    0: "created_never_classified",
    1: "unclassified",
    2: "ground",
    3: "low_vegetation",
    4: "medium_vegetation",
    5: "high_vegetation",
    6: "building",
    7: "low_point_noise",
    8: "model_key_point",
    9: "water",
    10: "rail",
    11: "road_surface",
    12: "overlap",
    13: "wire_guard",
    14: "wire_conductor",
    15: "transmission_tower",
    16: "wire_connector",
    17: "bridge_deck",
    18: "high_noise",
}


def safe_name(path: Path) -> str:
    return path.stem


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def counter_dict(counter: Counter[int], names: dict[int, str] | None = None) -> dict[str, int]:
    out = {}
    for key, value in sorted(counter.items()):
        label = f"{key}"
        if names and key in names:
            label = f"{key}_{names[key]}"
        out[label] = int(value)
    return out


def update_counter(counter: Counter[int], values: np.ndarray) -> None:
    if values.size == 0:
        return
    keys, counts = np.unique(values.astype(np.int64), return_counts=True)
    for key, count in zip(keys, counts):
        counter[int(key)] += int(count)


def has_dim(dimensions: set[str], name: str) -> bool:
    return name in dimensions


def get_dim(points: laspy.ScaleAwarePointRecord, dimensions: set[str], name: str, default: int = 0) -> np.ndarray:
    if has_dim(dimensions, name):
        return np.asarray(getattr(points, name))
    return np.full(len(points), default)


def point_count_from_header(header: laspy.LasHeader) -> int:
    return int(getattr(header, "point_count", 0) or 0)


def make_profile(header: laspy.LasHeader, cell_size: float) -> tuple[dict, tuple[int, int], tuple[float, float, float, float]]:
    min_x, min_y, min_z = [float(v) for v in header.mins]
    max_x, max_y, max_z = [float(v) for v in header.maxs]
    width = max(int(math.ceil((max_x - min_x) / cell_size)) + 1, 1)
    height = max(int(math.ceil((max_y - min_y) / cell_size)) + 1, 1)
    crs = header.parse_crs()
    transform = from_origin(min_x, max_y, cell_size, cell_size)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "nodata": -9999.0,
        "compress": "deflate",
        "tiled": True,
    }
    return profile, (height, width), (min_x, max_y, min_z, max_z)


def rows_cols(
    x: np.ndarray,
    y: np.ndarray,
    min_x: float,
    max_y: float,
    cell_size: float,
    height: int,
    width: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cols = np.clip(((x - min_x) / cell_size).astype(np.int64), 0, width - 1)
    rows = np.clip(((max_y - y) / cell_size).astype(np.int64), 0, height - 1)
    flat = rows * width + cols
    return rows, cols, flat


def update_top_color(
    flat: np.ndarray,
    z: np.ndarray,
    red: np.ndarray,
    green: np.ndarray,
    blue: np.ndarray,
    top_z: np.ndarray,
    top_red: np.ndarray,
    top_green: np.ndarray,
    top_blue: np.ndarray,
) -> None:
    if flat.size == 0:
        return
    order = np.lexsort((z, flat))
    sorted_flat = flat[order]
    group_ends = np.r_[np.where(sorted_flat[1:] != sorted_flat[:-1])[0], len(sorted_flat) - 1]
    top_idx = order[group_ends]
    top_flat = flat[top_idx]
    update = z[top_idx] > top_z[top_flat]
    if not np.any(update):
        return
    target = top_flat[update]
    source = top_idx[update]
    top_z[target] = z[source]
    top_red[target] = red[source]
    top_green[target] = green[source]
    top_blue[target] = blue[source]


def update_top_single(
    flat: np.ndarray,
    z: np.ndarray,
    value: np.ndarray,
    top_z: np.ndarray,
    top_value: np.ndarray,
) -> None:
    if flat.size == 0:
        return
    order = np.lexsort((z, flat))
    sorted_flat = flat[order]
    group_ends = np.r_[np.where(sorted_flat[1:] != sorted_flat[:-1])[0], len(sorted_flat) - 1]
    top_idx = order[group_ends]
    top_flat = flat[top_idx]
    update = z[top_idx] > top_z[top_flat]
    if not np.any(update):
        return
    target = top_flat[update]
    source = top_idx[update]
    top_z[target] = z[source]
    top_value[target] = value[source]


def write_float_tif(path: Path, arr: np.ndarray, profile: dict) -> None:
    data = np.where(np.isfinite(arr), arr, -9999.0).astype(np.float32)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)


def write_float_preview(path: Path, arr: np.ndarray, high_hint: float | None = None) -> str | None:
    valid = np.isfinite(arr)
    if not np.any(valid):
        return None
    values = arr[valid]
    low = 0.0 if float(np.nanmin(values)) >= 0 else float(np.nanpercentile(values, 2))
    pct_high = float(np.nanpercentile(values, 98))
    high = min(high_hint, pct_high) if high_hint is not None else pct_high
    if high <= low:
        high = float(np.nanmax(values))
    if high <= low:
        high = low + 1.0
    norm = np.zeros(arr.shape, dtype=np.uint8)
    norm[valid] = np.clip(np.rint((arr[valid] - low) / (high - low) * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(norm, mode="L").save(path)
    return str(path)


def rgb_to_uint8(rgb: np.ndarray) -> np.ndarray:
    max_value = int(rgb.max()) if rgb.size else 0
    if max_value > 255:
        return np.clip(np.rint(rgb.astype(np.float32) / 257.0), 0, 255).astype(np.uint8)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def write_rgb_products(
    out_dir: Path,
    profile: dict,
    valid: np.ndarray,
    red: np.ndarray,
    green: np.ndarray,
    blue: np.ndarray,
    height: int,
    width: int,
) -> dict[str, str]:
    if not np.any(valid):
        return {}

    rgb = np.zeros((3, height, width), dtype=np.uint16)
    rgb[0].flat[valid] = red[valid].astype(np.uint16)
    rgb[1].flat[valid] = green[valid].astype(np.uint16)
    rgb[2].flat[valid] = blue[valid].astype(np.uint16)

    tif_path = out_dir / "rgb_topdown.tif"
    tif_profile = profile.copy()
    tif_profile.update({"count": 3, "dtype": "uint16", "nodata": None})
    with rasterio.open(tif_path, "w", **tif_profile) as dst:
        dst.write(rgb)

    png_path = out_dir / "rgb_topdown.png"
    png = np.moveaxis(rgb_to_uint8(rgb), 0, -1)
    Image.fromarray(png, mode="RGB").save(png_path)
    return {"rgb_topdown_tif": str(tif_path), "rgb_topdown_png": str(png_path)}


def write_nir_product(
    out_dir: Path,
    profile: dict,
    valid: np.ndarray,
    nir: np.ndarray,
    height: int,
    width: int,
) -> dict[str, str]:
    if not np.any(valid):
        return {}
    arr = np.zeros((height, width), dtype=np.uint16)
    arr.flat[valid] = nir[valid].astype(np.uint16)
    path = out_dir / "nir_topdown.tif"
    nir_profile = profile.copy()
    nir_profile.update({"dtype": "uint16", "nodata": 0})
    with rasterio.open(path, "w", **nir_profile) as dst:
        dst.write(arr, 1)
    return {"nir_topdown_tif": str(path)}


def external_dtm_for_source(source: str) -> Path | None:
    folder = DATASPACE_ROOT / source
    if not folder.exists():
        return None
    candidates = [
        path for path in sorted(folder.glob("*.tif"))
        if "DTM" in path.name.upper() and "HILLSHADE" not in path.name.upper()
    ]
    return candidates[0] if candidates else None


def write_external_dtm_products(
    out_dir: Path,
    profile: dict,
    dsm: np.ndarray,
    source: str,
    max_canopy_height: float,
) -> dict:
    dtm_path = external_dtm_for_source(source)
    if dtm_path is None:
        return {}

    external = np.full(dsm.shape, np.nan, dtype=np.float32)
    with rasterio.open(dtm_path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=external,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=profile["transform"],
            dst_crs=profile["crs"],
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )

    raw = np.where(np.isfinite(dsm) & np.isfinite(external), np.maximum(dsm - external, 0.0), np.nan).astype(np.float32)
    gated = np.where(raw <= max_canopy_height, raw, np.nan).astype(np.float32)
    raw_path = out_dir / "surface_minus_external_dtm.tif"
    gated_path = out_dir / "canopy_like_external_dtm.tif"
    raw_preview = out_dir / "surface_minus_external_dtm_preview.png"
    gated_preview = out_dir / "canopy_like_external_dtm_preview.png"
    write_float_tif(raw_path, raw, profile)
    write_float_tif(gated_path, gated, profile)
    raw_preview_out = write_float_preview(raw_preview, raw, max_canopy_height)
    gated_preview_out = write_float_preview(gated_preview, gated, max_canopy_height)
    return {
        "external_dtm": str(dtm_path),
        "surface_minus_external_dtm": str(raw_path),
        "canopy_like_external_dtm": str(gated_path),
        "surface_minus_external_dtm_preview_png": raw_preview_out,
        "canopy_like_external_dtm_preview_png": gated_preview_out,
        "surface_minus_external_dtm_valid_cells": int(np.isfinite(raw).sum()),
        "surface_minus_external_dtm_max_m": float(np.nanmax(raw)) if np.isfinite(raw).any() else None,
        "surface_minus_external_dtm_mean_m": float(np.nanmean(raw)) if np.isfinite(raw).any() else None,
        "canopy_like_external_dtm_valid_cells": int(np.isfinite(gated).sum()),
        "canopy_like_external_dtm_max_m": float(np.nanmax(gated)) if np.isfinite(gated).any() else None,
        "canopy_like_external_dtm_mean_m": float(np.nanmean(gated)) if np.isfinite(gated).any() else None,
        "canopy_like_external_dtm_p95_m": float(np.nanpercentile(gated, 95)) if np.isfinite(gated).any() else None,
        "canopy_like_external_dtm_rejected_cells_above_max": int(np.isfinite(raw).sum() - np.isfinite(gated).sum()),
    }


def sample_row(points: laspy.ScaleAwarePointRecord, dimensions: set[str], i: int) -> dict:
    row = {
        "x": float(points.x[i]),
        "y": float(points.y[i]),
        "z": float(points.z[i]),
        "classification": int(points.classification[i]) if has_dim(dimensions, "classification") else "",
        "intensity": int(points.intensity[i]) if has_dim(dimensions, "intensity") else "",
        "return_number": int(points.return_number[i]) if has_dim(dimensions, "return_number") else "",
        "number_of_returns": int(points.number_of_returns[i]) if has_dim(dimensions, "number_of_returns") else "",
        "gps_time": float(points.gps_time[i]) if has_dim(dimensions, "gps_time") else "",
    }
    if all(has_dim(dimensions, name) for name in ("red", "green", "blue")):
        row.update({
            "red": int(points.red[i]),
            "green": int(points.green[i]),
            "blue": int(points.blue[i]),
        })
    if has_dim(dimensions, "nir"):
        row["nir"] = int(points.nir[i])
    return row


def write_point_csv(path: Path, rows: list[dict]) -> None:
    base = ["x", "y", "z", "classification", "intensity", "return_number", "number_of_returns", "gps_time"]
    extras = []
    for name in ("red", "green", "blue", "nir"):
        if any(name in row for row in rows):
            extras.append(name)
    fieldnames = base + extras
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def summarize_laz(path: Path, cell_size: float, sample_count: int, max_canopy_height: float, chunk_size: int) -> dict:
    source = path.parent.name
    out_dir = OUT_ROOT / source / safe_name(path)
    out_dir.mkdir(parents=True, exist_ok=True)

    with laspy.open(path) as reader:
        header = reader.header
        dimensions = set(header.point_format.dimension_names)
        point_count = point_count_from_header(header)
        profile, shape, bounds = make_profile(header, cell_size)
        height, width = shape
        min_x, max_y, min_z, max_z = bounds

        dsm = np.full((height, width), -np.inf, dtype=np.float32)
        dtm = np.full((height, width), np.inf, dtype=np.float32)
        veg_surface = np.full((height, width), -np.inf, dtype=np.float32)

        has_rgb = all(has_dim(dimensions, name) for name in ("red", "green", "blue"))
        has_nir = has_dim(dimensions, "nir")
        flat_size = height * width
        rgb_z = np.full(flat_size, -np.inf, dtype=np.float32)
        rgb_red = np.zeros(flat_size, dtype=np.uint16)
        rgb_green = np.zeros(flat_size, dtype=np.uint16)
        rgb_blue = np.zeros(flat_size, dtype=np.uint16)
        nir_z = np.full(flat_size, -np.inf, dtype=np.float32)
        nir_value = np.zeros(flat_size, dtype=np.uint16)

        class_counts: Counter[int] = Counter()
        return_counts: Counter[int] = Counter()
        number_of_returns_counts: Counter[int] = Counter()
        intensity_min: int | None = None
        intensity_max: int | None = None
        intensity_sum = 0
        intensity_count = 0
        intensity_sample: list[int] = []
        rgb_min = [None, None, None]
        rgb_max = [None, None, None]
        rgb_sum = [0, 0, 0]
        rgb_count = 0
        sample_rows: list[dict] = []
        sample_stride = max(point_count // max(sample_count, 1), 1) if point_count else 1
        stat_stride = max(point_count // 100000, 1) if point_count else 1

        offset = 0
        for points in reader.chunk_iterator(chunk_size):
            n = len(points)
            x = np.asarray(points.x)
            y = np.asarray(points.y)
            z = np.asarray(points.z).astype(np.float32)
            cls = get_dim(points, dimensions, "classification", 0).astype(np.uint8)
            rows, cols, flat = rows_cols(x, y, min_x, max_y, cell_size, height, width)

            update_counter(class_counts, cls)
            if has_dim(dimensions, "return_number"):
                update_counter(return_counts, np.asarray(points.return_number))
            if has_dim(dimensions, "number_of_returns"):
                update_counter(number_of_returns_counts, np.asarray(points.number_of_returns))
            if has_dim(dimensions, "intensity"):
                intensity = np.asarray(points.intensity)
                if intensity.size:
                    mn = int(np.min(intensity))
                    mx = int(np.max(intensity))
                    intensity_min = mn if intensity_min is None else min(intensity_min, mn)
                    intensity_max = mx if intensity_max is None else max(intensity_max, mx)
                    intensity_sum += int(np.sum(intensity, dtype=np.int64))
                    intensity_count += int(intensity.size)
                    global_indices = np.arange(offset, offset + n, dtype=np.int64)
                    stat_take = np.where((global_indices % stat_stride) == 0)[0]
                    if stat_take.size:
                        intensity_sample.extend(int(v) for v in intensity[stat_take[: max(0, 100000 - len(intensity_sample))]])

            noise = np.isin(cls, [7, 18])
            surface = ~noise
            if np.any(surface):
                np.maximum.at(dsm, (rows[surface], cols[surface]), z[surface])

            ground = cls == 2
            if np.any(ground):
                np.minimum.at(dtm, (rows[ground], cols[ground]), z[ground])

            vegetation = np.isin(cls, [3, 4, 5])
            if np.any(vegetation):
                np.maximum.at(veg_surface, (rows[vegetation], cols[vegetation]), z[vegetation])

            if has_rgb:
                red = np.asarray(points.red).astype(np.uint16)
                green = np.asarray(points.green).astype(np.uint16)
                blue = np.asarray(points.blue).astype(np.uint16)
                for idx, arr in enumerate((red, green, blue)):
                    mn = int(np.min(arr))
                    mx = int(np.max(arr))
                    rgb_min[idx] = mn if rgb_min[idx] is None else min(int(rgb_min[idx]), mn)
                    rgb_max[idx] = mx if rgb_max[idx] is None else max(int(rgb_max[idx]), mx)
                    rgb_sum[idx] += int(np.sum(arr, dtype=np.uint64))
                rgb_count += int(red.size)
                update_top_color(flat[surface], z[surface], red[surface], green[surface], blue[surface], rgb_z, rgb_red, rgb_green, rgb_blue)

            if has_nir:
                nir = np.asarray(points.nir).astype(np.uint16)
                update_top_single(flat[surface], z[surface], nir[surface], nir_z, nir_value)

            if len(sample_rows) < sample_count:
                global_indices = np.arange(offset, offset + n, dtype=np.int64)
                take = np.where((global_indices % sample_stride) == 0)[0]
                remaining = sample_count - len(sample_rows)
                for raw_i in take[:remaining]:
                    sample_rows.append(sample_row(points, dimensions, int(raw_i)))

            offset += n

    dsm[dsm == -np.inf] = np.nan
    dtm[dtm == np.inf] = np.nan
    veg_surface[veg_surface == -np.inf] = np.nan

    nsm_raw = np.where(np.isfinite(dsm) & np.isfinite(dtm), np.maximum(dsm - dtm, 0.0), np.nan).astype(np.float32)
    chm_raw = np.where(np.isfinite(veg_surface) & np.isfinite(dtm), np.maximum(veg_surface - dtm, 0.0), np.nan).astype(np.float32)
    chm = np.where(chm_raw <= max_canopy_height, chm_raw, np.nan).astype(np.float32)

    paths = {
        "dtm_ground": out_dir / "dtm_ground.tif",
        "dsm_surface": out_dir / "dsm_surface.tif",
        "surface_minus_ground_raw": out_dir / "surface_minus_ground_raw.tif",
        "chm_vegetation": out_dir / "chm_vegetation.tif",
    }
    for key, arr in [
        ("dtm_ground", dtm),
        ("dsm_surface", dsm),
        ("surface_minus_ground_raw", nsm_raw),
        ("chm_vegetation", chm),
    ]:
        write_float_tif(paths[key], arr, profile)
    preview_paths = {
        "surface_minus_ground_raw_preview_png": write_float_preview(out_dir / "surface_minus_ground_raw_preview.png", nsm_raw, max_canopy_height),
        "chm_vegetation_preview_png": write_float_preview(out_dir / "chm_vegetation_preview.png", chm, max_canopy_height),
    }

    color_paths: dict[str, str] = {}
    if has_rgb:
        color_paths.update(write_rgb_products(out_dir, profile, np.isfinite(rgb_z), rgb_red, rgb_green, rgb_blue, height, width))
    if has_nir:
        color_paths.update(write_nir_product(out_dir, profile, np.isfinite(nir_z), nir_value, height, width))

    external_products = write_external_dtm_products(out_dir, profile, dsm, source, max_canopy_height)

    csv_path = out_dir / "points_sample.csv"
    write_point_csv(csv_path, sample_rows)

    intensity = {
        "min": intensity_min,
        "max": intensity_max,
        "mean": (float(intensity_sum) / intensity_count) if intensity_count else None,
        "p95_sample": float(np.percentile(np.asarray(intensity_sample), 95)) if intensity_sample else None,
    }
    rgb_stats = None
    if has_rgb and rgb_count:
        rgb_stats = {
            "min": [int(v) if v is not None else None for v in rgb_min],
            "max": [int(v) if v is not None else None for v in rgb_max],
            "mean": [float(v) / rgb_count for v in rgb_sum],
        }

    summary = {
        "source": source,
        "path": str(path),
        "bytes": path.stat().st_size,
        "las_version": f"{header.version.major}.{header.version.minor}",
        "point_format": header.point_format.id,
        "point_count": point_count,
        "dimensions": list(header.point_format.dimension_names),
        "has_rgb": has_rgb,
        "has_nir": has_nir,
        "has_gps_time": has_dim(dimensions, "gps_time"),
        "has_classification": has_dim(dimensions, "classification"),
        "has_intensity": has_dim(dimensions, "intensity"),
        "bounds": {
            "min_x": float(header.mins[0]),
            "max_x": float(header.maxs[0]),
            "min_y": float(header.mins[1]),
            "max_y": float(header.maxs[1]),
            "min_z": float(header.mins[2]),
            "max_z": float(header.maxs[2]),
        },
        "classification_counts": counter_dict(class_counts, CLASS_NAMES),
        "return_number_counts": counter_dict(return_counts),
        "number_of_returns_counts": counter_dict(number_of_returns_counts),
        "intensity": intensity,
        "rgb": rgb_stats,
        "crs": str(header.parse_crs()),
        "raster_products": {
            "cell_size_m": cell_size,
            "width": width,
            "height": height,
            "paths": {key: str(value) for key, value in paths.items()},
            **{key: value for key, value in preview_paths.items() if value is not None},
            **color_paths,
            "dtm_valid_cells": int(np.isfinite(dtm).sum()),
            "dsm_valid_cells": int(np.isfinite(dsm).sum()),
            "surface_minus_ground_raw_valid_cells": int(np.isfinite(nsm_raw).sum()),
            "surface_minus_ground_raw_max_m": float(np.nanmax(nsm_raw)) if np.isfinite(nsm_raw).any() else None,
            "surface_minus_ground_raw_mean_m": float(np.nanmean(nsm_raw)) if np.isfinite(nsm_raw).any() else None,
            "chm_valid_cells": int(np.isfinite(chm).sum()),
            "chm_max_m": float(np.nanmax(chm)) if np.isfinite(chm).any() else None,
            "chm_mean_m": float(np.nanmean(chm)) if np.isfinite(chm).any() else None,
            "chm_max_canopy_height_m": max_canopy_height,
            "chm_rejected_cells_above_max": int(np.isfinite(chm_raw).sum() - np.isfinite(chm).sum()),
            **external_products,
        },
        "points_sample_csv": str(csv_path),
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def selected_paths(source: str | None) -> list[Path]:
    paths = sorted(POINT_ROOT.rglob("*.la?"))
    if source:
        wanted = {part.strip() for part in source.split(",") if part.strip()}
        paths = [path for path in paths if path.parent.name in wanted]
    return paths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell-size", type=float, default=2.0, help="output raster cell size in source units/meters")
    ap.add_argument("--sample-count", type=int, default=5000, help="point sample CSV row limit")
    ap.add_argument("--max-canopy-height", type=float, default=120.0, help="reject canopy cells above this height")
    ap.add_argument("--chunk-size", type=int, default=1_000_000, help="points per streaming chunk")
    ap.add_argument("--source", default=None, help="optional comma list of source folders under raw/pointcloud")
    args = ap.parse_args()

    summaries = []
    for path in selected_paths(args.source):
        summary = summarize_laz(path, args.cell_size, args.sample_count, args.max_canopy_height, args.chunk_size)
        summaries.append(summary)
        products = summary["raster_products"]
        print(
            f"{summary['source']}/{Path(summary['path']).name}: "
            f"points={summary['point_count']} rgb={summary['has_rgb']} nir={summary['has_nir']} "
            f"classes={summary['classification_counts']} "
            f"external_canopy_max={products.get('canopy_like_external_dtm_max_m')}"
        )

    out = OUT_ROOT / "pointcloud_summary.json"
    existing = []
    if out.exists() and args.source:
        existing = json.loads(out.read_text(encoding="utf-8"))
        replaced = {(item["source"], Path(item["path"]).name) for item in summaries}
        existing = [item for item in existing if (item.get("source"), Path(item.get("path", "")).name) not in replaced]
    write_json(out, existing + summaries)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
