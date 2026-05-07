"""Blender headless render comparison of HY3D-2.1 (geometry + PBR) and Trellis2 outputs.

Uses Blender's bundled Python via the existing Blender exe at the path our
preprocess scripts reference. Renders each GLB at 4 angles + a flat lit setup
so we can eye geometry, textures, and proportions.

Output: D:/tmp/glb_compare/<id>/{front,back,left,right,iso}.png
"""
# Run as: blender --background --python render_glb_compare.py
import bpy
import sys
import os
import math
from pathlib import Path

OUT_ROOT = Path(r"D:\tmp\glb_compare")
GLBS = [
    ("t2_low",     r"D:\assets\world\props\ai_routes\trellis2\sweep\low\model_lod0.glb"),
    ("t2_mid",     r"D:\assets\world\props\ai_routes\trellis2\sweep\mid\model_lod0.glb"),
    ("t2_hi",      r"D:\assets\world\props\ai_routes\trellis2\sweep\hi\model_lod0.glb"),
    ("t2_hi_tex",  r"D:\assets\world\props\ai_routes\trellis2\sweep\hi_tex\model_lod0.glb"),
]

# Camera positions (azimuth degrees from +X axis, elevation degrees from XZ plane)
VIEWS = [
    ("front", 0, 0),
    ("right", 90, 0),
    ("back", 180, 0),
    ("left", 270, 0),
    ("iso", 35, 25),
]


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def add_lighting():
    # Three-point: key + fill + back, plus an HDRI-ish ambient via World
    world = bpy.data.worlds.new("World") if not bpy.data.worlds else bpy.data.worlds[0]
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background") or world.node_tree.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (0.5, 0.5, 0.5, 1)
    bg.inputs[1].default_value = 0.6

    # Key
    bpy.ops.object.light_add(type="SUN", location=(4, -3, 5))
    bpy.context.object.data.energy = 4.0
    bpy.context.object.data.angle = math.radians(15)
    # Fill
    bpy.ops.object.light_add(type="AREA", location=(-4, -2, 2))
    bpy.context.object.data.energy = 200
    bpy.context.object.data.size = 5
    # Back
    bpy.ops.object.light_add(type="AREA", location=(0, 4, 3))
    bpy.context.object.data.energy = 100
    bpy.context.object.data.size = 4


def fit_view(camera, target_obj, dist_factor=2.5):
    """Position camera to fit target. dist_factor = distance multiplier of bbox diagonal."""
    bbox_corners = [target_obj.matrix_world @ mathutils_vec(c) for c in target_obj.bound_box]
    min_co = [min(c[i] for c in bbox_corners) for i in range(3)]
    max_co = [max(c[i] for c in bbox_corners) for i in range(3)]
    center = [(min_co[i] + max_co[i]) / 2 for i in range(3)]
    diag = math.sqrt(sum((max_co[i] - min_co[i]) ** 2 for i in range(3)))
    return center, diag * dist_factor


def mathutils_vec(v):
    import mathutils
    return mathutils.Vector(v)


def render_views(label, glb_path):
    out_dir = OUT_ROOT / label
    out_dir.mkdir(parents=True, exist_ok=True)
    reset_scene()
    add_lighting()

    bpy.ops.import_scene.gltf(filepath=str(glb_path))
    imported = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not imported:
        print(f"[render] {label}: no mesh imported", file=sys.stderr)
        return
    mesh = imported[0]

    # Center mesh on origin XY, rest on Z=0
    bbox_corners = [mesh.matrix_world @ mathutils_vec(c) for c in mesh.bound_box]
    min_co = [min(c[i] for c in bbox_corners) for i in range(3)]
    max_co = [max(c[i] for c in bbox_corners) for i in range(3)]
    mesh.location.x -= (min_co[0] + max_co[0]) / 2
    mesh.location.y -= (min_co[1] + max_co[1]) / 2
    mesh.location.z -= min_co[2]
    bpy.context.view_layer.update()

    # Pivot point for camera orbits
    diag = math.sqrt(sum((max_co[i] - min_co[i]) ** 2 for i in range(3)))
    center_z = (max_co[2] - min_co[2]) / 2  # half-height after recenter
    radius = diag * 1.5

    bpy.ops.object.camera_add()
    cam = bpy.context.object
    bpy.context.scene.camera = cam
    cam.data.lens = 50

    # Render settings
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 768
    scene.render.resolution_y = 768
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 32

    import mathutils
    for view_name, az_deg, el_deg in VIEWS:
        az = math.radians(az_deg)
        el = math.radians(el_deg)
        cx = radius * math.cos(el) * math.cos(az)
        cy = radius * math.cos(el) * math.sin(az)
        cz = center_z + radius * math.sin(el)
        cam.location = (cx, cy, cz)
        # point at object center (XY=origin, Z=center_z)
        direction = mathutils.Vector((-cx, -cy, center_z - cz))
        rot = direction.to_track_quat("-Z", "Y").to_euler()
        cam.rotation_euler = rot
        bpy.context.view_layer.update()

        scene.render.filepath = str(out_dir / f"{view_name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[render] {label}/{view_name} -> {scene.render.filepath}")


def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    for label, glb in GLBS:
        if not Path(glb).exists():
            print(f"[render] SKIP {label}: missing {glb}")
            continue
        print(f"\n[render] === {label} ({glb}) ===")
        render_views(label, glb)
    print(f"\n[render] DONE -> {OUT_ROOT}")


if __name__ == "__main__":
    main()
