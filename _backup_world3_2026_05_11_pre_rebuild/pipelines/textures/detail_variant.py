"""Generate a detail-variant PBR set tied to an existing macro texture.

The macro+detail shader pattern (world3/shaders/terrain_hex_detail.gdshader)
samples the same PBR set at two UV scales — 10m repeat for macro, 1.25m for
detail — and blends. Sampling the same texture twice works, but the source
was authored at the macro scale, so the detail layer is just a scaled-down
copy of macro features.

A purpose-built detail variant has:
  - finer-grained features (smaller pebbles, micro-cracks)
  - higher contrast (so it modulates the macro layer visibly)
  - the same hue family (so it doesn't fight the macro)

Strategy:
  1. Read the parent material's manifest to get the original prompt + category.
  2. Construct a detail-flavored prompt: append "fine grain, micro detail,
     small features, high contrast" and any category-specific hints.
  3. Run aaa_texture with a fresh seed and `--id <parent>_detail`.
  4. Pass a flag through so palette_lock-style hue matching can run after
     to ensure the detail's color family matches the macro.

Usage:
  python detail_variant.py --of wgv3_rock_dark
  python detail_variant.py --of wgv3_grass --strength 0.7  # palette match
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image


LIBRARY = Path(r"D:\assets\world\textures\library")
PIPELINE_DIR = Path(__file__).parent


# Per-category prompt suffixes that nudge FLUX toward fine-detail output.
DETAIL_SUFFIXES = {
    "Ground":   "extreme close-up macro, fine grit, tiny pebbles, micro-detail, high contrast",
    "Rock":     "extreme close-up macro, fine surface roughness, micro-cracks, grain, high contrast",
    "Snow":     "extreme close-up macro, fine snow crystal detail, sparkle, micro-roughness, high contrast",
    "Sand":     "extreme close-up macro, individual grains visible, fine crystalline detail, high contrast",
    "Foliage":  "extreme close-up macro, individual leaf veins, fine moss, tiny stems, high contrast",
    "Wood":     "extreme close-up macro, fine wood grain, splinters, micro-texture, high contrast",
    "Brick":    "extreme close-up macro, fine mortar grain, surface pores, micro-texture, high contrast",
    "Metal":    "extreme close-up macro, fine metal grain, micro-scratches, surface pores, high contrast",
    "Concrete": "extreme close-up macro, fine aggregate, micro-pores, surface grain, high contrast",
    "default":  "extreme close-up macro, fine grain, micro-detail, high contrast",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--of", required=True,
                    help="parent material ID (must exist in library/)")
    ap.add_argument("--id", default=None,
                    help="output ID (default: <parent>_detail)")
    ap.add_argument("--quality", default="default",
                    choices=["fast", "default", "strict"])
    ap.add_argument("--seed-base", type=int, default=None,
                    help="seed-base (default: parent's seed + 1000)")
    ap.add_argument("--strength", type=float, default=0.5,
                    help="palette match strength against parent (0 = no "
                         "match, 1 = full match). 0.5 keeps detail's "
                         "natural variation while pulling toward parent hue.")
    ap.add_argument("--no-palette-match", action="store_true",
                    help="skip the post-generation palette match")
    args = ap.parse_args()

    parent_dir = LIBRARY / args.of
    parent_manifest = parent_dir / "aaa_pipeline.json"
    if not parent_manifest.exists():
        raise SystemExit(f"parent manifest not found: {parent_manifest}")
    parent = json.loads(parent_manifest.read_text(encoding="utf-8"))

    parent_prompt: str = parent.get("prompt", "")
    parent_category: str = parent.get("category", "Ground")
    parent_seed: int = int(parent.get("seed_base", 42))

    detail_id = args.id or f"{args.of}_detail"
    detail_seed = args.seed_base if args.seed_base is not None else parent_seed + 1000

    suffix = DETAIL_SUFFIXES.get(parent_category, DETAIL_SUFFIXES["default"])
    # Drop any "top-down photo" / "photoreal" tail from the parent prompt
    # so we don't double up; we'll re-add a tighter version.
    base = parent_prompt
    for tail in [
        "top-down photo, even lighting, photoreal",
        "top-down view, even lighting, photoreal",
        "photoreal seamless tileable",
    ]:
        if base.endswith(tail):
            base = base[: -len(tail)].rstrip(", ")
    detail_prompt = f"{base}, {suffix}, top-down photo"

    print(f"[detail] parent: {args.of} ({parent_category})")
    print(f"  parent prompt: {parent_prompt!r}")
    print(f"[detail] generating: {detail_id}")
    print(f"  prompt: {detail_prompt!r}")
    print(f"  seed-base: {detail_seed}")

    # Run AAA pipeline with --no-gate (the palette match comes after)
    cmd = [
        sys.executable, str(PIPELINE_DIR / "aaa_texture.py"),
        "--prompt", detail_prompt,
        "--id", detail_id,
        "--category", parent_category,
        "--quality", args.quality,
        "--seed-base", str(detail_seed),
        "--no-gate",
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"[detail] AAA pipeline failed for {detail_id}")
        sys.exit(result.returncode)

    if args.no_palette_match:
        print("[detail] skipped palette match per --no-palette-match")
        return

    # Palette match against parent. Reuses palette_lock.hist_match_lab.
    sys.path.insert(0, str(PIPELINE_DIR))
    from palette_lock import hist_match_lab  # noqa: E402

    parent_albedo_path = parent_dir / f"{args.of}_albedo.png"
    detail_albedo_path = LIBRARY / detail_id / f"{detail_id}_albedo.png"
    if not (parent_albedo_path.exists() and detail_albedo_path.exists()):
        print("[detail] albedo paths missing; skipping palette match")
        return

    parent_rgb = np.asarray(Image.open(parent_albedo_path).convert("RGB"))
    detail_rgb = np.asarray(Image.open(detail_albedo_path).convert("RGB"))
    if parent_rgb.shape != detail_rgb.shape:
        parent_rgb = np.asarray(
            Image.fromarray(parent_rgb).resize(
                (detail_rgb.shape[1], detail_rgb.shape[0]), Image.LANCZOS
            )
        )

    # Backup before rewriting
    backup = detail_albedo_path.with_suffix(".pre_palette.png")
    if not backup.exists():
        shutil.copy2(detail_albedo_path, backup)

    matched = hist_match_lab(detail_rgb, parent_rgb, strength=args.strength)
    Image.fromarray(matched).save(detail_albedo_path)
    print(f"[detail] palette-matched to parent (strength={args.strength}); "
          f"backup at {backup.name}")

    # Re-QA the matched detail.
    subprocess.run([
        sys.executable, str(PIPELINE_DIR / "texture_qa.py"),
        "--material", str(LIBRARY / detail_id),
        "--category", parent_category,
    ])

    # Mark the detail manifest as a detail-variant (downstream tooling
    # may want to know).
    detail_manifest_path = LIBRARY / detail_id / "aaa_pipeline.json"
    if detail_manifest_path.exists():
        d = json.loads(detail_manifest_path.read_text(encoding="utf-8"))
        d["role"] = "detail_variant"
        d["parent"] = args.of
        d["palette_match_strength"] = args.strength
        detail_manifest_path.write_text(json.dumps(d, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
