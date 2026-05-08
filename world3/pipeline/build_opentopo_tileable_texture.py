"""Build source-real and tileable texture pilots from an OpenTopo fused stack.

This is intentionally conservative: source color comes from real orthophoto
layers, and the tileable pass uses wrap blending from the same real pixels. Any
stylized output is written as a separate derivative.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


Image.MAX_IMAGE_PIXELS = None


CROP_CLASSES = [
    "dry_wash",
    "scrub_sparse",
    "scrub_dense",
    "rocky_slope",
    "bare_soil",
    "bright_rock",
]


@dataclass
class CropPick:
    crop_class: str
    center_px: tuple[int, int]
    score: float
    stats: dict[str, float]


def load_rgb(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return ImageOps.exif_transpose(img).convert("RGB").copy()


def load_gray(path: Path, fallback_size: tuple[int, int]) -> Image.Image:
    if not path.exists():
        return Image.new("L", fallback_size, 0)
    with Image.open(path) as img:
        return ImageOps.exif_transpose(img).convert("L").copy()


def load_height_u16(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        arr = np.asarray(img)
    if arr.ndim == 3:
        arr = arr[:, :, 0]
    return arr.astype(np.float32)


def resize_for_output(img: Image.Image, size: int, resampling: Image.Resampling) -> Image.Image:
    if img.size == (size, size):
        return img.copy()
    return img.resize((size, size), resampling)


def crop_square(img: Image.Image, center: tuple[int, int], size_px: int) -> Image.Image:
    cx, cy = center
    half = size_px // 2
    left = int(round(cx - half))
    top = int(round(cy - half))
    right = left + size_px
    bottom = top + size_px
    if left < 0 or top < 0 or right > img.width or bottom > img.height:
        raise ValueError(f"Crop {left},{top},{right},{bottom} outside {img.size}")
    return img.crop((left, top, right, bottom))


def crop_array_square(arr: np.ndarray, center: tuple[int, int], size_px: int) -> np.ndarray:
    cx, cy = center
    half = size_px // 2
    left = int(round(cx - half))
    top = int(round(cy - half))
    right = left + size_px
    bottom = top + size_px
    if left < 0 or top < 0 or right > arr.shape[1] or bottom > arr.shape[0]:
        raise ValueError(f"Crop {left},{top},{right},{bottom} outside {arr.shape}")
    return arr[top:bottom, left:right].copy()


def normalize_to_u8(arr: np.ndarray, low: float = 2.0, high: float = 98.0) -> Image.Image:
    finite = np.isfinite(arr)
    if not finite.any():
        out = np.zeros(arr.shape, dtype=np.uint8)
        return Image.fromarray(out, mode="L")
    lo, hi = np.nanpercentile(arr[finite], [low, high])
    if not np.isfinite(lo):
        lo = float(np.nanmin(arr[finite]))
    if not np.isfinite(hi) or hi <= lo:
        hi = lo + 1.0
    scaled = (arr.astype(np.float32) - float(lo)) / (float(hi) - float(lo))
    out = np.clip(np.nan_to_num(scaled), 0.0, 1.0)
    return Image.fromarray((out * 255.0).astype(np.uint8), mode="L")


def tile_2x2(img: Image.Image) -> Image.Image:
    out = Image.new(img.mode, (img.width * 2, img.height * 2))
    for y in range(2):
        for x in range(2):
            out.paste(img, (x * img.width, y * img.height))
    return out


def save_tile_2x2(img: Image.Image, path: Path) -> None:
    preview = tile_2x2(img)
    max_side = 2048
    if max(preview.size) > max_side:
        preview.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    preview.save(path)


def offset_array(arr: np.ndarray) -> np.ndarray:
    h, w = arr.shape[:2]
    return np.roll(np.roll(arr, h // 2, axis=0), w // 2, axis=1)


def feather_mask(h: int, w: int, feather: int) -> np.ndarray:
    mask = np.ones((h, w), dtype=np.float32)
    if feather <= 0:
        return mask
    feather = min(feather, h // 2, w // 2)
    for i in range(feather):
        v = i / max(1, feather)
        mask[i, :] *= v
        mask[-(i + 1), :] *= v
        mask[:, i] *= v
        mask[:, -(i + 1)] *= v
    return mask


def find_best_patch(source: np.ndarray, target: np.ndarray, search_locs: int = 42) -> tuple[int, int]:
    h, w = source.shape[:2]
    th, tw = target.shape[:2]
    if th > h or tw > w:
        return 0, 0
    rng = np.random.default_rng(9173)
    locs: list[tuple[int, int]] = []
    for _ in range(search_locs):
        locs.append((
            int(rng.integers(0, max(1, h - th))),
            int(rng.integers(0, max(1, w - tw))),
        ))
    step_y = max(1, th // 2)
    step_x = max(1, tw // 2)
    for y in range(0, max(1, h - th), step_y):
        for x in range(0, max(1, w - tw), step_x):
            locs.append((y, x))
    target_f = target.astype(np.float32)
    best = (0, 0)
    best_err = float("inf")
    for y, x in locs:
        cand = source[y:y + th, x:x + tw].astype(np.float32)
        if cand.shape != target_f.shape:
            continue
        err = float(np.mean((cand - target_f) ** 2))
        if err < best_err:
            best_err = err
            best = (y, x)
    return best


def compute_patch_repair_plan(arr: np.ndarray, patch: int = 64) -> list[dict]:
    """Compute source-real patch operations for the centered offset seam."""
    h, w = arr.shape[:2]
    patch = max(16, min(patch, h // 5, w // 5))
    cy, cx = h // 2, w // 2
    offset = offset_array(arr)
    interior = arr[patch:h - patch, patch:w - patch]
    if interior.shape[0] < patch * 2 or interior.shape[1] < patch * 2:
        return []
    plan: list[dict] = []

    # Horizontal centered seam.
    for x in range(0, w, patch):
        target = offset[cy - patch:cy + patch, x:min(w, x + patch)]
        if min(target.shape[:2]) < 4:
            continue
        py, px = find_best_patch(interior, target)
        plan.append({
            "axis": "h",
            "x": x,
            "target_shape": [int(target.shape[0]), int(target.shape[1])],
            "source_yx": [int(py), int(px)],
        })

    # Vertical centered seam.
    for y in range(0, h, patch):
        target = offset[y:min(h, y + patch), cx - patch:cx + patch]
        if min(target.shape[:2]) < 4:
            continue
        py, px = find_best_patch(interior, target)
        plan.append({
            "axis": "v",
            "y": y,
            "target_shape": [int(target.shape[0]), int(target.shape[1])],
            "source_yx": [int(py), int(px)],
        })
    return plan


def apply_patch_repair_plan(arr: np.ndarray, plan: list[dict], patch: int = 64, feather: int = 18) -> np.ndarray:
    h, w = arr.shape[:2]
    patch = max(16, min(patch, h // 5, w // 5))
    cy, cx = h // 2, w // 2
    offset = offset_array(arr).astype(np.float32)
    interior = arr[patch:h - patch, patch:w - patch].astype(np.float32)
    out = offset.copy()
    for op in plan:
        ts_h, ts_w = int(op["target_shape"][0]), int(op["target_shape"][1])
        py, px = int(op["source_yx"][0]), int(op["source_yx"][1])
        if py < 0 or px < 0 or py + ts_h > interior.shape[0] or px + ts_w > interior.shape[1]:
            continue
        cand = interior[py:py + ts_h, px:px + ts_w]
        mask = feather_mask(ts_h, ts_w, feather)
        if cand.ndim == 3:
            mask = mask[:, :, None]
        if op["axis"] == "h":
            x = int(op["x"])
            y = cy - patch
        else:
            x = cx - patch
            y = int(op["y"])
        x2 = min(w, x + ts_w)
        y2 = min(h, y + ts_h)
        if x < 0 or y < 0 or x2 <= x or y2 <= y:
            continue
        sw = x2 - x
        sh = y2 - y
        local_mask = mask[:sh, :sw]
        local_cand = cand[:sh, :sw]
        out[y:y2, x:x2] = out[y:y2, x:x2] * (1.0 - local_mask) + local_cand * local_mask
    return np.clip(offset_array(out), 0, 255).astype(np.uint8)


def repair_image_with_plan(img: Image.Image, plan: list[dict], patch: int = 64, feather: int = 18) -> Image.Image:
    mode = img.mode
    work = img.convert("RGB") if mode not in ("RGB", "L") else img.copy()
    arr = np.asarray(work)
    repaired = apply_patch_repair_plan(arr, plan, patch=patch, feather=feather)
    return Image.fromarray(repaired, mode=work.mode).convert(mode)


def normal_from_height(height: Image.Image, strength: float = 3.0) -> Image.Image:
    h = np.asarray(height.convert("L"), dtype=np.float32) / 255.0
    gy, gx = np.gradient(h)
    nx = -gx * strength
    ny = -gy * strength
    nz = np.ones_like(h)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx /= length
    ny /= length
    nz /= length
    rgb = np.stack(
        [
            (nx * 0.5 + 0.5) * 255.0,
            (ny * 0.5 + 0.5) * 255.0,
            (nz * 0.5 + 0.5) * 255.0,
        ],
        axis=2,
    )
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")


def stylize_pixel(img: Image.Image, pixel_size: int = 128, colors: int = 32) -> Image.Image:
    small = img.resize((pixel_size, pixel_size), Image.Resampling.BILINEAR)
    pal = small.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    rgb = pal.convert("RGB")
    return rgb.resize(img.size, Image.Resampling.NEAREST)


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


def make_contact_sheet(products: list[dict], output: Path) -> None:
    rows = [p for p in products if p.get("kind") == "crop" and p.get("crop_size_m") == 64]
    if not rows:
        rows = [p for p in products if p.get("kind") == "crop"]
    rows = rows[:8]
    cols = ["source", "tileable_real", "stylized_pixel"]
    cell_w = 360
    image_h = 260
    caption_h = 62
    margin = 28
    gutter = 14
    title_h = 70
    sheet = Image.new(
        "RGB",
        (
            margin * 2 + len(cols) * cell_w + (len(cols) - 1) * gutter,
            margin * 2 + title_h + len(rows) * (image_h + caption_h) + max(0, len(rows) - 1) * gutter,
        ),
        (15, 18, 16),
    )
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, margin), "OpenTopo real-ground texture pilot", font=font(28, True), fill=(236, 238, 232))
    draw.text((margin, margin + 36), "Source crop vs tileable real vs stylized derivative", font=font(15), fill=(175, 184, 174))
    label_font = font(15, True)
    note_font = font(13)
    for row_idx, product in enumerate(rows):
        for col_idx, policy in enumerate(cols):
            path = Path(product["outputs"][policy]["albedo"])
            with Image.open(path) as img:
                thumb = img.convert("RGB")
                thumb.thumbnail((cell_w, image_h), Image.Resampling.LANCZOS)
                panel = Image.new("RGB", (cell_w, image_h), (27, 32, 29))
                panel.paste(thumb, ((cell_w - thumb.width) // 2, (image_h - thumb.height) // 2))
            x = margin + col_idx * (cell_w + gutter)
            y = margin + title_h + row_idx * (image_h + caption_h + gutter)
            sheet.paste(panel, (x, y))
            draw.rectangle((x, y + image_h, x + cell_w, y + image_h + caption_h), fill=(27, 32, 29))
            draw.text(
                (x + 12, y + image_h + 10),
                f"{product['crop_class']} / {policy}",
                font=label_font,
                fill=(236, 238, 232),
            )
            draw.text(
                (x + 12, y + image_h + 34),
                f"{product['crop_size_m']} m crop, score {product['selection_score']:.3f}",
                font=note_font,
                fill=(178, 188, 176),
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def feature_image(img: Image.Image, size: int, mode: str = "L") -> np.ndarray:
    resampling = Image.Resampling.BILINEAR if mode == "L" else Image.Resampling.BILINEAR
    resized = img.resize((size, size), resampling)
    arr = np.asarray(resized.convert(mode), dtype=np.float32) / 255.0
    return arr


def crop_stats(
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
    half = crop_px // 2
    left = cx - half
    top = cy - half
    right = left + crop_px
    bottom = top + crop_px
    if left < 0 or top < 0 or right > rgb.shape[1] or bottom > rgb.shape[0]:
        return None
    sl = np.s_[top:bottom, left:right]
    valid_mean = float(valid[sl].mean())
    fill_mean = float(fill[sl].mean())
    if valid_mean < 0.985 or fill_mean > 0.02:
        return None
    patch = rgb[sl]
    brightness = float(patch.mean())
    saturation = float((patch.max(axis=2) - patch.min(axis=2)).mean())
    return {
        "brightness": brightness,
        "saturation": saturation,
        "variance": float(patch.std()),
        "vegetation": float(veg[sl].mean()),
        "slope": float(slope[sl].mean()),
        "roughness": float(rough[sl].mean()),
        "valid": valid_mean,
        "fill": fill_mean,
    }


def class_score(crop_class: str, s: dict[str, float]) -> float:
    veg = s["vegetation"]
    slope = s["slope"]
    rough = s["roughness"]
    bright = s["brightness"]
    sat = s["saturation"]
    var = s["variance"]
    if crop_class == "dry_wash":
        return (1 - veg) * 0.35 + (1 - slope) * 0.2 + bright * 0.25 + (1 - sat) * 0.1 + var * 0.1
    if crop_class == "scrub_sparse":
        return (1 - abs(veg - 0.38)) * 0.45 + (1 - slope) * 0.2 + sat * 0.2 + var * 0.15
    if crop_class == "scrub_dense":
        return veg * 0.55 + sat * 0.2 + (1 - slope) * 0.15 + var * 0.1
    if crop_class == "rocky_slope":
        return slope * 0.35 + rough * 0.25 + (1 - veg) * 0.25 + var * 0.15
    if crop_class == "bare_soil":
        return (1 - veg) * 0.35 + (1 - slope) * 0.25 + (1 - abs(bright - 0.55)) * 0.25 + (1 - sat) * 0.15
    if crop_class == "bright_rock":
        return bright * 0.4 + (1 - veg) * 0.25 + rough * 0.2 + slope * 0.15
    return 0.0


def select_crops(stack_dir: Path, albedo: Image.Image, max_crop_px: int, output_count: int) -> list[CropPick]:
    layers = stack_dir / "layers"
    feature_size = 1024
    rgb = feature_image(albedo, feature_size, "RGB")
    veg = feature_image(load_gray(layers / "vegetation_ndvi_like.png", albedo.size), feature_size, "L")
    slope = feature_image(load_gray(layers / "slope_deg.png", albedo.size), feature_size, "L")
    rough = feature_image(load_gray(layers / "roughness.png", albedo.size), feature_size, "L")
    valid = feature_image(load_gray(layers / "source_valid_mask.png", albedo.size), feature_size, "L")
    fill = feature_image(load_gray(layers / "render_fill_mask.png", albedo.size), feature_size, "L")

    crop_px = max(24, int(round(max_crop_px * feature_size / albedo.width)))
    step = max(18, crop_px // 2)
    candidates: list[tuple[int, int, dict[str, float]]] = []
    for cy in range(crop_px // 2, feature_size - crop_px // 2, step):
        for cx in range(crop_px // 2, feature_size - crop_px // 2, step):
            stats = crop_stats(rgb, veg, slope, rough, valid, fill, cx, cy, crop_px)
            if stats is not None:
                candidates.append((cx, cy, stats))
    if not candidates:
        raise SystemExit("No valid crop candidates found")

    picks: list[CropPick] = []
    picked_feature_centers: list[tuple[int, int]] = []
    min_dist = crop_px * 1.1
    for crop_class in CROP_CLASSES[:output_count]:
        scored = sorted(
            ((class_score(crop_class, stats), cx, cy, stats) for cx, cy, stats in candidates),
            reverse=True,
        )
        for score, cx, cy, stats in scored:
            if all(math.dist((cx, cy), picked) >= min_dist for picked in picked_feature_centers):
                full_center = (
                    int(round(cx * albedo.width / feature_size)),
                    int(round(cy * albedo.height / feature_size)),
                )
                picks.append(CropPick(crop_class, full_center, float(score), stats))
                picked_feature_centers.append((cx, cy))
                break
    return picks


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


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


def process_crop(
    out_root: Path,
    stack_dir: Path,
    meta: dict,
    albedo: Image.Image,
    height: np.ndarray,
    roughness: Image.Image,
    slope: Image.Image,
    vegetation: Image.Image,
    pick: CropPick,
    crop_size_m: int,
    output_size: int,
) -> dict:
    world_size = float(meta.get("world_size_m", meta.get("world_size_x_m", 1600.0)))
    crop_px = max(8, int(round(crop_size_m * albedo.width / world_size)))
    name = f"{pick.crop_class}_{crop_size_m:03d}m"
    root = out_root / name
    source_dir = root / "source"
    tile_dir = root / "tileable_real"
    stylized_dir = root / "stylized_pixel"
    for d in (source_dir, tile_dir, stylized_dir):
        d.mkdir(parents=True, exist_ok=True)

    albedo_crop_native = crop_square(albedo, pick.center_px, crop_px)
    rough_crop_native = crop_square(roughness, pick.center_px, crop_px)
    slope_crop_native = crop_square(slope, pick.center_px, crop_px)
    veg_crop_native = crop_square(vegetation, pick.center_px, crop_px)
    height_crop_native = crop_array_square(height, pick.center_px, crop_px)

    source_albedo = resize_for_output(albedo_crop_native, output_size, Image.Resampling.LANCZOS)
    source_height = resize_for_output(normalize_to_u8(height_crop_native), output_size, Image.Resampling.BICUBIC)
    source_rough = resize_for_output(rough_crop_native, output_size, Image.Resampling.BILINEAR)
    source_slope = resize_for_output(slope_crop_native, output_size, Image.Resampling.BILINEAR)
    source_veg = resize_for_output(veg_crop_native, output_size, Image.Resampling.BILINEAR)

    source_albedo.save(source_dir / "albedo.png")
    source_height.save(source_dir / "height.png")
    normal_from_height(source_height).save(source_dir / "normal.png")
    source_rough.save(source_dir / "roughness.png")
    source_slope.save(source_dir / "slope.png")
    source_veg.save(source_dir / "vegetation_mask.png")
    save_tile_2x2(source_albedo, source_dir / "tile_2x2.png")

    repair_patch = max(32, output_size // 16)
    repair_plan = compute_patch_repair_plan(np.asarray(source_albedo), patch=repair_patch)
    tile_albedo = repair_image_with_plan(source_albedo, repair_plan, patch=repair_patch)
    tile_height = repair_image_with_plan(source_height, repair_plan, patch=repair_patch)
    tile_rough = repair_image_with_plan(source_rough, repair_plan, patch=repair_patch)
    tile_veg = repair_image_with_plan(source_veg, repair_plan, patch=repair_patch)
    tile_albedo.save(tile_dir / "albedo.png")
    tile_height.save(tile_dir / "height.png")
    normal_from_height(tile_height).save(tile_dir / "normal.png")
    tile_rough.save(tile_dir / "roughness.png")
    tile_veg.save(tile_dir / "masks.png")
    save_tile_2x2(tile_albedo, tile_dir / "tile_2x2.png")

    stylized = stylize_pixel(tile_albedo)
    stylized.save(stylized_dir / "albedo.png")
    tile_height.save(stylized_dir / "height.png")
    normal_from_height(tile_height, strength=2.0).save(stylized_dir / "normal.png")
    tile_rough.save(stylized_dir / "roughness.png")
    save_tile_2x2(stylized, stylized_dir / "tile_2x2.png")

    product = {
        "kind": "crop",
        "crop_class": pick.crop_class,
        "crop_size_m": crop_size_m,
        "source_stack": str(stack_dir),
        "center_px": [pick.center_px[0], pick.center_px[1]],
        "center_source_coord": source_coord(meta, pick.center_px, albedo.size),
        "native_crop_size_px": crop_px,
        "output_size_px": output_size,
        "meters_per_source_pixel": world_size / albedo.width,
        "meters_per_output_pixel": crop_size_m / output_size,
        "selection_score": pick.score,
        "selection_stats": pick.stats,
        "source_policy": "tileable_real_pilot",
        "outputs": {
            "source": {
                "policy": "source_crop",
                "albedo": str(source_dir / "albedo.png"),
                "height": str(source_dir / "height.png"),
                "normal": str(source_dir / "normal.png"),
                "roughness": str(source_dir / "roughness.png"),
                "tile_2x2": str(source_dir / "tile_2x2.png"),
                "geography_preserved": True,
            },
            "tileable_real": {
                "policy": "tileable_real",
                "albedo": str(tile_dir / "albedo.png"),
                "height": str(tile_dir / "height.png"),
                "normal": str(tile_dir / "normal.png"),
                "roughness": str(tile_dir / "roughness.png"),
                "tile_2x2": str(tile_dir / "tile_2x2.png"),
                "operations": ["offset_seam_repair", "same_crop_real_pixel_blend"],
                "repair_method": "offset_patch_quilt",
                "repair_patch_px": repair_patch,
                "repair_ops": len(repair_plan),
                "procedural_color_used": False,
                "ai_generated_color_used": False,
                "geography_preserved": False,
            },
            "stylized_pixel": {
                "policy": "stylized_derivative",
                "albedo": str(stylized_dir / "albedo.png"),
                "height": str(stylized_dir / "height.png"),
                "normal": str(stylized_dir / "normal.png"),
                "roughness": str(stylized_dir / "roughness.png"),
                "tile_2x2": str(stylized_dir / "tile_2x2.png"),
                "operations": ["palette_quantize", "nearest_pixel_upscale"],
                "procedural_color_used": False,
                "ai_generated_color_used": False,
                "geography_preserved": False,
            },
        },
    }
    write_json(root / "manifest.json", product)
    return product


def process_full_macro(out_root: Path, stack_dir: Path, meta: dict, albedo: Image.Image, output_size: int) -> dict:
    root = out_root / "full_map_macro_1600m"
    source_dir = root / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    macro = albedo.resize((output_size, output_size), Image.Resampling.LANCZOS)
    macro.save(source_dir / "albedo.png")
    save_tile_2x2(macro, source_dir / "repeat_2x2_not_seamless.png")
    product = {
        "kind": "macro_full_map",
        "source_stack": str(stack_dir),
        "crop_class": "full_map_macro",
        "ground_size_m": float(meta.get("world_size_m", 1600.0)),
        "output_size_px": output_size,
        "meters_per_output_pixel": float(meta.get("world_size_m", 1600.0)) / output_size,
        "source_policy": "source_crop_macro_atlas",
        "geography_preserved": True,
        "tileable": False,
        "note": "Full Phase 2 top-down map exported as a macro atlas. It looks good as broad color, but it is not forced seamless.",
        "outputs": {
            "source": {
                "policy": "source_crop",
                "albedo": str(source_dir / "albedo.png"),
                "tile_2x2": str(source_dir / "repeat_2x2_not_seamless.png"),
                "geography_preserved": True,
            }
        },
    }
    write_json(root / "manifest.json", product)
    return product


def parse_crop_sizes(raw: str) -> list[int]:
    sizes = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            sizes.append(int(part))
    return sorted(set(sizes))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack-dir", type=Path, default=Path("D:/assets/world3/toporeview/phase2_fusion_max"))
    ap.add_argument("--output-dir", type=Path, default=Path("D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress"))
    ap.add_argument("--crop-sizes-m", default="32,64")
    ap.add_argument("--output-size", type=int, default=1024)
    ap.add_argument("--macro-output-size", type=int, default=4096)
    ap.add_argument("--crop-count", type=int, default=6)
    args = ap.parse_args()

    stack_dir = args.stack_dir
    layers = stack_dir / "layers"
    meta = json.loads((stack_dir / "meta.json").read_text(encoding="utf-8"))
    albedo = load_rgb(layers / "render_albedo.png")
    height = load_height_u16(stack_dir / "heightmap.png")
    roughness = load_gray(layers / "roughness.png", albedo.size)
    slope = load_gray(layers / "slope_deg.png", albedo.size)
    vegetation = load_gray(layers / "vegetation_ndvi_like.png", albedo.size)

    crop_sizes = parse_crop_sizes(args.crop_sizes_m)
    if not crop_sizes:
        raise SystemExit("No crop sizes requested")
    max_crop_px = max(int(round(size * albedo.width / float(meta.get("world_size_m", 1600.0)))) for size in crop_sizes)
    picks = select_crops(stack_dir, albedo, max_crop_px, args.crop_count)

    products: list[dict] = []
    products.append(process_full_macro(args.output_dir, stack_dir, meta, albedo, args.macro_output_size))
    for pick in picks:
        for crop_size_m in crop_sizes:
            products.append(
                process_crop(
                    args.output_dir,
                    stack_dir,
                    meta,
                    albedo,
                    height,
                    roughness,
                    slope,
                    vegetation,
                    pick,
                    crop_size_m,
                    args.output_size,
                )
            )

    manifest = {
        "name": "guadalupe_cypress_tileable_real_texture_pilot",
        "source_stack": str(stack_dir),
        "output_dir": str(args.output_dir),
        "policy": {
            "source_color": "real OpenTopo render_albedo / orthophoto",
            "tileable_real": "offset seam repair by blending pixels from the same real crop",
            "stylized": "separate art derivative; not source repair",
            "full_map_macro": "preserve full map as broad atlas, not forced tileable",
        },
        "crop_sizes_m": crop_sizes,
        "output_size_px": args.output_size,
        "macro_output_size_px": args.macro_output_size,
        "products": products,
    }
    write_json(args.output_dir / "manifest.json", manifest)
    make_contact_sheet(products, args.output_dir / "comparison_sheet.png")
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "products": len(products),
        "comparison_sheet": str(args.output_dir / "comparison_sheet.png"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
