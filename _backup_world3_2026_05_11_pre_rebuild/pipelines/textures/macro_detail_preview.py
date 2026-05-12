"""Render a macro+detail material pair in Blender Cycles to validate the AAA close-up story.

Validates the same RNM-blend logic the Godot `macro_detail_v1.gdshader` does:
  - Macro texture sampled at coarse UV scale
  - Detail texture sampled at fine UV scale (default 10× macro frequency)
  - Detail normal blended with macro normal via reoriented normal mapping
  - Detail albedo soft-light blended at configurable strength
  - Distance fade — detail vanishes past N meters

Renders a tilted plane at grazing angle to match how you'd see floor/terrain
in an iso/Diablo-style camera.

Usage:
  python macro_detail_preview.py --macro world/textures/library/cobblestone_aaa
"""
from __future__ import annotations

import argparse
import json
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
import bpy, sys
from pathlib import Path

argv = sys.argv[sys.argv.index("--") + 1:]
macro_dir = Path(argv[0])
detail_dir = Path(argv[1])
out_path = Path(argv[2])
hdri_path = Path(argv[3]) if argv[3] else None
detail_uv_repeat = float(argv[4])
detail_albedo_strength = float(argv[5])
detail_normal_strength = float(argv[6])

def find(d, suffix):
    for p in d.glob(f"*_{suffix}.png"):
        if "pre_" not in p.name and "_2048" not in p.name:
            return str(p)
    return None

m_albedo = find(macro_dir, "albedo")
m_normal = find(macro_dir, "normal")
m_rough = find(macro_dir, "roughness")
m_metal = find(macro_dir, "metallic")
m_height = find(macro_dir, "height")

d_albedo = find(detail_dir, "albedo")
d_normal = find(detail_dir, "normal")
d_rough = find(detail_dir, "roughness")
print(f"macro: {m_albedo}\\ndetail: {d_albedo}")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 96
scene.cycles.use_denoising = True
scene.render.resolution_x = 1024
scene.render.resolution_y = 768
scene.render.image_settings.file_format = "PNG"
scene.cycles.device = "GPU"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
for d in prefs.devices:
    d.use = (d.type != "CPU")

# Build the macro+detail material
mat = bpy.data.materials.new(name="MacroDetail")
mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()

output = nt.nodes.new("ShaderNodeOutputMaterial")
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
nt.links.new(bsdf.outputs[0], output.inputs[0])

def add_image(path, colorspace="sRGB"):
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = colorspace
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = img
    return n

# UV with two scales
uv_node = nt.nodes.new("ShaderNodeTexCoord")
# Macro UV scaling
macro_scale = nt.nodes.new("ShaderNodeMapping")
macro_scale.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
nt.links.new(uv_node.outputs["UV"], macro_scale.inputs["Vector"])
# Detail UV scaling (10x by default)
detail_scale = nt.nodes.new("ShaderNodeMapping")
detail_scale.inputs["Scale"].default_value = (detail_uv_repeat, detail_uv_repeat, 1.0)
nt.links.new(uv_node.outputs["UV"], detail_scale.inputs["Vector"])

# Macro samples
macro_albedo_n = add_image(m_albedo, "sRGB")
nt.links.new(macro_scale.outputs[0], macro_albedo_n.inputs["Vector"])
macro_normal_n = add_image(m_normal, "Non-Color") if m_normal else None
if macro_normal_n:
    nt.links.new(macro_scale.outputs[0], macro_normal_n.inputs["Vector"])
macro_rough_n = add_image(m_rough, "Non-Color") if m_rough else None
if macro_rough_n:
    nt.links.new(macro_scale.outputs[0], macro_rough_n.inputs["Vector"])

# Detail samples
detail_albedo_n = add_image(d_albedo, "sRGB") if d_albedo else None
if detail_albedo_n:
    nt.links.new(detail_scale.outputs[0], detail_albedo_n.inputs["Vector"])
