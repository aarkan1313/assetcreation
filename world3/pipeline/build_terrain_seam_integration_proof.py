#!/usr/bin/env python3
"""Build terrain seam-integration proof artifacts.

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

try:
    from scipy import ndimage
except Exception:  # pragma: no cover - optional speed/quality path
    ndimage = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MACRO = ROOT / "textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png"
DEFAULT_MASK = ROOT / "textures/source_stack/gloss_scrub_source_stack/source_macro_valid_mask.png"
DEFAULT_HEIGHT = ROOT / "toporeview/gloss_mountain_textured_master/heightmap.png"
DEFAULT_META = ROOT / "toporeview/gloss_mountain_textured_master/meta.json"
DEFAULT_TEXTURE_OUT = ROOT / "textures/source_stack/gloss_scrub_seam_integration_proof"
DEFAULT_TOPO_OUT = ROOT / "toporeview/gloss_mountain_seam_integration_proof"
DEFAULT_METRICS = ROOT / "docs/captures/review/terrain_seam_integration_gloss_metrics.json"
LUMA_WEIGHTS = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


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


def gaussian_rgb(arr: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0.0:
        return arr
    img = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="RGB")
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32) / 255.0


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


def resize_array(arr: np.ndarray, out_size: tuple[int, int] | None, resampling: int) -> np.ndarray:
    if out_size is None:
        return arr
    out_w, out_h = out_size
    if arr.shape[1] == out_w and arr.shape[0] == out_h:
        return arr
    mode = "RGB" if arr.ndim == 3 else "F"
    if arr.ndim == 3:
        img = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode=mode)
        return np.asarray(img.resize((out_w, out_h), resampling), dtype=np.float32) / 255.0
    img = Image.fromarray(arr.astype(np.float32), mode=mode)
    return np.asarray(img.resize((out_w, out_h), resampling), dtype=np.float32)


def _connected_components(mask: np.ndarray) -> list[tuple[int, int, int, int, int, bool]]:
    """Return (area, min_x, min_y, max_x, max_y, touches_border) for true islands."""
    if not mask.any():
        return []

    if ndimage is not None:
        labels, count = ndimage.label(mask, structure=np.ones((3, 3), dtype=np.uint8))
        objects = ndimage.find_objects(labels)
        h, w = mask.shape
        comps: list[tuple[int, int, int, int, int, bool]] = []
        for label_index, slices in enumerate(objects, start=1):
            if slices is None:
                continue
            ys, xs = slices
            component = labels[slices] == label_index
            area = int(np.count_nonzero(component))
            min_y = int(ys.start)
            max_y = int(ys.stop - 1)
            min_x = int(xs.start)
            max_x = int(xs.stop - 1)
            touches = min_x == 0 or min_y == 0 or max_x == w - 1 or max_y == h - 1
            comps.append((area, min_x, min_y, max_x, max_y, touches))
        comps.sort(reverse=True, key=lambda item: item[0])
        return comps

    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    comps = []
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys, xs):
        if seen[y, x]:
            continue
        stack = [(int(y), int(x))]
        seen[y, x] = True
        area = 0
        min_x = w
        max_x = 0
        min_y = h
        max_y = 0
        touches = False
        while stack:
            cy, cx = stack.pop()
            area += 1
            min_x = min(min_x, cx)
            max_x = max(max_x, cx)
            min_y = min(min_y, cy)
            max_y = max(max_y, cy)
            if cx == 0 or cy == 0 or cx == w - 1 or cy == h - 1:
                touches = True
            for ny in range(cy - 1, cy + 2):
                for nx in range(cx - 1, cx + 2):
                    if ny == cy and nx == cx:
                        continue
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        comps.append((area, min_x, min_y, max_x, max_y, touches))
    comps.sort(reverse=True, key=lambda item: item[0])
    return comps


def _nearest_fill_rgb(rgb: np.ndarray, repair_mask: np.ndarray) -> np.ndarray:
    if not repair_mask.any():
        return rgb

    out = np.array(rgb, copy=True)
    if ndimage is not None:
        indices = ndimage.distance_transform_edt(
            repair_mask,
            return_distances=False,
            return_indices=True,
        )
        nearest = rgb[tuple(indices)]
        out[repair_mask] = nearest[repair_mask]
    else:
        grown = ~repair_mask
        for _ in range(max(rgb.shape[:2]) * 2):
            if grown.all():
                break
            next_grown = grown.copy()
            neighbor_sum = np.zeros_like(out)
            neighbor_count = np.zeros(repair_mask.shape, dtype=np.float32)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    src_y0 = max(0, -dy)
                    src_y1 = repair_mask.shape[0] - max(0, dy)
                    src_x0 = max(0, -dx)
                    src_x1 = repair_mask.shape[1] - max(0, dx)
                    dst_y0 = max(0, dy)
                    dst_y1 = repair_mask.shape[0] - max(0, -dy)
                    dst_x0 = max(0, dx)
                    dst_x1 = repair_mask.shape[1] - max(0, -dx)
                    src_valid = grown[src_y0:src_y1, src_x0:src_x1]
                    target = (~grown[dst_y0:dst_y1, dst_x0:dst_x1]) & src_valid
                    if target.any():
                        dst_sum = neighbor_sum[dst_y0:dst_y1, dst_x0:dst_x1]
                        dst_count = neighbor_count[dst_y0:dst_y1, dst_x0:dst_x1]
                        dst_grown = next_grown[dst_y0:dst_y1, dst_x0:dst_x1]
                        dst_sum[target] += out[src_y0:src_y1, src_x0:src_x1][target]
                        dst_count[target] += 1.0
                        dst_grown[target] = True
            fill = repair_mask & (neighbor_count > 0)
            if fill.any():
                out[fill] = neighbor_sum[fill] / neighbor_count[fill, None]
            if np.array_equal(next_grown, grown):
                break
            grown = next_grown
    return np.clip(out, 0.0, 1.0)


def repair_dark_spots(
    rgb: np.ndarray,
    valid_mask: np.ndarray | None,
    *,
    threshold: float,
    min_area_px: int,
    max_area_px: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    if threshold <= 0.0:
        return rgb, {"enabled": False}

    gray = np.tensordot(rgb, LUMA_WEIGHTS, axes=([2], [0])).astype(np.float32)
    candidate = gray <= threshold
    if valid_mask is not None:
        candidate &= valid_mask >= 0.98

    comps = _connected_components(candidate)
    selected = [
        comp for comp in comps
        if min_area_px <= comp[0] <= max_area_px and not comp[5]
    ]
    repair_mask = np.zeros(candidate.shape, dtype=bool)
    for area, min_x, min_y, max_x, max_y, _touches in selected:
        del area
        patch = candidate[min_y:max_y + 1, min_x:max_x + 1]
        repair_mask[min_y:max_y + 1, min_x:max_x + 1] |= patch

    repaired = _nearest_fill_rgb(rgb, repair_mask)
    repaired_gray = np.tensordot(repaired, LUMA_WEIGHTS, axes=([2], [0])).astype(np.float32)
    metrics = {
        "enabled": True,
        "threshold_luma01": float(threshold),
        "min_area_px": int(min_area_px),
        "max_area_px": int(max_area_px),
        "candidate_components": int(len(comps)),
        "candidate_pixels": int(np.count_nonzero(candidate)),
        "selected_components": int(len(selected)),
        "selected_pixels": int(np.count_nonzero(repair_mask)),
        "largest_selected_area_px": int(max((comp[0] for comp in selected), default=0)),
        "input_dark_fraction": float(np.mean(candidate)),
        "output_dark_fraction": float(np.mean(repaired_gray <= threshold)),
    }
    return repaired, metrics


def parse_size(value: str) -> tuple[int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 2:
        raise ValueError("size must be width,height")
    w, h = parts
    if w <= 0 or h <= 0:
        raise ValueError("size width/height must be positive")
    return w, h


def crop_height_from_macro_space(
    height_m: np.ndarray,
    macro_size: tuple[int, int],
    crop: tuple[int, int, int, int],
    out_size: tuple[int, int] | None = None,
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
    target_size = out_size if out_size is not None else (w, h)
    img = Image.fromarray(crop_m.astype(np.float32), mode="F")
    img = img.resize(target_size, Image.Resampling.BILINEAR)
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
    band_mode: str,
    bridge_blur_px: float,
    bridge_detail_strength: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    if left.shape != right.shape:
        raise ValueError(f"left/right RGB shapes differ: {left.shape} vs {right.shape}")
    if overlap_px <= 1 or overlap_px >= left.shape[1]:
        raise ValueError("overlap_px must be > 1 and smaller than crop width")

    a = left[:, -overlap_px:, :]
    b_raw = right[:, :overlap_px, :]
    diff = a - b_raw
    global_bias = np.median(diff.reshape(-1, 3), axis=0).astype(np.float32)

    right_matched = np.array(right, copy=True)
    feather_px = max(0, min(right_feather_px, right.shape[1]))
    if feather_px > 0:
        t = smoothstep(np.linspace(0.0, 1.0, feather_px, dtype=np.float32))[None, :, None]
        decay = 1.0 - t
        right_matched[:, :feather_px, :] = np.clip(
            right[:, :feather_px, :] + global_bias[None, None, :] * decay,
            0.0,
            1.0,
        )
    else:
        right_matched = np.clip(right + global_bias[None, None, :], 0.0, 1.0)

    b = right_matched[:, :overlap_px, :]
    t = smoothstep((np.arange(overlap_px, dtype=np.float32) + 0.5) / float(overlap_px))[None, :, None]
    if band_mode == "lowpass_bridge":
        a_low = gaussian_rgb(a, bridge_blur_px)
        b_low = gaussian_rgb(b, bridge_blur_px)
        band = a_low * (1.0 - t) + b_low * t
        if bridge_detail_strength > 0.0:
            a_detail = a - a_low
            b_detail = b - b_low
            detail = (a_detail * (1.0 - t) + b_detail * t) * bridge_detail_strength
            band = np.clip(band + detail, 0.0, 1.0)
    else:
        band = a * (1.0 - t) + b * t
    out = np.concatenate([left[:, :-overlap_px, :], band, right_matched[:, overlap_px:, :]], axis=1)
    left_width = left.shape[1] - overlap_px

    metrics = {
        "raw_overlap_delta_rgb01": stats(diff),
        "band_mode": band_mode,
        "bridge_blur_px": float(bridge_blur_px),
        "bridge_detail_strength": float(bridge_detail_strength),
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


def _arg_path(primary: Path | None, fallback: Path) -> Path:
    return primary if primary is not None else fallback


def _source_bundle(args: argparse.Namespace, side: str) -> dict[str, Any]:
    macro_path = _arg_path(getattr(args, f"{side}_macro"), args.macro)
    mask_path = _arg_path(getattr(args, f"{side}_valid_mask"), args.valid_mask)
    height_path = _arg_path(getattr(args, f"{side}_heightmap"), args.heightmap)
    meta_path = _arg_path(getattr(args, f"{side}_meta"), args.meta)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    macro = load_rgb(macro_path)
    mask = load_mask(mask_path)
    height_m = load_height_m(height_path, meta)
    return {
        "macro_path": macro_path,
        "mask_path": mask_path,
        "height_path": height_path,
        "meta_path": meta_path,
        "meta": meta,
        "macro": macro,
        "mask": mask,
        "height_m": height_m,
    }


def _crop_world_size(meta: dict[str, Any], macro_size: tuple[int, int], crop: tuple[int, int, int, int]) -> tuple[float, float]:
    macro_w, macro_h = macro_size
    world_x = float(meta.get("world_size_x_m", meta.get("world_size_m", 1.0)))
    world_z = float(meta.get("world_size_z_m", meta.get("world_size_m", 1.0)))
    return world_x * (crop[2] / float(macro_w)), world_z * (crop[3] / float(macro_h))


def write_outputs(args: argparse.Namespace) -> dict[str, Any]:
    left_source = _source_bundle(args, "left")
    right_source = _source_bundle(args, "right")
    left_macro = left_source["macro"]
    right_macro = right_source["macro"]
    left_macro_h, left_macro_w = left_macro.shape[:2]
    right_macro_h, right_macro_w = right_macro.shape[:2]

    left_crop = parse_crop(args.left_crop)
    right_crop = parse_crop(args.right_crop)
    output_size = parse_size(args.output_size) if args.output_size else None
    if output_size is None and left_crop[2:] != right_crop[2:]:
        raise ValueError("left and right crops must have matching width/height")
    target_crop_w, target_crop_h = output_size if output_size is not None else left_crop[2:]

    left_rgb = resize_array(crop_array(left_macro, left_crop), output_size, Image.Resampling.BILINEAR)
    right_rgb = resize_array(crop_array(right_macro, right_crop), output_size, Image.Resampling.BILINEAR)
    left_mask = resize_array(crop_array(left_source["mask"], left_crop), output_size, Image.Resampling.BILINEAR)
    right_mask = resize_array(crop_array(right_source["mask"], right_crop), output_size, Image.Resampling.BILINEAR)
    left_h = crop_height_from_macro_space(left_source["height_m"], (left_macro_w, left_macro_h), left_crop, output_size)
    right_h = crop_height_from_macro_space(right_source["height_m"], (right_macro_w, right_macro_h), right_crop, output_size)

    dark_spot_metrics: dict[str, Any] = {
        "side": args.dark_spot_repair_side,
        "left": {"enabled": False},
        "right": {"enabled": False},
    }
    if args.dark_spot_repair_side in ("left", "both"):
        left_rgb, dark_spot_metrics["left"] = repair_dark_spots(
            left_rgb,
            left_mask,
            threshold=args.dark_spot_threshold,
            min_area_px=args.dark_spot_min_area_px,
            max_area_px=args.dark_spot_max_area_px,
        )
    if args.dark_spot_repair_side in ("right", "both"):
        right_rgb, dark_spot_metrics["right"] = repair_dark_spots(
            right_rgb,
            right_mask,
            threshold=args.dark_spot_threshold,
            min_area_px=args.dark_spot_min_area_px,
            max_area_px=args.dark_spot_max_area_px,
        )

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
        args.macro_band_mode,
        args.macro_bridge_blur_px,
        args.macro_bridge_detail_strength,
    )
    mask_out, mask_metrics = integrate_mask(left_mask, right_mask, args.overlap_px)
    if float(mask_out.mean()) >= args.fill_valid_mask_above:
        mask_out[:, :] = 1.0
        mask_metrics["output_coverage_before_hole_fill"] = mask_metrics["output_coverage"]
        mask_metrics["output_coverage"] = 1.0
        mask_metrics["hole_fill_policy"] = (
            f"filled_to_full_valid_because_coverage_above_{args.fill_valid_mask_above:.4f}"
        )

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
    left_width = target_crop_w - args.overlap_px
    seam_mask[:, left_width : left_width + args.overlap_px] = 1.0
    Image.fromarray(np.clip(seam_mask * 255.0, 0, 255).astype(np.uint8), mode="L").save(seam_mask_path)
    Image.fromarray(np.clip(height_norm * 65535.0, 0, 65535).astype(np.uint16), mode="I;16").save(height_path)

    left_crop_world_x, left_crop_world_z = _crop_world_size(left_source["meta"], (left_macro_w, left_macro_h), left_crop)
    right_crop_world_x, right_crop_world_z = _crop_world_size(right_source["meta"], (right_macro_w, right_macro_h), right_crop)
    avg_mpp_x = ((left_crop_world_x / float(target_crop_w)) + (right_crop_world_x / float(target_crop_w))) * 0.5
    avg_mpp_z = ((left_crop_world_z / float(target_crop_h)) + (right_crop_world_z / float(target_crop_h))) * 0.5
    out_meta = dict(left_source["meta"])
    out_meta.update(
        {
            "name": args.artifact_name,
            "builder": "build_terrain_seam_integration_proof.py",
            "heightmap_size_px": [int(out_w), int(out_h)],
            "world_size_x_m": avg_mpp_x * float(out_w),
            "world_size_z_m": avg_mpp_z * float(out_h),
            "world_size_m": max(avg_mpp_x * float(out_w), avg_mpp_z * float(out_h)),
            "elevation_min_m": output_elev_min,
            "elevation_max_m": output_elev_max,
            "elevation_range_m": output_elev_range,
            "terrain_seam_integration": {
                "version": 1,
                "kind": args.integration_kind,
                "left_source_macro": res_path(left_source["macro_path"]),
                "left_source_heightmap": res_path(left_source["height_path"]),
                "right_source_macro": res_path(right_source["macro_path"]),
                "right_source_heightmap": res_path(right_source["height_path"]),
                "left_crop_macro_px": list(left_crop),
                "right_crop_macro_px": list(right_crop),
                "target_crop_size_px": [int(target_crop_w), int(target_crop_h)],
                "overlap_px": args.overlap_px,
                "integration_band_world_m": avg_mpp_x * float(args.overlap_px),
                "left_crop_world_m": [left_crop_world_x, left_crop_world_z],
                "right_crop_world_m": [right_crop_world_x, right_crop_world_z],
                "policy": args.policy,
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
            "macro": res_path(left_source["macro_path"]),
            "valid_mask": res_path(left_source["mask_path"]),
            "heightmap": res_path(left_source["height_path"]),
            "meta": res_path(left_source["meta_path"]),
            "crop_macro_px": list(left_crop),
            "crop_world_m": [left_crop_world_x, left_crop_world_z],
        },
        "right_source": {
            "macro": res_path(right_source["macro_path"]),
            "valid_mask": res_path(right_source["mask_path"]),
            "heightmap": res_path(right_source["height_path"]),
            "meta": res_path(right_source["meta_path"]),
            "crop_macro_px": list(right_crop),
            "crop_world_m": [right_crop_world_x, right_crop_world_z],
        },
        "integration": {
            "overlap_px": args.overlap_px,
            "height_feather_px": args.height_feather_px,
            "color_feather_px": args.color_feather_px,
            "profile_blur_px": args.profile_blur_px,
            "macro_band_mode": args.macro_band_mode,
            "macro_bridge_blur_px": args.macro_bridge_blur_px,
            "macro_bridge_detail_strength": args.macro_bridge_detail_strength,
            "dark_spot_repair_side": args.dark_spot_repair_side,
            "dark_spot_threshold": args.dark_spot_threshold,
            "dark_spot_min_area_px": args.dark_spot_min_area_px,
            "dark_spot_max_area_px": args.dark_spot_max_area_px,
            "left_output_width_px": left_width,
            "integration_band_output_px": args.overlap_px,
            "right_output_width_px": target_crop_w - args.overlap_px,
            "target_crop_size_px": [int(target_crop_w), int(target_crop_h)],
        },
        "metrics": {
            "height_m": height_metrics,
            "macro_rgb01": rgb_metrics,
            "valid_mask": mask_metrics,
            "dark_spot_repair": dark_spot_metrics,
        },
        "policy": args.policy,
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
    parser.add_argument("--left-macro", type=Path)
    parser.add_argument("--left-valid-mask", type=Path)
    parser.add_argument("--left-heightmap", type=Path)
    parser.add_argument("--left-meta", type=Path)
    parser.add_argument("--right-macro", type=Path)
    parser.add_argument("--right-valid-mask", type=Path)
    parser.add_argument("--right-heightmap", type=Path)
    parser.add_argument("--right-meta", type=Path)
    parser.add_argument("--texture-out", type=Path, default=DEFAULT_TEXTURE_OUT)
    parser.add_argument("--topo-out", type=Path, default=DEFAULT_TOPO_OUT)
    parser.add_argument("--metrics-out", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--left-crop", default="240,520,416,1024")
    parser.add_argument("--right-crop", default="592,520,416,1024")
    parser.add_argument("--output-size", default="")
    parser.add_argument("--overlap-px", type=int, default=64)
    parser.add_argument("--height-feather-px", type=int, default=128)
    parser.add_argument("--color-feather-px", type=int, default=96)
    parser.add_argument("--profile-blur-px", type=float, default=12.0)
    parser.add_argument("--macro-band-mode", choices=["blend", "lowpass_bridge"], default="blend")
    parser.add_argument("--macro-bridge-blur-px", type=float, default=28.0)
    parser.add_argument("--macro-bridge-detail-strength", type=float, default=0.0)
    parser.add_argument(
        "--dark-spot-repair-side",
        choices=["none", "left", "right", "both"],
        default="none",
        help="Opt-in repair for valid interior dark islands after crop/resize.",
    )
    parser.add_argument(
        "--dark-spot-threshold",
        type=float,
        default=18.0 / 255.0,
        help="Luma threshold in 0..1 for dark-island repair candidates.",
    )
    parser.add_argument("--dark-spot-min-area-px", type=int, default=4)
    parser.add_argument("--dark-spot-max-area-px", type=int, default=5000)
    parser.add_argument("--fill-valid-mask-above", type=float, default=0.995)
    parser.add_argument("--artifact-name", default="Gloss Mountain terrain seam integration proof")
    parser.add_argument("--integration-kind", default="overlap_integration_band_proof")
    parser.add_argument(
        "--policy",
        default="adjacent_overlap_sources_solved_into_single_runtime_bundle",
    )
    args = parser.parse_args()

    manifest = write_outputs(args)
    print(json.dumps(manifest["metrics"], indent=2))
    print(f"wrote {args.texture_out}")
    print(f"wrote {args.topo_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
