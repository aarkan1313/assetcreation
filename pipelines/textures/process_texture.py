"""Process a base color texture into a tileable Godot-ready PBR material.

Usage:
    python process_texture.py <input_image> [<output_dir>] [options]

Operations performed:
  1. Resize to power-of-two square (default 1024)
  2. Make seamless via mirror/blend at edges (optional)
  3. Generate normal map from luminance (Sobel-derived height)
  4. Generate roughness map from luminance (inverted, contrast-shaped)
  5. Generate AO map from luminance (darkened in low areas)
  6. Save as <name>_albedo.png, <name>_normal.png, <name>_roughness.png, <name>_ao.png
  7. Write Godot StandardMaterial3D template (.tres) referencing all maps

Options:
    --size N                output size (default 1024, power of two)
    --seamless              apply mirror/blend tiling (default off — assumes input is already tileable)
    --normal-strength F     normal map intensity (default 1.0)
    --roughness-base F      roughness baseline (default 0.7)
    --no-godot-tres         skip writing the Godot material template
    --name NAME             override base name for outputs (default: input filename stem)
"""
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from PIL import Image, ImageFilter, ImageOps
except ImportError as e:
    raise SystemExit("Pillow required. pip install Pillow") from e

try:
    import numpy as np
except ImportError as e:
    raise SystemExit("numpy required. pip install numpy") from e


def to_power_of_two(im: Image.Image, size: int) -> Image.Image:
    """Resize to a square of `size` × `size` (longest side fits, then crop)."""
    return im.resize((size, size), Image.LANCZOS)


