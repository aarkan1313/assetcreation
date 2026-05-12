"""W4 biome materials emitter.

Generates one ShaderMaterial .tres per new biome (alpine, desert, rocky,
wetland). Mirrors write_material_tres_scale_v1.py but binds the 3 slots
from materials/biome_<name>/<slot>/ instead of materials/anchor_v2/<...>/.

Each biome uses the terrain_scale_v1.gdshader and inherits the same safety
floors (albedo_luma_floor, ao_floor). Per-biome tints adjust the
sky/ground ambient warmth so each biome reads in its own atmosphere.

The existing material_scale_v1.tres (temperate forest) stays the default
binding for scale_demo and is NOT overwritten by this script.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path("D:/assets")
W4_ROOT = ROOT / "world 4" / "the world 4"
SCALE_DIR = W4_ROOT / "worlds" / "scale_demo"
BIOMES_DIR = SCALE_DIR / "biomes"

SLOTS = ["ground", "mid", "rock"]
MAPS = ["albedo", "normal", "rough", "ao"]
MAP_FILES = {
    "albedo": "albedo",
    "normal": "normal",
    "rough":  "roughness",
    "ao":     "ao",
}

# Per-biome ambient tinting. Sky tint is what the upward-facing surfaces
# pick up; ground tint is the bounce light on downward-facing surfaces.
# Tints are subtle — actual color comes from the textures.
BIOME_TINTS = {
    "alpine": {
        # Cold overcast sky, dark slate bounce
        "sky_tint":     (0.78, 0.86, 0.96),
        "ground_tint":  (0.55, 0.58, 0.62),
        "sun_color":    (0.98, 0.97, 0.96),
    },
    "desert": {
        # Warm clear sky, hot reflective sand bounce
        "sky_tint":     (0.86, 0.88, 0.92),
        "ground_tint":  (0.75, 0.65, 0.50),
        "sun_color":    (1.00, 0.95, 0.82),
    },
    "rocky": {
        # Cool low-sat sky, dust-grey bounce
        "sky_tint":     (0.78, 0.82, 0.88),
        "ground_tint":  (0.58, 0.58, 0.55),
        "sun_color":    (1.00, 0.96, 0.88),
    },
    "wetland": {
        # Hazy muted sky, dark damp ground bounce
        "sky_tint":     (0.74, 0.80, 0.84),
        "ground_tint":  (0.45, 0.48, 0.45),
        "sun_color":    (0.96, 0.95, 0.90),
    },
}


def res(path: Path) -> str:
    rel = path.resolve().relative_to(W4_ROOT.resolve())
    return "res://" + rel.as_posix()


def ext(kind: str, path: str, ident: str) -> str:
    return f'[ext_resource type="{kind}" path="{path}" id="{ident}"]'


def col(rgb) -> str:
    r, g, b = rgb
    return f"Color({r:.2f}, {g:.2f}, {b:.2f}, 1.0)"


def emit_biome_material(biome: str) -> Path:
    shader_path = W4_ROOT / "shaders" / "terrain_scale_v1.gdshader"
    if not shader_path.exists():
        raise SystemExit(f"ERROR: shader missing {shader_path}")

    tint = BIOME_TINTS[biome]
    biome_root = W4_ROOT / "materials" / f"biome_{biome}"

    ext_lines = [ext("Shader", res(shader_path), "shader")]
    res_ident_for: dict[tuple[str, str], str] = {}

    for slot in SLOTS:
        for kind in MAPS:
            file_name = MAP_FILES[kind]
            tex_path = biome_root / slot / f"{file_name}.png"
            if not tex_path.exists():
                raise SystemExit(f"ERROR: missing texture {tex_path}")
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
        f'shader_parameter/sun_color = {col(tint["sun_color"])}',
        "shader_parameter/sun_intensity = 1.0",
        "shader_parameter/lambert_floor = 0.35",
        f'shader_parameter/sky_tint = {col(tint["sky_tint"])}',
        f'shader_parameter/ground_tint = {col(tint["ground_tint"])}',
        "shader_parameter/ambient_strength = 0.45",
    ]
    for slot in SLOTS:
        for kind in MAPS:
            uniform = f"{slot}_{kind}"
            lines.append(f'shader_parameter/{uniform} = ExtResource("{res_ident_for[(slot, kind)]}")')

    out_path = BIOMES_DIR / f"material_{biome}.tres"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  wrote {out_path}")
    return out_path


def main() -> int:
    print("[biomes/tres] emitting 4 biome materials")
    for biome in BIOME_TINTS:
        emit_biome_material(biome)
    print("[biomes/tres] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
