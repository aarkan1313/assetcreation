#!/usr/bin/env python3
"""Build an M11 four-way terrain corner proof.

This is the next M11 case after the accepted three-way junction proof. It uses
the same runtime contract, but fills all four explicit splat channels:

- R: our current Comfy/procedural grassland candidate;
- G: controlled fantasy lava/basalt material;
- B: canyon/dry-rock terrain;
- A: photoreal source scrub.

The goal is not final game art. The goal is to prove the workflow can compose
four unlike terrain ownership fields into one continuous height/macro/splat
surface without a hard cross-shaped strip.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import build_ecotone_layer_proof as eco
import build_m11_junction_layer_proof as m11
import build_procedural_neighbor_bundle as procedural
import build_source_stack_runtime_review as source_review


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT.parent

DEFAULT_SOURCE_MACRO = m11.DEFAULT_SOURCE_MACRO
DEFAULT_SOURCE_MASK = m11.DEFAULT_SOURCE_MASK
DEFAULT_SOURCE_HEIGHT = m11.DEFAULT_SOURCE_HEIGHT
DEFAULT_SOURCE_META = m11.DEFAULT_SOURCE_META
DEFAULT_CANYON_REFERENCE = m11.DEFAULT_CANYON_REFERENCE

DEFAULT_TEXTURE_OUT = ROOT / "textures/source_stack/m11_fourway_corner_proof"
DEFAULT_TOPO_OUT = ROOT / "toporeview/m11_fourway_corner_proof"
DEFAULT_MATERIAL_OUT = ROOT / "textures/wgv3/terrain_m11_fourway_corner.tres"
DEFAULT_CONTACT = ROOT / "docs/captures/review/m11_fourway_corner_contact_sheet.png"
DEFAULT_METRICS = ROOT / "docs/captures/review/m11_fourway_corner_metrics.json"
DEFAULT_FANTASY_SOURCE = ASSET_ROOT / "world/textures/library/biome_lava_field"
DEFAULT_FANTASY_RUNTIME = ROOT / "textures/wgv3/fantasy_lava_field_controlled"
DEFAULT_FANTASY_CATALOG = ROOT / "materials/catalog_m11_fourway_generated.json"

FANTASY_MATERIAL_ID = "fantasy_lava_field_controlled"


def write_controlled_lava_albedo(src: Path, dst: Path) -> None:
    rgb = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32) / 255.0
    luma = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    shadow_lift = np.clip((0.26 - luma) * 0.42, 0.0, 0.13)
    hot = np.clip(rgb[:, :, 0] * 1.18 + rgb[:, :, 1] * 0.52 - rgb[:, :, 2] * 0.34 - 0.42, 0.0, 1.0)
    ash = np.array([0.18, 0.135, 0.105], dtype=np.float32)
    ember = np.array([0.86, 0.39, 0.12], dtype=np.float32)
    out = rgb * 0.66 + ash[None, None, :] * 0.34
    out += shadow_lift[:, :, None]
    out = out * (1.0 - hot[:, :, None] * 0.18) + ember[None, None, :] * (hot[:, :, None] * 0.18)
    Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8), mode="RGB").save(dst)


def stage_fantasy_material(src_dir: Path, out_dir: Path, catalog_path: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    map_sources = {
        "albedo": src_dir / "biome_lava_field_albedo.png",
        "normal": src_dir / "biome_lava_field_normal.png",
        "roughness": src_dir / "biome_lava_field_roughness.png",
        "height": src_dir / "biome_lava_field_height.png",
        "ao": src_dir / "biome_lava_field_ao.png",
    }
    for kind, src in map_sources.items():
        if not src.exists():
            raise FileNotFoundError(src)
        dst = out_dir / f"{kind}.png"
        if kind == "albedo":
            write_controlled_lava_albedo(src, dst)
        elif not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
            shutil.copyfile(src, dst)

    rel_dir = "world3/" + out_dir.relative_to(ROOT).as_posix()
    material = {
        "id": FANTASY_MATERIAL_ID,
        "source": "fantasy",
        "asset_status": "m11_fourway_validation_candidate",
        "provenance": {
            "type": "staged_existing_library_material",
            "source_asset_id": "biome_lava_field",
            "source_path": "world/textures/library/biome_lava_field",
            "policy": "M11 four-way proof only; review in terrain context before promotion",
            "visual_note": (
                "Chosen over mana crystal and ice cavern because it can read as controlled "
                "fantasy basalt/lava terrain. The staged albedo lifts the black values and "
                "subdues the hot cracks for terrain-context review."
            ),
            "settings": {
                "world_uv_scale": 0.012,
                "detail_uv_scale_mult": 8.0,
                "normal_strength": 0.045,
                "detail_albedo_strength": 0.025,
            },
        },
        "scale_m_per_repeat": 10.0,
        "color_family": "fantasy-basalt-lava",
        "runtime_texture_dir": rel_dir,
        "pbr_maps": {
            "albedo": f"{rel_dir}/albedo.png",
            "normal": f"{rel_dir}/normal.png",
            "roughness": f"{rel_dir}/roughness.png",
            "height": f"{rel_dir}/height.png",
            "ao": f"{rel_dir}/ao.png",
            "detail_albedo": f"{rel_dir}/albedo.png",
            "detail_normal": f"{rel_dir}/normal.png",
            "detail_roughness": f"{rel_dir}/roughness.png",
        },
        "shader_binding": "terrain_hex_detail",
        "validated_views": {
            "close": "needs_review",
            "mid": "needs_review",
            "far": "needs_review",
        },
    }
    catalog = {
        "version": 1,
        "updated": "2026-05-10",
        "role": "m11_fourway_sidecar_catalog_not_canonical",
        "materials": [material],
    }
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")


def load_gray(path: Path, width: int, height: int) -> np.ndarray:
    img = Image.open(path).convert("L")
    if img.size != (width, height):
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def build_domain_fields(width: int, height: int, seed: int) -> dict[str, np.ndarray]:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x = (xx / max(width - 1, 1) - 0.5) * 2.0
    y = (yy / max(height - 1, 1) - 0.5) * 2.0

    low = eco.smooth_noise(width, height, 164, seed + 11) * 2.0 - 1.0
    med = eco.smooth_noise(width, height, 64, seed + 17) * 2.0 - 1.0
    fine = eco.smooth_noise(width, height, 24, seed + 23) * 2.0 - 1.0

    split_x = -0.05 + low * 0.17 + np.sin((y * 1.18 + med * 0.28) * np.pi) * 0.15
    split_y = 0.04 + med * 0.16 + np.sin((x * 1.02 - low * 0.32) * np.pi) * 0.14
    east = np.clip(((x - split_x) / 0.56) * 0.5 + 0.5, 0.0, 1.0)
    south = np.clip(((y - split_y) / 0.60) * 0.5 + 0.5, 0.0, 1.0)
    east = east * east * (3.0 - 2.0 * east)
    south = south * south * (3.0 - 2.0 * south)

    weights = np.stack(
        [
            (1.0 - east) * (1.0 - south),  # grassland
            east * (1.0 - south),          # fantasy lava/basalt
            east * south,                  # canyon rock
            (1.0 - east) * south,          # source scrub
        ],
        axis=2,
    )
    eddy = np.exp(-((x * x + y * y) / 0.36)) * 0.18
    weights[:, :, 0] += eddy * np.clip(0.62 - south, 0.0, 1.0)
    weights[:, :, 1] += eddy * np.clip(east - 0.38, 0.0, 1.0)
    weights[:, :, 2] += eddy * np.clip(south - 0.36, 0.0, 1.0)
    weights[:, :, 3] += eddy * np.clip(0.60 - east, 0.0, 1.0)
    weights += np.stack(
        [
            np.maximum(low, 0.0) * 0.025,
            np.maximum(med, 0.0) * 0.024,
            np.maximum(-low, 0.0) * 0.025,
            np.maximum(-med, 0.0) * 0.024,
        ],
        axis=2,
    )
    weights /= np.maximum(np.sum(weights, axis=2, keepdims=True), 1e-6)

    for idx in range(4):
        weights[:, :, idx] = eco.gaussian_gray(weights[:, :, idx], 1.15)
    weights /= np.maximum(np.sum(weights, axis=2, keepdims=True), 1e-6)

    max_w = np.max(weights, axis=2)
    junction = np.clip((1.0 - max_w) / 0.70, 0.0, 1.0)
    junction = np.power(junction, 0.68)
    quad = np.clip(np.prod(weights, axis=2) * 430.0, 0.0, 1.0)
    quad = eco.gaussian_gray(quad, 3.2)

    rel_x = x - split_x
    rel_y = y - split_y
    cross_a = np.exp(-np.square((rel_x + rel_y + low * 0.10) / 0.24))
    cross_b = np.exp(-np.square((rel_x - rel_y + med * 0.12) / 0.24))
    cross_wash = eco.gaussian_gray(np.clip((cross_a + cross_b) * junction * 0.42, 0.0, 1.0), 2.0)

    return {
        "grassland_domain": weights[:, :, 0].astype(np.float32),
        "fantasy_lava_domain": weights[:, :, 1].astype(np.float32),
        "canyon_domain": weights[:, :, 2].astype(np.float32),
        "source_scrub_domain": weights[:, :, 3].astype(np.float32),
        "junction_weight": junction.astype(np.float32),
        "quad_core_weight": quad.astype(np.float32),
        "cross_wash_weight": cross_wash.astype(np.float32),
        "noise_low": low.astype(np.float32),
        "noise_med": med.astype(np.float32),
        "noise_fine": fine.astype(np.float32),
    }


def build_height(
    source_h: np.ndarray,
    fantasy_height: np.ndarray,
    fields: dict[str, np.ndarray],
    seed: int,
    grass_range_m: float,
    canyon_range_m: float,
    fantasy_range_m: float,
) -> np.ndarray:
    height, width = source_h.shape
    target_mid = float(np.median(source_h))
    grass_h = procedural.build_height(width, height, target_mid - grass_range_m * 0.42, grass_range_m, seed + 300)
    canyon_h = procedural.build_height(width, height, target_mid - canyon_range_m * 0.38, canyon_range_m, seed + 400)
    fantasy_h = procedural.build_height(width, height, target_mid - fantasy_range_m * 0.50, fantasy_range_m, seed + 500)

    fantasy_detail = eco.normalize01(fantasy_height)
    fantasy_detail = eco.gaussian_gray(fantasy_detail, 1.4)
    fantasy_h += (fantasy_detail - 0.5) * 7.5

    grass_h += target_mid - float(np.median(grass_h))
    canyon_h += target_mid - float(np.median(canyon_h)) + 2.2
    fantasy_h += target_mid - float(np.median(fantasy_h)) - 1.5

    hard = (
        grass_h * fields["grassland_domain"]
        + fantasy_h * fields["fantasy_lava_domain"]
        + canyon_h * fields["canyon_domain"]
        + source_h * fields["source_scrub_domain"]
    )
    low_relief = eco.gaussian_gray(eco.normalize01(hard), 2.8)
    low_relief = float(np.min(hard)) + low_relief * max(float(np.max(hard) - np.min(hard)), 1e-6)
    blend = np.clip(fields["junction_weight"] * 0.58 + fields["quad_core_weight"] * 0.20, 0.0, 0.76)
    out = hard * (1.0 - blend) + low_relief * blend
    out -= fields["cross_wash_weight"] * 2.1
    return out.astype(np.float32)


def build_layers(
    source_rgb: np.ndarray,
    grass_rgb: np.ndarray,
    canyon_rgb: np.ndarray,
    fantasy_rgb: np.ndarray,
    height_m: np.ndarray,
    fields: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    source = fields["source_scrub_domain"]
    grass = fields["grassland_domain"]
    canyon = fields["canyon_domain"]
    fantasy = fields["fantasy_lava_domain"]
    junction = fields["junction_weight"]
    quad = fields["quad_core_weight"]
    cross_wash = fields["cross_wash_weight"]
    low = (fields["noise_low"] + 1.0) * 0.5
    med = (fields["noise_med"] + 1.0) * 0.5

    source_luma = source_rgb[:, :, 0] * 0.2126 + source_rgb[:, :, 1] * 0.7152 + source_rgb[:, :, 2] * 0.0722
    green_excess = np.maximum(source_rgb[:, :, 1] - np.maximum(source_rgb[:, :, 0], source_rgb[:, :, 2]) * 0.86, 0.0)
    dark_mass = np.maximum(0.34 - source_luma, 0.0)
    source_feature = eco.gaussian_gray(np.clip(green_excess * 4.2 + dark_mass * 2.0, 0.0, 1.0), 2.4)

    fantasy_hot = np.clip(fantasy_rgb[:, :, 0] * 1.22 + fantasy_rgb[:, :, 1] * 0.62 - fantasy_rgb[:, :, 2] * 0.42 - 0.42, 0.0, 1.0)
    fantasy_hot = eco.gaussian_gray(fantasy_hot, 1.2)

    grad_y, grad_x = np.gradient(height_m)
    slope = eco.normalize01(np.sqrt(grad_x * grad_x + grad_y * grad_y), 42.0, 99.7)
    soil_exposure = np.clip(junction * (0.13 + med * 0.28) + quad * 0.20 + cross_wash * 0.22, 0.0, 1.0)
    rock_cluster = np.clip(canyon * (0.18 + slope * 0.78) + junction * slope * 0.40 + cross_wash * canyon * 0.22, 0.0, 1.0)
    shrub_carryover = np.clip(source_feature * (source + junction * 0.46) + quad * 0.10, 0.0, 1.0)
    dry_grass_density = np.clip(grass * (0.46 + low * 0.26) + junction * (0.14 + med * 0.20), 0.0, 1.0)
    fantasy_crack_mask = np.clip(fantasy * fantasy_hot * 0.86 + quad * fantasy_hot * 0.22, 0.0, 1.0)
    wash_line = np.clip(cross_wash * 0.70 + canyon * junction * 0.16 + fantasy * fantasy_hot * 0.10, 0.0, 1.0)
    no_scatter = np.clip(slope * 0.82 + rock_cluster * 0.28 + fantasy_crack_mask * 0.24, 0.0, 1.0)

    grass_weight = np.clip(grass * (1.0 - soil_exposure * 0.20 - rock_cluster * 0.10) + dry_grass_density * junction * 0.16, 0.0, 1.0)
    fantasy_weight = np.clip(fantasy * (0.92 + fantasy_crack_mask * 0.20) + quad * 0.10 - soil_exposure * 0.04, 0.0, 1.0)
    canyon_weight = np.clip(canyon * (0.95 + slope * 0.34) + rock_cluster * 0.42 + cross_wash * 0.04, 0.0, 1.0)
    source_weight = np.clip(source * (1.0 - soil_exposure * 0.18 - rock_cluster * 0.12) + shrub_carryover * junction * 0.18, 0.0, 1.0)
    stack = np.stack([grass_weight, fantasy_weight, canyon_weight, source_weight], axis=2)
    stack = np.power(np.maximum(stack, 1e-5), 1.10)
    stack /= np.maximum(np.sum(stack, axis=2, keepdims=True), 1e-6)

    return {
        "grassland_domain": grass,
        "fantasy_lava_domain": fantasy,
        "canyon_domain": canyon,
        "source_scrub_domain": source,
        "junction_weight": junction,
        "quad_core_weight": quad,
        "cross_wash_weight": cross_wash,
        "grassland_weight": stack[:, :, 0],
        "fantasy_lava_weight": stack[:, :, 1],
        "canyon_rock_weight": stack[:, :, 2],
        "source_scrub_weight": stack[:, :, 3],
        "shrub_carryover_mask": shrub_carryover,
        "dry_grass_density_mask": dry_grass_density,
        "soil_exposure_mask": soil_exposure,
        "rock_cluster_mask": rock_cluster,
        "fantasy_crack_mask": fantasy_crack_mask,
        "wash_line_mask": wash_line,
        "no_scatter_mask": no_scatter,
    }


def build_macro_preview(
    source_rgb: np.ndarray,
    grass_rgb: np.ndarray,
    canyon_rgb: np.ndarray,
    fantasy_rgb: np.ndarray,
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

    if canyon_reference_rgb is not None:
        canyon_base = np.clip(canyon_reference_rgb * 0.78 + canyon_rgb * 0.22, 0.0, 1.0)
    else:
        warm_canyon = np.array([0.64, 0.42, 0.24], dtype=np.float32)
        canyon_base = np.clip(canyon_rgb * 0.62 + warm_canyon[None, None, :] * 0.38, 0.0, 1.0)
    rock_warm = np.array([0.74, 0.45, 0.24], dtype=np.float32)
    rock_shadow = np.array([0.18, 0.14, 0.11], dtype=np.float32)
    rock_alpha = np.clip(layers["rock_cluster_mask"] * 0.20 + slope * layers["canyon_domain"] * 0.14, 0.0, 0.34)
    shadow_alpha = np.clip(layers["wash_line_mask"] * 0.25 + slope * layers["canyon_domain"] * 0.10, 0.0, 0.32)
    rock_color = np.clip(canyon_base * (0.80 + light[:, :, None] * 0.32 + fine[:, :, None] * 0.035), 0.0, 1.0)
    rock_color = rock_color * (1.0 - rock_alpha[:, :, None]) + rock_warm[None, None, :] * rock_alpha[:, :, None]
    rock_color = rock_color * (1.0 - shadow_alpha[:, :, None]) + rock_shadow[None, None, :] * shadow_alpha[:, :, None]

    grass_color = np.clip(grass_rgb * (0.88 + low[:, :, None] * 0.12 + fine[:, :, None] * 0.04), 0.0, 1.0)
    grass_patch = np.clip((ridge_noise - 0.42) * 0.56 * layers["dry_grass_density_mask"], 0.0, 0.22)
    straw = np.array([0.54, 0.47, 0.29], dtype=np.float32)
    olive = np.array([0.25, 0.33, 0.19], dtype=np.float32)
    patch_color = straw[None, None, :] * (1.0 - ridge_noise[:, :, None]) + olive[None, None, :] * ridge_noise[:, :, None]
    grass_color = grass_color * (1.0 - grass_patch[:, :, None]) + patch_color * grass_patch[:, :, None]

    basalt = np.array([0.14, 0.105, 0.075], dtype=np.float32)
    ember = np.array([0.95, 0.48, 0.16], dtype=np.float32)
    fantasy_base = np.clip(fantasy_rgb * 0.78 + basalt[None, None, :] * 0.22, 0.0, 1.0)
    fantasy_base = fantasy_base * (0.86 + light[:, :, None] * 0.12 + fine[:, :, None] * 0.030)
    fantasy_alpha = np.clip(layers["fantasy_crack_mask"][:, :, None] * 0.24, 0.0, 0.24)
    fantasy_color = fantasy_base * (1.0 - fantasy_alpha) + ember[None, None, :] * fantasy_alpha

    source_color = np.clip(source_rgb * (0.95 + fine[:, :, None] * 0.055), 0.0, 1.0)
    preview = (
        grass_color * layers["grassland_weight"][:, :, None]
        + fantasy_color * layers["fantasy_lava_weight"][:, :, None]
        + rock_color * layers["canyon_rock_weight"][:, :, None]
        + source_color * layers["source_scrub_weight"][:, :, None]
    )

    wash_tint = np.array([0.28, 0.22, 0.16], dtype=np.float32)
    wash_alpha = np.clip(layers["cross_wash_weight"][:, :, None] * 0.14, 0.0, 0.14)
    preview = preview * (1.0 - wash_alpha) + wash_tint[None, None, :] * wash_alpha

    shrub_alpha = np.clip(layers["shrub_carryover_mask"] * (layers["source_scrub_domain"] * 0.07 + layers["junction_weight"] * 0.14), 0.0, 0.24)
    shrub_color = np.array([0.15, 0.21, 0.12], dtype=np.float32)
    preview = preview * (1.0 - shrub_alpha[:, :, None]) + shrub_color[None, None, :] * shrub_alpha[:, :, None]

    quad_tint = np.array([0.34, 0.26, 0.20], dtype=np.float32)
    quad = np.clip(layers["quad_core_weight"][:, :, None] * 0.10, 0.0, 0.10)
    preview = preview * (1.0 - quad) + quad_tint[None, None, :] * quad
    return np.clip(preview, 0.0, 1.0)


def build_macro_guidance_weight(layers: dict[str, np.ndarray]) -> np.ndarray:
    mask = 0.70 + layers["junction_weight"] * 0.12 + layers["quad_core_weight"] * 0.08
    mask += layers["cross_wash_weight"] * 0.04
    return eco.gaussian_gray(np.clip(mask, 0.0, 0.94), 2.0)


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
        [
            layers["grassland_domain"] * 0.78 + layers["source_scrub_domain"] * 0.32,
            layers["fantasy_lava_domain"] * 0.72 + layers["grassland_domain"] * 0.35,
            layers["canyon_domain"] * 0.70 + layers["quad_core_weight"] * 0.42,
        ],
        axis=2,
    )
    material_debug = np.stack(
        [
            layers["fantasy_lava_weight"] * 0.76 + layers["canyon_rock_weight"] * 0.42,
            layers["grassland_weight"] * 0.80 + layers["source_scrub_weight"] * 0.32,
            layers["source_scrub_weight"] * 0.58 + layers["quad_core_weight"] * 0.46,
        ],
        axis=2,
    )
    scatter_debug = np.stack(
        [
            layers["rock_cluster_mask"] * 0.72 + layers["fantasy_crack_mask"] * 0.55,
            layers["shrub_carryover_mask"] * 0.78 + layers["dry_grass_density_mask"] * 0.40,
            layers["wash_line_mask"] * 0.86 + layers["no_scatter_mask"] * 0.34,
        ],
        axis=2,
    )
    junction_debug = np.clip(
        layers["junction_weight"] + layers["quad_core_weight"] * 0.62 + layers["cross_wash_weight"] * 0.34,
        0.0,
        1.0,
    )
    panels = [
        label_panel("derived macro preview", preview, (420, 300)),
        label_panel("domain fields: grass/lava/canyon/source", domain_debug, (420, 300)),
        label_panel("RGBA material weights debug", np.clip(material_debug, 0.0, 1.0), (420, 300)),
        label_panel("scatter/feature masks debug", np.clip(scatter_debug, 0.0, 1.0), (420, 300)),
        label_panel("height field", eco.normalize01(height_m), (420, 300)),
        label_panel("junction + quad core + wash", junction_debug, (420, 300)),
    ]
    sheet = Image.new("RGB", (1260, 600), (10, 12, 12))
    for idx, panel in enumerate(panels):
        sheet.paste(panel, ((idx % 3) * 420, (idx // 3) * 300))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def write_fourway_material(path: Path, texture_out: Path, slot_materials: dict[str, str], extra_catalogs: list[Path]) -> None:
    eco.write_ecotone_material(
        path,
        texture_out / "source_macro_albedo.png",
        texture_out / "source_macro_weight_mask.png",
        texture_out / "layers/splat_weights_rgba.png",
        slot_materials,
        extra_catalogs,
    )
    text = path.read_text(encoding="utf-8")
    text = text.replace("shader_parameter/source_macro_strength = 0.76", "shader_parameter/source_macro_strength = 0.72")
    text = text.replace("shader_parameter/splat_weight_power = 1.95", "shader_parameter/splat_weight_power = 1.48")
    text = text.replace("shader_parameter/detail_albedo_strength = 0.035", "shader_parameter/detail_albedo_strength = 0.030")
    text = text.replace("shader_parameter/normal_strength = 0.075", "shader_parameter/normal_strength = 0.054")
    source_review.write_text_lf(path, text)


def write_outputs(args: argparse.Namespace) -> dict[str, Any]:
    stage_fantasy_material(args.fantasy_source_dir, args.fantasy_runtime_dir, args.fantasy_catalog)

    source_meta = json.loads(args.source_meta.read_text(encoding="utf-8"))
    source_macro = eco.load_rgb(args.source_macro)
    source_height = eco.load_height_m(args.source_heightmap, source_meta)
    source_crop = eco.parse_crop(args.source_crop)

    source_rgb = eco.crop_array(source_macro, source_crop)
    size = (source_crop[2], source_crop[3])
    if size[0] != size[1]:
        raise ValueError("M11 four-way proof expects a square source crop")
    width, height = size
    source_h = eco.crop_height_from_macro_space(
        source_height,
        (source_macro.shape[1], source_macro.shape[0]),
        source_crop,
        (width, height),
    )

    grass_rgb = m11.build_procedural_macro(args.grass_material_id, args.grass_catalog, width, height, args.seed + 100)
    canyon_rgb = m11.build_procedural_macro(args.canyon_material_id, args.canyon_catalog, width, height, args.seed + 200)
    fantasy_rgb = m11.build_procedural_macro(FANTASY_MATERIAL_ID, args.fantasy_catalog, width, height, args.seed + 250)
    fantasy_height = load_gray(args.fantasy_runtime_dir / "height.png", width, height)
    canyon_reference_rgb = m11.load_reference_macro(
        args.canyon_reference_macro,
        args.canyon_reference_crop,
        width,
        height,
    )

    fields = build_domain_fields(width, height, args.seed)
    height_out = build_height(
        source_h,
        fantasy_height,
        fields,
        args.seed,
        args.grass_elev_range_m,
        args.canyon_elev_range_m,
        args.fantasy_elev_range_m,
    )
    layers = build_layers(source_rgb, grass_rgb, canyon_rgb, fantasy_rgb, height_out, fields)
    preview = build_macro_preview(source_rgb, grass_rgb, canyon_rgb, fantasy_rgb, canyon_reference_rgb, height_out, layers, args.seed)
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

    m11.save_rgb(macro_path, preview)
    m11.save_gray(valid_mask_path, np.ones((height, width), dtype=np.float32))
    m11.save_gray(source_macro_weight_mask_path, macro_guidance_weight)
    m11.save_rgba(
        splat_weights_path,
        np.stack(
            [
                layers["grassland_weight"],
                layers["fantasy_lava_weight"],
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
        m11.save_gray(path, arr)
        layer_paths[name] = path
    layer_paths["splat_weights_rgba"] = splat_weights_path
    m11.save_rgb(layer_out / "source_crop_reference.png", source_rgb)
    m11.save_rgb(layer_out / "grassland_macro_reference.png", grass_rgb)
    m11.save_rgb(layer_out / "canyon_macro_reference.png", canyon_rgb)
    m11.save_rgb(layer_out / "fantasy_lava_macro_reference.png", fantasy_rgb)
    if canyon_reference_rgb is not None:
        m11.save_rgb(layer_out / "canyon_master_stack_reference.png", canyon_reference_rgb)

    write_contact_sheet(args.contact_sheet, preview, height_out, layers)
    write_fourway_material(
        args.material_out,
        args.texture_out,
        {
            "grass": args.grass_slot_material,
            "dirt": FANTASY_MATERIAL_ID,
            "rock_light": args.rock_slot_material,
            "rock_dark": args.source_slot_material,
            "snow": args.fallback_slot_material,
        },
        [args.grass_catalog, args.fantasy_catalog, ROOT / "materials/catalog_repair_candidates.json"],
    )

    world_x, world_z = eco.crop_world_size(source_meta, (source_macro.shape[1], source_macro.shape[0]), source_crop)
    meta = dict(source_meta)
    meta.update(
        {
            "name": args.artifact_name,
            "builder": "build_m11_fourway_corner_proof.py",
            "heightmap_size_px": [width, height],
            "world_size_x_m": world_x,
            "world_size_z_m": world_z,
            "world_size_m": max(world_x, world_z),
            "elevation_min_m": output_elev_min,
            "elevation_max_m": output_elev_max,
            "elevation_range_m": output_elev_range,
            "material": "m11_fourway_corner_layer_preview",
            "texture_is_real_imagery": False,
            "m11_fourway_corner_proof": {
                "version": 1,
                "kind": "m11_fourway_corner_layer_proof",
                "source_macro": eco.res_path(args.source_macro),
                "source_heightmap": eco.res_path(args.source_heightmap),
                "source_crop_macro_px": list(source_crop),
                "canyon_macro_reference": eco.res_path(args.canyon_reference_macro)
                if args.canyon_reference_macro
                else None,
                "canyon_macro_reference_crop": args.canyon_reference_crop,
                "fantasy_material": FANTASY_MATERIAL_ID,
                "domains": ["grassland", "fantasy_lava", "canyon_rock", "source_scrub"],
                "splat_rgba_contract": {
                    "R": "grassland_weight",
                    "G": "fantasy_lava_weight",
                    "B": "canyon_rock_weight",
                    "A": "source_scrub_weight",
                },
                "policy": "macro_guidance_plus_runtime_splat_weights_plus_mask_driven_scatter",
            },
        }
    )
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    weight_sum = (
        layers["grassland_weight"]
        + layers["fantasy_lava_weight"]
        + layers["canyon_rock_weight"]
        + layers["source_scrub_weight"]
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
            "quad_core_coverage_gt_0_25": float(np.mean(layers["quad_core_weight"] > 0.25)),
            "dominant_domain_min_coverage": float(
                min(
                    np.mean(layers["grassland_domain"] > 0.55),
                    np.mean(layers["fantasy_lava_domain"] > 0.55),
                    np.mean(layers["canyon_domain"] > 0.55),
                    np.mean(layers["source_scrub_domain"] > 0.55),
                )
            ),
        },
        "weights": {
            "max_sum_error": float(np.max(np.abs(weight_sum - 1.0))),
            "grassland_mean": float(np.mean(layers["grassland_weight"])),
            "fantasy_lava_mean": float(np.mean(layers["fantasy_lava_weight"])),
            "canyon_rock_mean": float(np.mean(layers["canyon_rock_weight"])),
            "source_scrub_mean": float(np.mean(layers["source_scrub_weight"])),
            "macro_guidance_weight_mean": float(np.mean(macro_guidance_weight)),
        },
        "feature_masks": {
            "shrub_carryover_mean": float(np.mean(layers["shrub_carryover_mask"])),
            "dry_grass_density_mean": float(np.mean(layers["dry_grass_density_mask"])),
            "soil_exposure_mean": float(np.mean(layers["soil_exposure_mask"])),
            "rock_cluster_mean": float(np.mean(layers["rock_cluster_mask"])),
            "fantasy_crack_mean": float(np.mean(layers["fantasy_crack_mask"])),
            "wash_line_mean": float(np.mean(layers["wash_line_mask"])),
            "no_scatter_mean": float(np.mean(layers["no_scatter_mask"])),
        },
    }
    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_out.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "version": 1,
        "kind": "m11_fourway_corner_layer_proof",
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
        "policy": "four_way_corner_macro_guidance_plus_runtime_splat_weights",
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
    parser.add_argument("--fantasy-source-dir", type=Path, default=DEFAULT_FANTASY_SOURCE)
    parser.add_argument("--fantasy-runtime-dir", type=Path, default=DEFAULT_FANTASY_RUNTIME)
    parser.add_argument("--fantasy-catalog", type=Path, default=DEFAULT_FANTASY_CATALOG)
    parser.add_argument("--grass-elev-range-m", type=float, default=22.0)
    parser.add_argument("--canyon-elev-range-m", type=float, default=42.0)
    parser.add_argument("--fantasy-elev-range-m", type=float, default=28.0)
    parser.add_argument("--texture-out", type=Path, default=DEFAULT_TEXTURE_OUT)
    parser.add_argument("--topo-out", type=Path, default=DEFAULT_TOPO_OUT)
    parser.add_argument("--material-out", type=Path, default=DEFAULT_MATERIAL_OUT)
    parser.add_argument("--contact-sheet", type=Path, default=DEFAULT_CONTACT)
    parser.add_argument("--metrics-out", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--grass-slot-material", default="m8_grassland_grass_calm_v3")
    parser.add_argument("--rock-slot-material", default="desert_canyon_rock")
    parser.add_argument("--source-slot-material", default="scrub_sparse")
    parser.add_argument("--fallback-slot-material", default="grassland_dirt")
    parser.add_argument("--seed", type=int, default=4117)
    parser.add_argument("--artifact-name", default="M11 four-way photoreal grassland fantasy canyon corner proof")
    args = parser.parse_args()

    manifest = write_outputs(args)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
