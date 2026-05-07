"""Import existing artifacts from D:/spell lab into the new vfx/catalog shape.

Per `research/I_vfx_lab_local_audit_and_migration_plan.md`. This is the
"don't redo the engine survey - the artifacts are already there" tool.

For each artifact in the old lab's index.json that we have a mapping for,
we copy the relevant files into the new layout and synthesize an effect.json
stub with `backend: external` (so `bake.py` won't try to re-simulate it).

The exporter's --all path will still emit Godot scenes for these, because
it only requires effect.json + manifest.json + flipbook.png (or frames/).

CLI:
  python import_spell_lab.py
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

OLD_ROOT = Path(r"D:\spell lab\spell-sandbox\artifacts")
NEW_ROOT = Path(r"D:\assets\vfx\migrated_from_spell_lab")


# Mapping: old_path -> (kind, phenomenon, new_id). Kept conservative for now;
# a curator can add more by extending this table.
DEFAULT_MAPPING = {
    "spell_prototype/fireball_projectile":
        ("spell", "fire", "fireball_projectile_legacy"),
    "spell_prototype/arcane_shock_ring":
        ("spell", "swirl", "arcane_shock_ring_legacy"),
    "spell_prototype/blood_orbit":
        ("spell", "swirl", "blood_orbit_legacy"),
    "spell_prototype/gravity_lens_field":
        ("environment", "field", "gravity_lens_field_legacy"),
    "spell_prototype/rune_shatter":
        ("destruction", "shatter", "rune_shatter_legacy"),
    "spell_prototype/smoke_rift":
        ("environment", "smoke", "smoke_rift_legacy"),
    "liquidfun/particle_splash":
        ("environment", "liquid", "liquidfun_particle_splash"),
    "fracture2d/shard_baker":
        ("destruction", "shatter", "fracture2d_shard_baker"),
    "phiflow/smoke_field":
        ("environment", "smoke", "phiflow_smoke_field"),
    "warp/blackhole_particles":
        ("spell", "swirl", "warp_blackhole_particles"),
    "taichi/sand_spell":
        ("environment", "particle", "taichi_sand_spell"),
}


def import_one(rel: str, mapping: dict, old_root: Path, new_root: Path) -> bool:
    src = old_root / rel
    if not src.exists():
        return False
    kind, phenomenon, new_id = mapping[rel]
    dst = new_root / kind / new_id
    dst.mkdir(parents=True, exist_ok=True)
    # Copy whatever's there - manifest.json, preview.svg, flipbook.png if any,
    # particles.json, fragments.json, bodies.json, field.json, ...
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, dst / f.name)
        # ignore subdirs for now; old lab doesn't typically have them inside artifact dirs
    # Build effect.json stub
    effect = {
        "id": new_id,
        "kind": kind,
        "phenomenon": phenomenon,
        "backend": "external",
        "duration_s": 1.0,
        "fps": 24,
        "bounds_px": [256, 256],
        "visual": {"palette": ["#ffffff"], "blend": "alpha", "background": "#00000000"},
        "backend_params": {"source": rel},
        "gameplay": {"shape": "point", "damage_tags": [], "collision": "none"},
        "notes": f"Imported from D:\\spell lab\\spell-sandbox\\artifacts\\{rel}",
    }
    (dst / "effect.json").write_text(json.dumps(effect, indent=2), encoding="utf-8")
    # Build a minimal manifest.json so the Godot exporter doesn't choke if
    # the original artifact doesn't have one in our new schema. We only do
    # this if we found frames or flipbook on disk; otherwise mark as
    # `reference_only`.
    has_flipbook = (dst / "flipbook.png").exists()
    has_frames = any(dst.glob("frame_*.png")) or (dst / "frames").is_dir()
    if has_flipbook or has_frames:
        # If there's no frames dir but a flipbook exists, just point at the dir
        manifest = {
            "effect_id": new_id,
            "backend": "external",
            "n_frames": 1,
            "fps": 24,
            "bounds_px": [256, 256],
            "flipbook": str(dst / "flipbook.png") if has_flipbook else "",
            "frames_dir": str(dst / "frames") if (dst / "frames").is_dir() else str(dst),
            "extras": {},
            "metrics": {},
            "timestamp": "",
        }
        # Don't overwrite a real manifest.json if it already came across
        if not (dst / "manifest.json").exists():
            (dst / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[import] {rel} -> {dst}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-root", type=Path, default=OLD_ROOT)
    ap.add_argument("--out", type=Path, default=NEW_ROOT)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    n = 0
    for rel in DEFAULT_MAPPING:
        if import_one(rel, DEFAULT_MAPPING, args.old_root, args.out):
            n += 1
    print(f"[import_spell_lab] imported {n}/{len(DEFAULT_MAPPING)} artifacts")


if __name__ == "__main__":
    main()