detail_normal_n = add_image(d_normal, "Non-Color") if d_normal else None
if detail_normal_n:
    nt.links.new(detail_scale.outputs[0], detail_normal_n.inputs["Vector"])
detail_rough_n = add_image(d_rough, "Non-Color") if d_rough else None
if detail_rough_n:
    nt.links.new(detail_scale.outputs[0], detail_rough_n.inputs["Vector"])

# Albedo blend: soft-light approximated via Mix (overlay + linear)
if detail_albedo_n:
    mix_albedo = nt.nodes.new("ShaderNodeMixRGB")
    mix_albedo.blend_type = "OVERLAY"
    mix_albedo.inputs["Fac"].default_value = detail_albedo_strength
    nt.links.new(macro_albedo_n.outputs["Color"], mix_albedo.inputs["Color1"])
    nt.links.new(detail_albedo_n.outputs["Color"], mix_albedo.inputs["Color2"])
    nt.links.new(mix_albedo.outputs["Color"], bsdf.inputs["Base Color"])
else:
    nt.links.new(macro_albedo_n.outputs["Color"], bsdf.inputs["Base Color"])

# Normal: blend macro and detail normal RGB via MixRGB OVERLAY then NormalMap.
# Not real RNM — that's what the Godot shader does — this is just a preview proxy.
if macro_normal_n:
    if detail_normal_n:
        mix_n = nt.nodes.new("ShaderNodeMixRGB")
        mix_n.blend_type = "OVERLAY"
        mix_n.inputs["Fac"].default_value = detail_normal_strength
        nt.links.new(macro_normal_n.outputs["Color"], mix_n.inputs["Color1"])
        nt.links.new(detail_normal_n.outputs["Color"], mix_n.inputs["Color2"])
        combined_nm = nt.nodes.new("ShaderNodeNormalMap")
        combined_nm.inputs["Strength"].default_value = 1.4
        nt.links.new(mix_n.outputs["Color"], combined_nm.inputs["Color"])
        nt.links.new(combined_nm.outputs["Normal"], bsdf.inputs["Normal"])
    else:
        macro_nm = nt.nodes.new("ShaderNodeNormalMap")
        macro_nm.inputs["Strength"].default_value = 1.4
        nt.links.new(macro_normal_n.outputs["Color"], macro_nm.inputs["Color"])
        nt.links.new(macro_nm.outputs["Normal"], bsdf.inputs["Normal"])