def make_seamless(im: Image.Image) -> Image.Image:
    """Make the texture tileable by blending opposite edges via offset+blend.
    Standard trick: shift by half, then blend the seams.
    """
    arr = np.asarray(im).astype(np.float32)
    h, w = arr.shape[:2]
    # Roll by half so old edges meet in the middle
    rolled = np.roll(arr, (h // 2, w // 2), axis=(0, 1))
    # Now blend the seams (a vertical and horizontal stripe at the new center)
    # We linearly interpolate across the seam zone, ~12% of the dim.
    blend_w = max(8, w // 8)
    blend_h = max(8, h // 8)
    out = arr.copy()
    # vertical seam: at x = w/2
    cx = w // 2
    for x in range(blend_w):
        a = x / blend_w
        # Smoothstep for nicer blend
        t = a * a * (3 - 2 * a)
        # left half of seam
        out[:, cx - blend_w + x] = arr[:, cx - blend_w + x] * (1 - t) + rolled[:, cx - blend_w + x] * t
        # right half mirror
        out[:, cx + x] = rolled[:, cx + x] * (1 - t) + arr[:, cx + x] * t
    # horizontal seam: at y = h/2
    cy = h // 2
    for y in range(blend_h):
        a = y / blend_h
        t = a * a * (3 - 2 * a)
        out[cy - blend_h + y, :] = out[cy - blend_h + y, :] * (1 - t) + rolled[cy - blend_h + y, :] * t
        out[cy + y, :] = rolled[cy + y, :] * (1 - t) + out[cy + y, :] * t
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), mode=arr_mode(im))


def arr_mode(im: Image.Image) -> str:
    return im.mode if im.mode in ("RGB", "RGBA", "L") else "RGB"


def luminance(im: Image.Image) -> np.ndarray:
    """Get a 2D luminance array (0..255)."""
    if im.mode != "RGB":
        im = im.convert("RGB")
    arr = np.asarray(im, dtype=np.float32)
    # ITU-R BT.601 luma
    lum = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    return lum


def normal_map_from_luminance(im: Image.Image, strength: float = 1.0) -> Image.Image:
    """Sobel-based normal map. Output in tangent-space encoded RGB."""
    lum = luminance(im) / 255.0  # 0..1
    # Sobel x and y derivatives
    # Use Pillow filters since they handle edge wrap; we'll use np for clarity.
    # 3×3 Sobel kernels:
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
    ky = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32)

    h, w = lum.shape
    pad = np.pad(lum, 1, mode="wrap")
    gx = (
        kx[0, 0] * pad[:-2, :-2] + kx[0, 1] * pad[:-2, 1:-1] + kx[0, 2] * pad[:-2, 2:] +
        kx[1, 0] * pad[1:-1, :-2] + kx[1, 1] * pad[1:-1, 1:-1] + kx[1, 2] * pad[1:-1, 2:] +
        kx[2, 0] * pad[2:, :-2] + kx[2, 1] * pad[2:, 1:-1] + kx[2, 2] * pad[2:, 2:]
    )
    gy = (
        ky[0, 0] * pad[:-2, :-2] + ky[0, 1] * pad[:-2, 1:-1] + ky[0, 2] * pad[:-2, 2:] +
        ky[1, 0] * pad[1:-1, :-2] + ky[1, 1] * pad[1:-1, 1:-1] + ky[1, 2] * pad[1:-1, 2:] +
        ky[2, 0] * pad[2:, :-2] + ky[2, 1] * pad[2:, 1:-1] + ky[2, 2] * pad[2:, 2:]
    )

    nx = -gx * strength
    ny = -gy * strength
    nz = np.ones_like(nx)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx /= norm
    ny /= norm
    nz /= norm

    # Encode to 0..255: each channel = (n * 0.5 + 0.5) * 255
    r = ((nx * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
    g = ((ny * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
    b = ((nz * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
    rgb = np.stack([r, g, b], axis=-1)
    return Image.fromarray(rgb, mode="RGB")


def roughness_map_from_luminance(im: Image.Image, base: float = 0.7) -> Image.Image:
    """Lighter areas = rougher surfaces (rough heuristic for stone/wood/cloth).
    Most sane textures should override this with hand-painted maps later.
    """
    lum = luminance(im) / 255.0
    # Map to roughness: brighter = rougher, but pulled toward `base`
    rough = base * (0.6 + 0.4 * lum)
    rough = np.clip(rough, 0.0, 1.0)
    return Image.fromarray((rough * 255).astype(np.uint8), mode="L")


def ao_map_from_luminance(im: Image.Image) -> Image.Image:
    """Cheap AO: darken low-luminance regions (cracks/crevices)."""
    lum = luminance(im) / 255.0
    # Smooth the luminance to find big shapes; subtract that to find local lows
    pil = Image.fromarray((lum * 255).astype(np.uint8), mode="L")
    blurred = pil.filter(ImageFilter.GaussianBlur(radius=8))
    blurred_arr = np.asarray(blurred, dtype=np.float32) / 255.0
    detail = lum - blurred_arr  # negative where it's darker than local average
    # Compress to AO: 1.0 (no occlusion) base, drop down with detail
    ao = np.clip(0.85 + detail * 1.5, 0.3, 1.0)
    return Image.fromarray((ao * 255).astype(np.uint8), mode="L")


GODOT_TRES_TEMPLATE = """[gd_resource type="StandardMaterial3D" load_steps=5 format=3]

[ext_resource type="Texture2D" path="res://{base}_albedo.png" id="1"]
[ext_resource type="Texture2D" path="res://{base}_normal.png" id="2"]
[ext_resource type="Texture2D" path="res://{base}_roughness.png" id="3"]
[ext_resource type="Texture2D" path="res://{base}_ao.png" id="4"]

[resource]
albedo_texture = ExtResource("1")
normal_enabled = true
normal_texture = ExtResource("2")
roughness_texture = ExtResource("3")
ao_enabled = true
ao_texture = ExtResource("4")
uv1_triplanar = false
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output_dir", type=Path, nargs="?", default=None)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--seamless", action="store_true")
    ap.add_argument("--normal-strength", type=float, default=1.0)
    ap.add_argument("--roughness-base", type=float, default=0.7)
    ap.add_argument("--no-godot-tres", action="store_true")
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")

    base = args.name or args.input.stem
    out_dir = args.output_dir or (Path(__file__).parent / "output" / base)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"input: {args.input}")
    print(f"out_dir: {out_dir}")
    print(f"base name: {base}")

    im = Image.open(args.input).convert("RGB")
    print(f"  source: {im.size[0]}×{im.size[1]} {im.mode}")

    if im.size != (args.size, args.size):
        im = to_power_of_two(im, args.size)
        print(f"  resized to {args.size}×{args.size}")

    if args.seamless:
        im = make_seamless(im)
        print(f"  applied seamless blend")

    # albedo
    albedo_path = out_dir / f"{base}_albedo.png"
    im.save(albedo_path)
    print(f"  wrote {albedo_path.name}")

    # normal
    normal = normal_map_from_luminance(im, strength=args.normal_strength)
    normal_path = out_dir / f"{base}_normal.png"
    normal.save(normal_path)
    print(f"  wrote {normal_path.name}")

    # roughness
    rough = roughness_map_from_luminance(im, base=args.roughness_base)
    rough_path = out_dir / f"{base}_roughness.png"
    rough.save(rough_path)
    print(f"  wrote {rough_path.name}")

    # ao
    ao = ao_map_from_luminance(im)
    ao_path = out_dir / f"{base}_ao.png"
    ao.save(ao_path)
    print(f"  wrote {ao_path.name}")

    # godot material
    if not args.no_godot_tres:
        tres_path = out_dir / f"{base}.tres"
        tres_path.write_text(GODOT_TRES_TEMPLATE.format(base=base))
        print(f"  wrote {tres_path.name}")

    print(f"\ndone: {out_dir}")


if __name__ == "__main__":
    main()
