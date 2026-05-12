"""Build unlike real-crop variants for one OpenTopo ground material class.

This is the next step after the single-tile pilot. It does not invent or
procedurally repaint photoreal detail. It selects several sibling crops from the
same fused stack, repairs each independently, normalizes color, and writes both
hard-mixed QA images and a soft periodic composite for seamless Godot review.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from build_opentopo_tileable_texture import (
    CROP_CLASSES,
    CropPick,
    class_score,
    crop_stats,
    feature_image,
    load_gray,
    load_height_u16,
    load_rgb,
    normal_from_height,
    process_crop,
    save_tile_2x2,
    write_json,
)


Image.MAX_IMAGE_PIXELS = None


def font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def source_coord(meta: dict, center_px: tuple[int, int], image_size: tuple[int, int]) -> dict:
    bounds = meta.get("source_bounds", {})
    left = float(bounds.get("left", 0.0))
    right = float(bounds.get("right", float(image_size[0])))
    top = float(bounds.get("top", float(image_size[1])))
    bottom = float(bounds.get("bottom", 0.0))
    cx, cy = center_px
    x = left + (cx / max(1, image_size[0] - 1)) * (right - left)
    y = top - (cy / max(1, image_size[1] - 1)) * (top - bottom)
    return {"x": x, "y": y, "crs": meta.get("source_crs")}


def extended_crop_stats(
    rgb: np.ndarray,
    veg: np.ndarray,
    slope: np.ndarray,
    rough: np.ndarray,
    valid: np.ndarray,
    fill: np.ndarray,
    cx: int,
    cy: int,
    crop_px: int,
) -> dict[str, float] | None:
    stats = crop_stats(rgb, veg, slope, rough, valid, fill, cx, cy, crop_px)
    if stats is None:
        return None
    half = crop_px // 2
    left = cx - half
    top = cy - half
    patch = rgb[top:top + crop_px, left:left + crop_px]
    if patch.size == 0:
        return None

    dx = np.abs(np.diff(patch, axis=1)).mean() if patch.shape[1] > 1 else 0.0
    dy = np.abs(np.diff(patch, axis=0)).mean() if patch.shape[0] > 1 else 0.0
    high_frequency = float((dx + dy) * 0.5)

    block = max(2, crop_px // 8)
    means = []
    for y in range(0, crop_px - block + 1, block):
        for x in range(0, crop_px - block + 1, block):
            means.append(patch[y:y + block, x:x + block].mean(axis=(0, 1)))
    large_pattern = float(np.asarray(means, dtype=np.float32).std()) if means else 0.0

    stats["high_frequency"] = high_frequency
    stats["large_pattern"] = large_pattern
    return stats


def variant_score(material_class: str, stats: dict[str, float], noise_penalty: float, pattern_penalty: float) -> float:
    base = class_score(material_class, stats)
    # A visually busy orthophoto crop can pass class scoring and still look wrong
    # when repeated. Penalize high-frequency speckle and large unique motifs.
    return base - noise_penalty * stats["high_frequency"] - pattern_penalty * stats["large_pattern"]


def select_variant_picks(
    stack_dir: Path,
    albedo: Image.Image,
    meta: dict,
    material_class: str,
    crop_size_m: int,
    variants: int,
    min_distance_m: float,
    noise_penalty: float,
    pattern_penalty: float,
) -> list[CropPick]:
    if material_class not in CROP_CLASSES:
        raise SystemExit(f"Unknown material class {material_class!r}; expected one of {', '.join(CROP_CLASSES)}")

    layers = stack_dir / "layers"
    feature_size = 1024
    rgb = feature_image(albedo, feature_size, "RGB")
    veg = feature_image(load_gray(layers / "vegetation_ndvi_like.png", albedo.size), feature_size, "L")
    slope = feature_image(load_gray(layers / "slope_deg.png", albedo.size), feature_size, "L")
    rough = feature_image(load_gray(layers / "roughness.png", albedo.size), feature_size, "L")
    valid = feature_image(load_gray(layers / "source_valid_mask.png", albedo.size), feature_size, "L")
    fill = feature_image(load_gray(layers / "render_fill_mask.png", albedo.size), feature_size, "L")

    world_size = float(meta.get("world_size_m", meta.get("world_size_x_m", 1600.0)))
    crop_px = max(24, int(round(crop_size_m * feature_size / world_size)))
    full_crop_px = max(8, int(round(crop_size_m * albedo.width / world_size)))
    full_half = full_crop_px // 2
    step = max(10, crop_px // 2)
    candidates: list[tuple[float, int, int, dict[str, float]]] = []
    for cy in range(crop_px // 2, feature_size - crop_px // 2, step):
        for cx in range(crop_px // 2, feature_size - crop_px // 2, step):
            stats = extended_crop_stats(rgb, veg, slope, rough, valid, fill, cx, cy, crop_px)
            if stats is None:
                continue
            score = variant_score(material_class, stats, noise_penalty, pattern_penalty)
            candidates.append((score, cx, cy, stats))
    if not candidates:
        raise SystemExit("No valid variant candidates found")

    candidates.sort(reverse=True, key=lambda item: item[0])
    min_dist_px = max(crop_px * 1.35, min_distance_m * feature_size / world_size)
    picked_feature_centers: list[tuple[int, int]] = []
    picks: list[CropPick] = []
    for score, cx, cy, stats in candidates:
        if any(math.dist((cx, cy), old) < min_dist_px for old in picked_feature_centers):
            continue
        full_center = (
            int(round(cx * albedo.width / feature_size)),
            int(round(cy * albedo.height / feature_size)),
        )
        if (
            full_center[0] - full_half < 0
            or full_center[1] - full_half < 0
            or full_center[0] - full_half + full_crop_px > albedo.width
            or full_center[1] - full_half + full_crop_px > albedo.height
        ):
            continue
        variant_name = f"{material_class}_v{len(picks):02d}"
        picks.append(CropPick(variant_name, full_center, float(score), stats))
        picked_feature_centers.append((cx, cy))
        if len(picks) >= variants:
            break

    if len(picks) < variants:
        print(f"[warn] requested {variants} variants but found {len(picks)} after distance filtering")
    return picks


def make_variant_sheet(products: list[dict], output: Path) -> None:
    cell = 220
    caption = 54
    cols = 4
    rows = int(math.ceil(len(products) / cols))
    margin = 24
    gutter = 14
    title_h = 74
    sheet = Image.new(
        "RGB",
        (margin * 2 + cols * cell + (cols - 1) * gutter, margin * 2 + title_h + rows * (cell + caption + gutter)),
        (15, 18, 16),
    )
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, margin), "OpenTopo unlike real-crop variant atlas", font=font(26, True), fill=(236, 238, 232))
    draw.text((margin, margin + 36), "Each tileable-real variant is a different source crop.", font=font(15), fill=(175, 184, 174))
    for idx, product in enumerate(products):
        x = margin + (idx % cols) * (cell + gutter)
        y = margin + title_h + (idx // cols) * (cell + caption + gutter)
        outputs = product["outputs"]
        policy = "tileable_real_norm" if "tileable_real_norm" in outputs else "tileable_real"
        path = Path(outputs[policy]["albedo"])
        with Image.open(path) as img:
            thumb = ImageOps.exif_transpose(img).convert("RGB").resize((cell, cell), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y))
        draw.rectangle((x, y + cell, x + cell, y + cell + caption), fill=(27, 32, 29))
        label = f"v{product['variant_index']:02d} score {product['selection_score']:.3f}"
        stats = product.get("selection_stats", {})
        note = f"hf {stats.get('high_frequency', 0):.3f} pattern {stats.get('large_pattern', 0):.3f}"
        draw.text((x + 10, y + cell + 8), label, font=font(14, True), fill=(236, 238, 232))
        draw.text((x + 10, y + cell + 30), note, font=font(12), fill=(178, 188, 176))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def variant_index(x: int, y: int, count: int) -> int:
    value = abs(math.sin((x + 1) * 12.9898 + (y + 1) * 78.233) * 43758.5453)
    return int(value * 1000.0) % max(1, count)


def make_variant_grid(products: list[dict], output: Path, repeat: int = 16, cell_px: int = 96) -> None:
    thumbs = []
    for product in products:
        outputs = product["outputs"]
        policy = "tileable_real_norm" if "tileable_real_norm" in outputs else "tileable_real"
        path = Path(outputs[policy]["albedo"])
        with Image.open(path) as img:
            thumbs.append(ImageOps.exif_transpose(img).convert("RGB").resize((cell_px, cell_px), Image.Resampling.LANCZOS))
    grid = Image.new("RGB", (repeat * cell_px, repeat * cell_px), (0, 0, 0))
    for y in range(repeat):
        for x in range(repeat):
            idx = variant_index(x, y, len(thumbs))
            grid.paste(thumbs[idx], (x * cell_px, y * cell_px))
    output.parent.mkdir(parents=True, exist_ok=True)
    grid.save(output)


def periodic_value_noise(size: int, grid: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    lattice = rng.random((grid, grid), dtype=np.float32)
    coord = np.arange(size, dtype=np.float32) * (float(grid) / float(size))
    i0 = np.floor(coord).astype(np.int32) % grid
    i1 = (i0 + 1) % grid
    f = coord - np.floor(coord)
    f = f * f * (3.0 - 2.0 * f)
    n00 = lattice[i0[:, None], i0[None, :]]
    n10 = lattice[i0[:, None], i1[None, :]]
    n01 = lattice[i1[:, None], i0[None, :]]
    n11 = lattice[i1[:, None], i1[None, :]]
    nx0 = n00 * (1.0 - f[None, :]) + n10 * f[None, :]
    nx1 = n01 * (1.0 - f[None, :]) + n11 * f[None, :]
    return nx0 * (1.0 - f[:, None]) + nx1 * f[:, None]


def periodic_weight_stack(
    variant_count: int,
    size: int,
    macro_cells: int,
    sharpness: float,
    seed: int,
) -> np.ndarray:
    fields = []
    for i in range(variant_count):
        coarse = periodic_value_noise(size, macro_cells, seed + i * 101)
        fine = periodic_value_noise(size, max(3, macro_cells * 2 + 1), seed + i * 101 + 37)
        field = coarse * 0.78 + fine * 0.22
        fields.append(field)
    stack = np.stack(fields, axis=0)
    stack = stack - stack.max(axis=0, keepdims=True)
    weights = np.exp(stack * sharpness)
    weights /= np.maximum(weights.sum(axis=0, keepdims=True), 1e-6)
    return weights.astype(np.float32)


def read_map(path: Path, mode: str) -> np.ndarray:
    with Image.open(path) as img:
        arr = np.asarray(ImageOps.exif_transpose(img).convert(mode), dtype=np.float32)
    return arr / 255.0


def tile_to_size(arr: np.ndarray, size: int, offset_x: int, offset_y: int) -> np.ndarray:
    rolled = np.roll(np.roll(arr, offset_y, axis=0), offset_x, axis=1)
    reps_y = int(math.ceil(size / rolled.shape[0]))
    reps_x = int(math.ceil(size / rolled.shape[1]))
    if rolled.ndim == 3:
        tiled = np.tile(rolled, (reps_y, reps_x, 1))
        return tiled[:size, :size, :]
    tiled = np.tile(rolled, (reps_y, reps_x))
    return tiled[:size, :size]


def edge_metrics(arr: np.ndarray) -> dict[str, float]:
    work = arr.astype(np.float32)
    if work.max() > 1.5:
        work = work / 255.0
    left_right = float(np.mean((work[:, 0] - work[:, -1]) ** 2))
    top_bottom = float(np.mean((work[0, :] - work[-1, :]) ** 2))
    return {
        "edge_mse_left_right": left_right,
        "edge_mse_top_bottom": top_bottom,
        "edge_mse_mean": (left_right + top_bottom) * 0.5,
    }


def save_float_image(arr: np.ndarray, path: Path, mode: str) -> Image.Image:
    out = np.clip(arr, 0.0, 1.0)
    if mode == "L":
        img = Image.fromarray((out * 255.0).astype(np.uint8), mode="L")
    else:
        img = Image.fromarray((out * 255.0).astype(np.uint8), mode="RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return img


def build_soft_composite(
    products: list[dict],
    output_root: Path,
    material_class: str,
    crop_size_m: int,
    composite_size: int,
    macro_cells: int,
    sharpness: float,
    seed: int,
) -> dict:
    if not products:
        return {}
    root = output_root / f"{material_class}_{crop_size_m:03d}m_soft_composite"
    out_dir = root / "tileable_soft"
    out_dir.mkdir(parents=True, exist_ok=True)
    weights = periodic_weight_stack(len(products), composite_size, macro_cells, sharpness, seed)
    rng = np.random.default_rng(seed + 404)
    offsets: list[dict[str, int]] = []
    variant_infos: list[dict] = []
    for product in products:
        outputs = product["outputs"]
        policy = "tileable_real_norm" if "tileable_real_norm" in outputs else "tileable_real"
        info = outputs[policy]
        with Image.open(info["albedo"]) as probe:
            w, h = probe.size
        ox = int(rng.integers(0, max(1, w)))
        oy = int(rng.integers(0, max(1, h)))
        offsets.append({"x": ox, "y": oy})
        variant_infos.append(info)

    composite: dict[str, np.ndarray] = {}
    for map_name, mode in (("albedo", "RGB"), ("height", "L"), ("roughness", "L")):
        accum_shape = (composite_size, composite_size, 3) if mode == "RGB" else (composite_size, composite_size)
        accum = np.zeros(accum_shape, dtype=np.float32)
        for idx, info in enumerate(variant_infos):
            ox = offsets[idx]["x"]
            oy = offsets[idx]["y"]
            tiled = tile_to_size(read_map(Path(info[map_name]), mode), composite_size, ox, oy)
            if mode == "RGB":
                accum += tiled * weights[idx, :, :, None]
            else:
                accum += tiled * weights[idx]
        composite[map_name] = accum

    albedo_img = save_float_image(composite["albedo"], out_dir / "albedo.png", "RGB")
    height_img = save_float_image(composite["height"], out_dir / "height.png", "L")
    rough_img = save_float_image(composite["roughness"], out_dir / "roughness.png", "L")
    normal_from_height(height_img, strength=2.0).save(out_dir / "normal.png")
    save_tile_2x2(albedo_img, out_dir / "tile_2x2.png")

    metrics = edge_metrics(composite["albedo"])
    product = {
        "kind": "soft_composite",
        "material_class": material_class,
        "crop_size_m": crop_size_m,
        "variant_count": len(products),
        "output_size_px": composite_size,
        "source_policy": "soft_blended_real_variant_composite",
        "source_variants": [p["crop_class"] for p in products],
        "operations": [
            "tileable_real_norm_input",
            "periodic_softmax_weight_masks",
            "wrap_safe_variant_offsets",
            "height_blend_then_normal_derive",
        ],
        "macro_cells": macro_cells,
        "softmax_sharpness": sharpness,
        "seed": seed,
        "variant_offsets_px": offsets,
        "procedural_color_used": False,
        "ai_generated_color_used": False,
        "geography_preserved": False,
        "edge_metrics": metrics,
        "outputs": {
            "tileable_soft": {
                "policy": "tileable_soft_real_variant_composite",
                "albedo": str(out_dir / "albedo.png"),
                "height": str(out_dir / "height.png"),
                "normal": str(out_dir / "normal.png"),
                "roughness": str(out_dir / "roughness.png"),
                "tile_2x2": str(out_dir / "tile_2x2.png"),
            }
        },
    }
    write_json(root / "manifest.json", product)
    return product


def normalize_variant_color(products: list[dict], strength: float = 0.85) -> None:
    arrays: list[np.ndarray] = []
    for product in products:
        path = Path(product["outputs"]["tileable_real"]["albedo"])
        with Image.open(path) as img:
            arrays.append(np.asarray(ImageOps.exif_transpose(img).convert("RGB"), dtype=np.float32) / 255.0)
    if not arrays:
        return
    means = np.asarray([arr.mean(axis=(0, 1)) for arr in arrays], dtype=np.float32)
    stds = np.asarray([arr.std(axis=(0, 1)) for arr in arrays], dtype=np.float32)
    target_mean = means.mean(axis=0)
    target_std = np.maximum(np.median(stds, axis=0), 0.015)
    strength = float(np.clip(strength, 0.0, 1.0))

    for product, arr in zip(products, arrays):
        mean = arr.mean(axis=(0, 1))
        std = np.maximum(arr.std(axis=(0, 1)), 0.01)
        matched = (arr - mean) * (target_std / std) + target_mean
        out = arr * (1.0 - strength) + matched * strength
        out_img = Image.fromarray((np.clip(out, 0.0, 1.0) * 255.0).astype(np.uint8), mode="RGB")
        root = Path(product["outputs"]["tileable_real"]["albedo"]).parents[1]
        norm_dir = root / "tileable_real_norm"
        norm_dir.mkdir(parents=True, exist_ok=True)
        out_img.save(norm_dir / "albedo.png")
        for map_name in ("height", "normal", "roughness"):
            src = Path(product["outputs"]["tileable_real"][map_name])
            with Image.open(src) as img:
                ImageOps.exif_transpose(img).save(norm_dir / f"{map_name}.png")
        save_tile_2x2(out_img, norm_dir / "tile_2x2.png")
        product["outputs"]["tileable_real_norm"] = {
            "policy": "tileable_real_norm",
            "albedo": str(norm_dir / "albedo.png"),
            "height": str(norm_dir / "height.png"),
            "normal": str(norm_dir / "normal.png"),
            "roughness": str(norm_dir / "roughness.png"),
            "tile_2x2": str(norm_dir / "tile_2x2.png"),
            "operations": ["per_variant_rgb_mean_std_match"],
            "normalization_strength": strength,
            "target_mean_rgb": [float(x) for x in target_mean],
            "target_std_rgb": [float(x) for x in target_std],
            "procedural_color_used": False,
            "ai_generated_color_used": False,
            "geography_preserved": False,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack-dir", type=Path, default=Path("D:/assets/world3/toporeview/phase2_fusion_max"))
    ap.add_argument("--output-dir", type=Path, default=Path("D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants"))
    ap.add_argument("--material-class", default="dry_wash")
    ap.add_argument("--crop-size-m", type=int, default=64)
    ap.add_argument("--variants", type=int, default=12)
    ap.add_argument("--output-size", type=int, default=1024)
    ap.add_argument("--min-distance-m", type=float, default=90.0)
    ap.add_argument("--noise-penalty", type=float, default=1.2)
    ap.add_argument("--pattern-penalty", type=float, default=0.6)
    ap.add_argument("--color-normalize-strength", type=float, default=0.85)
    ap.add_argument("--composite-size", type=int, default=2048)
    ap.add_argument("--composite-cells", type=int, default=6)
    ap.add_argument("--composite-sharpness", type=float, default=8.0)
    ap.add_argument("--composite-seed", type=int, default=4242)
    args = ap.parse_args()

    stack_dir = args.stack_dir
    layers = stack_dir / "layers"
    meta = json.loads((stack_dir / "meta.json").read_text(encoding="utf-8"))
    albedo = load_rgb(layers / "render_albedo.png")
    height = load_height_u16(stack_dir / "heightmap.png")
    roughness = load_gray(layers / "roughness.png", albedo.size)
    slope = load_gray(layers / "slope_deg.png", albedo.size)
    vegetation = load_gray(layers / "vegetation_ndvi_like.png", albedo.size)

    picks = select_variant_picks(
        stack_dir,
        albedo,
        meta,
        args.material_class,
        args.crop_size_m,
        args.variants,
        args.min_distance_m,
        args.noise_penalty,
        args.pattern_penalty,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    products: list[dict] = []
    for idx, pick in enumerate(picks):
        product = process_crop(
            args.output_dir,
            stack_dir,
            meta,
            albedo,
            height,
            roughness,
            slope,
            vegetation,
            pick,
            args.crop_size_m,
            args.output_size,
        )
        product["material_class"] = args.material_class
        product["variant_index"] = idx
        product["variant_policy"] = "unlike_real_crop"
        product["center_source_coord"] = source_coord(meta, pick.center_px, albedo.size)
        product["source_policy"] = "tileable_real_variant_atlas"
        product["outputs"]["tileable_real"]["variant_role"] = "meso_unlike_tile"
        product_root = args.output_dir / f"{pick.crop_class}_{args.crop_size_m:03d}m"
        write_json(product_root / "manifest.json", product)
        products.append(product)

    if args.color_normalize_strength > 0:
        normalize_variant_color(products, args.color_normalize_strength)
        for product in products:
            product_root = args.output_dir / f"{product['crop_class']}_{args.crop_size_m:03d}m"
            write_json(product_root / "manifest.json", product)

    sheet = args.output_dir / f"{args.material_class}_{args.crop_size_m:03d}m_variant_sheet.png"
    grid = args.output_dir / f"{args.material_class}_{args.crop_size_m:03d}m_variant_grid_16x16.png"
    make_variant_sheet(products, sheet)
    make_variant_grid(products, grid)
    soft_product = build_soft_composite(
        products,
        args.output_dir,
        args.material_class,
        args.crop_size_m,
        args.composite_size,
        args.composite_cells,
        args.composite_sharpness,
        args.composite_seed,
    )

    manifest = {
        "name": f"guadalupe_cypress_{args.material_class}_variant_atlas",
        "kind": "variant_atlas_manifest",
        "source_stack": str(stack_dir),
        "output_dir": str(args.output_dir),
        "material_class": args.material_class,
        "crop_size_m": args.crop_size_m,
        "variant_count": len(products),
        "output_size_px": args.output_size,
        "policy": {
            "source_color": "real OpenTopo render_albedo / orthophoto",
            "variant_role": "meso unlike real tile variants",
            "procedural_color_used": False,
            "ai_generated_color_used": False,
            "scale_note": "Variants are QA inputs, not final production shader blending.",
            "color_normalization": "tileable_real_norm matches per-variant RGB mean/std to reduce checkerboard blocks.",
        },
        "review_outputs": {
            "variant_sheet": str(sheet),
            "variant_grid_16x16": str(grid),
            "soft_composite_tile_2x2": soft_product.get("outputs", {}).get("tileable_soft", {}).get("tile_2x2", ""),
        },
        "products": products,
        "soft_composite": soft_product,
    }
    write_json(args.output_dir / "manifest.json", manifest)
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "material_class": args.material_class,
        "variants": len(products),
        "variant_sheet": str(sheet),
        "variant_grid_16x16": str(grid),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
