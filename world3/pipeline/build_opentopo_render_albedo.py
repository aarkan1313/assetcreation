"""Build a source-first render albedo from OpenTopo review layers.

This script deliberately does not try to procedurally repaint terrain. The
default output is the real orthophoto, optionally with real-pixel edge extension
for explicit color gaps. Geometry/no-data repair is handled by the heightmap
pipeline and tracked by masks; it should not force fake color into the albedo.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

try:
    from scipy import ndimage
except Exception:  # pragma: no cover - optional fallback
    ndimage = None


Image.MAX_IMAGE_PIXELS = None


def load_rgb_image(path: Path) -> tuple[np.ndarray, Image.Image]:
    with Image.open(path) as img:
        img = img.convert("RGB")
        return np.asarray(img, dtype=np.uint8), img.copy()


def load_mask(path: Path | None, size: tuple[int, int]) -> np.ndarray:
    if path is None or not path.exists():
        return np.zeros((size[1], size[0]), dtype=bool)
    with Image.open(path) as img:
        img = img.convert("L")
        if img.size != size:
            img = img.resize(size, Image.Resampling.NEAREST)
        return np.asarray(img, dtype=np.uint8) > 0


def detect_color_gaps(rgb: np.ndarray, threshold: int) -> np.ndarray:
    if threshold <= 0:
        return np.zeros(rgb.shape[:2], dtype=bool)
    return np.all(rgb <= threshold, axis=2)


def extend_real_pixels(rgb: np.ndarray, gap: np.ndarray) -> tuple[np.ndarray, str]:
    if not gap.any():
        return rgb, "none"
    valid = ~gap
    if not valid.any():
        return rgb, "skipped_no_valid_source_pixels"
    if ndimage is None:
        return rgb, "skipped_scipy_unavailable"
    indices = ndimage.distance_transform_edt(gap, return_distances=False, return_indices=True)
    filled = rgb.copy()
    nearest = rgb[tuple(indices)]
    filled[gap] = nearest[gap]
    # Blend only the repaired edge by a tiny amount so copied pixels do not
    # create a hard seam. This uses nearby real pixels, not generated color.
    edge = Image.fromarray((gap.astype(np.uint8) * 255), mode="L").filter(ImageFilter.GaussianBlur(1.25))
    edge_arr = (np.asarray(edge, dtype=np.float32) / 255.0)[:, :, None]
    out = rgb.astype(np.float32) * (1.0 - edge_arr) + filled.astype(np.float32) * edge_arr
    return out.clip(0, 255).astype(np.uint8), "nearest_real_pixel_extension"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layers-dir", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--orthophoto", default="orthophoto_rgb.png")
    ap.add_argument("--gap-mask", type=Path, default=None,
                    help="optional explicit mask of color pixels to repair")
    ap.add_argument("--auto-black-threshold", type=int, default=0,
                    help="treat RGB values <= threshold as color gaps")
    ap.add_argument("--contrast", type=float, default=1.0,
                    help="optional final contrast adjustment; 1.0 preserves source")
    ap.add_argument("--source-valid", default="source_valid_mask.png")
    ap.add_argument("--fill-mask", default="render_fill_mask.png")
    ap.add_argument("--cliff-mask", default="cliff_mask.png")
    args = ap.parse_args()

    ortho_path = args.layers_dir / args.orthophoto
    rgb, src_img = load_rgb_image(ortho_path)
    size = src_img.size

    explicit_gap = load_mask(args.gap_mask, size)
    auto_gap = detect_color_gaps(rgb, args.auto_black_threshold)
    gap = explicit_gap | auto_gap
    repaired, repair_method = extend_real_pixels(rgb, gap)

    out_img = Image.fromarray(repaired, mode="RGB")
    if args.contrast != 1.0:
        out_img = ImageEnhance.Contrast(out_img).enhance(args.contrast)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(args.output)

    source_valid_path = args.layers_dir / args.source_valid
    fill_mask_path = args.layers_dir / args.fill_mask
    cliff_mask_path = args.layers_dir / args.cliff_mask
    sidecar = {
        "output": str(args.output),
        "kind": "render_albedo",
        "method": "source_orthophoto_first",
        "description": (
            "Render-facing albedo that preserves the real orthophoto. "
            "It only repairs explicit color gaps by extending nearby real pixels."
        ),
        "inputs": {
            "orthophoto": str(ortho_path),
            "gap_mask": str(args.gap_mask) if args.gap_mask else None,
            "source_valid_mask": str(source_valid_path) if source_valid_path.exists() else None,
            "render_fill_mask": str(fill_mask_path) if fill_mask_path.exists() else None,
            "cliff_mask": str(cliff_mask_path) if cliff_mask_path.exists() else None,
        },
        "size": [size[0], size[1]],
        "contrast": args.contrast,
        "auto_black_threshold": args.auto_black_threshold,
        "gap_pixels": int(np.count_nonzero(gap)),
        "gap_repair_method": repair_method,
        "policy": {
            "geometry_repair_affects_albedo": False,
            "procedural_color_used": False,
            "source_texture_preserved": True,
        },
    }
    args.output.with_suffix(args.output.suffix + ".json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "size": sidecar["size"],
        "gap_pixels": sidecar["gap_pixels"],
        "gap_repair_method": repair_method,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
