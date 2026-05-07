"""Blender script — render a 4-view turnaround of a GLB to a single PNG sheet.

Run via:
    blender.exe -b -P render_preview.py -- <glb_path> <out_png>
"""
import sys
import math
from pathlib import Path

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
glb_path = Path(argv[0])
out_png = Path(argv[1])

# Reset scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Import model
bpy.ops.import_scene.gltf(filepath=str(glb_path))

# Collect imported mesh objects, frame them
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    raise SystemExit("no meshes imported from glb")

# Compute combined bounding box center + radius
import mathutils
mins = mathutils.Vector(( math.inf,)*3)
maxs = mathutils.Vector((-math.inf,)*3)
for o in meshes:
    for corner in o.bound_box:
        wc = o.matrix_world @ mathutils.Vector(corner)
        mins = mathutils.Vector((min(mins[i], wc[i]) for i in range(3)))
        maxs = mathutils.Vector((max(maxs[i], wc[i]) for i in range(3)))
center = (mins + maxs) * 0.5
size = (maxs - mins).length
radius = max(size * 0.9, 0.5)

# White world background
world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (1, 1, 1, 1)
bg.inputs[1].default_value = 1.0

# Sun light
light_data = bpy.data.lights.new(name="Sun", type="SUN")
light_data.energy = 3.0
light_obj = bpy.data.objects.new("Sun", light_data)
light_obj.rotation_euler = (math.radians(45), math.radians(15), math.radians(30))
bpy.context.collection.objects.link(light_obj)

# Camera
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 50
cam_obj = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# Render settings — small tiles per angle, then we let Blender stitch via frame range
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in scene.render.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"

# Render 4 views into a temp folder, then composite to a single sheet
tmp_dir = out_png.parent / f"_tmp_{out_png.stem}"
tmp_dir.mkdir(parents=True, exist_ok=True)

angles_deg = [0, 90, 180, 270]
view_paths = []
for i, deg in enumerate(angles_deg):
    angle = math.radians(deg)
    cam_obj.location = (
        center.x + math.sin(angle) * radius * 2.2,
        center.y - math.cos(angle) * radius * 2.2,
        center.z + radius * 0.6,
    )
    # Aim camera at center
    direction = mathutils.Vector(center) - mathutils.Vector(cam_obj.location)
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    view_file = tmp_dir / f"view_{i}.png"
    scene.render.filepath = str(view_file)
    bpy.ops.render.render(write_still=True)
    view_paths.append(view_file)

# Stitch with Pillow if available, else just keep the 4 separate files
try:
    from PIL import Image
    imgs = [Image.open(p) for p in view_paths]
    w, h = imgs[0].size
    sheet = Image.new("RGB", (w * 4, h), "white")
    for i, im in enumerate(imgs):
        sheet.paste(im, (i * w, 0))
    sheet.save(out_png)
    print(f"wrote sheet: {out_png}")
except ImportError:
    # Fallback: copy the front view as the preview
    import shutil
    shutil.copy(view_paths[0], out_png)
    print(f"PIL not available, wrote front view only: {out_png}")
    print(f"all 4 views in: {tmp_dir}")
