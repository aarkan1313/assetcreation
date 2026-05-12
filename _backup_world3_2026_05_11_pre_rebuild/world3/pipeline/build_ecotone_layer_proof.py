#!/usr/bin/env python3
"""Build a data-first M10 unlike-biome ecotone proof.

This intentionally does not extend the RGB seam bridge. It emits layer data
first, then derives a review macro from those layers:

- biome A / biome B / ecotone weights;
- material-weight masks;
- feature and future scatter masks;
- a continuous heightmap and a macro preview for Godot review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import build_procedural_neighbor_bundle as procedural
import build_source_stack_runtime_review as source_review


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEFT_MACRO = ROOT / "textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png"
DEFAULT_LEFT_MASK = ROOT / "textures/source_stack/gloss_scrub_source_stack/source_macro_valid_mask.png"
DEFAULT_LEFT_HEIGHT = ROOT / "toporeview/gloss_mountain_textured_master/heightmap.png"
DEFAULT_LEFT_META = ROOT / "toporeview/gloss_mountain_textured_master/meta.json"
DEFAULT_TEXTURE_OUT = ROOT / "textures/source_stack/gloss_grassland_ecotone_layer_proof"
DEFAULT_TOPO_OUT = ROOT / "toporeview/gloss_grassland_ecotone_layer_proof"
DEFAULT_MATERIAL_OUT = ROOT / "textures/wgv3/terrain_ecotone_layer_gloss_grassland.tres"
DEFAULT_CONTACT = ROOT / "docs/captures/review/m10_ecotone_layer_contact_sheet.png"
DEFAULT_METRICS = ROOT / "docs/captures/review/m10_ecotone_layer_metrics.json"


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


def smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def normalize01(arr: np.ndarray, low_pct: float = 1.0, high_pct: float = 99.0) -> np.ndarray:
    low = float(np.percentile(arr, low_pct))
    high = float(np.percentile(arr, high_pct))
    return np.clip((arr - low) / max(high - low, 1e-6), 0.0, 1.0)


def smooth_noise(width: int, height: int, grid: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    small_w = max(2, int(np.ceil(width / max(grid, 1))))
    small_h = max(2, int(np.ceil(height / max(grid, 1))))
    small = rng.normal(0.0, 1.0, (small_h, small_w)).astype(np.float32)
    small = normalize01(small)
    img = Image.fromarray(np.clip(small * 255.0, 0, 255).astype(np.uint8), mode="L")
    img = img.resize((width, height), Image.Resampling.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def gaussian_gray(arr: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0.0:
        return arr
    img = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="L")
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32) / 255.0


def blur_rows(values: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0.0:
        return values
    kernel_radius = max(1, int(round(radius * 3.0)))
    x = np.arange(-kernel_radius, kernel_radius + 1, dtype=np.float32)
    kernel = np.exp(-(x * x) / (2.0 * radius * radius))
    kernel /= np.sum(kernel)
    return np.convolve(values, kernel, mode="same").astype(np.float32)


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


def resize_array(arr: np.ndarray, size: tuple[int, int], resampling: int) -> np.ndarray:
    out_w, out_h = size
    if arr.shape[1] == out_w and arr.shape[0] == out_h:
        return arr
    if arr.ndim == 3:
        img = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="RGB")
        return np.asarray(img.resize((out_w, out_h), resampling), dtype=np.float32) / 255.0
    img = Image.fromarray(arr.astype(np.float32), mode="F")
    return np.asarray(img.resize((out_w, out_h), resampling), dtype=np.float32)


def crop_height_from_macro_space(
    height_m: np.ndarray,
    macro_size: tuple[int, int],
    crop: tuple[int, int, int, int],
    out_size: tuple[int, int],
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
    img = img.resize(out_size, Image.Resampling.BILINEAR)
    return np.asarray(img, dtype=np.float32)


def crop_world_size(meta: dict[str, Any], macro_size: tuple[int, int], crop: tuple[int, int, int, int]) -> tuple[float, float]:
    macro_w, macro_h = macro_size
    world_x = float(meta.get("world_size_x_m", meta.get("world_size_m", 1.0)))
    world_z = float(meta.get("world_size_z_m", meta.get("world_size_m", 1.0)))
    return world_x * (crop[2] / float(macro_w)), world_z * (crop[3] / float(macro_h))


def color_stat(arr: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    pixels = arr.reshape(-1, 3)
    if mask is not None:
        keep = mask.reshape(-1) > 0.25
        if np.any(keep):
            pixels = pixels[keep]
    return np.median(pixels, axis=0).astype(np.float32)


def build_ecotone_fields(
    width: int,
    height: int,
    left_width: int,
    seed: int,
    ecotone_width_px: float,
    boundary_jitter_px: float,
    boundary_diagonal_px: float,
) -> dict[str, np.ndarray]:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x = xx

    rng = np.random.default_rng(seed)
    row = rng.normal(0.0, 1.0, height).astype(np.float32)
    row = blur_rows(row, max(height * 0.055, 18.0))
    row /= max(float(np.max(np.abs(row))), 1e-6)

    broad = smooth_noise(width, height, max(96, width // 8), seed + 17) * 2.0 - 1.0
    medium = smooth_noise(width, height, max(44, width // 18), seed + 23) * 2.0 - 1.0
    diagonal = ((yy / max(height - 1, 1)) - 0.5) * boundary_diagonal_px
    contour = np.sin((yy / max(height - 1, 1) * 1.18 + broad * 0.16) * np.pi * 2.0) * boundary_jitter_px * 0.18
    boundary = left_width + diagonal + contour + row[:, None] * boundary_jitter_px + broad * boundary_jitter_px * 0.42
    width_noise = smooth_noise(width, height, max(120, width // 7), seed + 31)
    local_width = ecotone_width_px * (0.72 + width_noise * 0.62)

    raw = (x - boundary) / np.maximum(local_width, 1.0) + 0.5
    raw = raw + medium * 0.18
    biome_b = smoothstep(raw)

    left_lock = smoothstep((x - 12.0) / max(left_width * 0.25, 1.0))
    right_lock = smoothstep((x - (width - left_width * 0.25)) / max(left_width * 0.25, 1.0))
    biome_b = np.minimum(biome_b, left_lock)
    biome_b = np.maximum(biome_b, right_lock)
    biome_a = 1.0 - biome_b
    ecotone = np.clip(4.0 * biome_a * biome_b, 0.0, 1.0)
    ecotone = np.power(ecotone, 0.78)
    return {
        "biome_a_weight": biome_a.astype(np.float32),
        "biome_b_weight": biome_b.astype(np.float32),
        "ecotone_weight": ecotone.astype(np.float32),
        "boundary_x_px": boundary.astype(np.float32),
        "local_width_px": local_width.astype(np.float32),
    }


def build_height(
    left_h: np.ndarray,
    right_h: np.ndarray,
    fields: dict[str, np.ndarray],
) -> np.ndarray:
    height, left_w = left_h.shape
    right_w = right_h.shape[1]
    right_h = right_h.copy()
    edge_delta = float(np.median(left_h[:, -24:]) - np.median(right_h[:, :24]))
    right_h += edge_delta
    hard = np.concatenate([left_h, right_h], axis=1)

    biome_a = fields["biome_a_weight"]
    biome_b = fields["biome_b_weight"]
    ecotone = fields["ecotone_weight"]
    left_edge = np.repeat(left_h[:, -1:], left_w + right_w, axis=1)
    right_edge = np.repeat(right_h[:, :1], left_w + right_w, axis=1)
    total_w = left_w + right_w
    x = np.arange(total_w, dtype=np.float32)[None, :]
    join_blend_px = max(96.0, float(left_w) * 0.28)
    join_t = smoothstep((x - (float(left_w) - join_blend_px)) / (join_blend_px * 2.0))
    bridge_t = np.clip(biome_b * 0.62 + join_t * 0.38, 0.0, 1.0)
    bridge = left_edge * (1.0 - bridge_t) + right_edge * bridge_t

    left_detail = np.concatenate([left_h - left_h[:, -1:], np.zeros_like(right_h)], axis=1)
    right_detail = np.concatenate([np.zeros_like(left_h), right_h - right_h[:, :1]], axis=1)
    detail = left_detail * np.power(1.0 - bridge_t, 1.35) + right_detail * np.power(bridge_t, 1.35)
    join_weight = np.clip(4.0 * join_t * (1.0 - join_t), 0.0, 1.0)
    blend_weight = np.maximum(ecotone * 0.88, np.power(join_weight, 0.72))
    out = hard * (1.0 - blend_weight) + (bridge + detail * 0.56) * blend_weight

    out_min = float(np.min(out))
    out_range = max(float(np.max(out) - out_min), 1e-6)
    smooth_norm = gaussian_gray((out - out_min) / out_range, 1.1)
    smooth = out_min + smooth_norm * out_range
    return out * (1.0 - ecotone * 0.55) + smooth * (ecotone * 0.55)


def build_layers(
    left_rgb: np.ndarray,
    right_rgb: np.ndarray,
    height_m: np.ndarray,
    fields: dict[str, np.ndarray],
    seed: int,
) -> dict[str, np.ndarray]:
    height, left_w = left_rgb.shape[:2]
    right_w = right_rgb.shape[1]
    width = left_w + right_w
    biome_a = fields["biome_a_weight"]
    biome_b = fields["biome_b_weight"]
    ecotone = fields["ecotone_weight"]

    left_luma = left_rgb[:, :, 0] * 0.2126 + left_rgb[:, :, 1] * 0.7152 + left_rgb[:, :, 2] * 0.0722
    green_excess = np.maximum(left_rgb[:, :, 1] - np.maximum(left_rgb[:, :, 0], left_rgb[:, :, 2]) * 0.86, 0.0)
    dark_mass = np.maximum(0.34 - left_luma, 0.0)
    left_feature = gaussian_gray(np.clip(green_excess * 4.5 + dark_mass * 2.1, 0.0, 1.0), 2.8)
    feature_edge = np.repeat(np.mean(left_feature[:, -96:], axis=1, keepdims=True), right_w, axis=1)
    feature_full = np.concatenate([left_feature, feature_edge], axis=1)

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x01 = xx / max(width - 1, 1)
    y01 = yy / max(height - 1, 1)
    low = smooth_noise(width, height, 140, seed + 101)
    med = smooth_noise(width, height, 54, seed + 107)
    fine = smooth_noise(width, height, 22, seed + 113)
    wash_wave = np.sin((x01 * 1.45 + y01 * 2.25 + low * 0.18) * np.pi * 2.0)
    wash_lines = np.exp(-np.square(wash_wave / 0.20))
    source_finger = smoothstep((smooth_noise(width, height, 86, seed + 119) - 0.42) / 0.35)
    grass_finger = smoothstep((smooth_noise(width, height, 74, seed + 127) - 0.46) / 0.34)

    grad_y, grad_x = np.gradient(height_m)
    slope = normalize01(np.sqrt(grad_x * grad_x + grad_y * grad_y), 35.0, 99.5)
    rock_noise = smooth_noise(width, height, 38, seed + 131)

    shrub_carryover = np.clip((feature_full * 0.95 + med * 0.28) * (biome_a + ecotone * 0.58), 0.0, 1.0)
    shrub_carryover = np.clip(shrub_carryover * (0.88 + fine * 0.30), 0.0, 1.0)
    dry_grass_density = np.clip(biome_b * (0.58 + low * 0.22) + ecotone * (0.18 + med * 0.30), 0.0, 1.0)
    ecotone_core = np.power(ecotone, 0.78)
    soil_pattern = smoothstep((wash_lines * 0.62 + (1.0 - med) * 0.24 + low * 0.18 - 0.42) / 0.34)
    soil_exposure = np.clip(ecotone_core * (0.24 + soil_pattern * 0.72), 0.0, 1.0)
    rock_cluster = np.clip((slope * 0.82 + rock_noise * 0.48 + wash_lines * 0.16 - 0.54) * 2.2, 0.0, 1.0)
    rock_cluster = np.clip(rock_cluster * (0.32 + ecotone_core * 0.92), 0.0, 1.0)
    no_scatter = np.clip(slope * 0.95 + rock_cluster * 0.42, 0.0, 1.0)

    source_scrub_weight = np.clip(
        np.power(biome_a, 1.18) * (1.0 - soil_exposure * 0.55 - rock_cluster * 0.30)
        + shrub_carryover * ecotone_core * 0.30
        + source_finger * ecotone_core * np.power(1.0 - biome_b, 0.42) * 0.44,
        0.0,
        1.0,
    )
    grassland_weight = np.clip(
        np.power(biome_b, 1.12) * (1.0 - soil_exposure * 0.48 - rock_cluster * 0.24)
        + grass_finger * ecotone_core * np.power(biome_b, 0.42) * 0.38,
        0.0,
        1.0,
    )
    ecotone_soil_weight = np.clip(soil_exposure * (0.95 + ecotone_core * 0.38), 0.0, 1.0)
    rock_exposure_weight = np.clip(rock_cluster * (0.62 + ecotone_core * 0.55), 0.0, 1.0)
    stack = np.stack(
        [source_scrub_weight, grassland_weight, ecotone_soil_weight, rock_exposure_weight],
        axis=2,
    )
    stack = np.power(np.maximum(stack, 1e-5), 1.38)
    stack_sum = np.maximum(np.sum(stack, axis=2, keepdims=True), 1e-5)
    stack = stack / stack_sum

    return {
        "biome_a_weight": biome_a,
        "biome_b_weight": biome_b,
        "ecotone_weight": ecotone,
        "source_scrub_weight": stack[:, :, 0],
        "grassland_weight": stack[:, :, 1],
        "ecotone_soil_weight": stack[:, :, 2],
        "rock_exposure_weight": stack[:, :, 3],
        "shrub_carryover_mask": shrub_carryover,
        "dry_grass_density_mask": dry_grass_density,
        "soil_exposure_mask": soil_exposure,
        "rock_cluster_mask": rock_cluster,
        "wash_line_mask": np.clip(wash_lines * ecotone, 0.0, 1.0),
        "no_scatter_mask": no_scatter,
    }


def enhance_procedural_macro(
    macro: np.ndarray,
    material: dict[str, Any],
    seed: int,
) -> np.ndarray:
    height, width = macro.shape[:2]
    albedo_path = procedural.resolve_repo_path(material["pbr_maps"]["albedo"])
    detail = procedural.tiled_detail(albedo_path, width, height, max(92, width // 4), seed + 519)
    detail_soft = np.asarray(
        Image.fromarray(np.clip(detail * 255.0, 0, 255).astype(np.uint8), mode="RGB")
        .filter(ImageFilter.GaussianBlur(radius=0.45)),
        dtype=np.float32,
    ) / 255.0
    detail_signal = detail_soft - np.mean(detail_soft.reshape(-1, 3), axis=0)[None, None, :]
    out = macro + detail_signal * 0.58
    out = (out - 0.5) * 1.08 + 0.5
    return np.clip(out, 0.0, 1.0)


def build_macro_preview(left_rgb: np.ndarray, right_rgb: np.ndarray, layers: dict[str, np.ndarray], seed: int) -> np.ndarray:
    height, left_w = left_rgb.shape[:2]
    right_w = right_rgb.shape[1]
    width = left_w + right_w
    noise = smooth_noise(width, height, 48, seed + 211)
    fine = smooth_noise(width, height, 18, seed + 223)

    left_median = color_stat(left_rgb)
    shrub_mask = layers["shrub_carryover_mask"]
    shrub_color = np.array(
        [
            max(left_median[0] * 0.72, 0.16),
            min(left_median[1] * 1.02 + 0.045, 0.42),
            max(left_median[2] * 0.64, 0.12),
        ],
        dtype=np.float32,
    )
    grass_median = color_stat(right_rgb)
    soil_color = np.clip(left_median * 0.52 + grass_median * 0.34 + np.array([0.15, 0.10, 0.035]), 0.0, 1.0)
    rock_color = np.clip(left_median * 0.42 + np.array([0.36, 0.34, 0.28]), 0.0, 1.0)

    left_edge_w = min(max(96, left_w // 3), left_w)
    right_edge_w = min(max(96, right_w // 3), right_w)
    left_tile = np.concatenate([left_rgb[:, -left_edge_w:, :], left_rgb[:, -left_edge_w:, :][:, ::-1, :]], axis=1)
    right_tile = np.concatenate([right_rgb[:, :right_edge_w, :][:, ::-1, :], right_rgb[:, :right_edge_w, :]], axis=1)
    source_repeats = int(np.ceil(width / left_tile.shape[1])) + 2
    grass_repeats = int(np.ceil(width / right_tile.shape[1])) + 2
    source_synth = np.tile(left_tile, (1, source_repeats, 1))[:, :width, :]
    grass_synth = np.tile(right_tile, (1, grass_repeats, 1))[:, -width:, :]
    source_synth = source_synth * 0.70 + left_median[None, None, :] * 0.30
    grass_synth = grass_synth * 0.76 + grass_median[None, None, :] * 0.24

    source_panel = source_synth.copy()
    source_panel[:, :left_w, :] = left_rgb
    grass_panel = grass_synth.copy()
    grass_panel[:, left_w:, :] = right_rgb

    x = np.arange(width, dtype=np.float32)[None, :, None]
    ecotone_soft = np.clip(gaussian_gray(layers["ecotone_weight"], 18.0)[:, :, None] * 1.25, 0.0, 1.0)
    source_far_right = smoothstep((x - float(left_w + 60)) / 280.0)
    grass_far_right = smoothstep((x - float(left_w + 110)) / 320.0)
    source_synth_weight = np.maximum(ecotone_soft, source_far_right)
    grass_panel_weight = grass_far_right * (1.0 - ecotone_soft * 0.72)
    source_color = source_panel * (1.0 - source_synth_weight) + source_synth * source_synth_weight
    grass_color = grass_synth * (1.0 - grass_panel_weight) + grass_panel * grass_panel_weight

    value = 0.88 + noise[:, :, None] * 0.20 + fine[:, :, None] * 0.045
    soil = soil_color[None, None, :] * value
    rock = rock_color[None, None, :] * (0.90 + noise[:, :, None] * 0.18)
    source_color = source_color * (0.96 + fine[:, :, None] * 0.06)
    grass_color = grass_color * (0.94 + noise[:, :, None] * 0.08)
    grass_patch = smooth_noise(width, height, 84, seed + 229)
    grass_patch_alpha = np.clip((grass_patch - 0.42) * 0.55 * layers["grassland_weight"], 0.0, 0.20)
    straw_color = np.clip(grass_median * 1.08 + np.array([0.05, 0.04, -0.015], dtype=np.float32), 0.0, 1.0)
    olive_color = np.array([0.28, 0.34, 0.20], dtype=np.float32)
    patch_color = straw_color[None, None, :] * (1.0 - grass_patch[:, :, None]) + olive_color[None, None, :] * grass_patch[:, :, None]
    grass_color = grass_color * (1.0 - grass_patch_alpha[:, :, None]) + patch_color * grass_patch_alpha[:, :, None]

    preview = (
        source_color * layers["source_scrub_weight"][:, :, None]
        + grass_color * layers["grassland_weight"][:, :, None]
        + soil * layers["ecotone_soil_weight"][:, :, None]
        + rock * layers["rock_exposure_weight"][:, :, None]
    )
    shrub_alpha = np.clip(shrub_mask * (layers["ecotone_weight"] * 0.24 + layers["source_scrub_weight"] * 0.05), 0.0, 0.32)
    preview = preview * (1.0 - shrub_alpha[:, :, None]) + shrub_color[None, None, :] * shrub_alpha[:, :, None]
    return np.clip(preview, 0.0, 1.0)


def build_source_macro_weight(fields: dict[str, np.ndarray], layers: dict[str, np.ndarray]) -> np.ndarray:
    biome_a = fields["biome_a_weight"]
    height, width = biome_a.shape
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    _ = yy
    boundary = fields["boundary_x_px"]
    photo_gate = 1.0 - smoothstep((xx - (boundary - 320.0)) / 240.0)
    mask = smoothstep((biome_a - 0.72) / 0.22) * photo_gate
    return gaussian_gray(mask, 4.0)


def build_macro_guidance_weight(fields: dict[str, np.ndarray], layers: dict[str, np.ndarray]) -> np.ndarray:
    """Runtime macro influence for broad landcover color guidance.

    This should be high across the whole proof so topdown/iso views read from a
    macro landcover map, while the splat/material weights still provide the
    runtime material ownership and close detail.
    """
    ecotone = fields["ecotone_weight"]
    soil = layers["ecotone_soil_weight"]
    rock = layers["rock_exposure_weight"]
    mask = 0.72 + ecotone * 0.12 + soil * 0.10 + rock * 0.06
    return gaussian_gray(np.clip(mask, 0.0, 0.94), 2.0)


def build_source_macro_payload(
    left_rgb: np.ndarray,
    source_macro_weight: np.ndarray,
    seed: int,
) -> np.ndarray:
    """Build only the source-photo payload used by the runtime macro overlay.

    The final ecotone should be a shader/material-layer decision. This texture
    preserves the source imagery on the source side and lets the mask decide
    how much of that imagery survives into the transition.
    """
    height, left_w = left_rgb.shape[:2]
    width = source_macro_weight.shape[1]
    right_w = width - left_w
    left_edge_w = min(max(128, left_w // 2), left_w)
    edge = left_rgb[:, -left_edge_w:, :]
    mirrored_edge = np.concatenate([edge, edge[:, ::-1, :]], axis=1)
    repeats = int(np.ceil(max(width, 1) / mirrored_edge.shape[1])) + 2
    extension = np.tile(mirrored_edge, (1, repeats, 1))[:, :right_w, :]

    noise = smooth_noise(width, height, 58, seed + 251)
    fine = smooth_noise(width, height, 21, seed + 257)
    source_payload = np.concatenate([left_rgb, extension], axis=1)
    source_median = color_stat(left_rgb)
    payload_blend = smoothstep((np.arange(width, dtype=np.float32)[None, :] - float(left_w - 70)) / 520.0)
    source_payload = (
        source_payload * (1.0 - payload_blend[:, :, None] * 0.42)
        + source_median[None, None, :] * (payload_blend[:, :, None] * 0.42)
    )

    value = 0.94 + noise[:, :, None] * 0.11 + fine[:, :, None] * 0.035
    source_payload = source_payload * value

    # Keep non-source areas harmless. The shader mask should be near zero there,
    # but neutralizing the payload prevents accidental tinting during debug.
    neutral = np.array([0.46, 0.44, 0.36], dtype=np.float32)[None, None, :]
    fade = np.clip(source_macro_weight[:, :, None] * 1.55, 0.0, 1.0)
    source_payload = neutral * (1.0 - fade) + source_payload * fade
    return np.clip(source_payload, 0.0, 1.0)


def save_gray(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="L").save(path)


def save_rgb(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="RGB").save(path)


def save_rgba(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="RGBA").save(path)


def write_ecotone_material(
    path: Path,
    source_macro: Path,
    source_macro_weight_mask: Path,
    splat_weights: Path,
    slot_materials: dict[str, str],
    extra_catalogs: list[Path],
) -> None:
    catalog = source_review.load_catalog(extra_catalogs)
    _ = (source_macro, source_macro_weight_mask, splat_weights)
    ext_lines = [
        source_review.ext_resource("Shader", "res://shaders/terrain_splat_unified.gdshader", "shader"),
    ]
    res_id_for: dict[tuple[str, str], str] = {}
    for slot in source_review.SLOTS:
        maps = source_review.material_maps(slot_materials[slot], catalog)
        for kind in [*source_review.BASE_MAPS, *source_review.DETAIL_MAPS]:
            ident = f"{slot}_{source_review.SHORT_MAP[kind]}"
            ext_lines.append(source_review.ext_resource("Texture2D", maps[kind], ident))
            res_id_for[(slot, kind)] = ident

    lines = [
        f'[gd_resource type="ShaderMaterial" load_steps={len(ext_lines) + 1} format=3]',
        "",
        *ext_lines,
        "",
        "[resource]",
        'shader = ExtResource("shader")',
        "shader_parameter/use_source_macro_albedo = true",
        "shader_parameter/source_macro_strength = 0.76",
        "shader_parameter/use_source_macro_valid_mask = true",
        "shader_parameter/use_splat_weights = true",
        "shader_parameter/splat_uv_scale = 1.0",
        "shader_parameter/splat_weight_power = 1.95",
    ]
    for slot in source_review.SLOTS:
        for kind in [*source_review.BASE_MAPS, *source_review.DETAIL_MAPS]:
            uniform = f"{slot}_{source_review.SHORT_MAP[kind]}"
            lines.append(f'shader_parameter/{uniform} = ExtResource("{res_id_for[(slot, kind)]}")')
    values = {
        "world_uv_scale": 0.012,
        "hex_strength": 1.0,
        "blend_sharpness": 8.0,
        "roughness_strength": 1.0,
        "normal_strength": 0.075,
        "macro_scale": 180.0,
        "macro_value_strength": 0.0,
        "macro_hue_strength": 0.0,
        "detail_uv_scale_mult": 11.0,
        "detail_albedo_strength": 0.035,
        "detail_normal_strength": 0.030,
        "detail_rough_strength": 0.025,
        "detail_fade_start_m": 6.0,
        "detail_fade_end_m": 52.0,
        "elev_min_m": 0.0,
        "elev_range_m": 1.0,
        "slope_threshold": 1.0,
        "slope_softness": 0.15,
        "h_grass_dirt": 0.2,
        "h_dirt_rockdark": 0.55,
        "h_rockdark_snow": 0.85,
        "h_band_softness": 0.08,
    }
    for key, value in values.items():
        lines.append(f"shader_parameter/{key} = {value}")
    source_review.write_text_lf(path, "\n".join(lines) + "\n")


def label_panel(title: str, arr: np.ndarray, size: tuple[int, int]) -> Image.Image:
    if arr.ndim == 2:
        rgb = np.repeat(arr[:, :, None], 3, axis=2)
    else:
        rgb = arr
    img = Image.fromarray(np.clip(rgb * 255.0, 0, 255).astype(np.uint8), mode="RGB")
    img.thumbnail(size, Image.Resampling.LANCZOS)
    panel = Image.new("RGB", size, (18, 20, 20))
    panel.paste(img, ((size[0] - img.width) // 2, 30 + (size[1] - 30 - img.height) // 2))
    draw = ImageDraw.Draw(panel)
    font = ImageFont.load_default()
    draw.text((8, 8), title, fill=(235, 235, 225), font=font)
    return panel


def write_contact_sheet(
    path: Path,
    preview: np.ndarray,
    height_m: np.ndarray,
    layers: dict[str, np.ndarray],
) -> None:
    h_norm = normalize01(height_m)
    biome_debug = np.stack(
        [
            layers["biome_a_weight"],
            layers["biome_b_weight"],
            layers["ecotone_weight"],
        ],
        axis=2,
    )
    material_debug = np.stack(
        [
            layers["source_scrub_weight"] * 0.65 + layers["rock_exposure_weight"] * 0.45,
            layers["grassland_weight"] * 0.82 + layers["source_scrub_weight"] * 0.35,
            layers["ecotone_soil_weight"] * 0.62 + layers["rock_exposure_weight"] * 0.35,
        ],
        axis=2,
    )
    scatter_debug = np.stack(
        [
            layers["rock_cluster_mask"] * 0.92 + layers["soil_exposure_mask"] * 0.38,
            layers["shrub_carryover_mask"] * 0.9 + layers["dry_grass_density_mask"] * 0.45,
            layers["wash_line_mask"] * 0.9 + layers["no_scatter_mask"] * 0.35,
        ],
        axis=2,
    )
    panels = [
        label_panel("derived macro preview", preview, (420, 300)),
        label_panel("biome weights: A/R B/G ecotone/B", biome_debug, (420, 300)),
        label_panel("material weights debug", np.clip(material_debug, 0.0, 1.0), (420, 300)),
        label_panel("scatter/feature masks debug", np.clip(scatter_debug, 0.0, 1.0), (420, 300)),
        label_panel("height field", h_norm, (420, 300)),
        label_panel("ecotone weight", layers["ecotone_weight"], (420, 300)),
    ]
    sheet = Image.new("RGB", (1260, 600), (10, 12, 12))
    for idx, panel in enumerate(panels):
        x = (idx % 3) * 420
        y = (idx // 3) * 300
        sheet.paste(panel, (x, y))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def write_outputs(args: argparse.Namespace) -> dict[str, Any]:
    left_meta = json.loads(args.left_meta.read_text(encoding="utf-8"))
    left_macro = load_rgb(args.left_macro)
    left_mask = load_mask(args.left_valid_mask)
    left_height_m = load_height_m(args.left_heightmap, left_meta)
    left_crop = parse_crop(args.left_crop)

    left_rgb = crop_array(left_macro, left_crop)
    left_mask_crop = crop_array(left_mask, left_crop)
    left_h = crop_height_from_macro_space(
        left_height_m,
        (left_macro.shape[1], left_macro.shape[0]),
        left_crop,
        (left_crop[2], left_crop[3]),
    )
    left_w, out_h = left_crop[2], left_crop[3]
    right_w = args.right_width_px

    right_material = procedural.load_material(args.right_material_id, args.right_catalog)
    right_rgb = procedural.build_macro(right_material, right_w, out_h, args.seed + 300)
    right_rgb = enhance_procedural_macro(right_rgb, right_material, args.seed)
    right_h = procedural.build_height(
        right_w,
        out_h,
        float(np.percentile(left_h[:, -96:], 12)),
        args.right_elev_range_m,
        args.seed + 400,
    )

    fields = build_ecotone_fields(
        left_w + right_w,
        out_h,
        left_w,
        args.seed,
        args.ecotone_width_px,
        args.boundary_jitter_px,
        args.boundary_diagonal_px,
    )
    height_out = build_height(left_h, right_h, fields)
    layers = build_layers(left_rgb, right_rgb, height_out, fields, args.seed)
    preview = build_macro_preview(left_rgb, right_rgb, layers, args.seed)
    source_macro_weight = build_source_macro_weight(fields, layers)
    source_payload = build_source_macro_payload(left_rgb, source_macro_weight, args.seed)
    macro_guidance_weight = build_macro_guidance_weight(fields, layers)

    output_elev_min = float(np.min(height_out))
    output_elev_max = float(np.max(height_out))
    output_elev_range = max(output_elev_max - output_elev_min, 0.001)
    height_norm = np.clip((height_out - output_elev_min) / output_elev_range, 0.0, 1.0)

    args.texture_out.mkdir(parents=True, exist_ok=True)
    args.topo_out.mkdir(parents=True, exist_ok=True)
    layer_out = args.texture_out / "layers"
    layer_out.mkdir(parents=True, exist_ok=True)

    macro_path = args.texture_out / "source_macro_albedo.png"
    valid_mask_path = args.texture_out / "source_macro_valid_mask.png"
    source_macro_weight_mask_path = args.texture_out / "source_macro_weight_mask.png"
    splat_weights_path = layer_out / "splat_weights_rgba.png"
    preview_path = layer_out / "derived_macro_preview.png"
    source_payload_path = layer_out / "source_photo_payload.png"
    manifest_path = args.texture_out / "manifest.json"
    height_path = args.topo_out / "heightmap.png"
    meta_path = args.topo_out / "meta.json"
    right_preview_path = layer_out / "right_procedural_macro_reference.png"
    save_rgb(macro_path, preview)
    save_rgb(preview_path, preview)
    save_rgb(source_payload_path, source_payload)
    save_rgb(right_preview_path, right_rgb)
    save_gray(valid_mask_path, np.ones((out_h, left_w + right_w), dtype=np.float32))
    save_gray(source_macro_weight_mask_path, macro_guidance_weight)
    save_rgba(
        splat_weights_path,
        np.stack(
            [
                layers["grassland_weight"],
                layers["ecotone_soil_weight"],
                layers["rock_exposure_weight"],
                layers["source_scrub_weight"],
            ],
            axis=2,
        ),
    )
    Image.fromarray(np.clip(height_norm * 65535.0, 0, 65535).astype(np.uint16), mode="I;16").save(height_path)

    layer_paths: dict[str, Path] = {}
    for name, arr in layers.items():
        layer_path = layer_out / f"{name}.png"
        save_gray(layer_path, arr)
        layer_paths[name] = layer_path
    layer_paths["splat_weights_rgba"] = splat_weights_path

    write_contact_sheet(args.contact_sheet, preview, height_out, layers)
    write_ecotone_material(
        args.material_out,
        macro_path,
        source_macro_weight_mask_path,
        splat_weights_path,
        {
            "grass": args.grass_slot_material,
            "dirt": args.soil_slot_material,
            "rock_light": args.rock_slot_material,
            "rock_dark": args.source_slot_material,
            "snow": args.fallback_slot_material,
        },
        [args.right_catalog, ROOT / "materials/catalog_repair_candidates.json"],
    )

    left_world_x, left_world_z = crop_world_size(left_meta, (left_macro.shape[1], left_macro.shape[0]), left_crop)
    mpp_x = left_world_x / float(left_w)
    out_world_x = mpp_x * float(left_w + right_w)
    out_world_z = left_world_z

    out_meta = dict(left_meta)
    out_meta.update(
        {
            "name": args.artifact_name,
            "builder": "build_ecotone_layer_proof.py",
            "heightmap_size_px": [left_w + right_w, out_h],
            "world_size_x_m": out_world_x,
            "world_size_z_m": out_world_z,
            "world_size_m": max(out_world_x, out_world_z),
            "elevation_min_m": output_elev_min,
            "elevation_max_m": output_elev_max,
            "elevation_range_m": output_elev_range,
            "material": "unlike_biome_ecotone_layer_preview",
            "texture_is_real_imagery": False,
            "ecotone_layer_proof": {
                "version": 1,
                "kind": "m10_unlike_biome_ecotone_layer_proof",
                "left_source_macro": res_path(args.left_macro),
                "left_source_heightmap": res_path(args.left_heightmap),
                "left_crop_macro_px": list(left_crop),
                "right_material_id": args.right_material_id,
                "right_material_catalog": res_path(args.right_catalog),
                "ecotone_width_px": args.ecotone_width_px,
                "boundary_jitter_px": args.boundary_jitter_px,
                "boundary_diagonal_px": args.boundary_diagonal_px,
                "policy": "macro_guidance_plus_runtime_splat_weights",
            },
        }
    )
    meta_path.write_text(json.dumps(out_meta, indent=2) + "\n", encoding="utf-8")

    weight_sum = (
        layers["source_scrub_weight"]
        + layers["grassland_weight"]
        + layers["ecotone_soil_weight"]
        + layers["rock_exposure_weight"]
    )
    metrics = {
        "height_m": {
            "min": output_elev_min,
            "max": output_elev_max,
            "range": output_elev_range,
            "boundary_step_p95_m": float(
                np.percentile(np.abs(height_out[:, left_w] - height_out[:, left_w - 1]), 95)
            ),
        },
        "ecotone": {
            "mean_weight": float(np.mean(layers["ecotone_weight"])),
            "coverage_gt_0_25": float(np.mean(layers["ecotone_weight"] > 0.25)),
            "boundary_x_std_px": float(np.std(fields["boundary_x_px"])),
            "local_width_mean_px": float(np.mean(fields["local_width_px"])),
            "local_width_std_px": float(np.std(fields["local_width_px"])),
            "boundary_diagonal_px": float(args.boundary_diagonal_px),
        },
        "weights": {
            "max_sum_error": float(np.max(np.abs(weight_sum - 1.0))),
            "source_scrub_mean": float(np.mean(layers["source_scrub_weight"])),
            "grassland_mean": float(np.mean(layers["grassland_weight"])),
            "ecotone_soil_mean": float(np.mean(layers["ecotone_soil_weight"])),
            "rock_exposure_mean": float(np.mean(layers["rock_exposure_weight"])),
            "source_macro_weight_mean": float(np.mean(source_macro_weight)),
            "macro_guidance_weight_mean": float(np.mean(macro_guidance_weight)),
        },
        "feature_masks": {
            "shrub_carryover_mean": float(np.mean(layers["shrub_carryover_mask"])),
            "dry_grass_density_mean": float(np.mean(layers["dry_grass_density_mask"])),
            "soil_exposure_mean": float(np.mean(layers["soil_exposure_mask"])),
            "rock_cluster_mean": float(np.mean(layers["rock_cluster_mask"])),
            "wash_line_mean": float(np.mean(layers["wash_line_mask"])),
            "no_scatter_mean": float(np.mean(layers["no_scatter_mask"])),
        },
    }
    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_out.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "version": 1,
        "kind": "m10_unlike_biome_ecotone_layer_proof",
        "id": args.texture_out.name,
        "runtime_macro": res_path(macro_path),
        "runtime_source_macro_valid_mask": res_path(valid_mask_path),
        "runtime_source_macro_weight_mask": res_path(source_macro_weight_mask_path),
        "runtime_splat_weights": res_path(splat_weights_path),
        "runtime_material": res_path(args.material_out),
        "runtime_heightmap": res_path(height_path),
        "runtime_meta": res_path(meta_path),
        "derived_macro_preview": res_path(preview_path),
        "source_photo_payload": res_path(source_payload_path),
        "contact_sheet": res_path(args.contact_sheet),
        "right_procedural_macro_reference": res_path(right_preview_path),
        "left_source": {
            "macro": res_path(args.left_macro),
            "valid_mask": res_path(args.left_valid_mask),
            "heightmap": res_path(args.left_heightmap),
            "meta": res_path(args.left_meta),
            "crop_macro_px": list(left_crop),
        },
        "right_source": {
            "kind": "procedural_material_macro",
            "material_id": args.right_material_id,
            "catalog": res_path(args.right_catalog),
        },
        "layers": {name: res_path(path) for name, path in layer_paths.items()},
        "metrics": metrics,
        "policy": "macro_guidance_plus_splat_weights_requires_visual_review",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-macro", type=Path, default=DEFAULT_LEFT_MACRO)
    parser.add_argument("--left-valid-mask", type=Path, default=DEFAULT_LEFT_MASK)
    parser.add_argument("--left-heightmap", type=Path, default=DEFAULT_LEFT_HEIGHT)
    parser.add_argument("--left-meta", type=Path, default=DEFAULT_LEFT_META)
    parser.add_argument("--left-crop", default="520,880,512,1024")
    parser.add_argument("--right-material-id", default="m8_grassland_grass_calm_v3")
    parser.add_argument("--right-catalog", type=Path, default=ROOT / "materials/catalog_comfy_candidates.json")
    parser.add_argument("--right-width-px", type=int, default=512)
    parser.add_argument("--right-elev-range-m", type=float, default=24.0)
    parser.add_argument("--texture-out", type=Path, default=DEFAULT_TEXTURE_OUT)
    parser.add_argument("--topo-out", type=Path, default=DEFAULT_TOPO_OUT)
    parser.add_argument("--material-out", type=Path, default=DEFAULT_MATERIAL_OUT)
    parser.add_argument("--contact-sheet", type=Path, default=DEFAULT_CONTACT)
    parser.add_argument("--metrics-out", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--grass-slot-material", default="m8_grassland_grass_calm_v3")
    parser.add_argument("--soil-slot-material", default="grassland_dirt")
    parser.add_argument("--rock-slot-material", default="desert_canyon_rock")
    parser.add_argument("--source-slot-material", default="scrub_sparse")
    parser.add_argument("--fallback-slot-material", default="dry_wash")
    parser.add_argument("--seed", type=int, default=1907)
    parser.add_argument("--ecotone-width-px", type=float, default=260.0)
    parser.add_argument("--boundary-jitter-px", type=float, default=175.0)
    parser.add_argument("--boundary-diagonal-px", type=float, default=235.0)
    parser.add_argument("--artifact-name", default="Gloss scrub to grassland ecotone layer proof")
    args = parser.parse_args()

    manifest = write_outputs(args)
    print(json.dumps(manifest["metrics"], indent=2))
    print(f"wrote {args.texture_out}")
    print(f"wrote {args.topo_out}")
    print(f"wrote {args.contact_sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
