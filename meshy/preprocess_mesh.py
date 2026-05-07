"""Headless Blender mesh preprocessing for the AI-rigging pipeline.

Run via the project wrapper:
    python D:\\assets\\meshy\\preprocess.py <input.glb> [options]

Or directly via Blender:
    blender.exe -b -P preprocess_mesh.py -- <input.glb> <output.glb> [--target-tris 30000] [--quad-remesh] ...

Operations performed in order:
  1. Import GLB
  2. Join all mesh objects into one
  3. Apply transforms (scale, rotation, location -> identity)
  4. Recenter to origin, optionally normalize to unit cube
  5. Remove duplicate vertices (merge by distance)
  6. Recompute outward-facing normals + smooth shading
  7. Decimate to target triangle count (collapse mode)
  8. Optional: Voxel quad remesh (rebuild topology)
  9. Optional: smart UV unwrap (only if quad-remeshing destroys UVs)
 10. Export GLB
"""
import sys
import json
from pathlib import Path

import bpy
import bmesh
import mathutils


# --- Argument parsing (after Blender's `--` separator) -----------------------
def parse_args():
    if "--" not in sys.argv:
        raise SystemExit("missing `--` separator before script args")
    args = sys.argv[sys.argv.index("--") + 1:]
    opts = {
        "input": None,
        "output": None,
        "target_tris": 30000,
        "quad_remesh": False,
        "remesh_voxel_size": 0.01,
        "normalize_scale": False,
        "merge_distance": 0.0001,
        "unwrap_uvs": False,
        "dry_run": False,
        "report_topology": True,
        "remove_loose": True,
        "remove_small_components": True,
        "min_component_ratio": 0.01,
        "clean_internals": False,
        "internal_voxel_size": 0.005,
    }
    positional = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--target-tris":
            opts["target_tris"] = int(args[i + 1]); i += 2
        elif a == "--quad-remesh":
            opts["quad_remesh"] = True; i += 1
        elif a == "--remesh-voxel-size":
            opts["remesh_voxel_size"] = float(args[i + 1]); i += 2
        elif a == "--normalize-scale":
            opts["normalize_scale"] = True; i += 1
        elif a == "--merge-distance":
            opts["merge_distance"] = float(args[i + 1]); i += 2
        elif a == "--unwrap-uvs":
            opts["unwrap_uvs"] = True; i += 1
        elif a == "--no-topology-report":
            opts["report_topology"] = False; i += 1
        elif a == "--no-remove-loose":
            opts["remove_loose"] = False; i += 1
        elif a == "--keep-small-components":
            opts["remove_small_components"] = False; i += 1
        elif a == "--min-component-ratio":
            opts["min_component_ratio"] = float(args[i + 1]); i += 2
        elif a == "--clean-internals":
            opts["clean_internals"] = True; i += 1
        elif a == "--internal-voxel-size":
            opts["internal_voxel_size"] = float(args[i + 1]); i += 2
        elif a == "--dry-run":
            opts["dry_run"] = True; i += 1
        elif a.startswith("--"):
            raise SystemExit(f"unknown option: {a}")
        else:
            positional.append(a); i += 1
    if len(positional) < 2:
        raise SystemExit("usage: ... -- <input.glb> <output.glb> [options]")
    opts["input"] = Path(positional[0])
    opts["output"] = Path(positional[1])
    return opts


# --- Helpers -----------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path: Path) -> list:
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def join_meshes(meshes: list):
    """Join all mesh objects into a single object. Returns the joined object."""
    if not meshes:
        raise SystemExit("no mesh objects imported")
    if len(meshes) == 1:
        return meshes[0]
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    return bpy.context.active_object


def stats(obj) -> dict:
    me = obj.data
    return {
        "verts": len(me.vertices),
        "tris": sum((len(p.vertices) - 2) for p in me.polygons),  # n-gons -> tris fan
        "polys": len(me.polygons),
        "has_uvs": len(me.uv_layers) > 0,
        "bbox_dims": list((mathutils.Vector(obj.bound_box[6]) - mathutils.Vector(obj.bound_box[0]))[:]),
    }


