"""Quick procedural noise texture for pipeline testing.

Uses Pillow + numpy to build a stone-ish tileable noise texture.

Usage:
    python make_test_texture.py [--size 512] [--out PATH]
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image


def perlin_like_noise(size: int, scale: int, seed: int = 42) -> np.ndarray:
    """Generate value-noise that tiles seamlessly via wrapped grid lookups."""
    rng = np.random.default_rng(seed)
    grid = rng.random((scale + 1, scale + 1)).astype(np.float32)
    # Make it wrap: last col = first col, last row = first row
    grid[:, -1] = grid[:, 0]
    grid[-1, :] = grid[0, :]
    grid[-1, -1] = grid[0, 0]

    out = np.zeros((size, size), dtype=np.float32)
    # Bilinear interpolation
    for y in range(size):
        gy = y / size * scale
        y0 = int(gy)
        fy = gy - y0
        for x in range(size):
            gx = x / size * scale
            x0 = int(gx)
            fx = gx - x0
            # Smoothstep
            tx = fx * fx * (3 - 2 * fx)
            ty = fy * fy * (3 - 2 * fy)
            v00 = grid[y0, x0]
            v10 = grid[y0, x0 + 1]
            v01 = grid[y0 + 1, x0]
            v11 = grid[y0 + 1, x0 + 1]
            top = v00 * (1 - tx) + v10 * tx
            bot = v01 * (1 - tx) + v11 * tx
            out[y, x] = top * (1 - ty) + bot * ty
    return out


def fbm(size: int, octaves: int = 4, seed: int = 42) -> np.ndarray:
    """Fractal Brownian Motion — sum noise at multiple scales."""
    out = np.zeros((size, size), dtype=np.float32)
    amp = 1.0
    total = 0.0
    for o in range(octaves):
        scale = 4 * (2 ** o)
        out += amp * perlin_like_noise(size, scale, seed + o)
        total += amp
        amp *= 0.5
    return out / total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent.parent.parent / "world" / "textures" / "input_images" / "test_stone.png")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    print(f"generating {args.size}×{args.size} test stone texture...")
    n = fbm(args.size, octaves=5, seed=args.seed)
    # Color it gray-brown
    base_color = np.array([130, 120, 110], dtype=np.float32) / 255.0
    variance = np.array([60, 50, 40], dtype=np.float32) / 255.0

    rgb = np.zeros((args.size, args.size, 3), dtype=np.float32)
    for c in range(3):
        rgb[..., c] = base_color[c] + (n - 0.5) * variance[c] * 2
    rgb = np.clip(rgb * 255, 0, 255).astype(np.uint8)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(args.out)
    print(f"wrote: {args.out}")


if __name__ == "__main__":
    main()
