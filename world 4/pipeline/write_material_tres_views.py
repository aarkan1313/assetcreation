"""Emit per-view materials for scale_demo (Axis 4).

Two new materials:
- material_view_iso.tres  → terrain_view_iso.gdshader (flatter lambertian,
                            form light)
- material_view_topdown.tres → terrain_view_topdown.gdshader (cartographic
                                hillshade, sepia)

The walk view continues to use the existing material_scale_v1.tres. We
don't regenerate that here.
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


def emit(shader_filename: str, out_filename: str, extra_params: dict[str, str]) -> int:
    shader_path = W4_ROOT / "shaders" / shader_filename
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

    # Shared base params (common to walk + iso + topdown).
    base_params: dict[str, str] = {
        "slope_ground_max": "0.92",
        "slope_rock_max": "0.55",
        "world_uv_scale": "0.04",
        "albedo_luma_floor": "0.08",
        "ao_floor": "0.72",
    }
    params: dict[str, str] = {**base_params, **extra_params}

    lines = [
        f'[gd_resource type="ShaderMaterial" load_steps={len(ext_lines) + 1} format=3]',
        "",
        *ext_lines,
        "",
        "[resource]",
        'shader = ExtResource("shader")',
    ]
    for name, value in params.items():
        lines.append(f'shader_parameter/{name} = {value}')
    for slot in SLOTS:
        for kind in MAPS:
            uniform = f"{slot}_{kind}"
            lines.append(f'shader_parameter/{uniform} = ExtResource("{res_ident_for[(slot, kind)]}")')

    out_path = SCALE_DIR / out_filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    print(f"[views/tres] wrote {out_path}")
    return 0


def main() -> int:
    # ISO — flatter lambertian, form light pushes hills forward.
    iso_params: dict[str, str] = {
        "sun_dir": "Vector3(0.30, 0.85, 0.43)",
        "sun_color": "Color(1.0, 0.96, 0.88, 1.0)",
        "sun_intensity": "0.5",
        "lambert_floor": "0.55",
        "sky_tint": "Color(0.80, 0.86, 0.94, 1.0)",
        "ground_tint": "Color(0.62, 0.64, 0.58, 1.0)",
        "ambient_strength": "0.65",
        "form_light_strength": "0.18",
    }
    rc = emit("terrain_view_iso.gdshader", "material_view_iso.tres", iso_params)
    if rc != 0:
        return rc

    # Topdown — map style, hillshade replaces lambertian.
    topdown_params: dict[str, str] = {
        "hillshade_dir": "Vector3(-0.45, 0.78, 0.43)",
        "hillshade_min": "0.55",
        "hillshade_max": "1.20",
        "sepia_amount": "0.25",
        "sepia_color": "Color(0.96, 0.88, 0.74, 1.0)",
        "saturation": "1.10",
    }
    rc = emit("terrain_view_topdown.gdshader", "material_view_topdown.tres", topdown_params)
    if rc != 0:
        return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
