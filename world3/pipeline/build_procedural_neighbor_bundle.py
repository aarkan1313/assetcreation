#!/usr/bin/env python3
"""Build a small procedural terrain bundle for M10 seam-integration proofs.

The output intentionally matches the real-source bundle shape expected by
build_terrain_seam_integration_proof.py: macro albedo, valid mask, heightmap,
and meta. This keeps real-to-procedural tests on the same runtime path as
real-to-real tests.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]


def parse_size(value: str) -> tuple[int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 2:
        raise ValueError("size must be width,height")
    w, h = parts
    if w <= 0 or h <= 0:
        raise ValueError("size values must be positive")
    return w, h


def parse_world_size(value: str) -> tuple[float, float]:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 2:
        raise ValueError("world size must be width_m,height_m")
    w, h = parts
    if w <= 0.0 or h <= 0.0:
        raise ValueError("world size values must be positive")
    return w, h


def resolve_repo_path(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return ROOT.parent / p


def res_path(path: Path) -> str:
    rel = path.resolve().relative_to(ROOT.resolve())
    return "res://" + rel.as_posix()


def load_material(material_id: str, catalog_path: Path) -> dict[str, Any]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for mat in catalog.get("materials", []):
        if mat.get("id") == material_id:
            return mat
    raise KeyError(f"material id not found in catalog: {material_id}")


def smooth_noise(width: int, height: int, grid: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    small_w = max(2, int(np.ceil(width / grid)))
    small_h = max(2, int(np.ceil(height / grid)))
    small = rng.normal(0.0, 1.0, (small_h, small_w)).astype(np.float32)
    small = (small - small.min()) / max(float(small.max() - small.min()), 1e-6)
    img = Image.fromarray(np.clip(small * 255.0, 0, 255).astype(np.uint8), mode="L")
    img = img.resize((width, height), Image.Resampling.BICUBIC)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return arr * 2.0 - 1.0


def normalize01(arr: np.ndarray) -> np.ndarray:
    low = float(np.percentile(arr, 1))
    high = float(np.percentile(arr, 99))
    return np.clip((arr - low) / max(high - low, 1e-6), 0.0, 1.0)


def tiled_detail(albedo_path: Path, width: int, height: int, repeat_px: int, seed: int) -> np.ndarray:
    src = Image.open(albedo_path).convert("RGB")
    tile = src.resize((repeat_px, repeat_px), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width + repeat_px * 2, height + repeat_px * 2))
    rng = np.random.default_rng(seed)
    ox = int(rng.integers(0, repeat_px))
    oy = int(rng.integers(0, repeat_px))
    for y in range(-repeat_px, height + repeat_px, repeat_px):
        for x in range(-repeat_px, width + repeat_px, repeat_px):
            canvas.paste(tile, (x + ox + repeat_px, y + oy + repeat_px))
    crop = canvas.crop((repeat_px, repeat_px, repeat_px + width, repeat_px + height))
    return np.asarray(crop, dtype=np.float32) / 255.0


def build_macro(material: dict[str, Any], width: int, height: int, seed: int) -> np.ndarray:
    albedo_path = resolve_repo_path(material["pbr_maps"]["albedo"])
    albedo = Image.open(albedo_path).convert("RGB")
    albedo_arr = np.asarray(albedo, dtype=np.float32) / 255.0
    base = np.median(albedo_arr.reshape(-1, 3), axis=0)

    low = smooth_noise(width, height, 180, seed + 11)
    med = smooth_noise(width, height, 58, seed + 17)
    fine = smooth_noise(width, height, 22, seed + 23)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x = xx / max(width - 1, 1)
    y = yy / max(height - 1, 1)
    wash = np.sin((x * 1.35 + y * 2.1 + low * 0.10) * np.pi * 2.0)
    wash_bands = np.exp(-np.square(wash / 0.24))

    detail = tiled_detail(albedo_path, width, height, max(76, width // 5), seed + 31)
    detail_low = np.asarray(
        Image.fromarray(np.clip(detail * 255.0, 0, 255).astype(np.uint8), mode="RGB")
        .filter(ImageFilter.GaussianBlur(radius=0.8)),
        dtype=np.float32,
    ) / 255.0
    detail_signal = detail_low - np.mean(detail_low.reshape(-1, 3), axis=0)[None, None, :]

    value = 0.88 + low * 0.12 + med * 0.055 + fine * 0.018
    color = base[None, None, :] * value[:, :, None]
    color += detail_signal * 0.42
    color += wash_bands[:, :, None] * np.array([0.055, 0.035, 0.012], dtype=np.float32)
    color += (1.0 - y[:, :, None]) * np.array([0.025, 0.012, -0.006], dtype=np.float32)
    return np.clip(color, 0.0, 1.0)


def build_height(width: int, height: int, elev_min: float, elev_range: float, seed: int) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x = xx / max(width - 1, 1)
    y = yy / max(height - 1, 1)
    low = smooth_noise(width, height, 210, seed + 101)
    med = smooth_noise(width, height, 72, seed + 107)
    small = smooth_noise(width, height, 28, seed + 113)
    channel_wave = np.sin((x * 0.78 + y * 1.18 + low * 0.08) * np.pi * 2.0)
    channel = -0.045 * np.exp(-np.square(channel_wave / 0.35))
    ridge = 0.022 * np.sin((x * 1.35 - y * 0.42 + med * 0.12) * np.pi * 2.0)
    slope = x * 0.22 + y * 0.10
    field = slope + low * 0.22 + med * 0.06 + small * 0.012 + channel + ridge
    field = normalize01(field)
    img = Image.fromarray(np.clip(field * 255.0, 0, 255).astype(np.uint8), mode="L")
    field = np.asarray(img.filter(ImageFilter.GaussianBlur(radius=3.0)), dtype=np.float32) / 255.0
    norm = normalize01(field)
    return elev_min + norm * elev_range


def write_bundle(args: argparse.Namespace) -> dict[str, Any]:
    width, height = parse_size(args.size)
    world_x, world_z = parse_world_size(args.world_size_m)
    material = load_material(args.material_id, args.catalog)

    out = args.out
    layers = out / "layers"
    layers.mkdir(parents=True, exist_ok=True)

    macro = build_macro(material, width, height, args.seed)
    height_m = build_height(width, height, args.elev_min_m, args.elev_range_m, args.seed)
    elev_min = float(np.min(height_m))
    elev_max = float(np.max(height_m))
    elev_range = max(elev_max - elev_min, 0.001)
    height_norm = np.clip((height_m - elev_min) / elev_range, 0.0, 1.0)

    macro_path = layers / "render_albedo.png"
    valid_mask_path = layers / "source_valid_mask.png"
    height_path = out / "heightmap.png"
    meta_path = out / "meta.json"

    Image.fromarray(np.clip(macro * 255.0, 0, 255).astype(np.uint8), mode="RGB").save(macro_path)
    Image.fromarray(np.full((height, width), 255, dtype=np.uint8), mode="L").save(valid_mask_path)
    Image.fromarray(np.clip(height_norm * 65535.0, 0, 65535).astype(np.uint16), mode="I;16").save(height_path)

    meta = {
        "name": args.name or f"Procedural {args.material_id} M10 neighbor",
        "builder": "build_procedural_neighbor_bundle.py",
        "source": "procedural",
        "source_material_id": args.material_id,
        "source_material_albedo": material["pbr_maps"]["albedo"],
        "heightmap_size_px": [width, height],
        "world_size_x_m": world_x,
        "world_size_z_m": world_z,
        "world_size_m": max(world_x, world_z),
        "elevation_min_m": elev_min,
        "elevation_max_m": elev_max,
        "elevation_range_m": elev_range,
        "material": args.material_id,
        "texture_is_real_imagery": False,
        "procedural_neighbor": {
            "version": 1,
            "seed": args.seed,
            "macro_policy": "catalog_material_color_with_multiscale_procedural_variation",
            "height_policy": "synthetic_wash_slope_ridge_heightfield",
            "target": "M10 real_to_procedural seam proof",
        },
        "layers": {
            "render_albedo": res_path(macro_path),
            "source_valid_mask": res_path(valid_mask_path),
        },
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return {
        "macro": str(macro_path),
        "valid_mask": str(valid_mask_path),
        "heightmap": str(height_path),
        "meta": str(meta_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--material-id", default="desert_canyon_rock")
    parser.add_argument("--catalog", type=Path, default=ROOT / "materials/catalog.json")
    parser.add_argument("--out", type=Path, default=ROOT / "toporeview/procedural_desert_canyon_rock_m10")
    parser.add_argument("--size", default="512,1024")
    parser.add_argument("--world-size-m", default="120,240")
    parser.add_argument("--elev-min-m", type=float, default=412.0)
    parser.add_argument("--elev-range-m", type=float, default=18.0)
    parser.add_argument("--seed", type=int, default=1021)
    parser.add_argument("--name", default="")
    args = parser.parse_args()

    result = write_bundle(args)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