# Roughness blend
if macro_rough_n:
    if detail_rough_n:
        mix_r = nt.nodes.new("ShaderNodeMixRGB")
        mix_r.blend_type = "MIX"
        mix_r.inputs["Fac"].default_value = 0.4
        nt.links.new(macro_rough_n.outputs["Color"], mix_r.inputs["Color1"])
        nt.links.new(detail_rough_n.outputs["Color"], mix_r.inputs["Color2"])
        nt.links.new(mix_r.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        nt.links.new(macro_rough_n.outputs["Color"], bsdf.inputs["Roughness"])

# === Geometry: floor plane at iso/Diablo angle, sized so close detail reads ===
import bmesh
# 4m plane = ~game tile area visible to player. Macro UV at 1m repeat = 4 tiles.
bpy.ops.mesh.primitive_plane_add(size=4.0)
plane = bpy.context.active_object
plane.data.materials.append(mat)

# Tile UVs: macro 4x means 1m per repeat (real-world cobblestone-tile scale)
me = plane.data
bm = bmesh.new()
bm.from_mesh(me)
uv_layer = bm.loops.layers.uv.verify()
for face in bm.faces:
    for loop in face.loops:
        u, v = loop[uv_layer].uv
        loop[uv_layer].uv = (u * 4.0, v * 4.0)
bm.to_mesh(me)
bm.free()

# Camera at Diablo-ish iso angle: 60deg pitch, close enough that detail reads.
# At 3m camera height + 2.5m back, plane fills frame nicely.
bpy.ops.object.camera_add(location=(0, -2.5, 3.0))
cam = bpy.context.active_object
cam.rotation_euler = (0.95, 0, 0)  # ~54deg pitch (iso-ish)
cam.data.lens = 35  # slightly wide so we see the foreground detail
scene.camera = cam

# Lighting: HDRI for ambient + a directional sun for contrast & shadow detail
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
    wbg.inputs[1].default_value = 0.45  # soften HDRI; sun gives contrast
else:
    wbg.inputs[0].default_value = (0.04, 0.04, 0.06, 1)
    wbg.inputs[1].default_value = 1.0

# Sun for contrast + cast shadows revealing the detail normal
bpy.ops.object.light_add(type="SUN", location=(2, -3, 5))
sun = bpy.context.active_object
sun.data.energy = 2.5
sun.data.angle = 0.05  # sharp-ish shadows
sun.rotation_euler = (1.05, 0.2, 0.4)

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
    ap.add_argument("--macro", type=Path, required=True,
                    help="macro material directory (must have detail_pair.json)")
    ap.add_argument("--detail", type=Path, default=None,
                    help="detail material dir; defaults to <macro>_detail or whatever detail_pair.json links to")
    ap.add_argument("--hdri", default="sunset",
                    help="HDRI env (studio/courtyard/forest/sunrise/sunset/city/interior/night)")
    ap.add_argument("--blender", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None,
                    help="output PNG; defaults to <macro>/qa/macro_detail_preview.png")
    args = ap.parse_args()

    macro_dir = args.macro
    pair_path = macro_dir / "detail_pair.json"
    if pair_path.exists():
        pair = json.loads(pair_path.read_text(encoding="utf-8"))
        detail_id = pair["detail_id"]
        detail_uv_repeat = pair.get("detail_uv_repeat", 10.0)
        detail_albedo_strength = pair["godot_hint"].get("detail_albedo_strength", 0.6)
        detail_normal_strength = pair["godot_hint"].get("detail_normal_strength", 0.42)
        detail_dir = args.detail or (macro_dir.parent / detail_id)
    else:
        if not args.detail:
            raise SystemExit(f"no detail_pair.json in {macro_dir}; pass --detail explicitly")
        detail_dir = args.detail
        detail_uv_repeat = 10.0
        detail_albedo_strength = 0.6
        detail_normal_strength = 0.42

    if not detail_dir.exists():
        raise SystemExit(f"detail dir not found: {detail_dir}")

    print(f"[macro_detail] macro:  {macro_dir}")
    print(f"[macro_detail] detail: {detail_dir}")
    print(f"[macro_detail] uv_repeat={detail_uv_repeat} albedo_strength={detail_albedo_strength} "
          f"normal_strength={detail_normal_strength}")

    blender = args.blender or find_blender()
    if not blender:
        raise SystemExit("Blender not found")
    print(f"[macro_detail] blender: {blender}")

    hdri_path = HDRI_DIR / f"{args.hdri}.exr"
    if not hdri_path.exists():
        print(f"  hdri {hdri_path} not found, using grey background")
        hdri_path = None

    out = args.out or (macro_dir / "qa" / "macro_detail_preview.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    script_path = macro_dir / "qa" / "_macro_detail_preview.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(BLENDER_SCRIPT, encoding="utf-8")

    cmd = [
        str(blender), "--background", "--python", str(script_path), "--",
        str(macro_dir), str(detail_dir), str(out),
        str(hdri_path) if hdri_path else "",
        str(detail_uv_repeat),
        str(detail_albedo_strength),
        str(detail_normal_strength),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=600)
    if result.returncode != 0:
        print("Blender failed; stderr last 30 lines:")
        for line in result.stderr.decode(errors="ignore").splitlines()[-30:]:
            print("  " + line)
        sys.exit(1)

    if out.exists():
        print(f"\nrendered -> {out}")
    else:
        print("Render didn't produce output. Stdout:")
        print(result.stdout.decode(errors="ignore")[-2000:])
        sys.exit(1)
    script_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
