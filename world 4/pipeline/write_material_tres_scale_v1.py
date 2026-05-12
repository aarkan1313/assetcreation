"""Scale demo v1 — emit material.tres bound to terrain_scale_v1.gdshader.

Same 3-slot binding as v2, but the shader is `unshaded` and does its own
lighting math — Godot's PBR pipeline is bypassed entirely to sidestep the
black-patch artifact bug. See terrain_scale_v1.gdshader for context.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path("D:/assets")
W4_ROOT = ROOT / "world 4" / "the world 4"
SCALE_DIR = W4_ROOT / "worlds" / "scale_demo"

SLOTS = ["ground", "mid", "rock"]
SLOT_MATERIALS = {
    "ground": "scrub_dense",
    "mid":    "tundra_lichen",
    "rock":   "rocky_slope",
}
MAPS = ["albedo", "normal", "rough", "ao"]
MAP_FILES = {
    "albedo":  "albedo",
    "normal":  "normal",
    "rough":   "roughness",
    "ao":      "ao",
}


def res(path: Path) -> str:
    rel = path.resolve().relative_to(W4_ROOT.resolve())
    return "res://" + rel.as_posix()


def ext(kind: str, path: str, ident: str) -> str:
    return f'[ext_resource type="{kind}" path="{path}" id="{ident}"]'


def main() -> int:
    shader_path = W4_ROOT / "shaders" / "terrain_scale_v1.gdshader"
    if not shader_path.exists():
        print(f"ERROR: shader missing {shader_path}")
        return 1

    ext_lines = [ext("Shader", res(shader_path), "shader")]
    res_ident_for: dict[tuple[str, str], str] = {}

    for slot in SLOTS:
        mat_id = SLOT_MATERIALS[slot]
        for kind in MAPS:
            file_name = MAP_FILES[kind]
            tex_path = W4_ROOT / "materials" / "anchor_v2" / mat_id / f"{file_name}.png"
            if not tex_path.exists():
                print(f"ERROR: missing texture {tex_path}")
                return 1
            ident = f"{slot}_{kind}"
            ext_lines.append(ext("Texture2D", res(tex_path), ident))
            res_ident_for[(slot, kind)] = ident

    lines = [
        f'[gd_resource type="ShaderMaterial" load_steps={len(ext_lines) + 1} format=3]',
        "",
        *ext_lines,
        "",
        "[resource]",
        'shader = ExtResource("shader")',
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
    for slot in SLOTS:
        for kind in MAPS:
            uniform = f"{slot}_{kind}"
            lines.append(f'shader_parameter/{uniform} = ExtResource("{res_ident_for[(slot, kind)]}")')

    out_path = SCALE_DIR / "material_scale_v1.tres"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    print(f"[scale v1/tres] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
