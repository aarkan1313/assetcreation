"""Blender-headless procedural prop generator.

Spawns Blender 5.1 (path from D:\\assets\\meshy\\config.json) running
`blender_scripts/proc_props.py` to build one prop. Output is the canonical
prop_asset.v1 layout (matches art_lab/props/PROP_CONTRACT.md).

13 demo kinds (v2):
  rock_small         displaced ico-sphere with subdivision + decimation
  mushroom_lantern   stem cylinder + cap with curvy displacement
  wooden_crate       beveled cube with planks
  barrel             belly-bowed cylinder with iron bands
  lantern            base + glass + roof + loop (emissive glass)
  signpost           pole + plank
  treasure_chest     beveled body + half-cylinder lid + brass lock
  fence              two posts + 2 horizontal rails
  log                tapered cylinder + bark jitter
  stump              short trunk
  tombstone          rounded slab + chipped top
  bone_pile          5-7 stretched ellipsoids
  ruin_block         beveled stone block with edge chip noise

CLI:
  python proc_generate.py rock_small --id rock_small_01 --seed 7
  python proc_generate.py barrel --id barrel_a01 --params '{"color_variant":"oak"}'
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = Path(r"D:\assets")
CONFIG = json.loads((ASSETS / "meshy" / "config.json").read_text())
BLENDER = Path(CONFIG["blender_exe"])
LIBRARY = ASSETS / "world" / "props" / "library"
SCRIPT = ROOT / "blender_scripts" / "proc_props.py"


KINDS = [
    "rock_small",
    "mushroom_lantern",
    "wooden_crate",
    "barrel",
    "lantern",
    "signpost",
    "treasure_chest",
    "fence",
    "log",
    "stump",
    "tombstone",
    "bone_pile",
    "ruin_block",
]


# Per-kind defaults. render_class drives Godot LOD/MultiMesh treatment;
# collision drives whether collision_decompose runs.
KIND_DEFAULTS = {
    "rock_small":       dict(rclass="scatter_multimesh", collision="none",   tags=["rock", "ground", "slope_ok"],         mats=["stone"],                          rad=0.6),
    "mushroom_lantern": dict(rclass="scatter_multimesh", collision="none",   tags=["mushroom", "ground", "shaded"],       mats=["mushroom_cap", "mushroom_stem"],  rad=0.4),
    "wooden_crate":     dict(rclass="scene_prop",        collision="convex", tags=["wood", "ground", "interactable"],     mats=["wood"],                           rad=0.45),
    "barrel":           dict(rclass="scene_prop",        collision="convex", tags=["wood", "ground", "interactable"],     mats=["wood", "iron"],                   rad=0.40),
    "lantern":          dict(rclass="scene_prop",        collision="convex", tags=["light", "ground", "interactable"],    mats=["iron", "glass"],                  rad=0.20),
    "signpost":         dict(rclass="scene_prop",        collision="convex", tags=["wood", "ground", "marker"],           mats=["wood"],                           rad=0.25),
    "treasure_chest":   dict(rclass="scene_prop",        collision="convex", tags=["wood", "ground", "interactable"],     mats=["wood", "brass"],                  rad=0.55),
    "fence":            dict(rclass="scene_prop",        collision="convex", tags=["wood", "ground", "barrier"],          mats=["wood"],                           rad=0.90),
    "log":              dict(rclass="scene_prop",        collision="convex", tags=["wood", "ground", "obstacle"],         mats=["bark"],                           rad=0.85),
    "stump":            dict(rclass="scatter_multimesh", collision="none",   tags=["wood", "ground"],                     mats=["bark"],                           rad=0.35),
    "tombstone":        dict(rclass="scene_prop",        collision="convex", tags=["stone", "ground", "marker"],          mats=["stone"],                          rad=0.30),
    "bone_pile":        dict(rclass="scatter_multimesh", collision="none",   tags=["bone", "ground", "decoration"],       mats=["bone"],                           rad=0.35),
    "ruin_block":       dict(rclass="scatter_multimesh", collision="none",   tags=["stone", "ground", "ruin"],            mats=["stone"],                          rad=0.45),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=KINDS)
    ap.add_argument("--id", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--target-tris", type=int, default=1500)
    ap.add_argument("--params", default="{}",
                    help="JSON dict of recipe overrides (passed to Blender script)")
    ap.add_argument("--kit", default="first_party_proc",
                    help="Kit name written into prop.json")
    args = ap.parse_args()

    out_dir = LIBRARY / args.id
    out_dir.mkdir(parents=True, exist_ok=True)

    if not BLENDER.exists():
        print(f"[proc_generate] FAIL: Blender not found at {BLENDER}", file=sys.stderr)
        return 1
    if not SCRIPT.exists():
        print(f"[proc_generate] FAIL: blender script missing at {SCRIPT}", file=sys.stderr)
        return 1

    cmd = [
        str(BLENDER),
        "--background",
        "--factory-startup",
        "--python", str(SCRIPT),
        "--",
        "--kind", args.kind,
        "--id", args.id,
        "--out", str(out_dir),
        "--seed", str(args.seed),
        "--target-tris", str(args.target_tris),
        "--params", args.params,
    ]
    print(f"[proc_generate] running Blender for kind={args.kind} id={args.id}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[proc_generate] Blender returncode {r.returncode}", file=sys.stderr)
        print(r.stdout[-2000:], file=sys.stderr)
        print(r.stderr[-2000:], file=sys.stderr)
        return r.returncode

    glb = out_dir / "model_lod0.glb"
    thumb = out_dir / "thumbnail.png"
    if not glb.exists():
        print(f"[proc_generate] FAIL: GLB not produced ({glb})", file=sys.stderr)
        return 2

    d = KIND_DEFAULTS[args.kind]
    prop = {
        "schema": "prop_asset.v1",
        "id": args.id,
        "family": args.kind,
        "kit": args.kit,
        "source_method": "blender_procedural",
        "source_recipe": f"pipelines/props/blender_scripts/proc_props.py:{args.kind}",
        "license": "project_generated",
        "render_class": d["rclass"],
        "collision": d["collision"],
        "origin": "bottom_center",
        "scale_m": [1.0, 1.0, 1.0],
        "footprint_radius_m": d["rad"],
        "lods": [{"file": "model_lod0.glb", "max_distance_m": 25, "triangles": args.target_tris}],
        "thumbnail": "thumbnail.png" if thumb.exists() else None,
        "placement_tags": d["tags"],
        "material_slots": d["mats"],
        "qa": "qa.json",
        "provenance": {
            "seed": args.seed,
            "params": json.loads(args.params or "{}"),
            "target_tris_hint": args.target_tris,
        },
    }
    (out_dir / "prop.json").write_text(json.dumps(prop, indent=2))

    qa = {
        "id": args.id,
        "kind": args.kind,
        "seed": args.seed,
        "target_tris": args.target_tris,
        "params": json.loads(args.params or "{}"),
        "blender_version": "5.1",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ok": True,
    }
    (out_dir / "qa.json").write_text(json.dumps(qa, indent=2))

    print(f"[proc_generate] {args.id} -> {out_dir}")
    print(f"  GLB: {glb}  thumbnail: {thumb if thumb.exists() else '(missing)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
