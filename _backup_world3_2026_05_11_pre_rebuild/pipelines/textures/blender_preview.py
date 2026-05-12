"""Blender headless render of a lit sphere + tiled plane for texture QA.

Real Cycles render with HDRI environment lighting — same model the engine
will use. Beats the fake "synthetic sphere" preview because PBR maps interact
correctly with the IBL.

Output (in <material>/qa/):
  blender_sphere.png   — lit sphere with full PBR + HDRI
  blender_plane.png    — tiled plane at grazing angle (shows tiling under light)
  blender_combo.png    — sphere + plane side-by-side at 1024×512

HDRI options (all at D:/assets/animators/MaterialAnything/hdr_env/):
  studio (default), courtyard, forest, sunrise, sunset, city, interior, night

Usage:
  python blender_preview.py --material world/textures/library/cobblestone_aaa
  python blender_preview.py --material <dir> --hdri sunset
  python blender_preview.py --kit highland --materials a,b,c  (multi-material panel)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from pathlib import Path

# Locate Blender
BLENDER_CANDIDATES = [
    Path(r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"),
    Path(r"C:\Users\josep\AppData\Local\Programs\Blender Foundation\Blender 4.5\blender.exe"),
]


BLENDER_SCRIPT = textwrap.dedent('''
import bpy, sys, os, json
from pathlib import Path

# Args after `--`
argv = sys.argv[sys.argv.index("--") + 1:]
material_dir = Path(argv[0])
out_sphere = Path(argv[1])
out_plane = Path(argv[2])
out_combo = Path(argv[3]) if len(argv) > 3 else None
hdri_path = Path(argv[4]) if len(argv) > 4 and argv[4] else None
hdri_strength = float(argv[5]) if len(argv) > 5 else 1.0

# Find PBR maps
def find(suffix):
    for p in material_dir.glob(f"*_{suffix}.png"):
        if "pre_" not in p.name:
            return str(p)
    return None

albedo = find("albedo")
normal = find("normal")
rough = find("roughness")
metal = find("metallic")
height = find("height")
ao = find("ao")
print(f"albedo={albedo}\\nnormal={normal}\\nrough={rough}\\nmetal={metal}\\nheight={height}\\nao={ao}")

# Reset scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Renderer
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.image_settings.file_format = "PNG"
scene.cycles.device = "GPU"

# Try GPU
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
for d in prefs.devices:
    d.use = (d.type != "CPU")

# Build the PBR material
def make_material(name):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    output = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], output.inputs[0])

    def add_image_tex(path, colorspace="sRGB"):
        img = bpy.data.images.load(path)
        if colorspace != "sRGB":
            img.colorspace_settings.name = colorspace
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        return node

    if albedo:
        n = add_image_tex(albedo, "sRGB")
        nt.links.new(n.outputs["Color"], bsdf.inputs["Base Color"])
    if rough:
        n = add_image_tex(rough, "Non-Color")
        nt.links.new(n.outputs["Color"], bsdf.inputs["Roughness"])
    if metal:
        n = add_image_tex(metal, "Non-Color")
        nt.links.new(n.outputs["Color"], bsdf.inputs["Metallic"])
    if normal:
        n = add_image_tex(normal, "Non-Color")
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(n.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat

mat = make_material("PBR")

# === SCENE 1: Lit sphere ===
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0)
sphere = bpy.context.active_object
bpy.ops.object.shade_smooth()
sphere.data.materials.append(mat)

# Subdivide for displacement (bump only as visual cue)
bpy.ops.object.modifier_add(type="SUBSURF")
sphere.modifiers["Subdivision"].levels = 3

# Camera
bpy.ops.object.camera_add(location=(0, -2.8, 0.6))
cam = bpy.context.active_object
cam.rotation_euler = (1.3, 0, 0)
scene.camera = cam

# Lighting (3-point)
bpy.ops.object.light_add(type="AREA", location=(2, -1.5, 2.5))
key = bpy.context.active_object
key.data.energy = 800
key.data.size = 2.5
bpy.ops.object.light_add(type="AREA", location=(-2, -2, 1.5))
fill = bpy.context.active_object
fill.data.energy = 200
fill.data.size = 2

# World background: HDRI if provided, else medium grey
world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputWorld")
bg = nt.nodes.new("ShaderNodeBackground")
nt.links.new(bg.outputs[0], out.inputs[0])

if hdri_path and hdri_path.exists():
    print(f"using HDRI: {hdri_path}")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(hdri_path))
    nt.links.new(env.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = hdri_strength
    # Also reduce the lights so HDRI dominates
    if "Area" in bpy.data.objects.get("Area", bpy.data.objects.get("Light", bpy.data.objects.get("key", bpy.context.scene.objects[0]))).name:
        pass  # left intact
    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            obj.data.energy *= 0.25
else:
    bg.inputs[0].default_value = (0.04, 0.04, 0.06, 1)
    bg.inputs[1].default_value = 1.0

scene.render.filepath = str(out_sphere)
bpy.ops.render.render(write_still=True)
print(f"sphere -> {out_sphere}")

# === SCENE 2: Tiled plane at grazing angle (shows tiling) ===
# Remove sphere
bpy.data.objects.remove(sphere, do_unlink=True)

# Big plane with UV scale so the texture tiles 4x4
bpy.ops.mesh.primitive_plane_add(size=8.0)
plane = bpy.context.active_object
plane.data.materials.append(mat)
# Tile UVs
import bmesh
me = plane.data
bm = bmesh.new()
bm.from_mesh(me)
uv_layer = bm.loops.layers.uv.verify()
for face in bm.faces:
    for loop in face.loops:
        u, v = loop[uv_layer].uv
        loop[uv_layer].uv = (u * 4, v * 4)
bm.to_mesh(me)
bm.free()

# Camera lower for grazing angle
cam.location = (0, -3.5, 1.2)
cam.rotation_euler = (1.15, 0, 0)

scene.render.filepath = str(out_plane)
bpy.ops.render.render(write_still=True)
print(f"plane -> {out_plane}")

# === SCENE 3: side-by-side combo (sphere + plane) ===
if out_combo:
    from PIL import Image as PIL_Image
    sphere_img = PIL_Image.open(str(out_sphere))
    plane_img = PIL_Image.open(str(out_plane))
    combo = PIL_Image.new("RGB", (sphere_img.width + plane_img.width, max(sphere_img.height, plane_img.height)),
                           (12, 12, 16))
    combo.paste(sphere_img, (0, 0))
    combo.paste(plane_img, (sphere_img.width, 0))
    combo.save(str(out_combo))
    print(f"combo -> {out_combo}")
''').strip()


def find_blender() -> Path | None:
    for p in BLENDER_CANDIDATES:
        if p.exists():
            return p
    return None


HDRI_DIR = Path(r"D:\assets\animators\MaterialAnything\hdr_env")
HDRI_OPTIONS = ["studio", "courtyard", "forest", "sunrise", "sunset", "city", "interior", "night"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--material", type=Path, required=True)
    ap.add_argument("--blender", type=Path, default=None)
    ap.add_argument("--hdri", choices=HDRI_OPTIONS, default="studio",
                    help="HDRI environment for IBL")
    ap.add_argument("--hdri-strength", type=float, default=1.0)
    ap.add_argument("--no-hdri", action="store_true",
                    help="use the legacy 3-point lighting instead of HDRI")
    args = ap.parse_args()

    blender = args.blender or find_blender()
    if not blender:
        print("Blender not found; tried:")
        for p in BLENDER_CANDIDATES:
            print(f"  {p}")
        print("Pass --blender <path> to override.")
        sys.exit(1)
    print(f"[blender] using {blender}")

    hdri_path = HDRI_DIR / f"{args.hdri}.exr" if not args.no_hdri else None
    if hdri_path and not hdri_path.exists():
        print(f"  warning: HDRI {hdri_path} missing; falling back to 3-point lighting")
        hdri_path = None
    if hdri_path:
        print(f"[blender] HDRI: {args.hdri} (strength={args.hdri_strength})")

    qa_dir = args.material / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    out_sphere = qa_dir / "blender_sphere.png"
    out_plane = qa_dir / "blender_plane.png"
    out_combo = qa_dir / "blender_combo.png"

    # Write the script to a temp file
    script_path = args.material / "qa" / "_blender_preview.py"
    script_path.write_text(BLENDER_SCRIPT, encoding="utf-8")

    cmd = [str(blender), "--background", "--python", str(script_path),
           "--", str(args.material), str(out_sphere), str(out_plane),
           str(out_combo),
           str(hdri_path) if hdri_path else "",
           str(args.hdri_strength)]

    print(f"[blender] rendering...")
    result = subprocess.run(cmd, capture_output=True, timeout=600)
    if result.returncode != 0:
        print("Blender stderr (last 30 lines):")
        for line in result.stderr.decode(errors="ignore").splitlines()[-30:]:
            print("  " + line)
        sys.exit(1)

    if out_sphere.exists() and out_plane.exists():
        print(f"  sphere: {out_sphere}")
        print(f"  plane:  {out_plane}")
    else:
        print("Renders missing — check Blender stdout:")
        print(result.stdout.decode(errors="ignore")[-2000:])
        sys.exit(1)

    script_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
