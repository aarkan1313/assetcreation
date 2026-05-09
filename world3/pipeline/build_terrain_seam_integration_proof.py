#!/usr/bin/env python3
"""Build the first terrain seam-integration proof artifact.

This is intentionally not a tile-wrap tool. It takes two adjacent/overlapping
source bundles, builds a world-space integration band, and writes a single
runtime bundle that Godot can inspect as one continuous terrain source.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MACRO = ROOT / "textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png"
DEFAULT_MASK = ROOT / "textures/source_stack/gloss_scrub_source_stack/source_macro_valid_mask.png"
DEFAULT_HEIGHT = ROOT / "toporeview/gloss_mountain_textured_master/heightmap.png"
DEFAULT_META = ROOT / "toporeview/gloss_mountain_textured_master/meta.json"
DEFAULT_TEXTURE_OUT = ROOT / "textures/source_stack/gloss_scrub_seam_integration_proof"
DEFAULT_TOPO_OUT = ROOT / "toporeview/gloss_mountain_seam_integration_proof"
DEFAULT_METRICS = ROOT / "docs/captures/review/terrain_seam_integration_gloss_metrics.json"


def smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def parse_crop(value: str) -> tuple[int, int, int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("crop must be x,y,width,height")
    x, y, w, h = parts
    if w <= 0 or h <= 0:
        raise ValueError("crop width/height must be positive")
    return x, y, w, h


def res_path(path: Path) -> str:
    rel = path.resolve().relative_to(ROOT.resolve())
    return "res://" + rel.as_posix()


def load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


def load_mask(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("L"), dtype=np.float32) / 255.0


def load_height_m(path: Path, meta: dict[str, Any]) -> np.ndarray:
    img = Image.open(path)
    arr = np.asarray(img)
    if arr.ndim == 3:
        arr = arr[:, :, 0]
    arr_f = arr.astype(np.float32)
    max_value = 65535.0 if np.issubdtype(arr.dtype, np.integer) else max(float(arr_f.max()), 1.0)
    norm = np.clip(arr_f / max_value, 0.0, 1.0)
    elev_min = float(meta.get("elevation_min_m", 0.0))
    elev_range = float(meta.get("elevation_range_m", 1.0))
    return elev_min + norm * elev_range


def crop_array(arr: np.ndarray, crop: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = crop
    if x < 0 or y < 0 or x + w > arr.shape[1] or y + h > arr.shape[0]:
        raise ValueError(f"crop {crop} outside array {arr.shape[1]}x{arr.shape[0]}")
    return arr[y : y + h, x : x + w].copy()


def crop_height_from_macro_space(
    height_m: np.ndarray,
    macro_size: tuple[int, int],
    crop: tuple[int, int, int, int],
) -> np.ndarray:
    macro_w, macro_h = macro_size
    x, y, w, h = crop
    height_h, height_w = height_m.shape
    hx0 = int(round((x / macro_w) * height_w))
    hy0 = int(round((y / macro_h) * height_h))
    hx1 = int(round(((x + w) / macro_w) * height_w))
    hy1 = int(round(((y + h) / macro_h) * height_h))
    hx0 = max(0, min(hx0, height_w - 1))
    hy0 = max(0, min(hy0, height_h - 1))
    hx1 = max(hx0 + 1, min(hx1, height_w))
    hy1 = max(hy0 + 1, min(hy1, height_h))
    crop_m = height_m[hy0:hy1, hx0:hx1]
    img = Image.fromarray(crop_m.astype(np.float32), mode="F")
    img = img.resize((w, h), Image.Resampling.BILINEAR)
    return np.asarray(img, dtype=np.float32)


def blur_rows(values: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0.0:
        return values
    sigma = max(float(radius), 0.001)
    kernel_radius = max(1, int(round(sigma * 3.0)))
    x = np.arange(-kernel_radius, kernel_radius + 1, dtype=np.float32)
    kernel = np.exp(-(x * x) / (2.0 * sigma * sigma))
    kernel /= np.sum(kernel)
    padded = np.pad(values.astype(np.float32), (kernel_radius, kernel_radius), mode="edge")
    return np.convolve(padded, kernel, mode="valid").astype(np.float32)


def stats(values: np.ndarray) -> dict[str, float]:
    flat = np.abs(values).astype(np.float64).ravel()
    if flat.size == 0:
        return {"mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "mean": float(np.mean(flat)),
        "median": float(np.median(flat)),
        "p95": float(np.percentile(flat, 95)),
        "max": float(np.max(flat)),
    }


def seam_step_stats(arr: np.ndarray, left_width: int, band_width: int) -> dict[str, dict[str, float]]:
    left_join = left_width - 1
    right_join = left_width + band_width - 1
    return {
        "left_to_band": stats(arr[:, left_join + 1] - arr[:, left_join]),
        "band_to_right": stats(arr[:, right_join + 1] - arr[:, right_join]),
    }


def integrate_scalar(
    left: np.ndarray,
    right: np.ndarray,
    overlap_px: int,
    right_feather_px: int,
    profile_blur_px: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    if left.shape != right.shape:
        raise ValueError(f"left/right scalar shapes differ: {left.shape} vs {right.shape}")
    if overlap_px <= 1 or overlap_px >= left.shape[1]:
        raise ValueError("overlap_px must be > 1 and smaller than crop width")

    a = left[:, -overlap_px:]
    b_raw = right[:, :overlap_px]
    diff = a - b_raw
    global_bias = float(np.median(diff))
    row_bias = blur_rows(np.median(diff - global_bias, axis=1), profile_blur_px)

    right_matched = right + global_bias
    feather_px = max(0, min(right_feather_px, right.shape[1]))
    if feather_px > 0:
        t = smoothstep(np.linspace(0.0, 1.0, feather_px, dtype=np.float32))[None, :]
        decay = 1.0 - t
        right_matched[:, :feather_px] += row_bias[:, None] * decay

    b = right_matched[:, :overlap_px]
    t = smoothstep((np.arange(overlap_px, dtype=np.float32) + 0.5) / float(overlap_px))[None, :]
    band = a * (1.0 - t) + b * t
    out = np.concatenate([left[:, :-overlap_px], band, right_matched[:, overlap_px:]], axis=1)
    left_width = left.shape[1] - overlap_px

    metrics = {
        "raw_overlap_delta": stats(diff),
        "global_bias": global_bias,
        "row_bias": stats(row_bias),
        "post_overlap_delta": stats(a - b),
        "post_join_steps": seam_step_stats(out, left_width, overlap_px),
    }
    return out, metrics


def integrate_rgb(
    left: np.ndarray,
    right: np.ndarray,
    overlap_px: int,
    right_feather_px: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    if left.shape != right.shape:
        raise ValueError(f"left/right RGB shapes differ: {left.shape} vs {right.shape}")
    if overlap_px <= 1 or overlap_px >= left.shape[1]:
        raise ValueError("overlap_px must be > 1 and smaller than crop width")

    a = left[:, -overlap_px:, :]
    b_raw = right[:, :overlap_px, :]
    diff = a - b_raw
    global_bias = np.median(diff.reshape(-1, 3), axis=0).astype(np.float32)

    right_matched = np.clip(right + global_bias[None, None, :], 0.0, 1.0)
    feather_px = max(0, min(right_feather_px, right.shape[1]))
    if feather_px > 0:
        t = smoothstep(np.linspace(0.0, 1.0, feather_px, dtype=np.float32))[None, :, None]
        decay = 1.0 - t
        right_matched[:, :feather_px, :] = np.clip(
            right[:, :feather_px, :] + global_bias[None, None, :] * decay,
            0.0,
            1.0,
        )

    b = right_matched[:, :overlap_px, :]
    t = smoothstep((np.arange(overlap_px, dtype=np.float32) + 0.5) / float(overlap_px))[None, :, None]
    band = a * (1.0 - t) + b * t
    out = np.concatenate([left[:, :-overlap_px, :], band, right_matched[:, overlap_px:, :]], axis=1)
    left_width = left.shape[1] - overlap_px

    metrics = {
        "raw_overlap_delta_rgb01": stats(diff),
        "global_bias_rgb01": [float(v) for v in global_bias],
        "post_overlap_delta_rgb01": stats(a - b),
        "post_join_steps_rgb01": seam_step_stats(out.mean(axis=2), left_width, overlap_px),
    }
    return out, metrics


def integrate_mask(left: np.ndarray, right: np.ndarray, overlap_px: int) -> tuple[np.ndarray, dict[str, Any]]:
    if left.shape != right.shape:
        raise ValueError(f"left/right mask shapes differ: {left.shape} vs {right.shape}")
    a = left[:, -overlap_px:]
    b = right[:, :overlap_px]
    t = smoothstep((np.arange(overlap_px, dtype=np.float32) + 0.5) / float(overlap_px))[None, :]
    band = np.minimum(a, b) * 0.75 + (a * (1.0 - t) + b * t) * 0.25
    out = np.concatenate([left[:, :-overlap_px], band, right[:, overlap_px:]], axis=1)
    return out, {
        "left_coverage": float(left.mean()),
        "right_coverage": float(right.mean()),
        "band_coverage": float(band.mean()),
        "output_coverage": float(out.mean()),
    }


def write_outputs(args: argparse.Namespace) -> dict[str, Any]:
    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    macro = load_rgb(args.macro)
    mask = load_mask(args.valid_mask)
    height_m = load_height_m(args.heightmap, meta)
    macro_h, macro_w = macro.shape[:2]

    left_crop = parse_crop(args.left_crop)
    right_crop = parse_crop(args.right_crop)
    if left_crop[2:] != right_crop[2:]:
        raise ValueError("left and right crops must have matching width/height")

    left_rgb = crop_array(macro, left_crop)
    right_rgb = crop_array(macro, right_crop)
    left_mask = crop_array(mask, left_crop)
    right_mask = crop_array(mask, right_crop)
    left_h = crop_height_from_macro_space(height_m, (macro_w, macro_h), left_crop)
    right_h = crop_height_from_macro_space(height_m, (macro_w, macro_h), right_crop)

    height_out, height_metrics = integrate_scalar(
        left_h,
        right_h,
        args.overlap_px,
        args.height_feather_px,
        args.profile_blur_px,
    )
    rgb_out, rgb_metrics = integrate_rgb(
        left_rgb,
        right_rgb,
        args.overlap_px,
        args.color_feather_px,
    )
    mask_out, mask_metrics = integrate_mask(left_mask, right_mask, args.overlap_px)

    out_h, out_w = height_out.shape
    output_elev_min = float(np.min(height_out))
    output_elev_max = float(np.max(height_out))
    output_elev_range = max(output_elev_max - output_elev_min, 0.001)
    height_norm = np.clip((height_out - output_elev_min) / output_elev_range, 0.0, 1.0)

    args.texture_out.mkdir(parents=True, exist_ok=True)
    args.topo_out.mkdir(parents=True, exist_ok=True)
    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)

    macro_path = args.texture_out / "source_macro_albedo.png"
    mask_path = args.texture_out / "source_macro_valid_mask.png"
    seam_mask_path = args.texture_out / "seam_integration_mask.png"
    height_path = args.topo_out / "heightmap.png"
    meta_path = args.topo_out / "meta.json"
    manifest_path = args.texture_out / "manifest.json"

    Image.fromarray(np.clip(rgb_out * 255.0, 0, 255).astype(np.uint8), mode="RGB").save(macro_path)
    Image.fromarray(np.clip(mask_out * 255.0, 0, 255).astype(np.uint8), mode="L").save(mask_path)

    seam_mask = np.zeros((out_h, out_w), dtype=np.float32)
    left_width = left_crop[2] - args.overlap_px
    seam_mask[:, left_width : left_width + args.overlap_px] = 1.0
    Image.fromarray(np.clip(seam_mask * 255.0, 0, 255).astype(np.uint8), mode="L").save(seam_mask_path)
    Image.fromarray(np.clip(height_norm * 65535.0, 0, 65535).astype(np.uint16), mode="I;16").save(height_path)

    source_world_x = float(meta.get("world_size_x_m", meta.get("world_size_m", 1.0)))
    source_world_z = float(meta.get("world_size_z_m", meta.get("world_size_m", 1.0)))
    out_meta = dict(meta)
    out_meta.update(
        {
            "name": "Gloss Mountain terrain seam integration proof",
            "heightmap_size_px": [int(out_w), int(out_h)],
            "world_size_x_m": source_world_x * (out_w / float(macro_w)),
            "world_size_z_m": source_world_z * (out_h / float(macro_h)),
            "world_size_m": max(
                source_world_x * (out_w / float(macro_w)),
                source_world_z * (out_h / float(macro_h)),
            ),
            "elevation_min_m": output_elev_min,
            "elevation_max_m": output_elev_max,
            "elevation_range_m": output_elev_range,
            "terrain_seam_integration": {
                "version": 1,
                "kind": "overlap_integration_band_proof",
                "source_macro": res_path(args.macro),
                "source_heightmap": res_path(args.heightmap),
                "left_crop_macro_px": list(left_crop),
                "right_crop_macro_px": list(right_crop),
                "overlap_px": args.overlap_px,
                "integration_band_world_m": (
                    source_world_x * (args.overlap_px / float(macro_w))
                ),
                "policy": "adjacent_overlap_sources_solved_into_single_runtime_bundle",
            },
        }
    )
    meta_path.write_text(json.dumps(out_meta, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "version": 1,
        "kind": "terrain_seam_integration_proof",
        "id": args.texture_out.name,
        "runtime_macro": res_path(macro_path),
        "runtime_source_macro_valid_mask": res_path(mask_path),
        "runtime_seam_mask": res_path(seam_mask_path),
        "runtime_heightmap": res_path(height_path),
        "runtime_meta": res_path(meta_path),
        "left_source": {
            "macro": res_path(args.macro),
            "heightmap": res_path(args.heightmap),
            "crop_macro_px": list(left_crop),
        },
        "right_source": {
            "macro": res_path(args.macro),
            "heightmap": res_path(args.heightmap),
            "crop_macro_px": list(right_crop),
        },
        "integration": {
            "overlap_px": args.overlap_px,
            "height_feather_px": args.height_feather_px,
            "color_feather_px": args.color_feather_px,
            "profile_blur_px": args.profile_blur_px,
            "left_output_width_px": left_width,
            "integration_band_output_px": args.overlap_px,
            "right_output_width_px": right_crop[2] - args.overlap_px,
        },
        "metrics": {
            "height_m": height_metrics,
            "macro_rgb01": rgb_metrics,
            "valid_mask": mask_metrics,
        },
        "policy": "production_path_proof_not_tile_wrap",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    args.metrics_out.write_text(json.dumps(manifest["metrics"], indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--macro", type=Path, default=DEFAULT_MACRO)
    parser.add_argument("--valid-mask", type=Path, default=DEFAULT_MASK)
    parser.add_argument("--heightmap", type=Path, default=DEFAULT_HEIGHT)
    parser.add_argument("--meta", type=Path, default=DEFAULT_META)
    parser.add_argument("--texture-out", type=Path, default=DEFAULT_TEXTURE_OUT)
    parser.add_argument("--topo-out", type=Path, default=DEFAULT_TOPO_OUT)
    parser.add_argument("--metrics-out", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--left-crop", default="240,520,416,1024")
    parser.add_argument("--right-crop", default="592,520,416,1024")
    parser.add_argument("--overlap-px", type=int, default=64)
    parser.add_argument("--height-feather-px", type=int, default=128)
    parser.add_argument("--color-feather-px", type=int, default=96)
    parser.add_argument("--profile-blur-px", type=float, default=12.0)
    args = parser.parse_args()

    manifest = write_outputs(args)
    print(json.dumps(manifest["metrics"], indent=2))
    print(f"wrote {args.texture_out}")
    print(f"wrote {args.topo_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
