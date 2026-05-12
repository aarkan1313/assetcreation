"""Deterministic PBR derivation v2 (Materialize-style).

Given an albedo image (PNG/JPG), derive plausible:
  - height (frequency separation: low = base, high = surface detail)
  - normal (from height, with configurable strength)
  - AO    (blurred curvature from height)
  - roughness (category preset + albedo contrast/saturation)
  - metallic (zeros unless category=metal)

This is a baseline; PATINA / Material Anything can replace it later behind
the same interface. Outputs go into the same material folder so the manifest
tracks them as derived maps with provenance.

Usage:
  python derive_pbr_v2.py --albedo D:/assets/world/textures/inputs/stone.png \
      --id stone_alpha --category Rock --out D:/assets/world/textures/library/stone_alpha
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


# Roughness presets per category (mean, contrast)
ROUGHNESS_PRESETS = {
    "Rock":     (0.85, 0.15),
    "Ground":   (0.90, 0.10),
    "Wood":     (0.65, 0.20),
    "Bricks":   (0.80, 0.15),
    "Concrete": (0.85, 0.10),
    "Metal":    (0.30, 0.25),
    "Fabric":   (0.95, 0.05),
    "Tiles":    (0.40, 0.30),
    "Marble":   (0.30, 0.20),
    "Snow":     (0.95, 0.05),
    "Plastic":  (0.50, 0.20),
    "Leather":  (0.75, 0.15),
    "default":  (0.75, 0.15),
}


def luminance(rgb: np.ndarray) -> np.ndarray:
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def derive_height(albedo_lum: np.ndarray, low_strength: float = 0.7, high_strength: float = 0.3) -> np.ndarray:
    """Frequency-separated height: low-pass for base shape + high-pass for detail."""
    im = Image.fromarray((albedo_lum * 255).astype(np.uint8), mode="L")
    low = np.asarray(im.filter(ImageFilter.GaussianBlur(radius=24)), dtype=np.float32) / 255.0
    high = albedo_lum - low + 0.5
    h = low_strength * low + high_strength * high
    h = (h - h.min()) / (h.max() - h.min() + 1e-9)
    return h


def derive_normal(height: np.ndarray, strength: float = 4.0) -> np.ndarray:
    pad = np.pad(height, 1, mode="edge")
    gx = (pad[1:-1, 2:] - pad[1:-1, :-2]) * strength
    gy = (pad[2:, 1:-1] - pad[:-2, 1:-1]) * strength
    nx, ny, nz = -gx, -gy, np.ones_like(gx)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx /= n
    ny /= n
    nz /= n
    rgb = np.stack([
        (nx * 0.5 + 0.5),
        (ny * 0.5 + 0.5),
        (nz * 0.5 + 0.5),
    ], axis=-1)
    return (rgb * 255).clip(0, 255).astype(np.uint8)


def derive_ao(height: np.ndarray, blur_radius: int = 8) -> np.ndarray:
    im = Image.fromarray((height * 255).astype(np.uint8), mode="L")
    blurred = np.asarray(im.filter(ImageFilter.GaussianBlur(radius=blur_radius)), dtype=np.float32) / 255.0
    curvature = height - blurred  # negative in concavities
    ao = 1.0 + np.clip(curvature * 2.0, -1.0, 0.0)
    return (ao * 255).clip(0, 255).astype(np.uint8)


def derive_roughness(albedo: np.ndarray, category: str) -> np.ndarray:
    mean, contrast = ROUGHNESS_PRESETS.get(category, ROUGHNESS_PRESETS["default"])
    lum = luminance(albedo / 255.0)
    saturation = albedo.max(axis=-1) - albedo.min(axis=-1)
    saturation = saturation / 255.0
    detail = (lum - lum.mean()) * contrast
    detail += (saturation - saturation.mean()) * (contrast * 0.5)
    rough = np.clip(mean + detail, 0.0, 1.0)
    return (rough * 255).astype(np.uint8)


def derive_metallic(category: str, shape: tuple[int, int]) -> np.ndarray:
    val = 230 if category == "Metal" else 0
    return np.full(shape, val, dtype=np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--albedo", type=Path, required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--category", default="Rock")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--normal-strength", type=float, default=4.0)
    args = ap.parse_args()

    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    rgb = np.asarray(Image.open(args.albedo).convert("RGB"), dtype=np.uint8)
    albedo_lum = luminance(rgb / 255.0)

    height = derive_height(albedo_lum)
    Image.fromarray((height * 255).astype(np.uint8), mode="L").save(out / f"{args.id}_height.png")

    Image.fromarray(derive_normal(height, strength=args.normal_strength), mode="RGB").save(out / f"{args.id}_normal.png")
    Image.fromarray(derive_ao(height), mode="L").save(out / f"{args.id}_ao.png")
    Image.fromarray(derive_roughness(rgb, args.category), mode="L").save(out / f"{args.id}_roughness.png")
    Image.fromarray(derive_metallic(args.category, rgb.shape[:2]), mode="L").save(out / f"{args.id}_metallic.png")
    Image.fromarray(rgb, mode="RGB").save(out / f"{args.id}_albedo.png")

    record = {
        "id": args.id,
        "source": "derived_v2",
        "source_albedo": str(args.albedo),
        "category": args.category,
        "license": "depends-on-source",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "library_path": str(out.relative_to(Path("D:/assets"))),
        "maps": {
            "albedo": f"{args.id}_albedo.png",
            "normal": f"{args.id}_normal.png",
            "roughness": f"{args.id}_roughness.png",
            "ao": f"{args.id}_ao.png",
            "height": f"{args.id}_height.png",
            "metallic": f"{args.id}_metallic.png",
        },
        "map_completeness": ["albedo", "normal", "roughness", "ao", "height", "metallic"],
        "derivation_notes": "v2 deterministic; height=freq-separated, normal=sobel-strength, AO=curvature, roughness=category+contrast",
    }
    catalog = Path("D:/assets/world/textures/catalog/materials.jsonl")
    catalog.parent.mkdir(parents=True, exist_ok=True)
    with catalog.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"  derived 5 maps + albedo -> {out}")
    print(f"  catalog appended")


if __name__ == "__main__":
    main()
