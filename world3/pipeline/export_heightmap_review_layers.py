"""Export diagnostic Godot review layers from a 16-bit heightmap + meta.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling


def normalize(values: np.ndarray, low: float = 2.0, high: float = 98.0) -> np.ndarray:
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


def ramp_color(values: np.ndarray, ramp: np.ndarray) -> np.ndarray:
    values = np.clip(values, 0.0, 1.0)
    pos = values * (len(ramp) - 1)
    lo = np.floor(pos).astype(np.int32)
    hi = np.clip(lo + 1, 0, len(ramp) - 1)
    t = (pos - lo)[..., None]
    return ramp[lo] * (1.0 - t) + ramp[hi] * t


def read_raster_to_shape(path: Path, shape: tuple[int, int]) -> tuple[np.ndarray, float | None]:
    with rasterio.open(path) as src:
        arr = src.read(1, out_shape=shape, resampling=Resampling.bilinear)
        nodata = src.nodata
    return arr.astype(np.float32), nodata


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heightmap", required=True, type=Path)
    ap.add_argument("--meta", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--terrain-style", choices=["appalachian", "rock", "alpine", "sandstone"], default="appalachian")
    ap.add_argument("--coverage-raster", type=Path)
    ap.add_argument("--seam-raster", type=Path)
    args = ap.parse_args()

    Image.MAX_IMAGE_PIXELS = None
    args.output_dir.mkdir(parents=True, exist_ok=True)
    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    img = Image.open(args.heightmap)
    raw = np.asarray(img, dtype=np.float32)
    if raw.max(initial=0) > 0:
        norm = raw / 65535.0
    else:
        norm = raw
    elev_min = float(meta["elevation_min_m"])
    elev_range = float(meta["elevation_range_m"])
    elev = elev_min + norm * elev_range

    world_x = float(meta.get("world_size_x_m", meta.get("world_size_m", raw.shape[1])))
    world_z = float(meta.get("world_size_z_m", meta.get("world_size_m", raw.shape[0])))
    dx = world_x / max(raw.shape[1] - 1, 1)
    dz = world_z / max(raw.shape[0] - 1, 1)

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
    hillshade = np.clip(shaded * 255.0, 0, 255).astype(np.uint8)

    slope_y, slope_x = np.gradient(slope_deg, dz, dx)
    roughness = np.sqrt(slope_x * slope_x + slope_y * slope_y).astype(np.float32)

    Image.fromarray((norm * 255.0).clip(0, 255).astype(np.uint8), mode="L").save(args.output_dir / "elevation_gray.png")
    Image.fromarray(hillshade, mode="L").save(args.output_dir / "hillshade.png")
    Image.fromarray(np.clip(slope_deg / 70.0 * 255.0, 0, 255).astype(np.uint8), mode="L").save(args.output_dir / "slope_deg.png")
    Image.fromarray(normalize(roughness), mode="L").save(args.output_dir / "roughness.png")

    if args.terrain_style == "appalachian":
        ramp = np.array(
            [
                [47, 71, 44],
                [66, 95, 51],
                [93, 116, 67],
                [128, 126, 80],
                [153, 135, 91],
                [119, 113, 105],
                [205, 202, 188],
            ],
            dtype=np.float32,
        ) / 255.0
    elif args.terrain_style == "rock":
        ramp = np.array(
            [[74, 58, 44], [116, 88, 61], [158, 124, 78], [188, 168, 126], [214, 210, 190]],
            dtype=np.float32,
        ) / 255.0
    elif args.terrain_style == "alpine":
        ramp = np.array(
            [
                [43, 69, 49],
                [67, 92, 55],
                [105, 104, 75],
                [130, 119, 96],
                [144, 141, 132],
                [193, 193, 184],
                [238, 240, 238],
            ],
            dtype=np.float32,
        ) / 255.0
    else:
        ramp = np.array(
            [
                [83, 67, 48],
                [119, 82, 53],
                [154, 101, 63],
                [185, 134, 83],
                [205, 166, 111],
                [181, 171, 146],
                [214, 210, 190],
            ],
            dtype=np.float32,
        ) / 255.0

    color = ramp_color(norm, ramp)
    cliff = np.clip((slope_deg - 32.0) / 30.0, 0.0, 1.0) ** 1.25
    rock = np.array([0.50, 0.49, 0.45], dtype=np.float32)
    color = color * (1.0 - cliff[..., None] * 0.45) + rock * cliff[..., None] * 0.45
    shade = 0.48 + (hillshade.astype(np.float32) / 255.0)[..., None] * 0.70
    detail = (normalize(roughness).astype(np.float32) / 255.0 - 0.5)[..., None] * 0.12
    color = np.clip(color * shade + detail, 0.0, 1.0)
    Image.fromarray((color * 255.0).astype(np.uint8), mode="RGB").save(args.output_dir / "terrain_texture.png")

    qa_layers: list[str] = []
    if args.coverage_raster:
        coverage, nodata = read_raster_to_shape(args.coverage_raster, raw.shape)
        valid_coverage = np.isfinite(coverage)
        if nodata is not None:
            valid_coverage &= coverage != nodata
        max_count = float(max(coverage[valid_coverage].max(initial=1.0), 1.0)) if valid_coverage.any() else 1.0
        coverage_img = np.zeros(coverage.shape, dtype=np.uint8)
        coverage_img[valid_coverage] = np.clip(coverage[valid_coverage] / max_count * 255.0, 0, 255).astype(np.uint8)
        Image.fromarray(coverage_img, mode="L").save(args.output_dir / "coverage_count.png")
        qa_layers.append("coverage_count")
    if args.seam_raster:
        seam, nodata = read_raster_to_shape(args.seam_raster, raw.shape)
        valid_seam = np.isfinite(seam)
        if nodata is not None:
            valid_seam &= seam != nodata
        seam_img = np.zeros(seam.shape, dtype=np.uint8)
        if valid_seam.any():
            seam_abs = np.abs(seam)
            hi = max(float(np.nanpercentile(seam_abs[valid_seam], 99.0)), 0.25)
            seam_img[valid_seam] = np.clip(seam_abs[valid_seam] / hi * 255.0, 0, 255).astype(np.uint8)
        Image.fromarray(seam_img, mode="L").save(args.output_dir / "seam_delta.png")
        qa_layers.append("seam_delta")

    sidecar = {
        "heightmap": str(args.heightmap),
        "meta": str(args.meta),
        "output_dir": str(args.output_dir),
        "mode": "procedural_review_layers_from_heightmap",
        "not_real_imagery": True,
        "size_px": [int(raw.shape[1]), int(raw.shape[0])],
        "world_size_x_m": world_x,
        "world_size_z_m": world_z,
        "terrain_style": args.terrain_style,
        "qa_layers": qa_layers,
    }
    (args.output_dir / "review_layers.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(f"OK {args.output_dir} ({raw.shape[1]}x{raw.shape[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
