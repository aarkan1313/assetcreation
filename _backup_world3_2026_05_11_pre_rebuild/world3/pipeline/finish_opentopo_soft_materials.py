"""Finish OpenTopo soft composites into Godot-ready material candidates.

The inputs are the source-real `tileable_soft` composites from
build_opentopo_texture_variant_atlas.py. This pass keeps those originals intact
and writes a sibling `finished_material` folder with:

- a low-frequency-balanced albedo for less obvious repeated real-world motifs
- neutral close-detail albedo/normal/roughness maps derived from source pixels
- a Godot ShaderMaterial using terrain_hex_detail.gdshader
- a manifest with settings and QA metrics
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from build_opentopo_texture_variant_atlas import edge_metrics
from build_opentopo_tileable_texture import normal_from_height, save_tile_2x2, write_json


Image.MAX_IMAGE_PIXELS = None


def project_res_path(path: Path) -> str:
    text = str(path).replace("\\", "/")
    prefix = "D:/assets/world3/"
    if text.startswith(prefix):
        return "res://" + text[len(prefix):]
    return text


def load_float(path: Path, mode: str) -> np.ndarray:
    with Image.open(path) as img:
        arr = np.asarray(ImageOps.exif_transpose(img).convert(mode), dtype=np.float32)
    return arr / 255.0


def save_float(arr: np.ndarray, path: Path, mode: str) -> Image.Image:
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.clip(arr, 0.0, 1.0)
    img = Image.fromarray((arr * 255.0 + 0.5).astype(np.uint8), mode=mode)
    img.save(path)
    return img


def periodic_blur(arr: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0.0:
        return arr.copy()
    pad = int(max(8, min(512, radius * 3.0)))
    if arr.ndim == 3:
        padded = np.pad(arr, ((pad, pad), (pad, pad), (0, 0)), mode="wrap")
        mode = "RGB"
    else:
        padded = np.pad(arr, ((pad, pad), (pad, pad)), mode="wrap")
        mode = "L"
    img = Image.fromarray((np.clip(padded, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), mode=mode)
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    out = np.asarray(blurred, dtype=np.float32) / 255.0
    return out[pad:-pad, pad:-pad, ...] if arr.ndim == 3 else out[pad:-pad, pad:-pad]


def local_balance_albedo(
    albedo: np.ndarray,
    blur_radius: float,
    low_frequency_strength: float,
    detail_strength: float,
) -> np.ndarray:
    low = periodic_blur(albedo, blur_radius)
    mean = albedo.mean(axis=(0, 1), keepdims=True)
    balanced = mean + (low - mean) * low_frequency_strength + (albedo - low) * detail_strength
    return np.clip(balanced, 0.0, 1.0)


def luminance(rgb: np.ndarray) -> np.ndarray:
    return rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722


def neutral_detail_albedo(albedo: np.ndarray, radius: float, contrast: float) -> np.ndarray:
    lum = luminance(albedo)
    base = periodic_blur(lum, radius)
    high = lum - base
    scale = np.percentile(np.abs(high), 95.0)
    scale = max(float(scale), 1e-4)
    detail = np.clip(0.5 + (high / scale) * contrast * 0.18, 0.0, 1.0)
    return np.repeat(detail[:, :, None], 3, axis=2)


def detail_height_from_albedo_height(albedo: np.ndarray, height: np.ndarray, radius: float) -> Image.Image:
    lum = luminance(albedo)
    lum_high = lum - periodic_blur(lum, radius)
    height_high = height - periodic_blur(height, max(radius * 1.5, 2.0))
    combined = lum_high * 0.65 + height_high * 0.35
    scale = np.percentile(np.abs(combined), 96.0)
    scale = max(float(scale), 1e-4)
    detail_h = np.clip(0.5 + combined / scale * 0.18, 0.0, 1.0)
    return Image.fromarray((detail_h * 255.0 + 0.5).astype(np.uint8), mode="L")


def detail_roughness_from_albedo(albedo: np.ndarray, base_rough: np.ndarray) -> np.ndarray:
    lum = luminance(albedo)
    local = periodic_blur(lum, 14.0)
    high = np.abs(lum - local)
    scale = max(float(np.percentile(high, 95.0)), 1e-4)
    rough_detail = np.clip(0.56 + (high / scale) * 0.22, 0.0, 1.0)
    rough_base = float(np.median(base_rough))
    return np.clip(rough_detail * 0.65 + rough_base * 0.35, 0.0, 1.0)


def write_material(
    path: Path,
    outputs: dict[str, Path],
    settings: dict[str, float],
) -> None:
    shader = "res://shaders/terrain_hex_detail.gdshader"
    text = f"""[gd_resource type="ShaderMaterial" load_steps=9 format=3]

