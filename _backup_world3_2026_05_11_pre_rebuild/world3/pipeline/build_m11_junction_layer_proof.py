#!/usr/bin/env python3
"""Build an M11 three-way terrain junction proof.

This extends the accepted M10 ecotone contract from one pairwise band to a
three-domain Y junction:

- real-source scrub/photo terrain;
- procedural grassland;
- procedural canyon/dry-wash rock;
- shared height, macro guidance, runtime splat weights, feature/scatter masks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import build_ecotone_layer_proof as eco
import build_procedural_neighbor_bundle as procedural
import build_source_stack_runtime_review as source_review


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_MACRO = ROOT / "textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png"
DEFAULT_SOURCE_MASK = ROOT / "textures/source_stack/gloss_scrub_source_stack/source_macro_valid_mask.png"
DEFAULT_SOURCE_HEIGHT = ROOT / "toporeview/gloss_mountain_textured_master/heightmap.png"
DEFAULT_SOURCE_META = ROOT / "toporeview/gloss_mountain_textured_master/meta.json"
DEFAULT_TEXTURE_OUT = ROOT / "textures/source_stack/m11_three_way_junction_proof"
DEFAULT_TOPO_OUT = ROOT / "toporeview/m11_three_way_junction_proof"
DEFAULT_MATERIAL_OUT = ROOT / "textures/wgv3/terrain_m11_three_way_junction.tres"
DEFAULT_CONTACT = ROOT / "docs/captures/review/m11_junction_layer_contact_sheet.png"
DEFAULT_METRICS = ROOT / "docs/captures/review/m11_junction_layer_metrics.json"
DEFAULT_CANYON_REFERENCE = (
    ROOT
    / "opentopo/processed/master_stacks/zion_usgs10m_master_4call/layers/terrain_texture.png"
)


def softmax(scores: np.ndarray, sharpness: float) -> np.ndarray:
    scaled = scores * sharpness
    scaled = scaled - np.max(scaled, axis=2, keepdims=True)
    exp = np.exp(scaled)
    return exp / np.maximum(np.sum(exp, axis=2, keepdims=True), 1e-6)


def save_gray(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="L").save(path)


def save_rgb(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="RGB").save(path)


def save_rgba(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="RGBA").save(path)


def build_domain_fields(width: int, height: int, seed: int) -> dict[str, np.ndarray]:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x = (xx / max(width - 1, 1) - 0.5) * 2.0
    y = (yy / max(height - 1, 1) - 0.5) * 2.0
    low = eco.smooth_noise(width, height, 142, seed + 11) * 2.0 - 1.0
    med = eco.smooth_noise(width, height, 58, seed + 17) * 2.0 - 1.0
    fine = eco.smooth_noise(width, height, 24, seed + 23) * 2.0 - 1.0

    # Three roughly equidistant sector anchors around the center. Noisy scores
    # make the boundaries drift and finger instead of forming a clean pie chart.
    seeds = np.array(
        [
            [-0.96, 0.08],   # source scrub
            [0.30, -0.92],   # grassland
            [0.66, 0.73],    # canyon/dry-wash rock
        ],
        dtype=np.float32,
    )
    scores = []
    for idx, (sx, sy) in enumerate(seeds):
        dist2 = (x - sx) ** 2 + (y - sy) ** 2
        directional = np.sin((x * (1.4 + idx * 0.23) + y * (0.9 + idx * 0.31) + low * 0.16) * np.pi)
        scores.append(-dist2 + low * 0.12 + med * 0.11 + directional * 0.055)
    weights = softmax(np.stack(scores, axis=2), 4.35)

    # Keep boundaries legible but not razor sharp.
    for idx in range(3):
        weights[:, :, idx] = eco.gaussian_gray(weights[:, :, idx], 1.2)
    weights = weights / np.maximum(np.sum(weights, axis=2, keepdims=True), 1e-6)

    max_w = np.max(weights, axis=2)
    junction = np.clip((1.0 - max_w) / 0.54, 0.0, 1.0)
    junction = np.power(junction, 0.78)
    triple = np.clip(weights[:, :, 0] * weights[:, :, 1] * weights[:, :, 2] * 30.0, 0.0, 1.0)
    triple = eco.gaussian_gray(triple, 3.0)

    return {
        "source_scrub_domain": weights[:, :, 0].astype(np.float32),
        "grassland_domain": weights[:, :, 1].astype(np.float32),
        "canyon_domain": weights[:, :, 2].astype(np.float32),
        "junction_weight": junction.astype(np.float32),
        "triple_core_weight": triple.astype(np.float32),
        "noise_low": low.astype(np.float32),
        "noise_med": med.astype(np.float32),
        "noise_fine": fine.astype(np.float32),
    }


def build_procedural_macro(material_id: str, catalog: Path, width: int, height: int, seed: int) -> np.ndarray:
    material = procedural.load_material(material_id, catalog)
    macro = procedural.build_macro(material, width, height, seed)
    return eco.enhance_procedural_macro(macro, material, seed + 71)


def resize_rgb(arr: np.ndarray, width: int, height: int) -> np.ndarray:
    img = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="RGB")
    img = img.resize((width, height), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def load_reference_macro(path: Path | None, crop: str | None, width: int, height: int) -> np.ndarray | None:
    if path is None or not path.exists():
        return None
    rgb = eco.load_rgb(path)
    if crop:
        rgb = eco.crop_array(rgb, eco.parse_crop(crop))
    else:
        side = min(rgb.shape[0], rgb.shape[1])
        x0 = (rgb.shape[1] - side) // 2
        y0 = (rgb.shape[0] - side) // 2
        rgb = eco.crop_array(rgb, (x0, y0, side, side))
    if rgb.shape[1] != width or rgb.shape[0] != height:
        rgb = resize_rgb(rgb, width, height)
    return rgb


def build_height(
    source_h: np.ndarray,
    fields: dict[str, np.ndarray],
    seed: int,
    grass_range_m: float,
    canyon_range_m: float,
) -> np.ndarray:
    height, width = source_h.shape
    target_mid = float(np.median(source_h))
    grass_h = procedural.build_height(width, height, target_mid - grass_range_m * 0.45, grass_range_m, seed + 300)
    canyon_h = procedural.build_height(width, height, target_mid - canyon_range_m * 0.40, canyon_range_m, seed + 400)
    grass_h += target_mid - float(np.median(grass_h))
    canyon_h += target_mid - float(np.median(canyon_h)) + 2.4

    source_w = fields["source_scrub_domain"]
    grass_w = fields["grassland_domain"]
    canyon_w = fields["canyon_domain"]
    junction = fields["junction_weight"]

    hard = source_h * source_w + grass_h * grass_w + canyon_h * canyon_w
    low_relief = eco.gaussian_gray(eco.normalize01(hard), 2.0)
    low_relief = float(np.min(hard)) + low_relief * max(float(np.max(hard) - np.min(hard)), 1e-6)
    out = hard * (1.0 - junction * 0.58) + low_relief * (junction * 0.58)
    return out.astype(np.float32)


def build_layers(
    source_rgb: np.ndarray,
    grass_rgb: np.ndarray,
    canyon_rgb: np.ndarray,
    height_m: np.ndarray,
    fields: dict[str, np.ndarray],
    seed: int,
) -> dict[str, np.ndarray]:
    source = fields["source_scrub_domain"]
    grass = fields["grassland_domain"]
    canyon = fields["canyon_domain"]
    junction = fields["junction_weight"]
    triple = fields["triple_core_weight"]
    low = (fields["noise_low"] + 1.0) * 0.5
    med = (fields["noise_med"] + 1.0) * 0.5

    source_luma = source_rgb[:, :, 0] * 0.2126 + source_rgb[:, :, 1] * 0.7152 + source_rgb[:, :, 2] * 0.0722
    green_excess = np.maximum(source_rgb[:, :, 1] - np.maximum(source_rgb[:, :, 0], source_rgb[:, :, 2]) * 0.86, 0.0)
    dark_mass = np.maximum(0.34 - source_luma, 0.0)
    source_feature = eco.gaussian_gray(np.clip(green_excess * 4.2 + dark_mass * 2.0, 0.0, 1.0), 2.4)

    grad_y, grad_x = np.gradient(height_m)
    slope = eco.normalize01(np.sqrt(grad_x * grad_x + grad_y * grad_y), 42.0, 99.7)
    yy, xx = np.mgrid[0:height_m.shape[0], 0:height_m.shape[1]].astype(np.float32)
    x01 = xx / max(height_m.shape[1] - 1, 1)
    y01 = yy / max(height_m.shape[0] - 1, 1)
    wash_wave = np.sin((x01 * 1.9 + y01 * 1.28 + low * 0.20) * np.pi * 2.0)
    wash = np.exp(-np.square(wash_wave / 0.22))

    soil_exposure = np.clip(junction * (0.16 + med * 0.42) + triple * 0.34, 0.0, 1.0)
    rock_cluster = np.clip(canyon * (0.18 + slope * 0.82) + junction * slope * 0.52 + wash * canyon * 0.26, 0.0, 1.0)
    shrub_carryover = np.clip(source_feature * (source + junction * 0.52) + triple * 0.16, 0.0, 1.0)
    dry_grass_density = np.clip(grass * (0.48 + low * 0.26) + junction * (0.18 + med * 0.24), 0.0, 1.0)
    wash_line = np.clip(wash * (junction * 0.58 + canyon * 0.34), 0.0, 1.0)
    no_scatter = np.clip(slope * 0.82 + rock_cluster * 0.32, 0.0, 1.0)

    source_weight = np.clip(source * (1.0 - soil_exposure * 0.32 - rock_cluster * 0.18) + shrub_carryover * junction * 0.24, 0.0, 1.0)
    grass_weight = np.clip(grass * (1.0 - soil_exposure * 0.24 - rock_cluster * 0.12) + dry_grass_density * junction * 0.22, 0.0, 1.0)
    rock_weight = np.clip(canyon * (0.94 + slope * 0.38) + rock_cluster * 0.64, 0.0, 1.0)
    soil_weight = np.clip(soil_exposure * 0.62 + wash_line * 0.20 + triple * 0.14, 0.0, 1.0)
    stack = np.stack([grass_weight, soil_weight, rock_weight, source_weight], axis=2)
    stack = np.power(np.maximum(stack, 1e-5), 1.12)
    stack /= np.maximum(np.sum(stack, axis=2, keepdims=True), 1e-6)

    return {
        "source_scrub_domain": source,
        "grassland_domain": grass,
        "canyon_domain": canyon,
        "junction_weight": junction,
        "triple_core_weight": triple,
        "source_scrub_weight": stack[:, :, 3],
        "grassland_weight": stack[:, :, 0],
        "junction_soil_weight": stack[:, :, 1],
        "canyon_rock_weight": stack[:, :, 2],
        "shrub_carryover_mask": shrub_carryover,
        "dry_grass_density_mask": dry_grass_density,
        "soil_exposure_mask": soil_exposure,
        "rock_cluster_mask": rock_cluster,
        "wash_line_mask": wash_line,
        "no_scatter_mask": no_scatter,
    }


def build_macro_preview(
    source_rgb: np.ndarray,
    grass_rgb: np.ndarray,
    canyon_rgb: np.ndarray,
    canyon_reference_rgb: np.ndarray | None,
    height_m: np.ndarray,
    layers: dict[str, np.ndarray],
    seed: int,
) -> np.ndarray:
    height, width = source_rgb.shape[:2]
    low = eco.smooth_noise(width, height, 72, seed + 501)
    fine = eco.smooth_noise(width, height, 24, seed + 503)
    ridge_noise = eco.smooth_noise(width, height, 36, seed + 509)
    grad_y, grad_x = np.gradient(height_m)
    slope = eco.normalize01(np.sqrt(grad_x * grad_x + grad_y * grad_y), 45.0, 99.5)
    light = eco.normalize01(-(grad_x * 0.48 + grad_y * 0.82), 1.0, 99.0)
    source_med = eco.color_stat(source_rgb)
    grass_med = eco.color_stat(grass_rgb)
    soil_color = np.clip(
        source_med * 0.34
        + grass_med * 0.28
        + np.array([0.22, 0.15, 0.075], dtype=np.float32),
        0.0,
        1.0,
    )
    if canyon_reference_rgb is not None:
        canyon_base = np.clip(canyon_reference_rgb * 0.78 + canyon_rgb * 0.22, 0.0, 1.0)
    else:
        warm_canyon = np.array([0.64, 0.42, 0.24], dtype=np.float32)
        canyon_base = np.clip(canyon_rgb * 0.62 + warm_canyon[None, None, :] * 0.38, 0.0, 1.0)
    rock_warm = np.array([0.74, 0.45, 0.24], dtype=np.float32)
    rock_shadow = np.array([0.19, 0.15, 0.12], dtype=np.float32)
    rock_alpha = np.clip(layers["rock_cluster_mask"] * 0.22 + slope * layers["canyon_domain"] * 0.16, 0.0, 0.36)
    shadow_alpha = np.clip(layers["wash_line_mask"] * 0.34 + slope * layers["canyon_domain"] * 0.10, 0.0, 0.36)
    rock_color = np.clip(canyon_base * (0.78 + light[:, :, None] * 0.34 + fine[:, :, None] * 0.035), 0.0, 1.0)
    rock_color = rock_color * (1.0 - rock_alpha[:, :, None]) + rock_warm[None, None, :] * rock_alpha[:, :, None]
    rock_color = rock_color * (1.0 - shadow_alpha[:, :, None]) + rock_shadow[None, None, :] * shadow_alpha[:, :, None]

    grass_color = np.clip(grass_rgb * (0.90 + low[:, :, None] * 0.12 + fine[:, :, None] * 0.04), 0.0, 1.0)
    grass_patch = np.clip((ridge_noise - 0.42) * 0.62 * layers["dry_grass_density_mask"], 0.0, 0.24)
    straw = np.array([0.56, 0.49, 0.30], dtype=np.float32)
    olive = np.array([0.25, 0.33, 0.19], dtype=np.float32)
    patch_color = straw[None, None, :] * (1.0 - ridge_noise[:, :, None]) + olive[None, None, :] * ridge_noise[:, :, None]
    grass_color = grass_color * (1.0 - grass_patch[:, :, None]) + patch_color * grass_patch[:, :, None]

    source_color = np.clip(source_rgb * (0.96 + fine[:, :, None] * 0.06), 0.0, 1.0)
    soil = soil_color[None, None, :] * (0.86 + low[:, :, None] * 0.16 + fine[:, :, None] * 0.06)
    soil = soil * (1.0 - layers["wash_line_mask"][:, :, None] * 0.18) + rock_shadow[None, None, :] * layers["wash_line_mask"][:, :, None] * 0.18

    preview = (
        grass_color * layers["grassland_weight"][:, :, None]
        + soil * layers["junction_soil_weight"][:, :, None]
        + rock_color * layers["canyon_rock_weight"][:, :, None]
        + source_color * layers["source_scrub_weight"][:, :, None]
    )
    shrub_alpha = np.clip(layers["shrub_carryover_mask"] * (layers["source_scrub_domain"] * 0.08 + layers["junction_weight"] * 0.18), 0.0, 0.30)
    shrub_color = np.array([0.16, 0.22, 0.12], dtype=np.float32)
    preview = preview * (1.0 - shrub_alpha[:, :, None]) + shrub_color[None, None, :] * shrub_alpha[:, :, None]
    triple_tint = np.array([0.42, 0.32, 0.20], dtype=np.float32)
    triple = np.clip(layers["triple_core_weight"][:, :, None] * 0.14, 0.0, 0.14)
    preview = preview * (1.0 - triple) + triple_tint[None, None, :] * triple
    return np.clip(preview, 0.0, 1.0)


def build_macro_guidance_weight(layers: dict[str, np.ndarray]) -> np.ndarray:
    mask = 0.72 + layers["junction_weight"] * 0.14 + layers["triple_core_weight"] * 0.08
    mask += layers["junction_soil_weight"] * 0.05
    return eco.gaussian_gray(np.clip(mask, 0.0, 0.96), 2.0)


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
    draw.text((8, 8), title, fill=(235, 235, 225), font=ImageFont.load_default())
    return panel


def write_contact_sheet(path: Path, preview: np.ndarray, height_m: np.ndarray, layers: dict[str, np.ndarray]) -> None:
    domain_debug = np.stack(
        [layers["source_scrub_domain"], layers["grassland_domain"], layers["canyon_domain"]],
        axis=2,
    )
    material_debug = np.stack(
        [
            layers["source_scrub_weight"] * 0.62 + layers["canyon_rock_weight"] * 0.36,
            layers["grassland_weight"] * 0.80 + layers["source_scrub_weight"] * 0.28,
            layers["junction_soil_weight"] * 0.70 + layers["triple_core_weight"] * 0.48,
        ],
        axis=2,
    )
    scatter_debug = np.stack(
        [
            layers["rock_cluster_mask"] * 0.85 + layers["soil_exposure_mask"] * 0.34,
            layers["shrub_carryover_mask"] * 0.82 + layers["dry_grass_density_mask"] * 0.42,
            layers["wash_line_mask"] * 0.88 + layers["no_scatter_mask"] * 0.34,
        ],
        axis=2,
    )
    panels = [
        label_panel("derived macro preview", preview, (420, 300)),
        label_panel("domain weights: source/R grass/G canyon/B", domain_debug, (420, 300)),
        label_panel("material weights debug", np.clip(material_debug, 0.0, 1.0), (420, 300)),
        label_panel("scatter/feature masks debug", np.clip(scatter_debug, 0.0, 1.0), (420, 300)),
        label_panel("height field", eco.normalize01(height_m), (420, 300)),
        label_panel("junction + triple core", np.clip(layers["junction_weight"] + layers["triple_core_weight"] * 0.65, 0.0, 1.0), (420, 300)),
    ]
    sheet = Image.new("RGB", (1260, 600), (10, 12, 12))
    for idx, panel in enumerate(panels):
        sheet.paste(panel, ((idx % 3) * 420, (idx // 3) * 300))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def write_junction_material(path: Path, slot_materials: dict[str, str], extra_catalogs: list[Path]) -> None:
    eco.write_ecotone_material(
        path,
        DEFAULT_TEXTURE_OUT / "source_macro_albedo.png",
        DEFAULT_TEXTURE_OUT / "source_macro_weight_mask.png",
        DEFAULT_TEXTURE_OUT / "layers/splat_weights_rgba.png",
        slot_materials,
        extra_catalogs,
    )
    text = path.read_text(encoding="utf-8")
    text = text.replace("shader_parameter/source_macro_strength = 0.76", "shader_parameter/source_macro_strength = 0.72")
    text = text.replace("shader_parameter/splat_weight_power = 1.95", "shader_parameter/splat_weight_power = 1.55")
    source_review.write_text_lf(path, text)


def write_outputs(args: argparse.Namespace) -> dict[str, Any]:
    source_meta = json.loads(args.source_meta.read_text(encoding="utf-8"))
    source_macro = eco.load_rgb(args.source_macro)
    source_mask = eco.load_mask(args.source_valid_mask)
    source_height = eco.load_height_m(args.source_heightmap, source_meta)
    source_crop = eco.parse_crop(args.source_crop)

    source_rgb = eco.crop_array(source_macro, source_crop)
    source_mask_crop = eco.crop_array(source_mask, source_crop)
    size = (source_crop[2], source_crop[3])
    if size[0] != size[1]:
        raise ValueError("M11 proof expects a square source crop")
    width, height = size
    source_h = eco.crop_height_from_macro_space(
        source_height,
        (source_macro.shape[1], source_macro.shape[0]),
        source_crop,
        (width, height),
    )
    grass_rgb = build_procedural_macro(args.grass_material_id, args.grass_catalog, width, height, args.seed + 100)
    canyon_rgb = build_procedural_macro(args.canyon_material_id, args.canyon_catalog, width, height, args.seed + 200)
    canyon_reference_rgb = load_reference_macro(
        args.canyon_reference_macro,
        args.canyon_reference_crop,
        width,
        height,
    )

    fields = build_domain_fields(width, height, args.seed)
    height_out = build_height(source_h, fields, args.seed, args.grass_elev_range_m, args.canyon_elev_range_m)
    layers = build_layers(source_rgb, grass_rgb, canyon_rgb, height_out, fields, args.seed)
    preview = build_macro_preview(source_rgb, grass_rgb, canyon_rgb, canyon_reference_rgb, height_out, layers, args.seed)
    macro_guidance_weight = build_macro_guidance_weight(layers)

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
    height_path = args.topo_out / "heightmap.png"
    meta_path = args.topo_out / "meta.json"
    manifest_path = args.texture_out / "manifest.json"

    save_rgb(macro_path, preview)
    save_gray(valid_mask_path, np.ones((height, width), dtype=np.float32))
    save_gray(source_macro_weight_mask_path, macro_guidance_weight)
    save_rgba(
        splat_weights_path,
        np.stack(
            [
                layers["grassland_weight"],
                layers["junction_soil_weight"],
                layers["canyon_rock_weight"],
                layers["source_scrub_weight"],
            ],
            axis=2,
        ),
    )
    Image.fromarray(np.clip(height_norm * 65535.0, 0, 65535).astype(np.uint16), mode="I;16").save(height_path)

    layer_paths: dict[str, Path] = {}
    for name, arr in layers.items():
        path = layer_out / f"{name}.png"
        save_gray(path, arr)
        layer_paths[name] = path
    layer_paths["splat_weights_rgba"] = splat_weights_path
    save_rgb(layer_out / "source_crop_reference.png", source_rgb)
    save_rgb(layer_out / "grassland_macro_reference.png", grass_rgb)
    save_rgb(layer_out / "canyon_macro_reference.png", canyon_rgb)

    write_contact_sheet(args.contact_sheet, preview, height_out, layers)
    write_junction_material(
        args.material_out,
        {
            "grass": args.grass_slot_material,
            "dirt": args.soil_slot_material,
            "rock_light": args.rock_slot_material,
            "rock_dark": args.source_slot_material,
            "snow": args.fallback_slot_material,
        },
        [args.grass_catalog, ROOT / "materials/catalog_repair_candidates.json"],
    )

    world_x, world_z = eco.crop_world_size(source_meta, (source_macro.shape[1], source_macro.shape[0]), source_crop)
    meta = dict(source_meta)
    meta.update(
        {
            "name": args.artifact_name,
            "builder": "build_m11_junction_layer_proof.py",
            "heightmap_size_px": [width, height],
            "world_size_x_m": world_x,
            "world_size_z_m": world_z,
            "world_size_m": max(world_x, world_z),
            "elevation_min_m": output_elev_min,
            "elevation_max_m": output_elev_max,
            "elevation_range_m": output_elev_range,
            "material": "m11_three_way_junction_layer_preview",
            "texture_is_real_imagery": False,
            "m11_junction_layer_proof": {
                "version": 1,
                "kind": "m11_three_way_junction_layer_proof",
                "source_macro": eco.res_path(args.source_macro),
                "source_heightmap": eco.res_path(args.source_heightmap),
                "source_crop_macro_px": list(source_crop),
                "canyon_macro_reference": eco.res_path(args.canyon_reference_macro)
                if args.canyon_reference_macro
                else None,
                "canyon_macro_reference_crop": args.canyon_reference_crop,
                "domains": ["source_scrub", "grassland", "canyon_rock"],
                "policy": "macro_guidance_plus_runtime_splat_weights_plus_mask_driven_scatter",
            },
        }
    )
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    weight_sum = (
        layers["source_scrub_weight"]
        + layers["grassland_weight"]
        + layers["junction_soil_weight"]
        + layers["canyon_rock_weight"]
    )
    grad_y, grad_x = np.gradient(height_out)
    junction_mask = layers["junction_weight"] > 0.25
    metrics = {
        "height_m": {
            "min": output_elev_min,
            "max": output_elev_max,
            "range": output_elev_range,
            "junction_gradient_p95_m_per_px": float(np.percentile(np.sqrt(grad_x * grad_x + grad_y * grad_y)[junction_mask], 95)),
        },
        "junction": {
            "mean_weight": float(np.mean(layers["junction_weight"])),
            "coverage_gt_0_25": float(np.mean(layers["junction_weight"] > 0.25)),
            "triple_core_coverage_gt_0_25": float(np.mean(layers["triple_core_weight"] > 0.25)),
            "dominant_domain_min_coverage": float(
                min(
                    np.mean(layers["source_scrub_domain"] > 0.55),
                    np.mean(layers["grassland_domain"] > 0.55),
                    np.mean(layers["canyon_domain"] > 0.55),
                )
            ),
        },
        "weights": {
            "max_sum_error": float(np.max(np.abs(weight_sum - 1.0))),
            "source_scrub_mean": float(np.mean(layers["source_scrub_weight"])),
            "grassland_mean": float(np.mean(layers["grassland_weight"])),
            "junction_soil_mean": float(np.mean(layers["junction_soil_weight"])),
            "canyon_rock_mean": float(np.mean(layers["canyon_rock_weight"])),
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
        "kind": "m11_three_way_junction_layer_proof",
        "id": args.texture_out.name,
        "runtime_macro": eco.res_path(macro_path),
        "runtime_source_macro_valid_mask": eco.res_path(valid_mask_path),
        "runtime_source_macro_weight_mask": eco.res_path(source_macro_weight_mask_path),
        "runtime_splat_weights": eco.res_path(splat_weights_path),
        "runtime_material": eco.res_path(args.material_out),
        "runtime_heightmap": eco.res_path(height_path),
        "runtime_meta": eco.res_path(meta_path),
        "contact_sheet": eco.res_path(args.contact_sheet),
        "layers": {name: eco.res_path(path) for name, path in layer_paths.items()},
        "metrics": metrics,
        "policy": "three_way_junction_macro_guidance_plus_runtime_splat_weights",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-macro", type=Path, default=DEFAULT_SOURCE_MACRO)
    parser.add_argument("--source-valid-mask", type=Path, default=DEFAULT_SOURCE_MASK)
    parser.add_argument("--source-heightmap", type=Path, default=DEFAULT_SOURCE_HEIGHT)
    parser.add_argument("--source-meta", type=Path, default=DEFAULT_SOURCE_META)
    parser.add_argument("--source-crop", default="80,760,1024,1024")
    parser.add_argument("--grass-material-id", default="m8_grassland_grass_calm_v3")
    parser.add_argument("--grass-catalog", type=Path, default=ROOT / "materials/catalog_comfy_candidates.json")
    parser.add_argument("--canyon-material-id", default="desert_canyon_rock")
    parser.add_argument("--canyon-catalog", type=Path, default=ROOT / "materials/catalog.json")
    parser.add_argument("--canyon-reference-macro", type=Path, default=DEFAULT_CANYON_REFERENCE)
    parser.add_argument("--canyon-reference-crop", default="2400,3500,3600,3600")
    parser.add_argument("--grass-elev-range-m", type=float, default=22.0)
    parser.add_argument("--canyon-elev-range-m", type=float, default=42.0)
    parser.add_argument("--texture-out", type=Path, default=DEFAULT_TEXTURE_OUT)
    parser.add_argument("--topo-out", type=Path, default=DEFAULT_TOPO_OUT)
    parser.add_argument("--material-out", type=Path, default=DEFAULT_MATERIAL_OUT)
    parser.add_argument("--contact-sheet", type=Path, default=DEFAULT_CONTACT)
    parser.add_argument("--metrics-out", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--grass-slot-material", default="m8_grassland_grass_calm_v3")
    parser.add_argument("--soil-slot-material", default="dry_wash")
    parser.add_argument("--rock-slot-material", default="desert_canyon_rock")
    parser.add_argument("--source-slot-material", default="scrub_sparse")
    parser.add_argument("--fallback-slot-material", default="grassland_dirt")
    parser.add_argument("--seed", type=int, default=2311)
    parser.add_argument("--artifact-name", default="M11 three-way source grassland canyon junction proof")
    args = parser.parse_args()

    manifest = write_outputs(args)
    print(json.dumps(manifest["metrics"], indent=2))
    print(f"wrote {args.texture_out}")
    print(f"wrote {args.topo_out}")
    print(f"wrote {args.contact_sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