def apply_transforms(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def recenter_to_origin(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    obj.location = (0, 0, 0)


def normalize_to_unit(obj):
    """Scale uniformly so that the largest bounding-box axis = 1."""
    bbox = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    mins = mathutils.Vector((min(v[i] for v in bbox) for i in range(3)))
    maxs = mathutils.Vector((max(v[i] for v in bbox) for i in range(3)))
    size = maxs - mins
    longest = max(size)
    if longest <= 0:
        return
    scale = 1.0 / longest
    obj.scale = (scale, scale, scale)
    apply_transforms(obj)


def merge_close_verts(obj, distance: float):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=distance)
    bpy.ops.object.mode_set(mode="OBJECT")


def recompute_normals(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()


def report_topology(obj) -> dict:
    """Inspect the mesh for common AI-generated topology issues."""
    bpy.context.view_layer.objects.active = obj
    me = obj.data

    # Connected components via bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    visited = [False] * len(bm.verts)
    components = []
    bm.verts.ensure_lookup_table()
    for start_idx in range(len(bm.verts)):
        if visited[start_idx]:
            continue
        # BFS over connected verts
        stack = [start_idx]
        comp_size = 0
        while stack:
            i = stack.pop()
            if visited[i]:
                continue
            visited[i] = True
            comp_size += 1
            for e in bm.verts[i].link_edges:
                other = e.other_vert(bm.verts[i])
                if not visited[other.index]:
                    stack.append(other.index)
        components.append(comp_size)
    components.sort(reverse=True)

    # Non-manifold edges (3+ faces sharing one edge — internal geometry signal)
    non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)
    # Loose verts (no faces) — easy garbage
    loose_verts = sum(1 for v in bm.verts if not v.link_faces)
    # Loose edges (have verts but no face) — wireframes
    loose_edges = sum(1 for e in bm.edges if not e.link_faces)
    # Interior faces (faces fully surrounded — proxy for "wall inside body")
    interior_faces = sum(1 for f in bm.faces if all(e.is_manifold and len(e.link_faces) > 1 for e in f.edges) and not any(v.is_boundary for v in f.verts))

    bm.free()

    return {
        "components": components,
        "n_components": len(components),
        "largest_component": components[0] if components else 0,
        "non_manifold_edges": non_manifold_edges,
        "loose_verts": loose_verts,
        "loose_edges": loose_edges,
    }


def remove_loose_geometry(obj):
    """Delete vertices/edges with no faces. Cheap and safe."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.mesh.select_loose()
    bpy.ops.mesh.delete(type="VERT")
    bpy.ops.object.mode_set(mode="OBJECT")


def remove_small_components(obj, min_relative_size: float = 0.01):
    """Delete small disconnected mesh islands smaller than min_relative_size of largest.
    Useful for removing floating debris that's not part of the main character.
    """
    bpy.context.view_layer.objects.active = obj
    me = obj.data

    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()

    # Find components
    visited = [False] * len(bm.verts)
    components = []
    for start in range(len(bm.verts)):
        if visited[start]:
            continue
        stack = [start]
        members = []
        while stack:
            i = stack.pop()
            if visited[i]:
                continue
            visited[i] = True
            members.append(i)
            for e in bm.verts[i].link_edges:
                other = e.other_vert(bm.verts[i])
                if not visited[other.index]:
                    stack.append(other.index)
        components.append(members)

    if len(components) <= 1:
        bm.free()
        return 0

    largest = max(len(c) for c in components)
    threshold = largest * min_relative_size
    to_delete = []
    for comp in components:
        if len(comp) < threshold:
            to_delete.extend(comp)

    if not to_delete:
        bm.free()
        return 0

    delete_verts = [bm.verts[i] for i in to_delete]
    bmesh.ops.delete(bm, geom=delete_verts, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(to_delete)


def fill_internal_cavities_via_voxel(obj, voxel_size: float = 0.005):
    """Use voxel remesh as a topology-fixing pass: dissolves internal webs by
    rebuilding the mesh from a voxel grid + marching cubes. Preserves outer
    shell shape; loses UVs (caller should re-unwrap if textured).
    """
    obj.data.remesh_voxel_size = voxel_size
    obj.data.remesh_voxel_adaptivity = 0
    obj.data.use_remesh_smooth_normals = True
    obj.data.use_remesh_fix_poles = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.voxel_remesh()


def decimate_to_tris(obj, target: int):
    current_tris = sum((len(p.vertices) - 2) for p in obj.data.polygons)
    if current_tris <= target:
        print(f"  already at {current_tris} tris, target {target}, skipping decimate")
        return
    ratio = target / current_tris
    print(f"  current {current_tris} tris, target {target}, ratio {ratio:.4f}")
    mod = obj.modifiers.new(name="Decimate", type="DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)


def voxel_quad_remesh(obj, voxel_size: float):
    """Apply Blender's built-in voxel remesh (produces clean topology, but loses UVs)."""
    obj.data.remesh_voxel_size = voxel_size
    obj.data.remesh_voxel_adaptivity = 0
    obj.data.use_remesh_smooth_normals = True
    obj.data.use_remesh_fix_poles = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.voxel_remesh()


def smart_uv_unwrap(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def export_glb(obj, path: Path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_normals=True,
        export_tangents=False,
        export_materials="EXPORT",
        export_image_format="AUTO",
    )


# --- Main --------------------------------------------------------------------
def main():
    opts = parse_args()
    print(f"input:  {opts['input']}")
    print(f"output: {opts['output']}")
    print(f"options: {json.dumps({k: v for k, v in opts.items() if k not in ('input','output')}, indent=2)}")

    if not opts["input"].exists():
        raise SystemExit(f"input not found: {opts['input']}")

    reset_scene()
    meshes = import_glb(opts["input"])
    obj = join_meshes(meshes)

    stats_before = stats(obj)
    print(f"before: {stats_before}")

    if opts["dry_run"]:
        print("dry-run: stopping after stats")
        return

    apply_transforms(obj)
    recenter_to_origin(obj)
    if opts["normalize_scale"]:
        normalize_to_unit(obj)
    merge_close_verts(obj, opts["merge_distance"])

    if opts["report_topology"]:
        topo = report_topology(obj)
        print(f"topology: components={topo['n_components']} (largest={topo['largest_component']}), "
              f"non_manifold_edges={topo['non_manifold_edges']}, "
              f"loose_verts={topo['loose_verts']}, loose_edges={topo['loose_edges']}")
        if topo["n_components"] > 5:
            print(f"  ⚠ {topo['n_components']} disconnected components — may include floating debris or improperly-connected limbs")
        if topo["non_manifold_edges"] > 100:
            print(f"  ⚠ {topo['non_manifold_edges']} non-manifold edges — likely internal/hidden geometry")

    if opts["remove_loose"]:
        remove_loose_geometry(obj)

    if opts["remove_small_components"]:
        deleted = remove_small_components(obj, opts["min_component_ratio"])
        if deleted:
            print(f"  removed {deleted} verts in floating debris components")

    if opts["clean_internals"]:
        # Voxel remesh dissolves hidden internal geometry. Loses UVs — caller should --unwrap-uvs.
        had_uvs = stats(obj)["has_uvs"]
        print(f"  cleaning internals via voxel remesh (size={opts['internal_voxel_size']})...")
        fill_internal_cavities_via_voxel(obj, opts["internal_voxel_size"])
        if had_uvs and not stats(obj)["has_uvs"]:
            print("  internals cleaning removed UVs (expected — pass --unwrap-uvs to regenerate)")

    recompute_normals(obj)
    decimate_to_tris(obj, opts["target_tris"])

    if opts["report_topology"]:
        topo_after = report_topology(obj)
        print(f"topology after: components={topo_after['n_components']}, "
              f"non_manifold_edges={topo_after['non_manifold_edges']}")

    if opts["quad_remesh"]:
        # Voxel remesh destroys UVs; track that
        had_uvs = stats(obj)["has_uvs"]
        voxel_quad_remesh(obj, opts["remesh_voxel_size"])
        if had_uvs and not stats(obj)["has_uvs"]:
            print("  voxel remesh removed UVs (expected)")
        if opts["unwrap_uvs"] and not stats(obj)["has_uvs"]:
            smart_uv_unwrap(obj)

    if opts["unwrap_uvs"] and not stats(obj)["has_uvs"]:
        smart_uv_unwrap(obj)

    stats_after = stats(obj)
    print(f"after:  {stats_after}")
    print(f"reduction: tris {stats_before['tris']} -> {stats_after['tris']}, "
          f"verts {stats_before['verts']} -> {stats_after['verts']}")

    export_glb(obj, opts["output"])
    print(f"exported: {opts['output']}")


if __name__ == "__main__":
    main()
