"""LOD-chain authoring inside Blender 5.x. Per J2 SOTA:

  - DECIMATE modifier in COLLAPSE mode (QEM error metric, same algorithm as
    Unreal Auto-LOD), use_collapse_triangulate=True so GLB exports are tri-only.
  - bpy.ops.object.modifier_apply (NOT bpy.ops.mesh.decimate, which is the
    edit-mode operator and breaks in --background).
  - Tier ratios applied off LOD0 triangle count (not chained), so error doesn't
    accumulate.
  - Triangle floors: skip a tier if it would fall below 32 tris.

Usage (called by lod_chain.py):
  blender --background --factory-startup --python proc_lod.py -- \
    --in <prop_dir>/model_lod0.glb \
    --out-dir <prop_dir> \
    --ratios 1.0,0.5,0.2,0.08
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True, help="path to model_lod0.glb")
    ap.add_argument("--out-dir", required=True, help="prop directory")
    ap.add_argument("--ratios", default="1.0,0.5,0.2,0.08",
                    help="comma list, applied off LOD0 tris (LOD0 stays as-is)")
    ap.add_argument("--tri-floor", type=int, default=32)
    return ap.parse_args(argv)


def import_glb_as_single(path: Path) -> bpy.types.Object:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes:
        raise RuntimeError(f"no mesh imported from {path}")
    if len(meshes) > 1:
        bpy.ops.object.select_all(action='DESELECT')
        for m in meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def export_glb(obj: bpy.types.Object, out_path: Path) -> None:
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=str(out_path),
        use_selection=True,
        export_format='GLB',
        export_image_format='AUTO',
        export_yup=True,
    )


def make_lod_clone(base: bpy.types.Object, ratio: float, idx: int) -> tuple[bpy.types.Object, int]:
    new_obj = base.copy()
    new_obj.data = base.data.copy()
    new_obj.name = f"{base.name}_LOD{idx}"
    bpy.context.collection.objects.link(new_obj)
    if ratio < 1.0:
        mod = new_obj.modifiers.new(f"Dec{idx}", "DECIMATE")
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = max(0.005, ratio)
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = new_obj
        bpy.ops.object.select_all(action='DESELECT')
        new_obj.select_set(True)
        bpy.ops.object.modifier_apply(modifier=mod.name)
    tris = len(new_obj.data.polygons)
    return new_obj, tris


def main() -> int:
    args = parse_args()
    src = Path(args.src)
    out_dir = Path(args.out_dir)
    if not src.exists():
        print(f"[proc_lod] missing {src}", file=sys.stderr)
        return 1
    ratios = [float(x) for x in args.ratios.split(",") if x.strip()]
    if not ratios:
        print("[proc_lod] empty --ratios", file=sys.stderr)
        return 1

    base = import_glb_as_single(src)
    base.name = "Base"
    base_tris = len(base.data.polygons)

    written = []
    # LOD0 is the source — already on disk. Re-emit only LOD1+.
    for i, r in enumerate(ratios):
        if i == 0:
            written.append({"index": 0, "file": "model_lod0.glb",
                            "ratio": 1.0, "triangles": base_tris})
            continue
        target = max(args.tri_floor, int(round(base_tris * r)))
        if target < args.tri_floor or base_tris * r < args.tri_floor:
            print(f"[proc_lod] LOD{i} (r={r}) would fall below tri-floor {args.tri_floor}; skipping")
            continue
        new_obj, tris = make_lod_clone(base, r, i)
        out_path = out_dir / f"model_lod{i}.glb"
        export_glb(new_obj, out_path)
        written.append({"index": i, "file": f"model_lod{i}.glb",
                        "ratio": r, "triangles": tris})
        # Drop the duplicate to avoid carrying state.
        bpy.data.objects.remove(new_obj, do_unlink=True)

    # Write a tiny report the orchestrator picks up via stdout.
    print("[proc_lod] result_json=" + str(written))
    print(f"[proc_lod] base_tris={base_tris} ladder_count={len(written)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
