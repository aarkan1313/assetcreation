"""VFX Godot 4.5 3D / volumetric / mesh-trail / decal exporter.

Per `research/C2_vfx_3d_volumetric.md`: every baked Effect can target multiple
Godot scene shapes without re-baking. This module owns the four 3D variants;
`export_godot.py` keeps owning `2d`.

Output convention (post-2026-05-06 rewrite):
  All emitted .tscn / .tres / .gdshader files land in the effect's own
  `godot/` subdir:
      vfx/catalog/<kind>/<id>/godot/<id>_<target>.tscn
      vfx/catalog/<kind>/<id>/godot/<target>_material.tres
      vfx/catalog/<kind>/<id>/godot/<target>.gdshader
  All frames / flipbook / density images are referenced AT THEIR EXISTING
  catalog paths via `res://vfx/<kind>/<id>/...`. NO file copies.

Why no copies:
  Earlier version did `shutil.copytree(frames_dir, dst)` per export target.
  46 effects x 4 targets x ~20 frames produced 580k+ files in `vfx/godot/`
  and overflowed disk. Rewritten 2026-05-06; see HANDOFF_vfx_v2_*.md.

Routing (driven by `Effect.export_target`):

  3d_billboard  -> MeshInstance3D + QuadMesh + ShaderMaterial (flipbook UV
                   anim, billboard via Y_BILLBOARD or BILLBOARD; depth-tested,
                   unshaded)
  decal         -> Decal node + ShaderMaterial overlay (atlas UV anim)
  mesh_trail    -> MeshInstance3D + RibbonTrailMesh/TubeTrailMesh + script
                   (MeshTrail3D.gd from vfx/runtime/)
  fog_volume    -> FogVolume + FogMaterial.tres reference (the .tres ships
                   from the volumetric_fog baker into the effect dir; this
                   exporter just emits the .tscn that wires them)

CLI:
  python export_godot_3d.py --all
  python export_godot_3d.py vfx/catalog/spells/fireball_projectile --target 3d_billboard
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


# --- shaders ---------------------------------------------------------------
# Reusable spatial shader for 3D billboard flipbook playback. Samples a grid
# atlas (h_frames x v_frames) at TIME-driven cell index. We bake the math
# rather than using StandardMaterial3D's PARTICLES_ANIM flags because those
# only auto-advance inside GPUParticles3D - a static MeshInstance3D needs
# explicit TIME math (per C2 §6 risk note).

BILLBOARD_SHADER = """\
shader_type spatial;
render_mode unshaded, depth_draw_opaque, cull_disabled, blend_{blend_mode};

uniform sampler2D albedo_tex : source_color, filter_linear, repeat_disable;
uniform int h_frames = 1;
uniform int v_frames = 1;
uniform int n_frames = 1;
uniform float fps = 24.0;
uniform bool loop = true;
uniform vec4 modulate : source_color = vec4(1.0);
uniform float emission_strength = 0.0;

void vertex() {{
{billboard_block}
}}

void fragment() {{
    float t = TIME * fps;
    int idx = int(t);
    if (loop) {{
        idx = idx % n_frames;
    }} else if (idx >= n_frames) {{
        idx = n_frames - 1;
    }}
    int col = idx % h_frames;
    int row = idx / h_frames;
    vec2 cell = vec2(1.0 / float(h_frames), 1.0 / float(v_frames));
    vec2 uv = vec2(float(col), float(row)) * cell + UV * cell;
    vec4 c = texture(albedo_tex, uv) * modulate;
    ALBEDO = c.rgb;
    ALPHA = c.a;
    EMISSION = c.rgb * emission_strength;
}}
"""

BILLBOARD_FACE_CAM = """\
    // Full-billboard: cancel rotation, apply view-space translate.
    MODELVIEW_MATRIX = VIEW_MATRIX * mat4(
        INV_VIEW_MATRIX[0],
        INV_VIEW_MATRIX[1],
        INV_VIEW_MATRIX[2],
        MODEL_MATRIX[3]);
    MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
