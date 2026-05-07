"""User-facing wrapper for the Blender preprocess script.

Usage:
    python preprocess.py <input.glb> [<output.glb>] [--target-tris 30000]
                          [--quad-remesh] [--remesh-voxel-size 0.01]
                          [--normalize-scale] [--merge-distance 0.0001]
                          [--unwrap-uvs] [--dry-run]

If <output.glb> is omitted, it's written to:
    D:\\assets\\meshy\\preprocessed\\<input-stem>_p.glb
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text())
PREPROCESS_DIR = ROOT / "preprocessed"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path, nargs="?", default=None)
    ap.add_argument("--target-tris", type=int, default=30000)
    ap.add_argument("--quad-remesh", action="store_true",
                    help="Apply Blender voxel remesh after decimation (rebuilds topology, loses UVs)")
    ap.add_argument("--remesh-voxel-size", type=float, default=0.01)
    ap.add_argument("--normalize-scale", action="store_true",
                    help="Scale model so longest bbox axis = 1.0")
    ap.add_argument("--merge-distance", type=float, default=0.0001)
    ap.add_argument("--unwrap-uvs", action="store_true",
                    help="Run smart UV unwrap (use after quad-remesh which destroys UVs)")
    ap.add_argument("--no-topology-report", action="store_true",
                    help="Skip the connected-components + non-manifold report")
    ap.add_argument("--keep-small-components", action="store_true",
                    help="Don't remove floating debris (small disconnected mesh islands)")
    ap.add_argument("--min-component-ratio", type=float, default=0.01,
                    help="Components smaller than this fraction of largest get deleted (default 0.01)")
    ap.add_argument("--clean-internals", action="store_true",
                    help="Voxel-remesh to dissolve hidden internal geometry (limb-fused-to-arm webs). "
                         "Loses UVs and textures; pair with --unwrap-uvs to regenerate them.")
    ap.add_argument("--internal-voxel-size", type=float, default=0.005,
                    help="Voxel size for --clean-internals (smaller = more detail preserved, default 0.005)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Just import + report stats, don't process or export")
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")

    if args.output is None:
        PREPROCESS_DIR.mkdir(parents=True, exist_ok=True)
        # Meshy outputs are typically <output_dir>/<asset_name>/model.glb — the parent
        # dir name is the asset name, not the file stem ("model"). Detect that case
        # so we don't collide every preprocess into "model_p.glb".
        if args.input.stem == "model" and args.input.parent.name not in ("", "/", "\\"):
            stem = args.input.parent.name
        else:
            stem = args.input.stem
        args.output = PREPROCESS_DIR / f"{stem}_p.glb"

    blender_args = [
        CONFIG["blender_exe"],
        "-b",
        "-P",
        str(ROOT / "preprocess_mesh.py"),
        "--",
        str(args.input),
        str(args.output),
        "--target-tris", str(args.target_tris),
        "--merge-distance", str(args.merge_distance),
    ]
    if args.quad_remesh:
        blender_args += ["--quad-remesh", "--remesh-voxel-size", str(args.remesh_voxel_size)]
    if args.normalize_scale:
        blender_args.append("--normalize-scale")
    if args.unwrap_uvs:
        blender_args.append("--unwrap-uvs")
    if args.no_topology_report:
        blender_args.append("--no-topology-report")
    if args.keep_small_components:
        blender_args.append("--keep-small-components")
    if args.min_component_ratio != 0.01:
        blender_args += ["--min-component-ratio", str(args.min_component_ratio)]
    if args.clean_internals:
        blender_args += ["--clean-internals", "--internal-voxel-size", str(args.internal_voxel_size)]
    if args.dry_run:
        blender_args.append("--dry-run")

    print(f"$ {' '.join(blender_args)}")
    r = subprocess.run(blender_args)
    if r.returncode != 0:
        sys.exit(r.returncode)

    if not args.dry_run:
        print(f"\noutput: {args.output}")


if __name__ == "__main__":
    main()
