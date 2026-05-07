"""Shader Lab: parameterized Godot shader generator + preview renderer.

Per the G deep dive: don't use an "AI shader generator" — write Godot shader
templates ourselves and let the LLM fill JSON parameters. Every accepted
shader has a PNG preview, optional flipbook atlas, and a .tscn scene.

Workflow:
  1. LLM writes a request JSON (or human passes an existing one)
  2. This tool reads the template, substitutes uniforms, writes:
       <id>/<id>.gdshader
       <id>/<id>.tscn
       <id>/request.json (provenance)
       <id>/preview.png
       <id>/flipbook.png   (optional, if flipbook frames > 1)
  3. Godot 4.5 renders the previews via headless CLI

Templates currently shipping (in art_lab/shaders/templates/):
  - ring_field_2d        magic circles, rune rings, portal rings
  - beam_lightning_2d    lightning bolts, energy beams, slashes
  - dissolve_fire_2d     burn-edge dissolve effect for sprites/panels
  - shield_ripple_2d     hex shield with hit ripples
  - portal_swirl_2d      spiraling portal vortex

Request JSON shape:
  {
    "id": "arcane_shield_ring",
    "template": "ring_field_2d",
    "params": {
      "color_inner": [0.33, 0.84, 1.0],
      "radius": 0.42,
      "edge_width": 0.04,
      ...
    },
    "preview": {
      "size": [512, 512],
      "frames": 32,         # 1 = single still; >1 = animated flipbook
      "duration_s": 2.0,
      "background": [0.05, 0.05, 0.08, 1.0]
    }
  }

Usage:
  python shader_compile_preview.py --request request.json
  python shader_compile_preview.py --template ring_field_2d --id ring_test
      (uses each template's default params)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

LAB_ROOT = Path(r"D:\assets\art_lab")
TEMPLATES_DIR = LAB_ROOT / "shaders" / "templates"
GENERATED_DIR = LAB_ROOT / "shaders" / "generated"


GD_PROJECT = """\
config_version=5

[application]
config/name="ShaderLabPreview"
config/features=PackedStringArray("4.5")

[rendering]
renderer/rendering_method="forward_plus"
"""


def render_scene(shader_id: str, shader_path: Path, size: tuple[int, int],
                 background: list[float], frames: int, duration_s: float) -> str:
    """Build a Godot 4 .tscn that displays the shader on a fullscreen ColorRect."""
    bg = ", ".join(f"{c:.4f}" for c in background)
    w, h = size
    return f"""[gd_scene load_steps=4 format=3 uid="uid://{shader_id}_preview"]

[ext_resource type="Shader" path="res://{shader_id}.gdshader" id="1"]

[sub_resource type="ShaderMaterial" id="ShaderMaterial_1"]
shader = ExtResource("1")

[sub_resource type="GDScript" id="GDScript_1"]
script/source = "extends Node\\nfunc _ready():\\n\\tget_window().size = Vector2i({w}, {h})\\n\\tget_window().borderless = true"

[node name="Root" type="Node"]
script = SubResource("GDScript_1")

[node name="Background" type="ColorRect" parent="."]
anchor_right = 1.0
anchor_bottom = 1.0
color = Color({bg})

[node name="Quad" type="ColorRect" parent="."]
anchor_right = 1.0
anchor_bottom = 1.0
material = SubResource("ShaderMaterial_1")
"""


def find_shader_uniforms(shader_text: str) -> dict[str, dict]:
    """Parse `uniform <type> <name> [: hint] = <default>;` lines."""
    pattern = re.compile(
        r'uniform\s+(\w+)\s+(\w+)(\s*:\s*(?:hint_range\([^)]+\)|source_color))?\s*(?:=\s*([^;]+))?;'
    )
    uniforms = {}
    for line in shader_text.splitlines():
        m = pattern.search(line)
        if m:
            t, name, hint, default = m.groups()
            uniforms[name] = {
                "type": t,
                "hint": (hint or "").strip(),
                "default": (default or "").strip(),
            }
    return uniforms


def serialize_param(name: str, value, uniform_info: dict) -> str:
    """Format a value as Godot text-resource literal for a uniform."""
    t = uniform_info["type"]
    if t == "vec3":
        if isinstance(value, list) and len(value) == 3:
            return f'shader_parameter/{name} = Color({value[0]}, {value[1]}, {value[2]}, 1.0)'
        raise ValueError(f"{name}: expected list[3] for vec3")
    if t == "vec2":
        return f'shader_parameter/{name} = Vector2({value[0]}, {value[1]})'
    if t == "vec4":
        v = list(value)
        return f'shader_parameter/{name} = Color({v[0]}, {v[1]}, {v[2]}, {v[3]})'
    if t == "float":
        return f"shader_parameter/{name} = {float(value)}"
    if t == "int":
        return f"shader_parameter/{name} = {int(value)}"
    if t == "bool":
        return f'shader_parameter/{name} = {str(bool(value)).lower()}'
    return f'shader_parameter/{name} = {value}'


def build_scene_with_params(shader_id: str, shader_text: str, params: dict,
                             size: tuple[int, int], background: list[float]) -> str:
    """Embed params into the ShaderMaterial sub_resource."""
    uniforms = find_shader_uniforms(shader_text)
    bg = ", ".join(f"{c:.4f}" for c in background)
    w, h = size

    param_lines = []
    for name, value in params.items():
        if name not in uniforms:
            print(f"  warning: unknown uniform '{name}' ignored")
            continue
        param_lines.append(serialize_param(name, value, uniforms[name]))
    param_block = "\n".join(param_lines)

    return f"""[gd_scene load_steps=4 format=3 uid="uid://{shader_id}_preview"]