"""

BILLBOARD_Y_AXIS = """\
    // Y-axis billboard: keep upright, rotate around world Y.
    vec3 obj_pos = MODEL_MATRIX[3].xyz;
    vec3 cam_pos = INV_VIEW_MATRIX[3].xyz;
    vec3 to_cam = cam_pos - obj_pos;
    to_cam.y = 0.0;
    if (length(to_cam) > 0.0001) {
        vec3 fwd = normalize(to_cam);
        vec3 up = vec3(0.0, 1.0, 0.0);
        vec3 right = normalize(cross(up, fwd));
        mat4 b = mat4(
            vec4(right, 0.0),
            vec4(up,    0.0),
            vec4(fwd,   0.0),
            vec4(obj_pos, 1.0));
        MODELVIEW_MATRIX = VIEW_MATRIX * b;
        MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
    }
"""

BILLBOARD_OFF = "    // billboard off; quad uses MODEL_MATRIX as-is"

DECAL_SHADER = """\
// Decal flipbook shader. UV-animates a sprite atlas into the decal's
// projected albedo via a same-size MeshInstance3D quad child.
shader_type spatial;
render_mode unshaded;

uniform sampler2D atlas : source_color, filter_linear;
uniform int h_frames = 1;
uniform int v_frames = 1;
uniform int n_frames = 1;
uniform float fps = 24.0;
uniform bool loop = true;
uniform float fade_in_s = 0.0;
uniform float fade_out_s = 0.0;
uniform float duration_s = 1.0;
uniform vec4 modulate : source_color = vec4(1.0);

void fragment() {
    float t = TIME * fps;
    int idx = int(t);
    if (loop) {
        idx = idx % n_frames;
    } else if (idx >= n_frames) {
        idx = n_frames - 1;
    }
    int col = idx % h_frames;
    int row = idx / h_frames;
    vec2 cell = vec2(1.0 / float(h_frames), 1.0 / float(v_frames));
    vec2 uv = vec2(float(col), float(row)) * cell + UV * cell;
    vec4 c = texture(atlas, uv) * modulate;

    float life = TIME;
    float fade_in = fade_in_s > 0.0 ? smoothstep(0.0, fade_in_s, life) : 1.0;
    float fade_out = fade_out_s > 0.0 ? 1.0 - smoothstep(duration_s - fade_out_s, duration_s, life) : 1.0;
    if (!loop) {
        c.a *= fade_in * fade_out;
    }

    ALBEDO = c.rgb;
    ALPHA = c.a;
}
"""

TRAIL_SHADER = """\
shader_type spatial;
render_mode unshaded, cull_disabled, blend_{blend_mode}, depth_draw_opaque;

uniform sampler2D albedo_tex : source_color, filter_linear;
uniform float scroll_uv_speed = 2.5;
uniform vec4 modulate : source_color = vec4(1.0);
uniform float emission_strength = 0.5;

