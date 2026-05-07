"""Fantasy-edit a real DEM heightmap.

Take a real-world heightmap (e.g. from import_dem.py) and apply stylization
filters that retain the geographic bones (rivers, ridges, plateaus) but push
the look toward fantasy: exaggerated verticals, terraced steps, sharpened
ridges, injected spires.

Operates on a normalized [0..1] heightmap PNG and emits another normalized
heightmap PNG, so it slots cleanly between import_dem.py and the biome engine.

Usage:
  python dem_fantasy_edit.py --in height_16.png --out fantasy.png --style mythic
  python dem_fantasy_edit.py --in <bundle>/height_16.png --out fantasy.png --style spired --strength 1.4

Styles:
  realistic    — passthrough (sanity check)
  exaggerated  — vertical 2-3× scaling
  terraced     — quantize to N step bands (temple-mountain look)
  sharpened    — Laplacian boost on ridges
  spired       — inject crystal-spire profile into peaks
  floating     — invert + mask (Avatar-style floating islands)
  mythic       — combo: exaggerated + sharpened + mild spire injection in highlands
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def load_height(path: Path) -> np.ndarray:
    arr = np.asarray(Image.open(path)).astype(np.float32)
    if arr.max() > 1.0:
        arr /= 65535.0 if arr.max() > 256.0 else 255.0
    return np.clip(arr, 0.0, 1.0)


def save_height(h: np.ndarray, path: Path) -> None:
    h = np.clip(h, 0.0, 1.0)
    arr16 = (h * 65535.0).astype(np.uint16)
    Image.fromarray(arr16, mode="I;16").save(path)


def style_realistic(h: np.ndarray, strength: float) -> np.ndarray:
    return h


def style_exaggerated(h: np.ndarray, strength: float) -> np.ndarray:
    """Push vertical contrast — high places higher, low places lower.
    Done in normalized space via gamma curve around the mean."""
    mean = float(h.mean())
    above = np.maximum(h - mean, 0.0) ** (1.0 / strength)
    below = np.maximum(mean - h, 0.0) ** strength
    out = np.where(h > mean, mean + above * (1.0 - mean) ** (1 - 1.0 / strength),
                              mean - below * mean ** (1 - strength))
    out = (out - out.min()) / (out.max() - out.min() + 1e-9)
    return out


def style_terraced(h: np.ndarray, strength: float, levels: int = 8) -> np.ndarray:
    """Quantize heights to discrete bands. Strength controls smoothness of the steps:
    0 = razor-sharp, 1 = soft transitions."""
    n = max(2, int(levels))
    quantized = np.round(h * (n - 1)) / (n - 1)
    soft = np.clip(strength, 0.0, 1.0)
    return h * soft + quantized * (1.0 - soft)


def style_sharpened(h: np.ndarray, strength: float) -> np.ndarray:
    """Unsharp mask on the heightmap — boosts ridges and crests."""
    blurred = ndimage.gaussian_filter(h, sigma=4.0)
    detail = h - blurred
    return np.clip(h + detail * strength, 0.0, 1.0)


def style_spired(h: np.ndarray, strength: float, spire_threshold: float = 0.6) -> np.ndarray:
    """Inject vertical spire injections at peaks. Wherever h > threshold, add a
    cubic-curve spike. Strength controls intensity."""
    above = np.clip(h - spire_threshold, 0.0, 1.0) / (1.0 - spire_threshold + 1e-9)
    spire = above ** 3 * strength * 0.4
    out = np.clip(h + spire, 0.0, 1.0)
    # Renormalize so we don't shift the overall histogram
    return (out - out.min()) / (out.max() - out.min() + 1e-9)


def style_floating(h: np.ndarray, strength: float) -> np.ndarray:
    """Invert above a threshold and gap below — Avatar floating-mountain look.
    The result is interpreted as: low areas become open sky, high areas float."""
    threshold = 0.45
    floating_mask = h > threshold
    out = np.where(floating_mask, h, 0.0)
    # Add a cubic taper at the bottom of each floating island for the "rooted" feel.
    blurred_mask = ndimage.gaussian_filter(floating_mask.astype(np.float32), sigma=3.0)
    out = out + (blurred_mask ** 2) * 0.1 * strength
    return np.clip(out, 0.0, 1.0)


def style_mythic(h: np.ndarray, strength: float) -> np.ndarray:
    """Combo preset: exaggerated → sharpened → mild spire injection.
    Strength scales each step proportionally."""
    s = max(strength, 0.5)
    h1 = style_exaggerated(h, 1.0 + 0.5 * s)
    h2 = style_sharpened(h1, 0.6 * s)
    h3 = style_spired(h2, 0.4 * s, spire_threshold=0.65)
    return h3


STYLES = {
    "realistic":   style_realistic,
    "exaggerated": style_exaggerated,
    "terraced":    style_terraced,
    "sharpened":   style_sharpened,
    "spired":      style_spired,
    "floating":    style_floating,
    "mythic":      style_mythic,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="input_path", type=Path, required=True,
                    help="input heightmap PNG (16-bit grayscale, 0..1)")
    ap.add_argument("--out", type=Path, required=True,
                    help="output heightmap PNG")
    ap.add_argument("--style", choices=list(STYLES.keys()), default="mythic")
    ap.add_argument("--strength", type=float, default=1.0,
                    help="style intensity multiplier (most styles in [0.5, 2.0])")
    args = ap.parse_args()

    h = load_height(args.input_path)
    print(f"  in:  {args.input_path}  shape={h.shape}  range=[{h.min():.3f}, {h.max():.3f}]")
    out = STYLES[args.style](h, args.strength)
    out = np.clip(out, 0.0, 1.0)
    print(f"  out: style={args.style} strength={args.strength}  range=[{out.min():.3f}, {out.max():.3f}]")
    save_height(out, args.out)
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
