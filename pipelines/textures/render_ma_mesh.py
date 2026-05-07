"""Render a Material Anything output (textured mesh + UV-space PBR maps) in Blender Cycles.

After running material_anything_adapter.py on a mesh, the output looks like:
  world/textures/library/<id>/
    input/mesh.obj         (the input mesh, copied)
    generate/
      mesh/9.obj           (final UV-textured mesh — the highest-numbered viewpoint)
      mesh/9.mtl
      mesh/9.png           (texture)
      material/
        final_albedo.png
        final_metallic.png
        final_roughness.png
        final_bump.png

This script renders the final mesh under HDRI lighting at multiple angles.

Usage:
  python render_ma_mesh.py --ma-out world/textures/library/goblin_bronze --hdri sunset
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import textwrap
from pathlib import Path


BLENDER_CANDIDATES = [
    Path(r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"),
    Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"),
]
HDRI_DIR = Path(r"D:\assets\animators\MaterialAnything\hdr_env")


BLENDER_SCRIPT = textwrap.dedent('''
import bpy, sys, os
from pathlib import Path

argv = sys.argv[sys.argv.index("--") + 1:]
ma_out = Path(argv[0])
out_path = Path(argv[1])
hdri_path = Path(argv[2]) if argv[2] else None

# Find the final OBJ (highest-numbered mesh)
# MA writes to either ma_out/generate/mesh/ (when called via test.sh)
# or ma_out/generate/generate/mesh/ (when called via material_anything_adapter.py)
mesh_dir = None
for candidate in [ma_out / "generate" / "mesh",
                   ma_out / "generate" / "generate" / "mesh"]:
    if candidate.exists():
        mesh_dir = candidate
        break
if mesh_dir is None:
    print(f"ERROR: no generate/mesh/ in {ma_out} (tried two layouts)")
    sys.exit(1)
obj_files = sorted([p for p in mesh_dir.glob("*.obj") if p.stem.isdigit()],
                    key=lambda p: int(p.stem))
if not obj_files:
    print(f"ERROR: no numbered OBJ in {mesh_dir}")
    sys.exit(1)
final_obj = obj_files[-1]
print(f"using final mesh: {final_obj}")

# Find PBR maps (same two-layout logic)
mat_dir = None
for candidate in [ma_out / "generate" / "material",
                   ma_out / "generate" / "generate" / "material"]:
    if candidate.exists():
        mat_dir = candidate
        break
if mat_dir is None:
    mat_dir = ma_out / "generate" / "material"  # placeholder; PBRs will be missing
final_albedo = mat_dir / "final_albedo.png"
final_normal = mat_dir / "final_bump.png"  # MA emits bump as the displacement source
final_rough  = mat_dir / "final_roughness.png"
final_metal  = mat_dir / "final_metallic.png"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 96
scene.cycles.use_denoising = True
scene.render.resolution_x = 768
scene.render.resolution_y = 768
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.cycles.device = "GPU"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
for d in prefs.devices:
    d.use = (d.type != "CPU")

# Import OBJ
bpy.ops.wm.obj_import(filepath=str(final_obj))
mesh_obj = bpy.context.selected_objects[0] if bpy.context.selected_objects else bpy.context.active_object
print(f"imported: {mesh_obj.name}")

# Build a clean PBR material that uses the final maps
mat = bpy.data.materials.new(name="MA_PBR")
mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial")
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
nt.links.new(bsdf.outputs[0], out.inputs[0])

def add_image(path, colorspace="sRGB"):
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = colorspace
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = img
    return n

if final_albedo.exists():
    a = add_image(final_albedo, "sRGB")
    nt.links.new(a.outputs["Color"], bsdf.inputs["Base Color"])
if final_rough.exists():
    r = add_image(final_rough, "Non-Color")
    nt.links.new(r.outputs["Color"], bsdf.inputs["Roughness"])
if final_metal.exists():
    m = add_image(final_metal, "Non-Color")
    nt.links.new(m.outputs["Color"], bsdf.inputs["Metallic"])
if final_normal.exists():
    n = add_image(final_normal, "Non-Color")
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    nt.links.new(n.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

# Replace the imported material with ours
if mesh_obj.data.materials:
    mesh_obj.data.materials[0] = mat
else:
    mesh_obj.data.materials.append(mat)

# Centre + scale: normalize the mesh to a 2-unit bounding sphere
bpy.ops.object.select_all(action="DESELECT")
mesh_obj.select_set(True)
bpy.context.view_layer.objects.active = mesh_obj
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# Compute bounds
bb = [mesh_obj.matrix_world @ bpy.mathutils.Vector(c) for c in mesh_obj.bound_box] if hasattr(bpy, 'mathutils') else None
if bb is None:
    import mathutils
    bb = [mesh_obj.matrix_world @ mathutils.Vector(c) for c in mesh_obj.bound_box]
import mathutils
xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
target = 2.0
scale = target / max(size, 1e-3)
mesh_obj.location = -center * scale
mesh_obj.scale = (scale, scale, scale)

# Camera
bpy.ops.object.camera_add(location=(0, -3.5, 1.2))
cam = bpy.context.active_object
cam.rotation_euler = (1.25, 0, 0)
cam.data.lens = 50
scene.camera = cam

# World — HDRI if given
world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
wnt.nodes.clear()
wout = wnt.nodes.new("ShaderNodeOutputWorld")
wbg = wnt.nodes.new("ShaderNodeBackground")
wnt.links.new(wbg.outputs[0], wout.inputs[0])
if hdri_path and hdri_path.exists():
    env = wnt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(hdri_path))
    wnt.links.new(env.outputs[0], wbg.inputs[0])
    wbg.inputs[1].default_value = 0.6
else:
    wbg.inputs[0].default_value = (0.04, 0.04, 0.06, 1)
    wbg.inputs[1].default_value = 1.0

# Sun for contrast
bpy.ops.object.light_add(type="SUN", location=(2, -3, 5))
sun = bpy.context.active_object
sun.data.energy = 2.0
sun.rotation_euler = (1.0, 0.2, 0.4)

scene.render.filepath = str(out_path)
bpy.ops.render.render(write_still=True)
print(f"rendered -> {out_path}")
''').strip()


def find_blender():
    for p in BLENDER_CANDIDATES:
        if p.exists():
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ma-out", type=Path, required=True)
    ap.add_argument("--hdri", default="sunset")
    ap.add_argument("--blender", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    blender = args.blender or find_blender()
    if not blender:
        sys.exit("Blender not found")

    hdri_path = HDRI_DIR / f"{args.hdri}.exr"
    if not hdri_path.exists():
        hdri_path = None

    out = args.out or (args.ma_out / "qa" / "ma_mesh_render.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    script_path = args.ma_out / "qa" / "_render_ma.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(BLENDER_SCRIPT, encoding="utf-8")

    cmd = [str(blender), "--background", "--python", str(script_path), "--",
           str(args.ma_out), str(out), str(hdri_path) if hdri_path else ""]
    print(f"[render-ma-mesh] launching Blender...")
    result = subprocess.run(cmd, capture_output=True, timeout=600)
    if result.returncode != 0:
        print("Blender failed:")
        for line in result.stderr.decode(errors="ignore").splitlines()[-20:]:
            print("  " + line)
        sys.exit(1)

    if out.exists():
        print(f"  rendered -> {out}")
    else:
        print("Render didn't produce output. Stdout:")
        print(result.stdout.decode(errors="ignore")[-2000:])
        sys.exit(1)
    script_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
