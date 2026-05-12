"""Emit the single global terrain material .tres for the new transitions
shader. Binds the shader + lighting uniform defaults. Texture arrays are
NOT bound here — ScaleWorld constructs them at runtime from the layer
manifest and sets them as shader parameters on a per-tile duplicate of
this material (along with the per-tile splat + index uniforms).

Usage:
    python write_global_terrain_material.py \\
        --w4-root "D:/assets/world 4/the world 4" \\
        --out     "worlds/scale_demo/material_world_v2.tres"
"""
from __future__ import annotations
import argparse
from pathlib import Path


SHADER_REL = "shaders/terrain_world_v2.gdshader"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--w4-root", required=True)
    ap.add_argument("--out", required=True,
                    help="Output .tres path relative to w4-root")
    args = ap.parse_args()

    w4 = Path(args.w4_root)
    lines = [
        '[gd_resource type="ShaderMaterial" load_steps=2 format=3]',
        "",
        f'[ext_resource type="Shader" path="res://{SHADER_REL}" id="shader"]',
        "",
        "[resource]",
        'shader = ExtResource("shader")',
        # Lighting + slope + safety defaults (mirror terrain_scale_v1).
        "shader_parameter/slope_ground_max = 0.92",
        "shader_parameter/slope_rock_max = 0.55",
        "shader_parameter/world_uv_scale = 0.04",
        "shader_parameter/albedo_luma_floor = 0.08",
        "shader_parameter/ao_floor = 0.72",
        "shader_parameter/sun_dir = Vector3(0.30, 0.85, 0.43)",
        'shader_parameter/sun_color = Color(1.0, 0.96, 0.88, 1.0)',
        "shader_parameter/sun_intensity = 1.0",
        "shader_parameter/lambert_floor = 0.35",
        'shader_parameter/sky_tint = Color(0.78, 0.84, 0.92, 1.0)',
        'shader_parameter/ground_tint = Color(0.58, 0.60, 0.55, 1.0)',
        "shader_parameter/ambient_strength = 0.45",
    ]
    out_path = w4 / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
