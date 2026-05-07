"""Headless Blender: convert GLB to Mixamo-friendly FBX.

Run via:
    blender.exe -b -P glb_to_fbx_blender.py -- <input.glb> <output.fbx>
"""
import sys
import math
from pathlib import Path

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
in_glb = Path(argv[0])
out_fbx = Path(argv[1])

# Reset scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Import GLB
bpy.ops.import_scene.gltf(filepath=str(in_glb))

# Collect meshes; if multiple, join into one (Mixamo prefers a single mesh)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    raise SystemExit("no meshes found in GLB")

if len(meshes) > 1:
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()

obj = bpy.context.scene.objects[bpy.context.view_layer.objects.active.name]

# Apply all transforms (Mixamo expects identity transforms)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Recenter to origin
bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
obj.location = (0, 0, 0)
bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

# Mixamo expects character to be roughly 1m-2m tall, Y-up.
# GLB native is Y-up by default; we just need to ensure the model isn't tiny / huge.
# Compute bbox height and rescale to ~1.7m
import mathutils
bbox_world = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
mins = mathutils.Vector((min(v[i] for v in bbox_world) for i in range(3)))
maxs = mathutils.Vector((max(v[i] for v in bbox_world) for i in range(3)))
size = maxs - mins
height = size.z
if height < 0.05 or height > 50.0:
    print(f"warning: model is {height:.2f}m tall, probably needs scaling")
target_height = 1.7  # Mixamo prefers ~human-scale
if height > 0:
    scale = target_height / height
    obj.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# Re-center after scale
bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
# Place feet at world origin (Mixamo expects character feet on ground plane)
bbox_world = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
mins = mathutils.Vector((min(v[i] for v in bbox_world) for i in range(3)))
obj.location = (0, 0, -mins.z)
bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

# Export FBX with Mixamo-friendly settings
out_fbx.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.fbx(
    filepath=str(out_fbx),
    use_selection=True,
    apply_unit_scale=True,
    apply_scale_options="FBX_SCALE_NONE",
    object_types={"MESH"},
    mesh_smooth_type="FACE",
    use_mesh_modifiers=True,
    embed_textures=True,
    path_mode="COPY",
    axis_forward="-Z",
    axis_up="Y",
)
print(f"exported: {out_fbx}")

# Print final stats
me = obj.data
print(f"final mesh: {len(me.vertices)} verts, {sum((len(p.vertices)-2) for p in me.polygons)} tris")
print(f"final size: {[round(s,3) for s in size]}")
