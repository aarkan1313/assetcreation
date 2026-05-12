"""High-pass detail extraction for an existing albedo.

Given a tileable albedo, produce a "detail" version by subtracting a
low-pass blur and rebalancing. Useful as:
  1. A cheap detail-variant for the macro+detail shader without
     spending compute on a fresh generation.
  2. A sharpening pass for textures that came out soft.
  3. An input to other tools that want "the high-frequency content of
     this material" as a separate signal.

Strategy:
  - Convert to LAB. Apply a Gaussian blur to get the low-pass.
  - Subtract: detail = original - blur. This is the high-pass.
  - Recenter to mid-grey (so 0 detail = 128 grey, not 0 black).
  - Optionally amplify (`--gain`) to make detail more pronounced.

Tileability: blur is symmetric so it preserves wrap-around. We pad
with the texture itself (replicating across edges) before blurring,
which keeps the high-pass continuous across the seam.

Usage:
  # Detail-only output (grey-centered):
  python high_pass_detail.py --in world/textures/library/wgv3_dirt --out detail.png
  # Sharpen the source itself in-place (amplify high-freq, keep low):
  python high_pass_detail.py --in <dir> --sharpen --gain 1.4
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def _gaussian_blur_tileable(rgb: np.ndarray, radius: float) -> np.ndarray:
    """Gaussian blur with seamless wrap. Pads with the image itself."""
    h, w = rgb.shape[:2]
    pad = max(int(radius * 3), 8)
    padded = np.zeros((h + 2 * pad, w + 2 * pad, rgb.shape[2]), dtype=rgb.dtype)
    padded[pad:pad + h, pad:pad + w] = rgb
    # Wrap-fill the padding from the opposite edges so blur doesn't leak
    # zeros at borders.
    padded[:pad, pad:pad + w] = rgb[h - pad:, :]
    padded[pad + h:, pad:pad + w] = rgb[:pad, :]
    padded[pad:pad + h, :pad] = rgb[:, w - pad:]
    padded[pad:pad + h, pad + w:] = rgb[:, :pad]
    padded[:pad, :pad] = rgb[h - pad:, w - pad:]
    padded[:pad, pad + w:] = rgb[h - pad:, :pad]
    padded[pad + h:, :pad] = rgb[:pad, w - pad:]
    padded[pad + h:, pad + w:] = rgb[:pad, :pad]
    blurred = np.asarray(
        Image.fromarray(padded).filter(ImageFilter.GaussianBlur(radius=radius))
    )
    return blurred[pad:pad + h, pad:pad + w]


def high_pass(rgb: np.ndarray, radius: float = 16.0) -> np.ndarray:
    """Return high-pass = original - blur, recentered to 128."""
    blur = _gaussian_blur_tileable(rgb, radius).astype(np.float32)
    src = rgb.astype(np.float32)
    detail = (src - blur) + 128.0
    return np.clip(detail, 0, 255).astype(np.uint8)


def sharpen(rgb: np.ndarray, radius: float = 16.0, gain: float = 1.4) -> np.ndarray:
    """Add gain × high-pass back to original. gain > 1 sharpens."""
    blur = _gaussian_blur_tileable(rgb, radius).astype(np.float32)
    src = rgb.astype(np.float32)
    detail_signed = src - blur  # range roughly [-128, +128]
    out = src + detail_signed * (gain - 1.0)
    return np.clip(out, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="input", type=Path, required=True,
                    help="material dir OR an albedo .png file")
    ap.add_argument("--out", type=Path,
                    help="output .png (default: <id>_detail.png next to input)")
    ap.add_argument("--radius", type=float, default=16.0,
                    help="Gaussian blur radius. Larger = lower-frequency low-pass = "
                         "more low-frequency content kept in the high-pass result")
    ap.add_argument("--sharpen", action="store_true",
                    help="instead of detail-only, sharpen the source by adding "
                         "gain*high_pass back. Output replaces input albedo.")
    ap.add_argument("--gain", type=float, default=1.4,
                    help="sharpen gain (only with --sharpen). 1.0 = no change")
    ap.add_argument("--no-backup", action="store_true",
                    help="for --sharpen, don't write a .pre_sharpen backup")
    args = ap.parse_args()

    # Resolve input.
    if args.input.is_dir():
        # Find the albedo. Prefer <id>_albedo.png, fall back to *albedo*.png
        candidates = (list(args.input.glob(f"{args.input.name}_albedo.png"))
                      + list(args.input.glob("*albedo*.png")))
        candidates = [c for c in candidates if "pre_" not in c.name]
        if not candidates:
            raise SystemExit(f"no albedo found in {args.input}")
        in_path = candidates[0]
    else:
        in_path = args.input

    rgb = np.asarray(Image.open(in_path).convert("RGB"))

    if args.sharpen:
        out_path = in_path  # in-place sharpen
        if not args.no_backup:
            backup = in_path.with_suffix(".pre_sharpen.png")
            if not backup.exists():
                shutil.copy2(in_path, backup)
        result = sharpen(rgb, radius=args.radius, gain=args.gain)
        Image.fromarray(result).save(out_path)
        print(f"  sharpened in place -> {out_path.name} (gain={args.gain})")
    else:
        if args.out:
            out_path = args.out
        else:
            stem = in_path.stem.replace("_albedo", "")
            out_path = in_path.with_name(f"{stem}_high_pass.png")
        result = high_pass(rgb, radius=args.radius)
        Image.fromarray(result).save(out_path)
        print(f"  high-pass detail -> {out_path}")


if __name__ == "__main__":
    main()
