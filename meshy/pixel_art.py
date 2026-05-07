"""Optional pixel-art post-processor for sprite frames.

Usage:
    python pixel_art.py <sprite_dir_or_atlas.png> [<out_path>] [options]

Options:
    --pixel-size N      target pixel size for downscale (default 64)
    --palette N         restrict to N colors via median-cut quantization (default off)
    --no-dither         disable Floyd-Steinberg dithering (default: dithering enabled)
    --upscale N         upscale by N (nearest neighbor) for chunky pixels (default 1)
    --outline           add 1-px black outline around opaque silhouettes
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from PIL import Image, ImageFilter
except ImportError as e:
    raise SystemExit("Pillow required. pip install Pillow") from e


def pixelate(im: Image.Image, pixel_size: int) -> Image.Image:
    """Downscale to pixel_size on the longest side, then back to original via nearest neighbor."""
    w, h = im.size
    long = max(w, h)
    if long <= pixel_size:
        return im
    r = pixel_size / long
    small_w, small_h = max(1, int(round(w * r))), max(1, int(round(h * r)))
    small = im.resize((small_w, small_h), Image.LANCZOS)
    return small.resize((w, h), Image.NEAREST)


def quantize_palette(im: Image.Image, palette_size: int, dither: bool) -> Image.Image:
    """Reduce to palette_size colors using a fresh per-image palette.
    Preserves alpha channel.
    """
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    rgb = Image.new("RGB", im.size, (0, 0, 0))
    rgb.paste(im, mask=im.split()[3])  # composite over black
    method = Image.Quantize.MEDIANCUT
    dither_mode = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    quantized = rgb.quantize(colors=palette_size, method=method, dither=dither_mode)
    quantized = quantized.convert("RGB")
    out = Image.new("RGBA", im.size)
    out.paste(quantized, (0, 0))
    out.putalpha(im.split()[3])  # restore alpha
    return out


def build_shared_palette(images: list[Image.Image], palette_size: int) -> Image.Image:
    """Build a single palette image from the union of multiple frames.
    Used for temporal coherence — every frame quantizes against the same colors,
    so colors don't shimmer/shift across an animation.
    """
    if not images:
        raise ValueError("need at least one image")
    # Stack images vertically into one big image so quantize sees them as one
    total_w = max(im.width for im in images)
    total_h = sum(im.height for im in images)
    merged = Image.new("RGB", (total_w, total_h), (0, 0, 0))
    y = 0
    for im in images:
        rgba = im.convert("RGBA")
        rgb = Image.new("RGB", rgba.size, (0, 0, 0))
        rgb.paste(rgba, mask=rgba.split()[3])
        merged.paste(rgb, (0, y))
        y += rgba.height
    palette_image = merged.quantize(colors=palette_size, method=Image.Quantize.MEDIANCUT)
    return palette_image  # in 'P' mode with palette set


def quantize_with_shared_palette(im: Image.Image, palette_image: Image.Image, dither: bool) -> Image.Image:
    """Apply a pre-built palette image to one frame. Preserves alpha."""
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    rgb = Image.new("RGB", im.size, (0, 0, 0))
    rgb.paste(im, mask=im.split()[3])
    dither_mode = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    quantized = rgb.quantize(palette=palette_image, dither=dither_mode).convert("RGB")
    out = Image.new("RGBA", im.size)
    out.paste(quantized, (0, 0))
    out.putalpha(im.split()[3])
    return out


def add_outline(im: Image.Image, color=(0, 0, 0, 255)) -> Image.Image:
    """Add a 1-pixel outline around the alpha silhouette."""
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    alpha = im.split()[3]
    edges = alpha.filter(ImageFilter.MaxFilter(3))  # dilate by 1
    outline_layer = Image.new("RGBA", im.size, color)
    outline_layer.putalpha(edges)
    composed = Image.alpha_composite(outline_layer, im)
    return composed


def process(im: Image.Image, args, shared_palette: Image.Image | None = None) -> Image.Image:
    if args.pixel_size > 0:
        im = pixelate(im, args.pixel_size)
    if args.palette > 0:
        if shared_palette is not None:
            im = quantize_with_shared_palette(im, shared_palette, dither=not args.no_dither)
        else:
            im = quantize_palette(im, args.palette, dither=not args.no_dither)
    if args.outline:
        im = add_outline(im)
    if args.upscale > 1:
        w, h = im.size
        im = im.resize((w * args.upscale, h * args.upscale), Image.NEAREST)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path,
                    help="single PNG or atlas, or sprite_dir from bake.py")
    ap.add_argument("out", type=Path, nargs="?", default=None)
    ap.add_argument("--pixel-size", type=int, default=64,
                    help="downscale longest-side to this many pixels (0 to skip)")
    ap.add_argument("--palette", type=int, default=0,
                    help="palette quantize to N colors (0 to skip)")
    ap.add_argument("--no-dither", action="store_true")
    ap.add_argument("--upscale", type=int, default=1)
    ap.add_argument("--outline", action="store_true")
    ap.add_argument("--no-shared-palette", action="store_true",
                    help="Disable temporal-coherence palette sharing (debug only)")
    ap.add_argument("--palette-sample", type=int, default=12,
                    help="Number of frames to sample when building shared palette "
                         "(more = better palette but slower setup, default 12)")
    args = ap.parse_args()

    if args.input.is_file() and args.input.suffix.lower() == ".png":
        # Single image
        im = Image.open(args.input).convert("RGBA")
        out_path = args.out or args.input.with_stem(args.input.stem + "_pix")
        process(im, args).save(out_path)
        print(f"wrote: {out_path}")
        return

    if args.input.is_dir():
        # Process all PNGs in tree (preserves structure under out_dir)
        out_dir = args.out or args.input.with_name(args.input.name + "_pix")
        out_dir.mkdir(parents=True, exist_ok=True)

        all_pngs = list(args.input.rglob("*.png"))
        if not all_pngs:
            raise SystemExit(f"no .png files found under {args.input}")

        # Build a shared palette across an evenly-distributed sample of frames.
        # This eliminates color-shimmer across animation frames.
        shared_palette = None
        if args.palette > 0 and not args.no_shared_palette:
            n = min(args.palette_sample, len(all_pngs))
            step = max(1, len(all_pngs) // n)
            sample_paths = all_pngs[::step][:n]
            print(f"building shared palette from {len(sample_paths)}/{len(all_pngs)} frames...")
            sample_images = []
            for sp in sample_paths:
                sim = Image.open(sp).convert("RGBA")
                # Pre-pixelate so palette is built from the actual output resolution
                if args.pixel_size > 0:
                    sim = pixelate(sim, args.pixel_size)
                sample_images.append(sim)
            shared_palette = build_shared_palette(sample_images, args.palette)

        count = 0
        for png in all_pngs:
            rel = png.relative_to(args.input)
            target = out_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            im = Image.open(png).convert("RGBA")
            process(im, args, shared_palette=shared_palette).save(target)
            count += 1
        # Copy manifest if present
        manifest = args.input / "manifest.json"
        if manifest.exists():
            (out_dir / "manifest.json").write_text(manifest.read_text())
        print(f"processed {count} pngs -> {out_dir}"
              + (" (shared palette)" if shared_palette is not None else ""))
        return

    raise SystemExit(f"input must be a .png file or a directory: {args.input}")


if __name__ == "__main__":
    main()
