"""Generate procedural heightmaps for Godot terrain.

Two modes:
  1. Synthetic — pure FBM/perlin-like noise with biome shaping
  2. Image-driven — derive a heightmap from any input grayscale image

Usage:
    python generate_heightmap.py [--mode synthetic|image] [options]

Synthetic mode options:
    --size N            output resolution (default 1024, square)
    --scale F           noise feature scale (default 1.0; lower = bigger features)
    --octaves N         noise detail levels (default 6)
    --erosion N         erosion passes (default 0; 30-100 for natural-looking terrain)
    --biome STR         "mountains", "plains", "islands", "canyon", or "custom"
    --seed N            random seed
    --out PATH          output path (default: terrain/output/<biome>_<seed>.png)
    --colormap          also output a hypsometric (height-shaded) preview PNG
    --normal            also output a derived normal map

Image mode options (--mode image):
    --input PATH        source image (grayscale or RGB; will be converted)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


# --- Noise primitives --------------------------------------------------------
def value_noise(size: int, scale: int, seed: int = 0) -> np.ndarray:
    """Wrapped value noise. Tiles seamlessly because grid wraps."""
    rng = np.random.default_rng(seed)
    grid = rng.random((scale + 1, scale + 1)).astype(np.float32)
    grid[:, -1] = grid[:, 0]
    grid[-1, :] = grid[0, :]
    grid[-1, -1] = grid[0, 0]

    out = np.zeros((size, size), dtype=np.float32)
    ys = np.linspace(0, scale, size, endpoint=False)
    xs = np.linspace(0, scale, size, endpoint=False)
    for i, gy in enumerate(ys):
        y0 = int(gy)
        fy = gy - y0
        ty = fy * fy * (3 - 2 * fy)
        for j, gx in enumerate(xs):
            x0 = int(gx)
            fx = gx - x0
            tx = fx * fx * (3 - 2 * fx)
            v00 = grid[y0, x0]
            v10 = grid[y0, x0 + 1]
            v01 = grid[y0 + 1, x0]
            v11 = grid[y0 + 1, x0 + 1]
            top = v00 * (1 - tx) + v10 * tx
            bot = v01 * (1 - tx) + v11 * tx
            out[i, j] = top * (1 - ty) + bot * ty
    return out


def fbm(size: int, base_scale: int = 4, octaves: int = 6, persistence: float = 0.5, seed: int = 0) -> np.ndarray:
    out = np.zeros((size, size), dtype=np.float32)
    amp = 1.0
    total = 0.0
    for o in range(octaves):
        scale = base_scale * (2 ** o)
        out += amp * value_noise(size, scale, seed + o)
        total += amp
        amp *= persistence
    return out / total


# --- Biome shaping -----------------------------------------------------------
def shape_biome(h: np.ndarray, biome: str) -> np.ndarray:
    """Apply a biome-specific transform to a 0..1 heightmap."""
    if biome == "mountains":
        # Sharpen peaks, valleys go flat
        h = np.power(h, 0.6) * 1.4 - 0.2
        return np.clip(h, 0, 1)
    if biome == "plains":
        # Compress middle, slight rolling
        return 0.3 + h * 0.4
    if biome == "islands":
        # Apply a radial mask + threshold so high spots are islands surrounded by sea
        size = h.shape[0]
        cy, cx = size / 2, size / 2
        ys, xs = np.indices(h.shape)
        r = np.sqrt((ys - cy) ** 2 + (xs - cx) ** 2) / (size / 2)
        mask = np.clip(1 - r, 0, 1)
        h_shaped = h * mask
        # threshold: sea level at 0.4
        return np.where(h_shaped < 0.4, h_shaped * 0.5, h_shaped)
    if biome == "canyon":
        # Carve a winding river
        size = h.shape[0]
        ys = np.arange(size).reshape(-1, 1)
        xs = np.arange(size).reshape(1, -1)
        # Sinusoidal river path
        river_x = size / 2 + np.sin(ys / size * 4 * np.pi) * size * 0.2
        river_dist = np.abs(xs - river_x) / size
        carve = 1.0 - np.exp(-river_dist * 30)
        return np.clip(h * carve, 0, 1)
    return h  # "custom" / default


# --- Erosion (cheap thermal) -------------------------------------------------
def thermal_erode(h: np.ndarray, iterations: int, talus: float = 0.005) -> np.ndarray:
    """Cheap thermal erosion: any cell taller than its neighbors by > talus
    gives some height to the lowest neighbor.
    """
    h = h.copy()
    for _ in range(iterations):
        # neighbors
        n = np.roll(h, -1, axis=0)
        s = np.roll(h, 1, axis=0)
        e = np.roll(h, -1, axis=1)
        w = np.roll(h, 1, axis=1)
        # for each cell, max difference to neighbor
        d_n = h - n
        d_s = h - s
        d_e = h - e
        d_w = h - w
        max_d = np.maximum(np.maximum(d_n, d_s), np.maximum(d_e, d_w))
        # cells that exceed talus erode by half the difference
        erode_amount = np.where(max_d > talus, (max_d - talus) * 0.4, 0)
        h -= erode_amount
        # deposit to lowest neighbor (just average for simplicity)
        deposit = erode_amount / 4
        h += np.roll(deposit, 1, axis=0)
        h += np.roll(deposit, -1, axis=0)
        h += np.roll(deposit, 1, axis=1)
        h += np.roll(deposit, -1, axis=1)
    return np.clip(h, 0, 1)


# --- Output helpers ----------------------------------------------------------
def to_png_16bit(h: np.ndarray, path: Path):
    """Save as 16-bit grayscale PNG (preserves more height precision)."""
    arr = (h * 65535).clip(0, 65535).astype(np.uint16)
    Image.fromarray(arr, mode="I;16").save(path)


def hypsometric_preview(h: np.ndarray) -> Image.Image:
    """Color-shaded preview: blue water → green land → brown mountains → white peaks."""
    out = np.zeros((h.shape[0], h.shape[1], 3), dtype=np.float32)
    sea = h < 0.35
    grass = (h >= 0.35) & (h < 0.55)
    rock = (h >= 0.55) & (h < 0.8)
    snow = h >= 0.8

    out[sea] = [40, 80, 130]
    out[grass] = [70, 120, 50]
    out[rock] = [110, 90, 70]
    out[snow] = [240, 240, 250]
    # Add height-based shading
    shading = (h * 0.4 + 0.6).reshape(*h.shape, 1)
    out = (out * shading).clip(0, 255).astype(np.uint8)
    return Image.fromarray(out, mode="RGB")


def normal_from_height(h: np.ndarray, strength: float = 4.0) -> Image.Image:
    """Compute tangent-space normal map from height field."""
    pad = np.pad(h, 1, mode="wrap")
    gx = (pad[1:-1, 2:] - pad[1:-1, :-2]) * strength
    gy = (pad[2:, 1:-1] - pad[:-2, 1:-1]) * strength
    nx = -gx
    ny = -gy
    nz = np.ones_like(nx)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx /= norm
    ny /= norm
    nz /= norm
    r = ((nx * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
    g = ((ny * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
    b = ((nz * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
    return Image.fromarray(np.stack([r, g, b], axis=-1), mode="RGB")


# --- Main --------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["synthetic", "image"], default="synthetic")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--octaves", type=int, default=6)
    ap.add_argument("--erosion", type=int, default=0)
    ap.add_argument("--biome", default="custom",
                    choices=["mountains", "plains", "islands", "canyon", "custom"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--input", type=Path, default=None,
                    help="(image mode) source image to derive heightmap from")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--colormap", action="store_true")
    ap.add_argument("--normal", action="store_true")
    args = ap.parse_args()

    OUT_DIR = Path(__file__).parent / "output"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.mode == "image":
        if not args.input or not args.input.exists():
            raise SystemExit("--input required and must exist for image mode")
        im = Image.open(args.input).convert("L")
        if im.size != (args.size, args.size):
            im = im.resize((args.size, args.size), Image.LANCZOS)
        h = np.asarray(im, dtype=np.float32) / 255.0
        name = f"{args.input.stem}_height"
    else:
        print(f"generating {args.size}×{args.size} {args.biome} heightmap, seed={args.seed}...")
        base_scale = max(2, int(4 / args.scale))
        h = fbm(args.size, base_scale=base_scale, octaves=args.octaves, seed=args.seed)
        # Normalize to 0..1
        h = (h - h.min()) / (h.max() - h.min() + 1e-9)
        h = shape_biome(h, args.biome)
        if args.erosion > 0:
            print(f"applying {args.erosion} erosion passes...")
            h = thermal_erode(h, args.erosion)
        name = f"{args.biome}_{args.seed}"

    out_dir = args.out or (OUT_DIR / name)
    out_dir.mkdir(parents=True, exist_ok=True)

    h_path = out_dir / f"{name}_height.png"
    to_png_16bit(h, h_path)
    print(f"  wrote {h_path.name}")

    if args.colormap:
        cmap_path = out_dir / f"{name}_preview.png"
        hypsometric_preview(h).save(cmap_path)
        print(f"  wrote {cmap_path.name}")

    if args.normal:
        n_path = out_dir / f"{name}_normal.png"
        normal_from_height(h).save(n_path)
        print(f"  wrote {n_path.name}")

    # Godot Terrain3D / HeightMapShape3D template hint
    readme = out_dir / "README.txt"
    readme.write_text(
        f"Heightmap for Godot terrain.\n\n"
        f"  size: {args.size}x{args.size} (16-bit PNG, 0=lowest, 65535=highest)\n"
        f"  biome: {args.biome}\n\n"
        "Use in Godot:\n"
        "  HeightMapShape3D - assign this PNG as the heightmap.\n"
        "  Terrain3D plugin - import as height layer.\n"
        f"  Recommended terrain Y scale: ~16-64 meters (height range 0-1 in PNG -> 0-N meters in world).\n",
        encoding="utf-8"
    )
    print(f"  wrote {readme.name}")
    print(f"\ndone: {out_dir}")


if __name__ == "__main__":
    main()
