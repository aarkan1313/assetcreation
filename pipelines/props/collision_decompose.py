"""Convex collision decomposition via CoACD (SIGGRAPH 2022).

Per J2 §4: CoACD beats archived V-HACD by ~30% on hull count for the same
collision fidelity. It's a pure-binary wheel (`pip install coacd`) and runs
on the orchestrator's Python — no Blender involvement.

For each prop with `collision != "none"`:
  - Load model_lod0.glb via trimesh.
  - Run coacd.run_coacd to decompose into N convex hulls.
  - Write `collision.json` with per-hull vertex arrays.
  - Update `prop.json` to point at it (`collision_file`, `collision_hulls`).

The exporter consumes `collision.json` and emits one `ConvexPolygonShape3D`
per hull under a single `StaticBody3D` in the Godot .tscn.

Per-render_class policy (overridable via --threshold/--max-hulls):
  scatter_multimesh / decal / billboard_only -> skipped (collision="none")
  scene_prop  -> threshold=0.05  max_hulls=8   (CoACD default-ish)
  hero_prop   -> threshold=0.02  max_hulls=24  (tighter)
  "convex" simple-shape kinds (crate, lantern, fence) -> CoACD default

Small-mesh fallback: if LOD0 has < 200 polygons, the voxelization overhead
dominates; we fall back to a single convex hull computed via trimesh.

CLI:
  python collision_decompose.py barrel_a01
  python collision_decompose.py wooden_crate_a01 --threshold 0.03 --max-hulls 12
  python collision_decompose.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

LIBRARY = Path(r"D:\assets\world\props\library")

# Per render_class
DEFAULT_POLICY = {
    "scene_prop": dict(threshold=0.05, max_hulls=8,  resolution=2000),
    "hero_prop":  dict(threshold=0.02, max_hulls=24, resolution=2500),
}


def _try_imports():
    try:
        import coacd  # noqa: F401
        import trimesh  # noqa: F401
    except ImportError as e:
        print(f"[collision_decompose] missing dep: {e}", file=sys.stderr)
        print("    pip install coacd trimesh", file=sys.stderr)
        sys.exit(2)


def load_mesh_as_trimesh(glb_path: Path):
    import trimesh
    scene = trimesh.load(glb_path, force='mesh')
    if scene.is_empty or len(scene.faces) == 0:
        raise RuntimeError(f"empty mesh in {glb_path}")
    return scene


def single_hull(verts: np.ndarray) -> list[np.ndarray]:
    import trimesh
    mesh = trimesh.Trimesh(vertices=verts, process=False)
    hull = mesh.convex_hull
    return [np.asarray(hull.vertices, dtype=float)]


def decompose_one(prop_dir: Path, *, threshold: float, max_hulls: int,
                  resolution: int = 2000, small_floor: int = 200,
                  verbose: bool = False) -> dict:
    import coacd
    glb = prop_dir / "model_lod0.glb"
    if not glb.exists():
        return {"id": prop_dir.name, "ok": False, "err": "no model_lod0.glb"}

    mesh = load_mesh_as_trimesh(glb)
    n_faces = len(mesh.faces)

    if n_faces < small_floor:
        # below CoACD's voxelization sweet spot — just take the convex hull.
        hulls = single_hull(np.asarray(mesh.vertices))
        algorithm = "trimesh.convex_hull (small mesh)"
    else:
        cmesh = coacd.Mesh(mesh.vertices, mesh.faces)
        # CoACD prints to stderr; let it through but throttle.
        if not verbose:
            # CoACD's verbose output goes via its C++ bindings; can't fully silence
            # without redirecting fd. Acceptable noise for now.
            pass
        parts = coacd.run_coacd(
            cmesh,
            threshold=threshold,
            max_convex_hull=max_hulls,
            preprocess_mode='auto',
            resolution=resolution,
            mcts_nodes=20,
            mcts_iterations=150,
            mcts_max_depth=3,
            pca=False,
            merge=True,
        )
        import trimesh
        hulls = []
        for p in parts:
            v_raw = np.asarray(p[0], dtype=float)
            f_raw = np.asarray(p[1], dtype=np.int64) if len(p) > 1 else None
            if len(v_raw) < 4:
                continue
            # Tighten to true convex hull of the part — drops interior points
            # that bloat ConvexPolygonShape3D unnecessarily.
            try:
                if f_raw is not None and len(f_raw) > 0:
                    sub = trimesh.Trimesh(vertices=v_raw, faces=f_raw, process=False)
                else:
                    sub = trimesh.Trimesh(vertices=v_raw, process=False)
                hull_mesh = sub.convex_hull
                v_tight = np.asarray(hull_mesh.vertices, dtype=float)
                if len(v_tight) >= 4:
                    hulls.append(v_tight)
                else:
                    hulls.append(v_raw)
            except Exception:
                hulls.append(v_raw)
        if not hulls:
            hulls = single_hull(np.asarray(mesh.vertices))
            algorithm = "trimesh.convex_hull (CoACD returned empty)"
        else:
            algorithm = f"coacd v1 threshold={threshold} max_hulls={max_hulls} (hull-tightened)"

    # Write collision.json
    collision = {
        "schema": "prop_collision.v1",
        "algorithm": algorithm,
        "hull_count": len(hulls),
        "hulls": [
            {"index": i, "vertices": h.tolist()}
            for i, h in enumerate(hulls)
        ],
    }
    (prop_dir / "collision.json").write_text(json.dumps(collision))

    # Update prop.json
    pj = prop_dir / "prop.json"
    if pj.exists():
        data = json.loads(pj.read_text(encoding="utf-8"))
        data["collision_file"] = "collision.json"
        data["collision_hull_count"] = len(hulls)
        # promote `collision` to the canonical "convex" if it was a generic flag.
        if data.get("collision") in ("simple", "convex", True):
            data["collision"] = "convex"
        pj.write_text(json.dumps(data, indent=2))

    return {"id": prop_dir.name, "ok": True,
            "hull_count": len(hulls),
            "algorithm": algorithm,
            "input_faces": n_faces}


def main() -> int:
    _try_imports()
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--library", type=Path, default=LIBRARY)
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--max-hulls", type=int, default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not args.all and not args.ids:
        print("usage: collision_decompose.py <id>... | --all", file=sys.stderr)
        return 1

    candidates: list[Path] = []
    if args.all:
        for d in sorted(args.library.iterdir()):
            if not d.is_dir():
                continue
            pj = d / "prop.json"
            if not pj.exists():
                continue
            data = json.loads(pj.read_text(encoding="utf-8"))
            coll = data.get("collision")
            if coll in (None, "none", False):
                continue
            candidates.append(d)
    candidates.extend(args.library / pid for pid in args.ids)

    rows = []
    for prop_dir in candidates:
        pj = prop_dir / "prop.json"
        if not pj.exists():
            print(f"[collision_decompose] skip {prop_dir.name} (no prop.json)")
            continue
        data = json.loads(pj.read_text(encoding="utf-8"))
        rclass = data.get("render_class", "scene_prop")
        policy = DEFAULT_POLICY.get(rclass, DEFAULT_POLICY["scene_prop"])
        threshold = args.threshold if args.threshold is not None else policy["threshold"]
        max_hulls = args.max_hulls if args.max_hulls is not None else policy["max_hulls"]
        result = decompose_one(prop_dir,
                                threshold=threshold,
                                max_hulls=max_hulls,
                                resolution=policy["resolution"],
                                verbose=args.verbose)
        rows.append(result)
        if result["ok"]:
            print(f"[collision_decompose] {result['id']}  hulls={result['hull_count']}  "
                  f"input_faces={result['input_faces']}  via {result['algorithm']}")
        else:
            print(f"[collision_decompose] {result['id']}  FAIL  {result.get('err')}",
                  file=sys.stderr)

    n_ok = sum(1 for r in rows if r["ok"])
    print(f"[collision_decompose] {n_ok}/{len(rows)} ok")
    return 0 if n_ok == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
