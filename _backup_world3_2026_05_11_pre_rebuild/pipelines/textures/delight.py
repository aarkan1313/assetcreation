"""De-lighting pass for AI-generated albedo maps.

AI generators bake shadows and highlights into the RGB output. AAA PBR
albedo should be flat-lit so engine lighting doesn't double up.

Strategy (deterministic; replaceable with learned model later):
  1. Convert to LAB, isolate luminance (L*)
  2. Estimate the low-frequency illumination component via large-blur
  3. Subtract a fraction of that from L (additive lighting removal)
  4. Optionally clip the brightness range to a tighter band
  5. Optionally desaturate slightly to reduce color-shift artifacts
  6. Recombine with original chroma (a*, b*) for natural color

Calibration knob `--strength` controls how aggressive the de-lighting is:
  0.0 = passthrough
  0.5 = balanced (default; gentle removal of large-scale lighting)
  1.0 = aggressive flat-lit (may wash out detail)

Usage:
  python delight.py --input albedo.png --output albedo_delit.png --strength 0.6
  python delight.py --material <dir>  # in-place delight albedo of a material
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB [0..255] -> LAB. Uses skimage if available, else simple approx."""
    try:
        from skimage import color
        return color.rgb2lab(rgb / 255.0).astype(np.float32)
    except ImportError:
        # Fallback: approximate luminance and pseudo-chroma
        rgb_n = rgb / 255.0
        L = 0.2126 * rgb_n[..., 0] + 0.7152 * rgb_n[..., 1] + 0.0722 * rgb_n[..., 2]
        L = (L * 100).astype(np.float32)
        a = ((rgb_n[..., 0] - rgb_n[..., 1]) * 50).astype(np.float32)
        b = ((rgb_n[..., 1] - rgb_n[..., 2]) * 50).astype(np.float32)
        return np.stack([L, a, b], axis=-1)


def lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    try:
        from skimage import color
        return (color.lab2rgb(lab) * 255).clip(0, 255).astype(np.uint8)
    except ImportError:
        L = lab[..., 0] / 100.0
        a = lab[..., 1] / 50.0
        b = lab[..., 2] / 50.0
        r = np.clip(L + a * 0.5, 0, 1)
        g = np.clip(L - a * 0.5 + b * 0.25, 0, 1)
        bl = np.clip(L - b * 0.5, 0, 1)
        return (np.stack([r, g, bl], axis=-1) * 255).astype(np.uint8)


def estimate_illumination(L: np.ndarray, blur_radius: int = 64) -> np.ndarray:
    """Large-blur estimate of low-frequency lighting."""
    L_im = Image.fromarray(L.astype(np.uint8) if L.max() > 1 else (L * 255).astype(np.uint8), mode="L")
    blurred = np.asarray(L_im.filter(ImageFilter.GaussianBlur(radius=blur_radius)),
                          dtype=np.float32)
    if L.max() <= 1:
        blurred /= 255.0
    return blurred


def delight(rgb: np.ndarray, strength: float = 0.6,
            blur_radius_frac: float = 0.0625,
            tighten_range: bool = True,
            desaturate: float = 0.0) -> np.ndarray:
    """Remove low-frequency illumination from an albedo image.

    Args:
        rgb: HxWx3 uint8 input
        strength: 0..1 — how much of the illumination component to subtract
        blur_radius_frac: blur radius as fraction of image min dim (default ~6%)
        tighten_range: clip extreme luminance after de-lighting
        desaturate: 0..1 — desaturate result a bit (helps texture-on-mesh)
    """
    h, w = rgb.shape[:2]
    blur_radius = max(8, int(min(h, w) * blur_radius_frac))

    lab = rgb_to_lab(rgb)
    L = lab[..., 0]  # 0..100

    # Estimate large-scale illumination
    illum = estimate_illumination(L, blur_radius=blur_radius)

    # Subtract a normalized fraction. We want the *deviation* of illum from
    # the global mean, multiplied by `strength`, removed from L.
    illum_mean = illum.mean()
    illum_dev = illum - illum_mean
    L_delit = L - illum_dev * strength

    if tighten_range:
        # Pull extremes back toward the median
        med = float(np.median(L_delit))
        spread = max(L_delit.std(), 1e-3)
        target_spread = spread * 0.85  # slightly compress range
        L_delit = med + (L_delit - med) * (target_spread / spread)

    L_delit = np.clip(L_delit, 0, 100)
    lab[..., 0] = L_delit

    if desaturate > 0:
        lab[..., 1] *= (1 - desaturate)
        lab[..., 2] *= (1 - desaturate)

    return lab_to_rgb(lab)


def run_on_material(material_dir: Path, strength: float, backup: bool = True):
    catalog = Path("D:/assets/world/textures/catalog/materials.jsonl")
    manifest = None
    if catalog.exists():
        for line in catalog.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec.get("id") == material_dir.name:
                manifest = rec
                break

    if manifest and "albedo" in manifest.get("maps", {}):
        albedo_path = material_dir / manifest["maps"]["albedo"]
    else:
        # Find any *_albedo.png
        candidates = list(material_dir.glob("*_albedo.png"))
        if not candidates:
            candidates = list(material_dir.glob("*albedo*"))
        if not candidates:
            raise SystemExit(f"no albedo found in {material_dir}")
        albedo_path = candidates[0]

    print(f"[delight] {albedo_path.name} strength={strength}")
    if backup:
        bk = albedo_path.with_suffix(".pre_delight.png")
        if not bk.exists():
            shutil.copy2(albedo_path, bk)

    rgb = np.asarray(Image.open(albedo_path).convert("RGB"))
    delit = delight(rgb, strength=strength)
    Image.fromarray(delit).save(albedo_path)
    print(f"  saved (backup at {bk.name if backup else 'no backup'})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, help="single albedo image")
    ap.add_argument("--output", type=Path, help="output path for --input mode")
    ap.add_argument("--material", type=Path, help="material directory (in-place)")
    ap.add_argument("--strength", type=float, default=0.6)
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    if args.material:
        run_on_material(args.material, args.strength, backup=not args.no_backup)
        return

    if not args.input or not args.output:
        ap.error("provide --material OR (--input AND --output)")

    rgb = np.asarray(Image.open(args.input).convert("RGB"))
    delit = delight(rgb, strength=args.strength)
    Image.fromarray(delit).save(args.output)
    print(f"[delight] {args.input.name} -> {args.output.name} (strength={args.strength})")


if __name__ == "__main__":
    main()
