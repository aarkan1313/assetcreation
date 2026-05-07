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
    """Find <id>_<map_name>.png in mat_dir, excluding pre_* backups."""
    candidates = [
        p for p in mat_dir.glob(f"*_{map_name}.png")
        if "pre_" not in p.name and "_baked" not in p.name
    ]
    return candidates[0] if candidates else None


def main():
    raise SystemExit("not implemented yet -- see Task 3")


if __name__ == "__main__":
    main()
