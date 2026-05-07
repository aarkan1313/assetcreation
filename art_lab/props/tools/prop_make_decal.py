"""CPU decal generator for prop recipes.

This is intentionally simple and local: it creates transparent PNG decals,
thumbnails, prop manifests, and QA files from `texture_decal_v1` recipes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from prop_common import ASSET_ROOT, load_json, rel, validate_recipe, write_json


def stable_seed(text: str) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    s = hex_color.strip().lstrip("#")
    if len(s) != 6:
        return (128, 128, 128)
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def first_material_color(recipe: dict) -> tuple[int, int, int]:
    materials = recipe.get("materials", [])
    if materials and isinstance(materials[0], dict):
        return hex_to_rgb(materials[0].get("color", "#808080"))
    return (128, 128, 128)


def blob_mask(size: int, rng: random.Random, blobs: int, blur: float, stretch: float = 1.0) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    for _ in range(blobs):
        cx = rng.uniform(size * 0.25, size * 0.75)
        cy = rng.uniform(size * 0.25, size * 0.75)
        rx = rng.uniform(size * 0.05, size * 0.24) * stretch
        ry = rng.uniform(size * 0.05, size * 0.22) / max(stretch, 0.25)
        alpha = rng.randint(70, 185)
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=alpha)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=blur))
    return mask


def crack_mask(size: int, rng: random.Random) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    branches = rng.randint(4, 8)
    for _ in range(branches):
        x = rng.uniform(size * 0.2, size * 0.8)
        y = rng.uniform(size * 0.2, size * 0.8)
        angle = rng.uniform(0, math.tau)
        length = rng.uniform(size * 0.18, size * 0.45)
        points = [(x, y)]
        steps = rng.randint(3, 6)
        for _ in range(steps):
            angle += rng.uniform(-0.7, 0.7)
            step = length / steps
            x += math.cos(angle) * step
            y += math.sin(angle) * step
            points.append((x, y))
        width = rng.randint(2, 5)
        draw.line(points, fill=rng.randint(130, 230), width=width, joint="curve")
        for px, py in points[1:-1]:
            if rng.random() < 0.55:
                a = angle + rng.uniform(-1.8, 1.8)
                l = rng.uniform(size * 0.05, size * 0.18)
                draw.line([(px, py), (px + math.cos(a) * l, py + math.sin(a) * l)], fill=rng.randint(90, 180), width=max(1, width - 2))
    mask = mask.filter(ImageFilter.GaussianBlur(radius=0.7))
    return mask


def rune_mask(size: int, rng: random.Random) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    cx = cy = size / 2
    for _ in range(rng.randint(2, 4)):
        r = rng.uniform(size * 0.16, size * 0.38)
        box = [cx - r, cy - r, cx + r, cy + r]
        start = rng.randint(0, 330)
        end = start + rng.randint(80, 250)
        draw.arc(box, start=start, end=end, fill=rng.randint(70, 155), width=rng.randint(2, 5))
    spokes = rng.randint(3, 7)
    for i in range(spokes):
        a = math.tau * i / spokes + rng.uniform(-0.18, 0.18)
        r0 = rng.uniform(size * 0.08, size * 0.16)
        r1 = rng.uniform(size * 0.20, size * 0.38)
        p0 = (cx + math.cos(a) * r0, cy + math.sin(a) * r0)
        p1 = (cx + math.cos(a) * r1, cy + math.sin(a) * r1)
        draw.line([p0, p1], fill=rng.randint(50, 130), width=rng.randint(1, 4))
    mask = mask.filter(ImageFilter.GaussianBlur(radius=1.2))
    organic = blob_mask(size, rng, blobs=6, blur=size * 0.035)
    mask_np = np.asarray(mask, dtype=np.float32)
    organic_np = np.asarray(organic, dtype=np.float32) / 255.0
    return Image.fromarray(np.clip(mask_np * organic_np, 0, 255).astype(np.uint8), mode="L")


def make_mask(family: str, size: int, rng: random.Random) -> Image.Image:
    if "cracked" in family:
        return crack_mask(size, rng)
    if "rune" in family:
        return rune_mask(size, rng)
    if "scorch" in family:
        return blob_mask(size, rng, blobs=10, blur=size * 0.055, stretch=rng.uniform(0.8, 1.45))
    if "mud" in family:
        return blob_mask(size, rng, blobs=16, blur=size * 0.030, stretch=rng.uniform(0.7, 1.7))
    return blob_mask(size, rng, blobs=14, blur=size * 0.040, stretch=rng.uniform(0.75, 1.35))


def colorize(mask: Image.Image, color: tuple[int, int, int], rng: random.Random) -> Image.Image:
    size = mask.size[0]
    alpha = np.asarray(mask, dtype=np.float32)
    noise = rng.normalvariate if False else None
    grain = np.random.default_rng(stable_seed(str(rng.random()))).normal(0.0, 8.0, (size, size, 1))
    rgb = np.zeros((size, size, 3), dtype=np.float32)
    rgb[:, :, 0] = color[0]
    rgb[:, :, 1] = color[1]
    rgb[:, :, 2] = color[2]
    rgb = np.clip(rgb + grain, 0, 255)
    out = np.dstack([rgb, alpha]).astype(np.uint8)
    return Image.fromarray(out, mode="RGBA")


def make_thumbnail(decal: Image.Image, out_path: Path) -> None:
    size = decal.size[0]
    cell = max(8, size // 16)
    bg = Image.new("RGB", decal.size, "#202722")
    draw = ImageDraw.Draw(bg)
    for y in range(0, size, cell):
        for x in range(0, size, cell):
            if (x // cell + y // cell) % 2 == 0:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill="#2b332e")
    bg = bg.convert("RGBA")
    bg.alpha_composite(decal)
    bg.convert("RGB").resize((256, 256), Image.Resampling.LANCZOS).save(out_path)


def average_scale(recipe: dict) -> list[float]:
    scale = recipe.get("scale_m", {})
    vals = []
    for axis in ["x", "y", "z"]:
        r = scale.get(axis, [1.0, 1.0])
        vals.append(round((float(r[0]) + float(r[1])) / 2.0, 3))
    return vals


def average_radius(recipe: dict) -> float:
    radius = recipe.get("placement", {}).get("footprint_radius_m", 0.5)
    if isinstance(radius, list):
        return round((float(radius[0]) + float(radius[1])) / 2.0, 3)
    return round(float(radius), 3)


def generate_decal(recipe_path: Path, variant_id: str, out_dir: Path, seed: int | None = None) -> dict:
    recipe = load_json(recipe_path)
    issues = validate_recipe(recipe, recipe_path)
    if issues:
        raise SystemExit("\n".join(issues))
    if recipe.get("generator") != "texture_decal_v1":
        raise SystemExit(f"{recipe_path} is not a texture_decal_v1 recipe")

    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed if seed is not None else stable_seed(f"{recipe_path}:{variant_id}"))
    size = int(recipe.get("budgets", {}).get("texture_px", 512))
    color = first_material_color(recipe)
    mask = make_mask(recipe["family"], size, rng)
    decal = colorize(mask, color, rng)

    decal_path = out_dir / "decal.png"
    thumb_path = out_dir / "thumbnail.png"
    decal.save(decal_path)
    make_thumbnail(decal, thumb_path)

    alpha = np.asarray(mask, dtype=np.float32) / 255.0
    coverage = float((alpha > 0.05).mean())
    qa = {
        "schema": "prop_qa.v1",
        "id": variant_id,
        "passed": 0.015 <= coverage <= 0.80,
        "metrics": {
            "alpha_coverage": round(coverage, 4),
            "size_px": size
        },
        "warnings": [] if 0.015 <= coverage <= 0.80 else ["alpha coverage outside preferred range"]
    }
    write_json(out_dir / "qa.json", qa)

    placement = recipe.get("placement", {})
    prop = {
        "schema": "prop_asset.v1",
        "id": variant_id,
        "family": recipe["family"],
        "kit": recipe["kit"],
        "source_method": "cpu_texture_decal",
        "source_recipe": rel(recipe_path),
        "license": "project_generated",
        "render_class": placement.get("render_class", "decal"),
        "collision": placement.get("collision", "none"),
        "origin": placement.get("origin", "center"),
        "scale_m": average_scale(recipe),
        "footprint_radius_m": average_radius(recipe),
        "decal": "decal.png",
        "thumbnail": "thumbnail.png",
        "placement_tags": placement.get("placement_tags", []),
        "material_slots": [m.get("slot") for m in recipe.get("materials", []) if isinstance(m, dict)],
        "qa": "qa.json"
    }
    write_json(out_dir / "prop.json", prop)
    return {
        "id": variant_id,
        "out_dir": rel(out_dir),
        "decal": rel(decal_path),
        "thumbnail": rel(thumb_path),
        "qa_passed": qa["passed"],
        "alpha_coverage": qa["metrics"]["alpha_coverage"]
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", type=Path, required=True)
    ap.add_argument("--variant-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    out_dir = args.out
    if not out_dir.is_absolute():
        out_dir = ASSET_ROOT / out_dir
    result = generate_decal(args.recipe, args.variant_id, out_dir, args.seed)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

