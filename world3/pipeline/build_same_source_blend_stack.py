"""Build a seam-conditioned source macro for same-source repeat tests.

The same-source blend scene is a workflow rung: if one real source cannot join
to itself cleanly, unlike-source blending is not ready. This tool creates a
review-only macro albedo whose border bands are conditioned from safer interior
strips so runtime wrap/blend tests do not inherit source-edge scars.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png"
DEFAULT_VALID_MASK = ROOT / "textures/source_stack/gloss_scrub_source_stack/source_macro_valid_mask.png"
DEFAULT_OUTPUT_DIR = ROOT / "textures/source_stack/gloss_scrub_same_source_blend"
DEFAULT_HEIGHT_INPUT = ROOT / "toporeview/gloss_mountain_textured_master/heightmap.png"
DEFAULT_META_INPUT = ROOT / "toporeview/gloss_mountain_textured_master/meta.json"
DEFAULT_HEIGHT_OUTPUT_DIR = ROOT / "toporeview/gloss_mountain_textured_master_same_source_blend"


def smoothstep(x: np.ndarray) -> np.ndarray:
    return x * x * (3.0 - 2.0 * x)


def edge_delta(arr: np.ndarray) -> dict[str, float]:
    x_delta = np.abs(arr[:, 0, :] - arr[:, -1, :]).mean()
    y_delta = np.abs(arr[0, :, :] - arr[-1, :, :]).mean()
    return {
        "x_edge_mean_abs_rgb": float(x_delta),
        "y_edge_mean_abs_rgb": float(y_delta),
    }


def roll_for_seam(arr: np.ndarray, roll_x_frac: float, roll_y_frac: float) -> tuple[np.ndarray, dict[str, int]]:
    height, width = arr.shape[:2]
    shift_x = int(round((roll_x_frac % 1.0) * width))
    shift_y = int(round((roll_y_frac % 1.0) * height))
    rolled = np.roll(arr, shift=(-shift_y, -shift_x), axis=(0, 1))
    return rolled, {"x_px": shift_x, "y_px": shift_y}


def valid_crop_box(mask_path: Path, inset_px: int) -> tuple[int, int, int, int]:
    mask = np.asarray(Image.open(mask_path).convert("L"), dtype=np.float32) / 255.0
    ys, xs = np.where(mask > 0.5)
    if xs.size == 0 or ys.size == 0:
        raise ValueError(f"valid mask has no valid pixels: {mask_path}")
    x0 = int(xs.min()) + inset_px
    x1 = int(xs.max()) + 1 - inset_px
    y0 = int(ys.min()) + inset_px
    y1 = int(ys.max()) + 1 - inset_px
    if x1 <= x0 or y1 <= y0:
        raise ValueError("valid crop inset is larger than the valid mask bounds")
    return x0, y0, x1, y1


def crop_array(arr: np.ndarray, crop: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = crop
    return arr[y0:y1, x0:x1, :]


def parse_crop_box(value: str) -> tuple[int, int, int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("--crop-box must be x0,y0,x1,y1")
    x0, y0, x1, y1 = parts
    if x1 <= x0 or y1 <= y0:
        raise ValueError("--crop-box must have x1 > x0 and y1 > y0")
    return x0, y0, x1, y1


def blur_strip(strip: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0.0:
        return strip
    if strip.shape[2] != 3:
        return strip
    img = Image.fromarray(np.clip(strip * 255.0, 0, 255).astype(np.uint8), "RGB")
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32) / 255.0


def condition_x_edges(arr: np.ndarray, band_px: int, blur_radius: float) -> np.ndarray:
    height, width, channels = arr.shape
    band_px = max(1, min(band_px, width // 4))
    out = arr.copy()

    left_ref = arr[:, band_px : band_px * 2, :]
    right_ref = arr[:, width - band_px * 2 : width - band_px, :][:, ::-1, :]
    common = blur_strip((left_ref + right_ref) * 0.5, blur_radius)

    t = (np.arange(band_px, dtype=np.float32) + 0.5) / float(band_px)
    weight = (1.0 - smoothstep(t))[None, :, None]

    left_orig = arr[:, :band_px, :]
    right_orig = arr[:, width - band_px :, :][:, ::-1, :]
    left_new = left_orig * (1.0 - weight) + common * weight
    right_new = right_orig * (1.0 - weight) + common * weight

    out[:, :band_px, :] = left_new
    out[:, width - band_px :, :] = right_new[:, ::-1, :]
    return out


def heal_x_seam(arr: np.ndarray, seam_x: int, band_px: int) -> np.ndarray:
    height, width, channels = arr.shape
    band_px = max(1, min(band_px, width // 8))
    if seam_x <= band_px or seam_x >= width - band_px:
        return arr
    out = arr.copy()
    start = seam_x - band_px
    end = seam_x + band_px
    left_ref = arr[:, start - 1 : start, :]
    right_ref = arr[:, end : end + 1, :]
    t = np.linspace(0.0, 1.0, end - start, dtype=np.float32)[None, :, None]
    smooth = left_ref * (1.0 - t) + right_ref * t
    original = arr[:, start:end, :]
    out[:, start:end, :] = original * 0.25 + smooth * 0.75
    return out


def heal_internal_roll_seams(arr: np.ndarray, roll_px: dict[str, int], band_px: int) -> np.ndarray:
    height, width = arr.shape[:2]
    out = arr
    seam_x = width - int(roll_px.get("x_px", 0))
    seam_y = height - int(roll_px.get("y_px", 0))
    out = heal_x_seam(out, seam_x, band_px)
    out = np.transpose(heal_x_seam(np.transpose(out, (1, 0, 2)), seam_y, band_px), (1, 0, 2))
    return out


def condition_edges(arr: np.ndarray, band_px: int, blur_radius: float) -> np.ndarray:
    out = condition_x_edges(arr, band_px, blur_radius)
    out = np.transpose(condition_x_edges(np.transpose(out, (1, 0, 2)), band_px, blur_radius), (1, 0, 2))
    return out


def write_macro_outputs(
    input_path: Path,
    output_dir: Path,
    band_px: int,
    blur_radius: float,
    roll_x_frac: float,
    roll_y_frac: float,
    crop: tuple[int, int, int, int] | None,
    internal_heal_band_px: int,
) -> dict:
    img = Image.open(input_path).convert("RGB")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    if crop is not None:
        arr = crop_array(arr, crop)
    arr, roll_px = roll_for_seam(arr, roll_x_frac, roll_y_frac)
    arr = heal_internal_roll_seams(arr, roll_px, internal_heal_band_px)
    band_px = max(1, min(band_px, min(arr.shape[0], arr.shape[1]) // 4))

    before = edge_delta(arr)
    conditioned = condition_edges(arr, band_px, blur_radius)
    after = edge_delta(conditioned)

    output_dir.mkdir(parents=True, exist_ok=True)
    albedo_path = output_dir / "source_macro_albedo.png"
    valid_path = output_dir / "source_macro_valid_mask.png"
    Image.fromarray(np.clip(conditioned * 255.0, 0, 255).astype(np.uint8), "RGB").save(albedo_path)
    Image.new("L", img.size, color=255).save(valid_path)

    manifest = {
        "version": 1,
        "kind": "same_source_blend_source_stack",
        "id": output_dir.name,
        "source_macro": res_path(input_path),
        "runtime_macro": res_path(albedo_path),
        "runtime_source_macro_valid_mask": res_path(valid_path),
        "source_macro_runtime_size_px": [img.size[0], img.size[1]],
        "conditioned_runtime_size_px": [int(arr.shape[1]), int(arr.shape[0])],
        "valid_crop_box_px": list(crop) if crop is not None else None,
        "edge_condition_band_px": band_px,
        "edge_condition_blur_radius_px": blur_radius,
        "internal_heal_band_px": internal_heal_band_px,
        "source_roll_fraction": {"x": roll_x_frac % 1.0, "y": roll_y_frac % 1.0},
        "source_roll_px": roll_px,
        "mask_policy": "review_only_full_valid_after_edge_conditioning",
        "before": before,
        "after": after,
        "policy": "same_source_repeat_poc_condition_source_edges_before_runtime_height_blend",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def write_height_outputs(
    input_path: Path,
    meta_path: Path,
    output_dir: Path,
    band_px: int,
    roll_x_frac: float,
    roll_y_frac: float,
    crop_fraction: tuple[float, float, float, float] | None,
    internal_heal_band_px: int,
) -> dict:
    img = Image.open(input_path)
    arr_raw = np.asarray(img)
    arr = arr_raw.astype(np.float32)
    scale = 65535.0 if arr.max() <= 65535.0 else float(arr.max())
    norm = np.clip(arr / scale, 0.0, 1.0)[:, :, None]
    if crop_fraction is not None:
        h, w = norm.shape[:2]
        fx0, fy0, fx1, fy1 = crop_fraction
        crop = (
            int(round(fx0 * w)),
            int(round(fy0 * h)),
            int(round(fx1 * w)),
            int(round(fy1 * h)),
        )
        norm = crop_array(norm, crop)
    else:
        crop = None
    norm, roll_px = roll_for_seam(norm, roll_x_frac, roll_y_frac)
    norm = heal_internal_roll_seams(norm, roll_px, internal_heal_band_px)
    band_px = max(1, min(band_px, min(norm.shape[0], norm.shape[1]) // 4))

    before = edge_delta(norm)
    conditioned = condition_edges(norm, band_px, 0.0)[:, :, 0]
    after = edge_delta(conditioned[:, :, None])

    output_dir.mkdir(parents=True, exist_ok=True)
    height_path = output_dir / "heightmap.png"
    Image.fromarray(np.clip(conditioned * 65535.0, 0, 65535).astype(np.uint16), mode="I;16").save(height_path)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if crop_fraction is not None:
        fx0, fy0, fx1, fy1 = crop_fraction
        world_size = float(meta.get("world_size_m", 1024.0))
        original_x = float(meta.get("world_size_x_m", world_size))
        original_z = float(meta.get("world_size_z_m", world_size))
        meta["world_size_x_m"] = original_x * max(fx1 - fx0, 0.001)
        meta["world_size_z_m"] = original_z * max(fy1 - fy0, 0.001)
        meta["world_size_m"] = max(float(meta["world_size_x_m"]), float(meta["world_size_z_m"]))
    meta["source_conditioning"] = {
        "kind": "same_source_blend_height_edge_conditioning",
        "source_heightmap": res_path(input_path),
        "height_edge_condition_band_px": band_px,
        "height_internal_heal_band_px": internal_heal_band_px,
        "valid_crop_fraction": list(crop_fraction) if crop_fraction is not None else None,
        "valid_crop_px": list(crop) if crop is not None else None,
        "source_roll_fraction": {"x": roll_x_frac % 1.0, "y": roll_y_frac % 1.0},
        "source_roll_px": roll_px,
        "before": before,
        "after": after,
        "policy": "review_only_same_source_repeat_poc",
    }
    (output_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    return {
        "runtime_heightmap": res_path(height_path),
        "runtime_meta": res_path(output_dir / "meta.json"),
        "height_edge_condition_band_px": band_px,
        "height_internal_heal_band_px": internal_heal_band_px,
        "valid_crop_fraction": list(crop_fraction) if crop_fraction is not None else None,
        "valid_crop_px": list(crop) if crop is not None else None,
        "source_roll_fraction": {"x": roll_x_frac % 1.0, "y": roll_y_frac % 1.0},
        "source_roll_px": roll_px,
        "before": before,
        "after": after,
    }


def res_path(path: Path) -> str:
    rel = path.resolve().relative_to(ROOT)
    return "res://" + rel.as_posix()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--valid-mask", type=Path, default=DEFAULT_VALID_MASK)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--band-px", type=int, default=24)
    parser.add_argument("--blur-radius", type=float, default=0.35)
    parser.add_argument("--height-input", type=Path, default=DEFAULT_HEIGHT_INPUT)
    parser.add_argument("--meta-input", type=Path, default=DEFAULT_META_INPUT)
    parser.add_argument("--height-output-dir", type=Path, default=DEFAULT_HEIGHT_OUTPUT_DIR)
    parser.add_argument("--height-band-px", type=int, default=128)
    parser.add_argument("--internal-heal-band-px", type=int, default=0)
    parser.add_argument("--height-internal-heal-band-px", type=int, default=0)
    parser.add_argument("--roll-x-frac", type=float, default=0.0)
    parser.add_argument("--roll-y-frac", type=float, default=0.0)
    parser.add_argument("--valid-crop-inset-px", type=int, default=24)
    parser.add_argument("--no-valid-crop", action="store_true")
    parser.add_argument("--crop-box", default="240,80,1040,1880")
    args = parser.parse_args()

    if args.crop_box:
        crop = parse_crop_box(args.crop_box)
    elif args.no_valid_crop:
        crop = None
    else:
        crop = valid_crop_box(args.valid_mask, args.valid_crop_inset_px)
    if crop is not None:
        src_img = Image.open(args.input)
        w, h = src_img.size
        x0, y0, x1, y1 = crop
        crop_fraction = (x0 / w, y0 / h, x1 / w, y1 / h)
    else:
        crop_fraction = None

    manifest = write_macro_outputs(
        args.input,
        args.output_dir,
        args.band_px,
        args.blur_radius,
        args.roll_x_frac,
        args.roll_y_frac,
        crop,
        args.internal_heal_band_px,
    )
    manifest["height"] = write_height_outputs(
        args.height_input,
        args.meta_input,
        args.height_output_dir,
        args.height_band_px,
        args.roll_x_frac,
        args.roll_y_frac,
        crop_fraction,
        args.height_internal_heal_band_px,
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
