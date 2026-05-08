"""Build a textured OpenTopography master stack from a DEM and orthophoto.

This is for datasets where the raw orthophoto is far higher resolution than the
terrain grid. The raw files stay untouched, while the stack gets:
- a lossless-ish aligned master DEM and RGB orthophoto on the DEM grid
- aspect-preserving Godot review heightmap and texture layers
- QA masks/layers that document validity and cliff risk
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageEnhance
from rasterio.coords import BoundingBox
from rasterio.enums import Resampling
from rasterio.fill import fillnodata
from rasterio.transform import array_bounds
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds


MASTER_NODATA = -999999.0


def valid_dem_mask(arr: np.ndarray, nodata: float | None) -> np.ndarray:
    mask = np.isfinite(arr)
    if nodata is not None and np.isfinite(nodata):
        mask &= arr != nodata
    return mask


def repair_dem(arr: np.ndarray, valid: np.ndarray, max_search_distance: float) -> np.ndarray:
    if valid.all():
        return arr.astype(np.float32, copy=True)
    image = arr.astype(np.float32, copy=True)
    finite_valid = image[valid]
    fallback = float(np.nanmedian(finite_valid)) if finite_valid.size else 0.0
    image[~valid] = fallback
    filled = fillnodata(
        image,
        mask=valid.astype(np.uint8),
        max_search_distance=max_search_distance,
        smoothing_iterations=1,
    )
    filled = filled.astype(np.float32, copy=False)
    filled[~np.isfinite(filled)] = fallback
    return filled


def review_shape(world_x: float, world_z: float, max_dim: int) -> tuple[int, int]:
    if world_x <= 0.0 or world_z <= 0.0:
        raise SystemExit("Invalid DEM world dimensions")
    if world_x >= world_z:
        width = max_dim
        height = max(1, int(round(max_dim * world_z / world_x)))
    else:
        height = max_dim
        width = max(1, int(round(max_dim * world_x / world_z)))
    return width, height


def normalize_u8(values: np.ndarray, low: float = 2.0, high: float = 98.0) -> np.ndarray:
    valid = np.isfinite(values)
    if not valid.any():
        return np.zeros(values.shape, dtype=np.uint8)
    lo, hi = np.nanpercentile(values[valid], [low, high])
    if not np.isfinite(lo):
        lo = float(values[valid].min())
    if not np.isfinite(hi) or hi <= lo:
        hi = lo + 1.0
    scaled = (values.astype(np.float32) - float(lo)) / float(hi - lo)
    return np.clip(scaled * 255.0, 0, 255).astype(np.uint8)


def resize_gray(arr: np.ndarray, size: tuple[int, int], mode: str = "L") -> Image.Image:
    return Image.fromarray(arr, mode=mode).resize(size, Image.Resampling.BILINEAR)


def resize_rgb(arr: np.ndarray, size: tuple[int, int]) -> Image.Image:
    return Image.fromarray(arr, mode="RGB").resize(size, Image.Resampling.LANCZOS)


def write_rgb_gtiff(path: Path, rgb: np.ndarray, profile: dict) -> None:
    out_profile = profile.copy()
    out_profile.update(
        {
            "driver": "GTiff",
            "count": 3,
            "dtype": "uint8",
            "nodata": None,
            "compress": "deflate",
            "predictor": 2,
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
            "BIGTIFF": "IF_SAFER",
        }
    )
    with rasterio.open(path, "w", **out_profile) as dst:
        dst.write(np.moveaxis(rgb, -1, 0))


def write_single_gtiff(path: Path, arr: np.ndarray, profile: dict, dtype: str, nodata) -> None:
    out_profile = profile.copy()
    out_profile.update(
        {
            "driver": "GTiff",
            "count": 1,
            "dtype": dtype,
            "nodata": nodata,
            "compress": "deflate",
            "predictor": 2,
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
            "BIGTIFF": "IF_SAFER",
        }
    )
    with rasterio.open(path, "w", **out_profile) as dst:
        dst.write(arr.astype(dtype), 1)


def read_ortho_on_dem_grid(ortho_path: Path, dem_profile: dict, dem_bounds) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(ortho_path) as src:
        window = from_bounds(*dem_bounds, transform=src.transform)
        raw = src.read(
            [1, 2, 3],
            window=window,
            out_shape=(3, int(dem_profile["height"]), int(dem_profile["width"])),
            boundless=True,
            fill_value=0,
            masked=True,
            resampling=Resampling.bilinear,
        )
    mask = np.ma.getmaskarray(raw)
    if mask.ndim == 0:
        valid = np.ones((int(dem_profile["height"]), int(dem_profile["width"])), dtype=bool)
    else:
        valid = ~np.any(mask, axis=0)
    rgb = np.ma.filled(raw, 0).astype(np.uint8)
    return np.moveaxis(rgb, 0, -1), valid


def hillshade(elev: np.ndarray, dx: float, dz: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    gy, gx = np.gradient(elev.astype(np.float32), dz, dx)
    slope_rad = np.arctan(np.sqrt(gx * gx + gy * gy))
    slope_deg = np.degrees(slope_rad).astype(np.float32)
    aspect = np.arctan2(-gx, gy)
    azimuth = np.deg2rad(315.0)
    altitude = np.deg2rad(45.0)
    shaded = (
        np.sin(altitude) * np.cos(slope_rad)
        + np.cos(altitude) * np.sin(slope_rad) * np.cos(azimuth - aspect)
    )
    shade = np.clip(shaded * 255.0, 0, 255).astype(np.uint8)
    slope_y, slope_x = np.gradient(slope_deg, dz, dx)
    roughness = np.sqrt(slope_x * slope_x + slope_y * slope_y).astype(np.float32)
    return shade, slope_deg, roughness


def stats(values: np.ndarray, valid: np.ndarray) -> dict:
    vals = values[valid]
    if vals.size == 0:
        return {"valid_pixels": 0}
    return {
        "valid_pixels": int(vals.size),
        "min": float(vals.min()),
        "max": float(vals.max()),
        "mean": float(vals.mean()),
        "p50": float(np.percentile(vals, 50)),
        "p95": float(np.percentile(vals, 95)),
        "p99": float(np.percentile(vals, 99)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True, type=Path)
    ap.add_argument("--orthophoto", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--review-max-dim", type=int, default=8192)
    ap.add_argument("--fill-distance-px", type=float, default=64.0)
    ap.add_argument("--texture-fill-distance-px", type=float, default=1024.0)
    ap.add_argument("--material", default="real_orthophoto")
    ap.add_argument("--crop-to-valid-dem", action="store_true")
    ap.add_argument("--crop-margin-px", type=int, default=0)
    args = ap.parse_args()

    Image.MAX_IMAGE_PIXELS = None
    args.output_dir.mkdir(parents=True, exist_ok=True)
    master_dir = args.output_dir / "master"
    layer_dir = args.output_dir / "layers"
    qa_dir = args.output_dir / "qa"
    for directory in (master_dir, layer_dir, qa_dir):
        directory.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.dem) as dem_src:
        dem = dem_src.read(1).astype(np.float32)
        dem_profile = dem_src.profile.copy()
        source_crs = str(dem_src.crs)
        nodata = dem_src.nodata
        dem_res = dem_src.res
        raw_valid = valid_dem_mask(dem, nodata)
        crop_window = None
        if args.crop_to_valid_dem:
            if not raw_valid.any():
                raise SystemExit("DEM contains no valid pixels")
            ys, xs = np.where(raw_valid)
            margin = max(args.crop_margin_px, 0)
            x0 = max(int(xs.min()) - margin, 0)
            x1 = min(int(xs.max()) + margin + 1, dem_src.width)
            y0 = max(int(ys.min()) - margin, 0)
            y1 = min(int(ys.max()) + margin + 1, dem_src.height)
            crop_window = Window(x0, y0, x1 - x0, y1 - y0)
            dem = dem[y0:y1, x0:x1]
            dem_profile.update(
                {
                    "height": int(crop_window.height),
                    "width": int(crop_window.width),
                    "transform": dem_src.window_transform(crop_window),
                }
            )
        else:
            dem_profile.update({"height": dem_src.height, "width": dem_src.width, "transform": dem_src.transform})
        left, bottom, right, top = array_bounds(
            int(dem_profile["height"]),
            int(dem_profile["width"]),
            dem_profile["transform"],
        )
        dem_bounds = BoundingBox(left, bottom, right, top)
        dem_bounds_wgs84 = transform_bounds(dem_src.crs, "EPSG:4326", *dem_bounds, densify_pts=21)

    source_valid = valid_dem_mask(dem, nodata)
    repaired = repair_dem(dem, source_valid, args.fill_distance_px)
    if not source_valid.any():
        raise SystemExit("DEM contains no valid pixels")
    elev_min = float(repaired[source_valid].min())
    elev_max = float(repaired[source_valid].max())
    elev_range = max(elev_max - elev_min, 1.0)
    world_x = float(dem_bounds.right - dem_bounds.left)
    world_z = float(dem_bounds.top - dem_bounds.bottom)
    review_w, review_h = review_shape(world_x, world_z, args.review_max_dim)

    aligned_rgb, ortho_valid = read_ortho_on_dem_grid(args.orthophoto, dem_profile, dem_bounds)

    dem_master_profile = dem_profile.copy()
    dem_master_profile.update({"nodata": MASTER_NODATA})
    write_single_gtiff(master_dir / "dem_repaired_float32.tif", repaired, dem_master_profile, "float32", MASTER_NODATA)
    write_single_gtiff(master_dir / "source_valid_mask.tif", source_valid.astype(np.uint8), dem_profile, "uint8", 0)
    write_rgb_gtiff(master_dir / "orthophoto_rgb_aligned_to_dem.tif", aligned_rgb, dem_profile)
    write_single_gtiff(master_dir / "texture_coverage_mask.tif", ortho_valid.astype(np.uint8), dem_profile, "uint8", 0)

    dem_review = np.array(
        Image.fromarray(repaired.astype(np.float32), mode="F").resize((review_w, review_h), Image.Resampling.BILINEAR),
        dtype=np.float32,
    )
    valid_review = np.array(
        Image.fromarray(source_valid.astype(np.uint8) * 255, mode="L").resize((review_w, review_h), Image.Resampling.NEAREST),
        dtype=np.uint8,
    )
    ortho_valid_review = np.array(
        Image.fromarray(ortho_valid.astype(np.uint8) * 255, mode="L").resize((review_w, review_h), Image.Resampling.NEAREST),
        dtype=np.uint8,
    )
    norm = np.clip((dem_review - elev_min) / elev_range, 0.0, 1.0)
    Image.fromarray((norm * 65535.0).astype(np.uint16), mode="I;16").save(args.output_dir / "heightmap.png")

    rgb_review_img = resize_rgb(aligned_rgb, (review_w, review_h))
    rgb_review_img.save(layer_dir / "orthophoto_rgb.png")

    render_arr = np.asarray(rgb_review_img, dtype=np.float32).copy()
    render_fill_mask = ortho_valid_review == 0
    if render_fill_mask.any() and np.any(~render_fill_mask):
        fill_mask = (~render_fill_mask).astype(np.uint8)
        for channel in range(3):
            render_arr[..., channel] = fillnodata(
                render_arr[..., channel],
                mask=fill_mask,
                max_search_distance=args.texture_fill_distance_px,
                smoothing_iterations=0,
            )
    render_arr = np.clip(render_arr, 0, 255).astype(np.uint8)
    render_img = Image.fromarray(render_arr, mode="RGB")
    render_img = ImageEnhance.Contrast(render_img).enhance(1.08)
    render_img = ImageEnhance.Color(render_img).enhance(1.06)
    render_img.save(layer_dir / "render_albedo.png")

    shade, slope_deg, roughness = hillshade(
        dem_review,
        world_x / max(review_w - 1, 1),
        world_z / max(review_h - 1, 1),
    )
    Image.fromarray(shade, mode="L").save(layer_dir / "hillshade.png")
    Image.fromarray(np.clip(slope_deg / 70.0 * 255.0, 0, 255).astype(np.uint8), mode="L").save(layer_dir / "slope_deg.png")
    Image.fromarray(normalize_u8(roughness), mode="L").save(layer_dir / "roughness.png")
    Image.fromarray((norm * 255.0).astype(np.uint8), mode="L").save(layer_dir / "elevation_gray.png")
    Image.fromarray(valid_review, mode="L").save(layer_dir / "source_valid_mask.png")
    Image.fromarray(ortho_valid_review, mode="L").save(layer_dir / "texture_coverage_mask.png")
    Image.fromarray((render_fill_mask.astype(np.uint8) * 255), mode="L").save(layer_dir / "render_fill_mask.png")
    cliff_mask = np.clip((slope_deg - 38.0) / 24.0, 0.0, 1.0)
    Image.fromarray((cliff_mask * 255.0).astype(np.uint8), mode="L").save(layer_dir / "cliff_mask.png")

    meta = {
        "name": args.name,
        "builder": "build_opentopo_textured_master_stack.py",
        "source_dem": str(args.dem),
        "source_orthophoto": str(args.orthophoto),
        "source_crs": source_crs,
        "source_bounds": {
            "left": float(dem_bounds.left),
            "bottom": float(dem_bounds.bottom),
            "right": float(dem_bounds.right),
            "top": float(dem_bounds.top),
        },
        "source_bounds_wgs84": {
            "west": float(dem_bounds_wgs84[0]),
            "south": float(dem_bounds_wgs84[1]),
            "east": float(dem_bounds_wgs84[2]),
            "north": float(dem_bounds_wgs84[3]),
        },
        "source_resolution_m": {"x": float(dem_res[0]), "y": float(dem_res[1])},
        "heightmap_size_px": [review_w, review_h],
        "elevation_min_m": elev_min,
        "elevation_max_m": elev_max,
        "elevation_range_m": elev_range,
        "world_size_m": float(min(world_x, world_z)),
        "world_size_x_m": world_x,
        "world_size_z_m": world_z,
        "material": args.material,
        "texture_is_real_imagery": True,
        "review_note": "The review texture is downsampled from the raw orthophoto; the raw 3 cm orthophoto is preserved separately.",
        "crop_to_valid_dem": bool(args.crop_to_valid_dem),
        "crop_margin_px": int(args.crop_margin_px),
    }
    if crop_window is not None:
        meta["crop_window_px"] = {
            "col_off": int(crop_window.col_off),
            "row_off": int(crop_window.row_off),
            "width": int(crop_window.width),
            "height": int(crop_window.height),
        }
    (args.output_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    report = {
        "name": args.name,
        "outputs": {
            "heightmap": "heightmap.png",
            "meta": "meta.json",
            "master_dem": "master/dem_repaired_float32.tif",
            "master_orthophoto": "master/orthophoto_rgb_aligned_to_dem.tif",
            "layers": sorted(path.name for path in layer_dir.glob("*.png")),
        },
        "stats": {
            "dem": stats(repaired, source_valid),
            "source_valid_percent": float(source_valid.sum() * 100.0 / source_valid.size),
            "orthophoto_coverage_percent": float(ortho_valid.sum() * 100.0 / ortho_valid.size),
            "render_fill_review_percent": float(render_fill_mask.sum() * 100.0 / render_fill_mask.size),
            "cliff_mask_review_percent_gt_0": float((cliff_mask > 0.0).sum() * 100.0 / cliff_mask.size),
        },
        "compression_policy": "raw orthophoto retained; aligned master is compressed GeoTIFF; Godot review layers are PNG downsampled for rendering.",
    }
    (qa_dir / "textured_master_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.output_dir / "stack_manifest.json").write_text(
        json.dumps(
            {
                "name": args.name,
                "builder": "build_opentopo_textured_master_stack.py",
                "target_crs": source_crs,
                "target_bounds": meta["source_bounds"],
                "target_cell_size_m": float(dem_res[0]),
                "target_width": int(dem_profile["width"]),
                "target_height": int(dem_profile["height"]),
                "vertical_datum": "source metadata",
                "base_height_layer": "dem_repaired_float32",
                "layers": [
                    {"name": "dem_repaired_float32", "path": "master/dem_repaired_float32.tif", "role": "base_height"},
                    {"name": "source_valid_mask", "path": "master/source_valid_mask.tif", "role": "qa"},
                    {"name": "orthophoto_rgb_aligned_to_dem", "path": "master/orthophoto_rgb_aligned_to_dem.tif", "role": "real_texture"},
                    {"name": "texture_coverage_mask", "path": "master/texture_coverage_mask.tif", "role": "qa"},
                    {"name": "raw_orthophoto", "path": str(args.orthophoto), "role": "preserved_highest_resolution_texture_source"},
                ],
                "review_layers": report["outputs"]["layers"],
                "known_limits": [
                    "Review scene uses a downsampled orthophoto layer for interactivity.",
                    "Vertical cliff faces are not photogrammetric side geometry; they need mesh/texture repair if exposed at close range.",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"OK {args.output_dir}")
    print(f"review {review_w}x{review_h}, world {world_x:.1f} x {world_z:.1f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
