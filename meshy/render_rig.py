"""Render a rigged GLB showing mesh + skeleton overlay from front + side.

Usage:
    blender.exe -b -P render_rig.py -- <input.glb> <out.png>
"""
import sys
import math
from pathlib import Path

import bpy
import bmesh
import mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
glb_path = Path(argv[0])
out_png = Path(argv[1])

# Reset scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Import GLB
bpy.ops.import_scene.gltf(filepath=str(glb_path))

# Scene contents
all_objs = list(bpy.context.scene.objects)
meshes = [o for o in all_objs if o.type == "MESH"]
armatures = [o for o in all_objs if o.type == "ARMATURE"]
print(f"Imported: {len(meshes)} meshes, {len(armatures)} armatures")
for a in armatures:
    print(f"  Armature '{a.name}': {len(a.data.bones)} bones")

if not meshes and not armatures:
    raise SystemExit("nothing to render")

# Combined bbox center + radius across all meshes
mins = mathutils.Vector((math.inf,)*3)
maxs = mathutils.Vector((-math.inf,)*3)
for o in meshes:
    for c in o.bound_box:
        wc = o.matrix_world @ mathutils.Vector(c)
        mins = mathutils.Vector((min(mins[i], wc[i]) for i in range(3)))
        maxs = mathutils.Vector((max(maxs[i], wc[i]) for i in range(3)))
center = (mins + maxs) * 0.5
size = (maxs - mins).length
radius = max(size * 0.9, 0.5)

# Render skeleton in front of mesh — use semi-transparent mesh + emissive bones
# This way mesh color shows but bones aren't hidden behind body geometry.
for m in meshes:
    if m.data.materials:
        for slot in m.data.materials:
            if slot is not None:
                slot.use_nodes = True
                bsdf = slot.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    bsdf.inputs["Alpha"].default_value = 0.35
                slot.blend_method = "BLEND"
                slot.show_transparent_back = False

# Build skeleton geometry from each armature: small spheres at joint heads + thin cylinders for bones
for a in armatures:
    bones_collection_name = f"_skel_{a.name}"
    coll = bpy.data.collections.new(bones_collection_name)
    bpy.context.scene.collection.children.link(coll)

    # Bright orange-red emissive material for the skeleton
    mat = bpy.data.materials.new(name=f"_skel_mat_{a.name}")
    mat.use_nodes = True
    nt = mat.node_tree
    # Replace BSDF with emission
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = (1.0, 0.0, 0.0, 1.0)  # pure red, fully saturated
    em.inputs[1].default_value = 8.0
    nt.links.new(em.outputs[0], out.inputs[0])

    # Compute reasonable bone visual radius based on overall model size
    bone_radius = max(size * 0.005, 0.005)
    joint_radius = bone_radius * 1.6

    arm_world = a.matrix_world

    for bone in a.data.bones:
        head_w = arm_world @ bone.head_local
        tail_w = arm_world @ bone.tail_local
        length = (tail_w - head_w).length
        if length < 1e-5:
            continue
        # Cylinder for bone
        bpy.ops.mesh.primitive_cylinder_add(radius=bone_radius, depth=length, vertices=8)
        cyl = bpy.context.active_object
        # Aim from head to tail
        midpoint = (head_w + tail_w) * 0.5
        direction = (tail_w - head_w).normalized()
        cyl.location = midpoint
        cyl.rotation_mode = "QUATERNION"
        cyl.rotation_quaternion = direction.to_track_quat("Z", "Y")
        cyl.data.materials.append(mat)
        # Move into our collection
        for c in cyl.users_collection:
            c.objects.unlink(cyl)
        coll.objects.link(cyl)

        # Joint sphere at head
        bpy.ops.mesh.primitive_uv_sphere_add(radius=joint_radius, location=head_w, segments=12, ring_count=8)
        sph = bpy.context.active_object
        sph.data.materials.append(mat)
        for c in sph.users_collection:
            c.objects.unlink(sph)
        coll.objects.link(sph)

    # Hide the original armature display so it doesn't double up
    a.hide_render = True
    a.hide_viewport = True

# White background
world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (1, 1, 1, 1)
bg.inputs[1].default_value = 1.0

# Sun light from upper-front
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

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in scene.render.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
scene.render.resolution_x = 600
scene.render.resolution_y = 600
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"

# 4 angles
out_png.parent.mkdir(parents=True, exist_ok=True)
tmp_dir = out_png.parent / f"_tmp_{out_png.stem}"
tmp_dir.mkdir(parents=True, exist_ok=True)

views = []
for i, deg in enumerate([0, 90, 180, 270]):
    angle = math.radians(deg)
    cam_obj.location = (
        center.x + math.sin(angle) * radius * 2.2,
        center.y - math.cos(angle) * radius * 2.2,
        center.z + radius * 0.6,
    )
    direction = mathutils.Vector(center) - mathutils.Vector(cam_obj.location)
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    view_file = tmp_dir / f"view_{i}.png"
    scene.render.filepath = str(view_file)
    bpy.ops.render.render(write_still=True)
    views.append(view_file)

# Stitch — use Blender's bundled Pillow if available, else just copy front view
try:
    from PIL import Image
    imgs = [Image.open(p) for p in views]
    w, h = imgs[0].size
    sheet = Image.new("RGB", (w * 4, h), "white")
    for i, im in enumerate(imgs):
        sheet.paste(im, (i * w, 0))
    sheet.save(out_png)
    print(f"wrote sheet: {out_png}")
except ImportError:
    import shutil
    shutil.copy(views[0], out_png)
    print(f"PIL unavailable, wrote front view only: {out_png}")
    print(f"all 4 views in: {tmp_dir}")