[ext_resource type="Shader" path="res://{shader_id}.gdshader" id="1"]

[sub_resource type="ShaderMaterial" id="ShaderMaterial_1"]
shader = ExtResource("1")
{param_block}

[sub_resource type="GDScript" id="GDScript_1"]
script/source = "extends Node
func _ready():
\tget_window().size = Vector2i({w}, {h})
\tget_window().borderless = true
\tawait get_tree().create_timer(0.5).timeout
\tvar img = get_viewport().get_texture().get_image()
\timg.save_png(\\"user://preview.png\\")
\tget_tree().quit()
"

[node name="Root" type="Node"]
script = SubResource("GDScript_1")

[node name="Background" type="ColorRect" parent="."]
anchor_right = 1.0
anchor_bottom = 1.0
color = Color({bg})

[node name="Quad" type="ColorRect" parent="."]
anchor_right = 1.0
anchor_bottom = 1.0
material = SubResource("ShaderMaterial_1")
"""


def render_preview(godot_exe: Path, project_dir: Path, scene_name: str,
                   out_png: Path, headless: bool = True) -> bool:
    """Run Godot headless; the embedded GDScript saves a PNG and quits."""
    if not godot_exe.exists():
        print(f"  godot not found at {godot_exe}; skipping render")
        return False

    cmd = [str(godot_exe), "--path", str(project_dir), "--quit-after", "120",
           "--quiet", scene_name + ".tscn"]
    if headless:
        cmd.append("--headless")

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        print("  godot timed out")
        return False

    # Godot writes to user:// which on Windows resolves to %APPDATA%\Godot\app_userdata\<projectname>
    user_data = Path.home() / "AppData" / "Roaming" / "Godot" / "app_userdata" / "ShaderLabPreview"
    saved = user_data / "preview.png"
    if saved.exists():
        shutil.move(str(saved), str(out_png))
        return True

    if result.returncode != 0:
        print(f"  godot returned {result.returncode}")
        if result.stderr:
            print(f"  stderr: {result.stderr.decode(errors='ignore')[:500]}")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", type=Path, help="JSON request file")
    ap.add_argument("--template", help="(no request) template name")
    ap.add_argument("--id", help="(no request) output id")
    ap.add_argument("--godot-exe", type=Path,
                    default=Path(r"C:\Program Files\Godot\Godot_v4.5-stable_win64.exe"),
                    help="Godot binary for preview render (optional)")
    ap.add_argument("--no-render", action="store_true",
                    help="Skip Godot preview render (just emit files)")
    args = ap.parse_args()

    # Load request
    if args.request:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        shader_id = request["id"]
        template_name = request["template"]
        params = request.get("params", {})
        preview_cfg = request.get("preview", {})
    else:
        if not args.template or not args.id:
            raise SystemExit("provide --request OR (--template AND --id)")
        shader_id = args.id
        template_name = args.template
        params = {}
        preview_cfg = {}

    template_path = TEMPLATES_DIR / f"{template_name}.gdshader"
    if not template_path.exists():
        raise SystemExit(f"template not found: {template_path}")

    out_dir = GENERATED_DIR / shader_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy shader (with optional comment header)
    shader_text = template_path.read_text(encoding="utf-8")
    shader_out = out_dir / f"{shader_id}.gdshader"
    shader_out.write_text(
        f"// Generated {datetime.now(timezone.utc).isoformat()} from template {template_name}\n"
        + shader_text,
        encoding="utf-8"
    )
    print(f"  wrote {shader_out.name}")

    # Build .tscn
    size = tuple(preview_cfg.get("size", [512, 512]))
    background = preview_cfg.get("background", [0.05, 0.05, 0.08, 1.0])
    scene = build_scene_with_params(shader_id, shader_text, params, size, background)
    scene_path = out_dir / f"{shader_id}.tscn"
    scene_path.write_text(scene, encoding="utf-8")
    print(f"  wrote {scene_path.name}")

    # Project file
    (out_dir / "project.godot").write_text(GD_PROJECT, encoding="utf-8")

    # Provenance
    request_record = {
        "id": shader_id,
        "template": template_name,
        "params": params,
        "preview": preview_cfg,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "request.json").write_text(json.dumps(request_record, indent=2), encoding="utf-8")

    # Optional preview render
    if not args.no_render and args.godot_exe.exists():
        preview_path = out_dir / "preview.png"
        ok = render_preview(args.godot_exe, out_dir, shader_id, preview_path)
        if ok:
            print(f"  rendered preview -> {preview_path.name}")
        else:
            print(f"  preview render failed; .gdshader and .tscn still written")
    else:
        print(f"  preview render skipped (use --godot-exe or install Godot 4.5)")

    print(f"\ndone: {out_dir}")


if __name__ == "__main__":
    main()
