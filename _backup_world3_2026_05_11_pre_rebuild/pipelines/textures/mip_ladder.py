"""Multi-tier mip ladder writer for PBR material sets.

Takes a directory of baked high-res PBR maps (output of bake_pbr.py) and
writes physically-correct downsampled tiers. Each tier uses per-map correct
filtering:

  albedo   -- gamma-aware: linearize -> Lanczos -> re-encode sRGB
  normal   -- vector-field: decode XYZ -> filter as floats -> renormalize -> re-encode
  roughness -- linear Lanczos (L mode)
  ao       -- linear Lanczos (L mode)
  metallic -- linear Lanczos (L mode)
  height   -- linear Lanczos (L mode)

Output layout:
  <out_dir>/
    2k/   <id>_albedo.png  <id>_normal.png  ...  (6 maps at 2048)
    1k/   <id>_albedo.png  ...                    (6 maps at 1024)
    512/  <id>_albedo.png  ...                    (6 maps at 512)

The source dir maps are copied into the highest tier (no upsampling).
Lower tiers are filtered down from the source.

Usage:
  python mip_ladder.py --in world/textures/library/wgv3_rock_dark
  python mip_ladder.py --in D:/tmp/baked_master --tiers 2k,1k,512 --out D:/tmp/ladder

Phase B.3 deliverable. See:
  docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


TIER_SIZES = {"4k": 4096, "2k": 2048, "1k": 1024, "512": 512, "256": 256}
MAP_NAMES = ["albedo", "normal", "roughness", "ao", "metallic", "height"]


def parse_tier(s: str) -> tuple[str, int]:
    """Parse a tier string like '2k' or '1024' -> (label, pixels)."""
    s = s.strip().lower()
    if s in TIER_SIZES:
        return s, TIER_SIZES[s]
    try:
        px = int(s)
        label = next((k for k, v in TIER_SIZES.items() if v == px), str(px))
        return label, px
    except ValueError:
        raise ValueError(f"unknown tier '{s}' -- use 4k, 2k, 1k, 512, or a pixel count")


def find_map(src_dir: Path, map_name: str) -> Path | None:
    """Find <id>_<map_name>[_suffix].png in src_dir, excluding backups/baked."""
    candidates = [
        p for p in src_dir.glob(f"*_{map_name}*.png")
        if "pre_" not in p.name and "_baked" not in p.name
        and (p.stem.endswith(f"_{map_name}") or f"_{map_name}_" in p.stem)
    ]
    exact = [p for p in candidates if p.stem.endswith(f"_{map_name}")]
    return (exact or candidates)[0] if (exact or candidates) else None


def downsample_normal(im: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Filter normal map as XYZ vector field, renormalize, re-encode.

    Naive RGB filtering produces shorter (faded) normals at lower mips.
    This decodes to float XYZ, filters each channel, then renormalizes.
    """
    arr = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    xyz = arr * 2.0 - 1.0  # decode [0,1] -> [-1,1]

    def _filter_channel(channel_arr: np.ndarray) -> np.ndarray:
        packed = ((channel_arr * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
        down = Image.fromarray(packed, mode="L").resize(target_size, Image.LANCZOS)
        return np.asarray(down, dtype=np.float32) / 255.0 * 2.0 - 1.0

    x = _filter_channel(xyz[..., 0])
    y = _filter_channel(xyz[..., 1])
    z = _filter_channel(xyz[..., 2])
    length = np.maximum(np.sqrt(x**2 + y**2 + z**2), 1e-8)
    x /= length
    y /= length
    z /= length
    rgb = np.stack([x * 0.5 + 0.5, y * 0.5 + 0.5, z * 0.5 + 0.5], axis=-1)
    return Image.fromarray((rgb * 255).clip(0, 255).astype(np.uint8), mode="RGB")


def downsample_albedo(im: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Gamma-aware downsample: linearize sRGB -> Lanczos -> re-encode sRGB.

    Direct Lanczos on sRGB data over-weights dark pixels (gamma ~2.2 bias).
    """
    arr = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    linear = arr ** 2.2  # approx sRGB decode
    lin_im = Image.fromarray((linear * 255).clip(0, 255).astype(np.uint8), mode="RGB")
    lin_down = np.asarray(lin_im.resize(target_size, Image.LANCZOS), dtype=np.float32) / 255.0
    srgb = np.clip(lin_down ** (1.0 / 2.2), 0.0, 1.0)
    return Image.fromarray((srgb * 255).astype(np.uint8), mode="RGB")


def downsample_linear(im: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Standard Lanczos for linearly-encoded maps (roughness, AO, metallic, height)."""
    return im.convert("L").resize(target_size, Image.LANCZOS)


def downsample_map(map_name: str, im: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Dispatch to the correct filter for each map type."""
    if map_name == "albedo":
        return downsample_albedo(im, target_size)
    elif map_name == "normal":
        return downsample_normal(im, target_size)
    else:
        return downsample_linear(im, target_size)


def build_ladder(src_dir: Path, tiers: list[tuple[str, int]], out_dir: Path) -> dict:
    """Write mip ladder tiers from src_dir into out_dir/<tier_label>/.

    Returns a dict with mat_id, src_dir, and per-tier per-map output paths.
    """
    src_maps: dict[str, Path] = {}
    for map_name in MAP_NAMES:
        p = find_map(src_dir, map_name)
        if p is None:
            print(f"  WARNING: no {map_name} found in {src_dir} -- skipping")
        else:
            src_maps[map_name] = p

    if not src_maps:
        raise FileNotFoundError(f"no PBR maps found in {src_dir}")

    # Derive material ID from first found map stem by stripping known map names
    first_map = next(iter(src_maps.values()))
    mat_id = first_map.stem
    for map_name in MAP_NAMES:
        if f"_{map_name}" in mat_id:
            mat_id = mat_id[: mat_id.rindex(f"_{map_name}")]
            break

    print(f"  mat_id={mat_id}  source_maps={list(src_maps.keys())}")

    results: dict[str, dict[str, str]] = {}

    for tier_label, tier_px in tiers:
        tier_dir = out_dir / tier_label
        tier_dir.mkdir(parents=True, exist_ok=True)
        results[tier_label] = {}
        target_size = (tier_px, tier_px)
        print(f"  tier={tier_label} ({tier_px}px)  -> {tier_dir}")

        for map_name, src_path in src_maps.items():
            im = Image.open(src_path)
            src_px = max(im.size)
            out_path = tier_dir / f"{mat_id}_{map_name}.png"

            if tier_px >= src_px:
                # Same or larger than source -- copy, normalizing mode
                if map_name in ("albedo", "normal"):
                    im.convert("RGB").save(out_path)
                else:
                    im.convert("L").save(out_path)
            else:
                downsampled = downsample_map(map_name, im, target_size)
                downsampled.save(out_path)

            results[tier_label][map_name] = str(out_path)
            print(f"    {map_name:12} {src_px}px -> {tier_px}px  {out_path.name}")

    return {"mat_id": mat_id, "src_dir": str(src_dir), "tiers": results}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src_dir", type=Path, required=True,
                    help="source dir containing baked PBR maps (from bake_pbr.py)")
    ap.add_argument("--tiers", default="2k,1k,512",
                    help="comma-separated tier list (default: 2k,1k,512)")
    ap.add_argument("--out", type=Path, default=None,
                    help="output root dir (default: <src_dir>/ladder/)")
    args = ap.parse_args()

    if not args.src_dir.is_dir():
        raise SystemExit(f"--in not found: {args.src_dir}")

    tiers = [parse_tier(t) for t in args.tiers.split(",")]
    out_dir = args.out if args.out is not None else args.src_dir / "ladder"

    print(f"building mip ladder")
    print(f"  source: {args.src_dir}")
    print(f"  tiers:  {[f'{l}({px})' for l, px in tiers]}")
    print(f"  output: {out_dir}")

    result = build_ladder(args.src_dir, tiers, out_dir)

    print(f"\ndone. ladder written to {out_dir}")
    for tier_label in result["tiers"]:
        maps_written = list(result["tiers"][tier_label].keys())
        print(f"  {tier_label}/  {len(maps_written)} maps: {maps_written}")


if __name__ == "__main__":
    main()