void fragment() {{
    vec2 uv = UV;
    uv.x = fract(uv.x - TIME * scroll_uv_speed);
    vec4 c = texture(albedo_tex, uv) * modulate;
    // Fade across V (0=core, 1=edge of strip)
    float edge = 1.0 - abs(UV.y - 0.5) * 2.0;
    c.a *= edge;
    ALBEDO = c.rgb;
    ALPHA = c.a;
    EMISSION = c.rgb * emission_strength;
}}
"""


# --- helpers ---------------------------------------------------------------

def _atlas_grid(n_frames: int) -> tuple[int, int]:
    cols = int(math.ceil(math.sqrt(n_frames)))
    rows = int(math.ceil(n_frames / cols))
    return cols, rows


def _palette_modulate(palette: list[str]) -> tuple[float, float, float, float]:
    if not palette:
        return (1.0, 1.0, 1.0, 1.0)
    h = palette[0].lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255,
            int(h[4:6], 16) / 255, 1.0)


# --- exporters per target --------------------------------------------------

def export_3d_billboard(effect: dict, manifest: dict, godot_dir: Path,
                        res_root: str) -> str:
    """Emit billboard.gdshader, billboard_material.tres, <id>_billboard.tscn
    into godot_dir. `res_root` = res://-relative path of the effect dir
    (e.g. 'vfx/spell/fireball_projectile')."""
    eid = effect["id"]
    n_frames = manifest["n_frames"]
    fps = manifest["fps"]
    h_frames, v_frames = _atlas_grid(n_frames)
    blend = effect.get("visual", {}).get("blend", "alpha")
    blend_mode = "add" if blend == "additive" else "mix"
    visual3d = effect.get("visual3d", {})
    bb_mode = visual3d.get("billboard_mode", "y_axis")
    world_size = visual3d.get("world_size_m") or max(effect.get("bounds_px", [256, 256])) / 100.0
    palette = effect.get("visual", {}).get("palette", ["#ffffff"])
    modulate = _palette_modulate(palette)
    emission = 1.5 if effect.get("visual", {}).get("bloom") or blend == "additive" else 0.0

    bb_block = {
        "off": BILLBOARD_OFF,
        "enabled": BILLBOARD_FACE_CAM,
        "particles": BILLBOARD_FACE_CAM,
        "y_axis": BILLBOARD_Y_AXIS,
    }.get(bb_mode, BILLBOARD_Y_AXIS)
    shader_text = BILLBOARD_SHADER.format(blend_mode=blend_mode, billboard_block=bb_block)
    (godot_dir / "billboard.gdshader").write_text(shader_text, encoding="utf-8")

    flipbook_godot = f"res://{res_root}/flipbook.png"
    shader_godot = f"res://{res_root}/godot/billboard.gdshader"

    mat_text = (
        '[gd_resource type="ShaderMaterial" load_steps=3 format=3]\n\n'
        f'[ext_resource type="Shader" path="{shader_godot}" id="1_sh"]\n'
        f'[ext_resource type="Texture2D" path="{flipbook_godot}" id="2_tex"]\n\n'
        '[resource]\n'
        'shader = ExtResource("1_sh")\n'
        'shader_parameter/albedo_tex = ExtResource("2_tex")\n'
        f'shader_parameter/h_frames = {h_frames}\n'
        f'shader_parameter/v_frames = {v_frames}\n'
        f'shader_parameter/n_frames = {n_frames}\n'
        f'shader_parameter/fps = {float(fps)}\n'
        'shader_parameter/loop = true\n'
        f'shader_parameter/modulate = Color({modulate[0]}, {modulate[1]}, {modulate[2]}, {modulate[3]})\n'
        f'shader_parameter/emission_strength = {emission}\n'
    )
    (godot_dir / "billboard_material.tres").write_text(mat_text, encoding="utf-8")

    scene_text = (
        '[gd_scene load_steps=4 format=3]\n\n'
        f'[ext_resource type="ShaderMaterial" path="res://{res_root}/godot/billboard_material.tres" id="1_mat"]\n\n'
        '[sub_resource type="QuadMesh" id="QuadMesh_1"]\n'
        f'size = Vector2({world_size}, {world_size})\n\n'
        f'[node name="{eid}_billboard" type="MeshInstance3D"]\n'
        'mesh = SubResource("QuadMesh_1")\n'
        f'cast_shadow = {1 if visual3d.get("cast_shadow") else 0}\n'
        'material_override = ExtResource("1_mat")\n'
    )
    scene_path = godot_dir / f"{eid}_billboard.tscn"
    scene_path.write_text(scene_text, encoding="utf-8")
    return str(scene_path)


def export_decal(effect: dict, manifest: dict, godot_dir: Path,
                 res_root: str) -> str:
    eid = effect["id"]
    n_frames = manifest["n_frames"]
    fps = manifest["fps"]
    h_frames, v_frames = _atlas_grid(n_frames)
    duration_s = effect.get("duration_s", 1.0)
    bp = effect.get("backend_params", {})
    fade_in = float(bp.get("fade_in_s", 0.0))
    fade_out = float(bp.get("fade_out_s", 0.0))
    loop = bool(bp.get("loop", True))
    world_size = (effect.get("visual3d", {}).get("world_size_m")
                  or float(bp.get("world_size_m", 3.0)))
    palette = effect.get("visual", {}).get("palette", ["#ffffff"])
    modulate = _palette_modulate(palette)

    (godot_dir / "decal_flipbook.gdshader").write_text(DECAL_SHADER, encoding="utf-8")

    flipbook_godot = f"res://{res_root}/flipbook.png"
    shader_godot = f"res://{res_root}/godot/decal_flipbook.gdshader"

    mat_text = (
        '[gd_resource type="ShaderMaterial" load_steps=3 format=3]\n\n'
        f'[ext_resource type="Shader" path="{shader_godot}" id="1_sh"]\n'
        f'[ext_resource type="Texture2D" path="{flipbook_godot}" id="2_tex"]\n\n'
        '[resource]\n'
        'shader = ExtResource("1_sh")\n'
        'shader_parameter/atlas = ExtResource("2_tex")\n'
        f'shader_parameter/h_frames = {h_frames}\n'
        f'shader_parameter/v_frames = {v_frames}\n'
        f'shader_parameter/n_frames = {n_frames}\n'
        f'shader_parameter/fps = {float(fps)}\n'
        f'shader_parameter/loop = {"true" if loop else "false"}\n'
        f'shader_parameter/fade_in_s = {fade_in}\n'
        f'shader_parameter/fade_out_s = {fade_out}\n'
        f'shader_parameter/duration_s = {duration_s}\n'
        f'shader_parameter/modulate = Color({modulate[0]}, {modulate[1]}, {modulate[2]}, {modulate[3]})\n'
    )
    (godot_dir / "decal_material.tres").write_text(mat_text, encoding="utf-8")

    # Decal projects DOWN by default along its -Y axis. size = (W, depth, D).
    scene_text = (
        '[gd_scene load_steps=2 format=3]\n\n'
        f'[ext_resource type="Texture2D" path="res://{res_root}/flipbook.png" id="1_tex"]\n\n'
        f'[node name="{eid}_decal" type="Decal"]\n'
        f'size = Vector3({world_size}, 1.5, {world_size})\n'
        'texture_albedo = ExtResource("1_tex")\n'
        'cull_mask = 1048575\n'
        'distance_fade_enabled = true\n'
        'distance_fade_begin = 30.0\n'
        'distance_fade_length = 10.0\n'
    )
    scene_path = godot_dir / f"{eid}_decal.tscn"
    scene_path.write_text(scene_text, encoding="utf-8")

    # Companion script: instances the animated ShaderMaterial-driven quad
    # under the Decal at runtime, since Godot 4.5's Decal node doesn't accept
    # arbitrary ShaderMaterial in its texture slots.
    script = (
        '# Attach to the Decal node from `' + eid + '_decal.tscn` to enable\n'
        '# animated UV playback. For static decals (logos, blood splats),\n'
        '# the .tscn alone (frame 0) is enough.\n'
        'extends Decal\n'
        f'class_name VFXDecalFlipbook_{eid}\n\n'
        f'const SHADER_MATERIAL := preload("res://{res_root}/godot/decal_material.tres")\n\n'
        'func _ready() -> void:\n'
        '    var quad := MeshInstance3D.new()\n'
        '    var qm := QuadMesh.new()\n'
        f'    qm.size = Vector2({world_size}, {world_size})\n'
        '    quad.mesh = qm\n'
        '    quad.material_override = SHADER_MATERIAL\n'
        '    quad.position.y = -size.y * 0.5 + 0.01\n'
        '    quad.rotation_degrees.x = -90.0\n'
        '    add_child(quad)\n'
    )
    (godot_dir / f"{eid}_decal.gd").write_text(script, encoding="utf-8")
    return str(scene_path)


def export_mesh_trail(effect: dict, manifest: dict, godot_dir: Path,
                      res_root: str) -> str:
    eid = effect["id"]
    bp = effect.get("backend_params", {})
    trail_type = bp.get("trail_type", "tube")
    radius = float(bp.get("radius", 0.08))
    segments = int(bp.get("segments", 24))
    section_length = float(bp.get("section_length", 0.05))
    scroll = float(bp.get("scroll_uv_speed", 2.5))
    blend = effect.get("visual", {}).get("blend", "additive")
    blend_mode = "add" if blend == "additive" else "mix"
    palette = effect.get("visual", {}).get("palette", ["#ffffff"])
    modulate = _palette_modulate(palette)

    shader_text = TRAIL_SHADER.format(blend_mode=blend_mode)
    (godot_dir / "trail.gdshader").write_text(shader_text, encoding="utf-8")

    flipbook_godot = f"res://{res_root}/flipbook.png"
    mat_text = (
        '[gd_resource type="ShaderMaterial" load_steps=3 format=3]\n\n'
        f'[ext_resource type="Shader" path="res://{res_root}/godot/trail.gdshader" id="1_sh"]\n'
        f'[ext_resource type="Texture2D" path="{flipbook_godot}" id="2_tex"]\n\n'
        '[resource]\n'
        'shader = ExtResource("1_sh")\n'
        'shader_parameter/albedo_tex = ExtResource("2_tex")\n'
        f'shader_parameter/scroll_uv_speed = {scroll}\n'
        f'shader_parameter/modulate = Color({modulate[0]}, {modulate[1]}, {modulate[2]}, {modulate[3]})\n'
        'shader_parameter/emission_strength = 1.2\n'
    )
    (godot_dir / "trail_material.tres").write_text(mat_text, encoding="utf-8")

    if trail_type == "ribbon":
        mesh_block = (
            '[sub_resource type="RibbonTrailMesh" id="Trail_1"]\n'
            f'size = {radius}\n'
            f'sections = {segments}\n'
            f'section_length = {section_length}\n'
            'section_segments = 4\n'
        )
    else:
        mesh_block = (
            '[sub_resource type="TubeTrailMesh" id="Trail_1"]\n'
            f'radius = {radius}\n'
            'radial_steps = 8\n'
            f'sections = {segments}\n'
            f'section_length = {section_length}\n'
            'section_rings = 2\n'
        )

    scene_text = (
        '[gd_scene load_steps=4 format=3]\n\n'
        f'[ext_resource type="ShaderMaterial" path="res://{res_root}/godot/trail_material.tres" id="1_mat"]\n'
        '[ext_resource type="Script" path="res://vfx/runtime/MeshTrail3D.gd" id="2_script"]\n\n'
        + mesh_block +
        f'\n[node name="{eid}_trail" type="MeshInstance3D"]\n'
        'mesh = SubResource("Trail_1")\n'
        'material_override = ExtResource("1_mat")\n'
        'script = ExtResource("2_script")\n'
        f'effect_id = "{eid}"\n'
    )
    scene_path = godot_dir / f"{eid}_trail.tscn"
    scene_path.write_text(scene_text, encoding="utf-8")
    return str(scene_path)


def export_fog_volume(effect: dict, manifest: dict, godot_dir: Path,
                     res_root: str, effect_dir: Path) -> str:
    """Emit a FogVolume scene that references the FogMaterial baked by
    `baker_volumetric_fog.py` (lives at <effect_dir>/fog_material.tres)."""
    eid = effect["id"]
    bp = effect.get("backend_params", {})
    extents = bp.get("extents_m", [16.0, 8.0, 16.0])
    shape_str = bp.get("fog_shape", "box")
    shape_int = {"world": 0, "box": 1, "ellipsoid": 2, "cone": 3, "cylinder": 4}.get(shape_str, 1)

    has_material = (effect_dir / "fog_material.tres").exists()
    if has_material:
        # baker_volumetric_fog now writes res://vfx/<kind>/<id>/ paths
        # directly (post 2026-05-06 fix), so no path rewriting required.
        scene_text = (
            '[gd_scene load_steps=2 format=3]\n\n'
            f'[ext_resource type="FogMaterial" path="res://{res_root}/fog_material.tres" id="1_fog"]\n\n'
            f'[node name="{eid}_fog" type="FogVolume"]\n'
            f'size = Vector3({extents[0]}, {extents[1]}, {extents[2]})\n'
            f'shape = {shape_int}\n'
            'material = ExtResource("1_fog")\n'
        )
    else:
        scene_text = (
            '[gd_scene load_steps=1 format=3]\n\n'
            f'[node name="{eid}_fog" type="FogVolume"]\n'
            f'size = Vector3({extents[0]}, {extents[1]}, {extents[2]})\n'
            f'shape = {shape_int}\n'
            '# fog_material.tres not yet baked; run baker_volumetric_fog.py first.\n'
        )
    scene_path = godot_dir / f"{eid}_fog.tscn"
    scene_path.write_text(scene_text, encoding="utf-8")
    return str(scene_path)


# --- top-level driver ------------------------------------------------------

def export_effect(effect_dir: Path, target_override: str | None = None) -> dict | None:
    eff_path = effect_dir / "effect.json"
    man_path = effect_dir / "manifest.json"
    if not eff_path.exists() or not man_path.exists():
        return None
    eff = json.loads(eff_path.read_text(encoding="utf-8"))
    man = json.loads(man_path.read_text(encoding="utf-8"))

    target = target_override or eff.get("export_target", "2d")
    if target == "2d":
        return None  # 2D exporter handles this; this module is 3D-only

    eid = eff["id"]
    kind = eff.get("kind", "spell")
    godot_dir = effect_dir / "godot"
    godot_dir.mkdir(exist_ok=True)
    res_root = f"vfx/{kind}/{eid}"

    if target == "3d_billboard":
        scene = export_3d_billboard(eff, man, godot_dir, res_root)
    elif target == "decal":
        scene = export_decal(eff, man, godot_dir, res_root)
    elif target == "mesh_trail":
        scene = export_mesh_trail(eff, man, godot_dir, res_root)
    elif target == "fog_volume":
        scene = export_fog_volume(eff, man, godot_dir, res_root, effect_dir)
    else:
        return None

    return {"id": eid, "kind": kind, "target": target, "scene": scene,
            "frames": man.get("n_frames", 0)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("effect_dir", type=Path, nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--target",
                    choices=["3d_billboard", "decal", "mesh_trail", "fog_volume"],
                    help="Override the effect.json's export_target")
    ap.add_argument("--catalog", type=Path,
                    default=Path(r"D:\assets\vfx\catalog"))
    args = ap.parse_args()

    if args.all:
        ok = 0
        skipped = 0
        for d in sorted(args.catalog.rglob("effect.json")):
            try:
                info = export_effect(d.parent, args.target)
                if info is None:
                    skipped += 1
                    continue
                print(f"[export_3d] {info['id']:32s} ({info['kind']}) "
                      f"-> {info['target']:12s} {info['scene']}")
                ok += 1
            except Exception as e:
                print(f"[export_3d] FAILED {d.parent}: {e}")
        print(f"[export_3d] exported {ok} 3D scenes ({skipped} 2D-only skipped)")
        return 0
    if not args.effect_dir:
        ap.error("provide effect_dir or --all")
    info = export_effect(args.effect_dir, args.target)
    if info:
        print(f"[export_3d] {info['id']} -> {info['target']} -> {info['scene']}")
    else:
        print(f"[export_3d] {args.effect_dir} skipped (export_target=2d)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
