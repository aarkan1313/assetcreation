"""Anchor demo — Phase 4: emit Godot ShaderMaterial .tres for the anchor bundle.

Binds the terrain_anchor.gdshader + 5 slot materials (each with 4 PBR maps)
+ the bundle's macro + valid_mask + splat. The .tres is what the Godot scene
will load and apply as material_override on the terrain mesh.

Writes:
  - worlds/anchor/material.tres
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path("D:/assets")
W4_ROOT = ROOT / "world 4" / "the world 4"
ANCHOR_DIR = W4_ROOT / "worlds" / "anchor"

# Slot bindings (matches build_splat_and_macro.py)
SLOTS = ["grass", "dirt", "rock_light", "rock_dark", "snow"]
SLOT_MATERIALS = {
    "grass":      "temperate_forest_grass",
    "dirt":       "temperate_forest_dirt",
    "rock_light": "temperate_forest_rock_light",
    "rock_dark":  "temperate_forest_rock_dark",
    "snow":       "temperate_forest_snow",
}
MAPS = ["albedo", "normal", "rough", "ao"]
MAP_FILES = {  # map name → file basename in the material dir
    "albedo":    "albedo",
    "normal":    "normal",
    "rough":     "roughness",
    "ao":        "ao",
}

# ----------------------------------------------------------------------

def res(path: Path) -> str:
    """W4 Godot project root is `D:/assets/world 4/the world 4/`. Convert
    any path under that to a res:// path."""
    rel = path.resolve().relative_to(W4_ROOT.resolve())
    return "res://" + rel.as_posix()


def ext(kind: str, path: str, ident: str) -> str:
    return f'[ext_resource type="{kind}" path="{path}" id="{ident}"]'


def main() -> int:
    macro_path = ANCHOR_DIR / "layers" / "render_albedo.png"
    valid_mask_path = ANCHOR_DIR / "layers" / "source_valid_mask.png"
    splat_path = ANCHOR_DIR / "layers" / "splat_weights_rgba.png"
    shader_path = W4_ROOT / "shaders" / "terrain_anchor.gdshader"

    # Verify all sources exist
    for p in [macro_path, valid_mask_path, splat_path, shader_path]:
        if not p.exists():
            print(f"ERROR: missing {p}")
            return 1

    ext_lines = [
        ext("Shader", res(shader_path), "shader"),
        ext("Texture2D", res(macro_path), "source_macro_albedo"),
        ext("Texture2D", res(valid_mask_path), "source_macro_valid_mask"),
        ext("Texture2D", res(splat_path), "splat_weights"),
    ]
    res_ident_for: dict[tuple[str, str], str] = {}

    # 5 slots × 4 maps = 20 texture bindings
    for slot in SLOTS:
        mat_id = SLOT_MATERIALS[slot]
        for kind in MAPS:
            file_name = MAP_FILES[kind]
            tex_path = W4_ROOT / "materials" / "anchor" / mat_id / f"{file_name}.png"
            if not tex_path.exists():
                print(f"ERROR: missing texture {tex_path}")
                return 1
            ident = f"{slot}_{kind}"
            ext_lines.append(ext("Texture2D", res(tex_path), ident))
            res_ident_for[(slot, kind)] = ident

    # ----------------------------------------------------------------------
    # Compose the .tres
    # ----------------------------------------------------------------------

    lines = [
        f'[gd_resource type="ShaderMaterial" load_steps={len(ext_lines) + 1} format=3]',
        "",
        *ext_lines,
        "",
        "[resource]",
        'shader = ExtResource("shader")',
        # Macro
        "shader_parameter/use_source_macro_albedo = true",
        'shader_parameter/source_macro_albedo = ExtResource("source_macro_albedo")',
        # W3 proven values (from world3/pipeline/f33_bundle_material.py).
        # Do NOT change these without a single-knob A/B capture cycle —
        # this is the M11 fourway tuning that was validated through
        # iterative review. Most of my earlier values were 5-20x off
        # from these. Anchor inherits these as the production baseline.
        "shader_parameter/source_macro_strength = 0.76",
        "shader_parameter/use_source_macro_valid_mask = true",
        'shader_parameter/source_macro_valid_mask = ExtResource("source_macro_valid_mask")',
        "shader_parameter/source_world_size_m = Vector2(256, 256)",
        # Splat
        "shader_parameter/use_splat_weights = true",
        'shader_parameter/splat_weights = ExtResource("splat_weights")',
        "shader_parameter/splat_weight_power = 1.48",  # W3: blend_sharpness 8.0 maps to this range
        # Global — W3 production values
        "shader_parameter/world_uv_scale = 0.012",  # W3 proven
        "shader_parameter/roughness_strength = 1.0",
        "shader_parameter/specular_strength = 0.5",  # W3 proven (was 0.0)
        "shader_parameter/albedo_gain = 1.0",  # W3 proven (was 1.35)
        "shader_parameter/normal_strength = 0.054",  # W3 proven — my 0.35 was ~6.5x too high
        "shader_parameter/roughness_floor = 0.04",  # W3 proven — was 0.85, crushing all variation
    ]

    # 20 slot texture bindings
    for slot in SLOTS:
        for kind in MAPS:
            uniform = f"{slot}_{kind}"
            lines.append(f'shader_parameter/{uniform} = ExtResource("{res_ident_for[(slot, kind)]}")')

    out_path = ANCHOR_DIR / "material.tres"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    print(f"[anchor/tres] wrote {out_path}")
    print(f"  shader:    {res(shader_path)}")
    print(f"  macro:     {res(macro_path)}")
    print(f"  splat:     {res(splat_path)}")
    print(f"  5 slots x 4 maps = 20 textures bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
