"""High-resolution PBR map re-derivation from SR'd albedo + height.

After super-resolving PBR maps with sr_upscale.py, the normal, AO, and
roughness maps are "upscaled 512-derivations" -- the same gradients stretched
to a higher resolution. This tool re-derives those maps from the SR'd
albedo and height at the working resolution, producing physically-correct
high-res versions.

Map bake rules (see Phase B design doc for ownership table):
  albedo   -- pass through (SR'd, no re-bake)
  height   -- pass through (SR'd, no re-bake)
  metallic -- pass through (SR'd, low-frequency, fine as-is)
  normal   -- RE-BAKED from 4K height (sub-texel accurate Sobel gradient)
  ao       -- RE-BAKED from 4K height (smoother hemisphere integral)
  roughness -- BLEND of SR'd + re-derived from 4K albedo+height

Baked maps are written alongside originals as <id>_<map>_baked.png for
A/B inspection. Use --apply to promote baked -> canonical (with backup).

Usage:
  # Bake a dir of SR'd maps (writes *_baked.png alongside originals):
  python bake_pbr.py --material-dir D:/tmp/b2_rock_dark_sr

  # Bake with backend-aware roughness trust (default: sm):
  python bake_pbr.py --material-dir D:/tmp/b2_rock_dark_sr --backend chord

  # After visual inspection, promote baked -> canonical:
  python bake_pbr.py --material-dir D:/tmp/b2_rock_dark_sr --apply

Phase B.2 deliverable. See:
  docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md
  pipelines/textures/EXTERNAL_SR_TECHNIQUES.md
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from derive_pbr_v2 import derive_normal, derive_ao, derive_roughness, luminance  # noqa: F401

# Roughness blend alpha per backend.
# alpha = weight given to the SR'd roughness (vs freshly-derived roughness).
# Higher = trust the original generation's roughness more.
ROUGHNESS_BLEND_ALPHA = {
    "sm":             0.65,  # SM roughness is physically modeled and trustworthy
    "chord_sm_rough": 0.65,  # SM roughness component; same trust as pure sm
    "chord":          0.35,  # CHORD roughness is near-flat (A.8 finding); derive more
    "derive":         0.40,  # fully heuristic; blend evenly
}
ROUGHNESS_BLEND_ALPHA_DEFAULT = 0.50  # fallback for unknown backends


def find_map(mat_dir: Path, map_name: str) -> Path | None:
    """Find <id>_<map_name>[_suffix].png in mat_dir, excluding pre_* backups.

    Matches both exact-suffix naming (e.g. wgv3_rock_dark_albedo.png) and
    resolution-tagged naming (e.g. wgv3_rock_dark_albedo_2k.png).
    Exact match (no trailing suffix) is preferred over tagged variants.
    """
    candidates = [
        p for p in mat_dir.glob(f"*_{map_name}*.png")
        if "pre_" not in p.name and "_baked" not in p.name
        and (p.stem.endswith(f"_{map_name}") or f"_{map_name}_" in p.stem)
    ]
    # Prefer exact match (stem ends with _{map_name})
    exact = [p for p in candidates if p.stem.endswith(f"_{map_name}")]
    return (exact or candidates)[0] if (exact or candidates) else None


def bake_material_dir(mat_dir: Path, category: str = "Rock",
                       backend: str = "sm",
                       normal_strength: float | None = None,
                       ao_blur_radius: int | None = None,
                       roughness_blend: float | None = None) -> dict:
    """Re-derive normal, AO, roughness from SR'd albedo+height in mat_dir.

    Writes *_baked.png files alongside originals. Returns a metrics dict.
    Does NOT overwrite originals -- call apply_baked() or use --apply to promote.
    """
    albedo_path = find_map(mat_dir, "albedo")
    height_path = find_map(mat_dir, "height")
    rough_path  = find_map(mat_dir, "roughness")

    if albedo_path is None:
        raise FileNotFoundError(f"no albedo found in {mat_dir}")
    if height_path is None:
        raise FileNotFoundError(f"no height found in {mat_dir}")
    if rough_path is None:
        raise FileNotFoundError(f"no roughness found in {mat_dir}")

    albedo_im = Image.open(albedo_path).convert("RGB")
    height_im = Image.open(height_path).convert("L")
    rough_im  = Image.open(rough_path).convert("L")

    h_px = height_im.size[1]
    scale = h_px / 512.0
    eff_normal_strength = normal_strength if normal_strength is not None else max(4.0, 4.0 * scale)
    eff_ao_blur         = ao_blur_radius  if ao_blur_radius  is not None else max(8, int(8 * scale))
    alpha               = roughness_blend if roughness_blend is not None else \
                          ROUGHNESS_BLEND_ALPHA.get(backend, ROUGHNESS_BLEND_ALPHA_DEFAULT)

    print(f"  resolution: {h_px}px  scale={scale:.1f}x vs 512 baseline")
    print(f"  normal_strength={eff_normal_strength:.1f}  ao_blur={eff_ao_blur}  roughness_alpha={alpha:.2f}  backend={backend}")

    albedo_arr = np.asarray(albedo_im, dtype=np.uint8)
    height_arr = np.asarray(height_im, dtype=np.float32) / 255.0
    rough_arr  = np.asarray(rough_im,  dtype=np.float32) / 255.0

    # Normal: re-derive from high-res height
    normal_baked = derive_normal(height_arr, strength=eff_normal_strength)
    prefix = height_path.stem.replace("_height", "")
    normal_out = mat_dir / f"{prefix}_normal_baked.png"
    Image.fromarray(normal_baked, mode="RGB").save(normal_out)
    print(f"  baked normal -> {normal_out.name}")

    # AO: re-bake from high-res height
    ao_baked = derive_ao(height_arr, blur_radius=eff_ao_blur)
    ao_out = mat_dir / f"{prefix}_ao_baked.png"
    Image.fromarray(ao_baked, mode="L").save(ao_out)
    print(f"  baked AO     -> {ao_out.name}")

    # Roughness: blend SR'd + freshly-derived
    rough_derived = derive_roughness(albedo_arr, category) / 255.0
    rough_blended = np.clip(alpha * rough_arr + (1.0 - alpha) * rough_derived, 0.0, 1.0)
    rough_baked = (rough_blended * 255).astype(np.uint8)
    rough_out = mat_dir / f"{prefix}_roughness_baked.png"
    Image.fromarray(rough_baked, mode="L").save(rough_out)
    print(f"  baked rough  -> {rough_out.name}  (alpha={alpha:.2f} SR + {1-alpha:.2f} derived)")

    return {
        "mat_dir": str(mat_dir),
        "resolution": h_px,
        "scale_vs_512": round(scale, 2),
        "backend": backend,
        "category": category,
        "normal_strength": eff_normal_strength,
        "ao_blur_radius": eff_ao_blur,
        "roughness_blend_alpha": alpha,
        "outputs": {
            "normal_baked": str(normal_out),
            "ao_baked": str(ao_out),
            "roughness_baked": str(rough_out),
        },
    }


def apply_baked(mat_dir: Path) -> list[str]:
    """Promote *_baked.png files to canonical (overwrite originals with backup).

    For each <prefix>_<map>_baked.png found:
      1. Locate canonical <prefix>_<map>.png
      2. Back up canonical to <prefix>_<map>.pre_bake.png (skip if already exists)
      3. Copy baked -> canonical

    Returns list of promoted canonical filenames.
    """
    promoted = []
    for baked in sorted(mat_dir.glob("*_baked.png")):
        stem = baked.stem  # e.g. "wgv3_rock_dark_normal_baked"
        if not stem.endswith("_baked"):
            continue
        canonical_stem = stem[: -len("_baked")]
        canonical = mat_dir / f"{canonical_stem}.png"
        if not canonical.exists():
            print(f"  skip {baked.name} -- canonical {canonical.name} not found")
            continue
        backup = canonical.with_suffix("").with_suffix("") \
            if False else mat_dir / f"{canonical_stem}.pre_bake.png"
        if not backup.exists():
            shutil.copy2(canonical, backup)
        shutil.copy2(baked, canonical)
        promoted.append(canonical.name)
        print(f"  promoted {baked.name} -> {canonical.name}  (backup: {backup.name})")
    return promoted


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--material-dir", type=Path, required=True,
                    help="dir containing SR'd PBR maps (albedo, height, roughness required)")
    ap.add_argument("--category", default="Rock",
                    help="material category for roughness preset (Rock, Ground, Snow, etc.)")
    ap.add_argument("--backend", default="sm",
                    choices=list(ROUGHNESS_BLEND_ALPHA) + ["unknown"],
                    help="PBR backend used during generation (affects roughness blend trust)")
    ap.add_argument("--normal-strength", type=float, default=None,
                    help="normal derivation strength (default: auto-scaled from resolution)")
    ap.add_argument("--ao-blur-radius", type=int, default=None,
                    help="AO blur radius in px (default: auto-scaled from resolution)")
    ap.add_argument("--roughness-blend", type=float, default=None,
                    help="roughness blend alpha 0-1 (0=all derived, 1=all SR'd; default: per-backend)")
    ap.add_argument("--apply", action="store_true",
                    help="promote *_baked.png -> canonical (overwrites originals with backup)")
    args = ap.parse_args()

    if not args.material_dir.is_dir():
        raise SystemExit(f"--material-dir not found: {args.material_dir}")

    if args.apply:
        print(f"applying baked maps in {args.material_dir} ...")
        promoted = apply_baked(args.material_dir)
        print(f"\ndone. promoted {len(promoted)} map(s): {promoted}")
    else:
        print(f"baking {args.material_dir}  category={args.category}  backend={args.backend}")
        info = bake_material_dir(
            args.material_dir,
            category=args.category,
            backend=args.backend,
            normal_strength=args.normal_strength,
            ao_blur_radius=args.ao_blur_radius,
            roughness_blend=args.roughness_blend,
        )
        print(f"\ndone. baked maps written (use --apply to promote to canonical):")
        for k, v in info["outputs"].items():
            print(f"  {k}: {Path(v).name}")


if __name__ == "__main__":
    main()