[ext_resource type="Shader" path="{shader}" id="shader"]
[ext_resource type="Texture2D" path="{project_res_path(outputs["albedo"])}" id="albedo"]
[ext_resource type="Texture2D" path="{project_res_path(outputs["normal"])}" id="normal"]
[ext_resource type="Texture2D" path="{project_res_path(outputs["roughness"])}" id="rough"]
[ext_resource type="Texture2D" path="{project_res_path(outputs["ao"])}" id="ao"]
[ext_resource type="Texture2D" path="{project_res_path(outputs["detail_albedo"])}" id="detail_albedo"]
[ext_resource type="Texture2D" path="{project_res_path(outputs["detail_normal"])}" id="detail_normal"]
[ext_resource type="Texture2D" path="{project_res_path(outputs["detail_roughness"])}" id="detail_rough"]

[resource]
shader = ExtResource("shader")
shader_parameter/albedo_tex = ExtResource("albedo")
shader_parameter/normal_tex = ExtResource("normal")
shader_parameter/rough_tex = ExtResource("rough")
shader_parameter/ao_tex = ExtResource("ao")
shader_parameter/detail_albedo_tex = ExtResource("detail_albedo")
shader_parameter/detail_normal_tex = ExtResource("detail_normal")
shader_parameter/detail_rough_tex = ExtResource("detail_rough")
shader_parameter/world_uv_scale = {settings["world_uv_scale"]}
shader_parameter/hex_strength = {settings["hex_strength"]}
shader_parameter/blend_sharpness = {settings["blend_sharpness"]}
shader_parameter/roughness_strength = {settings["roughness_strength"]}
shader_parameter/normal_strength = {settings["normal_strength"]}
shader_parameter/macro_scale = {settings["macro_scale"]}
shader_parameter/macro_value_strength = {settings["macro_value_strength"]}
shader_parameter/macro_hue_strength = {settings["macro_hue_strength"]}
shader_parameter/detail_uv_scale_mult = {settings["detail_uv_scale_mult"]}
shader_parameter/detail_albedo_strength = {settings["detail_albedo_strength"]}
shader_parameter/detail_normal_strength = {settings["detail_normal_strength"]}
shader_parameter/detail_rough_strength = {settings["detail_rough_strength"]}
shader_parameter/detail_fade_start_m = {settings["detail_fade_start_m"]}
shader_parameter/detail_fade_end_m = {settings["detail_fade_end_m"]}
"""
    path.write_text(text, encoding="utf-8")


def find_tileable_soft(manifest: dict) -> dict:
    soft = manifest.get("soft_composite", {})
    return soft.get("outputs", {}).get("tileable_soft", {})


def process_manifest(manifest_path: Path, args: argparse.Namespace) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tileable = find_tileable_soft(manifest)
    if not tileable:
        raise SystemExit(f"No tileable_soft output in {manifest_path}")

    material_class = str(manifest.get("material_class", manifest_path.parent.name))
    source_root = Path(tileable["albedo"]).parent
    out_dir = source_root.parent / "finished_material"
    out_dir.mkdir(parents=True, exist_ok=True)

    albedo = load_float(Path(tileable["albedo"]), "RGB")
    height = load_float(Path(tileable["height"]), "L")
    roughness = load_float(Path(tileable["roughness"]), "L")

    balanced = local_balance_albedo(
        albedo,
        args.balance_radius,
        args.low_frequency_strength,
        args.detail_strength,
    )
    detail_albedo = neutral_detail_albedo(albedo, args.detail_radius, args.detail_contrast)
    detail_height = detail_height_from_albedo_height(albedo, height, args.detail_radius)
    detail_rough = detail_roughness_from_albedo(albedo, roughness)

    outputs = {
        "albedo": out_dir / "albedo_balanced.png",
        "normal": Path(tileable["normal"]),
        "roughness": Path(tileable["roughness"]),
        "height": Path(tileable["height"]),
        "ao": out_dir / "ao_white.png",
        "detail_albedo": out_dir / "detail_albedo_neutral.png",
        "detail_height": out_dir / "detail_height.png",
        "detail_normal": out_dir / "detail_normal.png",
        "detail_roughness": out_dir / "detail_roughness.png",
        "tile_2x2": out_dir / "tile_2x2.png",
        "material": out_dir / "material_hex_detail_finished.tres",
    }

    albedo_img = save_float(balanced, outputs["albedo"], "RGB")
    save_tile_2x2(albedo_img, outputs["tile_2x2"])
    save_float(detail_albedo, outputs["detail_albedo"], "RGB")
    detail_height.save(outputs["detail_height"])
    normal_from_height(detail_height, strength=args.detail_normal_strength_px).save(outputs["detail_normal"])
    save_float(detail_rough, outputs["detail_roughness"], "L")
    Image.new("L", (16, 16), 255).save(outputs["ao"])

    settings = {
        "world_uv_scale": 1.0 / float(manifest.get("crop_size_m", 64)),
        "hex_strength": args.hex_strength,
        "blend_sharpness": 8.0,
        "roughness_strength": 1.0,
        "normal_strength": args.macro_normal_strength,
        "macro_scale": args.macro_scale,
        "macro_value_strength": args.macro_value_strength,
        "macro_hue_strength": args.macro_hue_strength,
        "detail_uv_scale_mult": args.detail_uv_scale_mult,
        "detail_albedo_strength": args.detail_albedo_strength,
        "detail_normal_strength": args.shader_detail_normal_strength,
        "detail_rough_strength": args.detail_rough_strength,
        "detail_fade_start_m": args.detail_fade_start_m,
        "detail_fade_end_m": args.detail_fade_end_m,
    }
    write_material(outputs["material"], outputs, settings)

    product = {
        "kind": "opentopo_finished_soft_material",
        "material_class": material_class,
        "source_manifest": str(manifest_path),
        "source_tileable_soft": tileable,
        "source_policy": "source_real_soft_composite_with_derived_detail",
        "procedural_color_used": False,
        "ai_generated_color_used": False,
        "geography_preserved": False,
        "operations": [
            "periodic_low_frequency_albedo_balance",
            "neutral_detail_albedo_from_source_luminance",
            "detail_normal_from_source_luminance_and_height",
            "terrain_hex_detail_shader_binding",
        ],
        "settings": settings,
        "image_settings": {
            "balance_radius_px": args.balance_radius,
            "low_frequency_strength": args.low_frequency_strength,
            "detail_strength": args.detail_strength,
            "detail_radius_px": args.detail_radius,
            "detail_contrast": args.detail_contrast,
        },
        "edge_metrics": {
            "balanced_albedo": edge_metrics(balanced),
            "source_albedo": edge_metrics(albedo),
        },
        "outputs": {key: str(value) for key, value in outputs.items()},
    }
    write_json(out_dir / "finish_manifest.json", product)
    return product


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", type=Path, default=Path("D:/assets/world3/opentopo/processed/textures"))
    ap.add_argument("--pattern", default="Guadalupe_Cypress_variants_*/manifest.json")
    ap.add_argument("--balance-radius", type=float, default=128.0)
    ap.add_argument("--low-frequency-strength", type=float, default=0.42)
    ap.add_argument("--detail-strength", type=float, default=1.05)
    ap.add_argument("--detail-radius", type=float, default=10.0)
    ap.add_argument("--detail-contrast", type=float, default=0.75)
    ap.add_argument("--detail-normal-strength-px", type=float, default=2.0)
    ap.add_argument("--hex-strength", type=float, default=1.0)
    ap.add_argument("--macro-normal-strength", type=float, default=0.45)
    ap.add_argument("--macro-scale", type=float, default=180.0)
    ap.add_argument("--macro-value-strength", type=float, default=0.05)
    ap.add_argument("--macro-hue-strength", type=float, default=0.012)
    ap.add_argument("--detail-uv-scale-mult", type=float, default=8.0)
    ap.add_argument("--detail-albedo-strength", type=float, default=0.22)
    ap.add_argument("--shader-detail-normal-strength", type=float, default=0.42)
    ap.add_argument("--detail-rough-strength", type=float, default=0.22)
    ap.add_argument("--detail-fade-start-m", type=float, default=8.0)
    ap.add_argument("--detail-fade-end-m", type=float, default=42.0)
    args = ap.parse_args()

    manifests = sorted(args.input_root.glob(args.pattern))
    if not manifests:
        raise SystemExit(f"No manifests matched {args.input_root / args.pattern}")

    products = [process_manifest(path, args) for path in manifests]
    index = {
        "kind": "opentopo_finished_soft_material_index",
        "input_root": str(args.input_root),
        "pattern": args.pattern,
        "count": len(products),
        "products": products,
    }
    index_path = args.input_root / "Guadalupe_Cypress_finished_materials_index.json"
    write_json(index_path, index)
    print(f"OK wrote {len(products)} finished materials")
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
