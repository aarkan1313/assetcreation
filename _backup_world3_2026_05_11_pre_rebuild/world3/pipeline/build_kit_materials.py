"""Generate one terrain_blend_<kit>.tres per biome kit defined in
world3/jobs/biome_kits.json.

Each emitted .tres is a Godot ShaderMaterial that binds the 5 PBR map
slots (albedo/normal/roughness for grass/dirt/rock_light/rock_dark/snow)
to the textures referenced by the kit's slot table, and sets the
height-band uniforms from the kit's `height_bands` block.

Run this whenever biome_kits.json changes or new textures are staged.

Usage:
    python world3/pipeline/build_kit_materials.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\assets\world3")
BIOME_KITS = ROOT / "jobs" / "biome_kits.json"
MATERIAL_CATALOG = ROOT / "materials" / "catalog.json"
OUT_DIR = ROOT / "textures" / "wgv3"

# Slot order matches terrain_blend.gdshader uniforms.
SLOTS = ["grass", "dirt", "rock_light", "rock_dark", "snow"]
MAPS = ["albedo", "normal", "roughness"]


def load_catalog() -> dict[str, dict]:
    if not MATERIAL_CATALOG.exists():
        return {}
    data = json.loads(MATERIAL_CATALOG.read_text(encoding="utf-8"))
    return {m["id"]: m for m in data.get("materials", [])}


def runtime_dir_name(material_id: str, catalog: dict[str, dict]) -> str:
    entry = catalog.get(material_id, {})
    runtime_texture_dir = entry.get("runtime_texture_dir")
    if runtime_texture_dir:
        return Path(runtime_texture_dir).name
    return material_id


def material_tres(kit_name: str, kit: dict, catalog: dict[str, dict]) -> str:
    """Render a Godot 4 .tres ShaderMaterial that binds this kit."""
    slots = kit["slots"]
    bands = kit.get("height_bands", {})
    slope = float(kit.get("slope_threshold", 0.45))

    # Collect ext_resources: shader + 15 textures (5 slots × 3 maps)
    ext_lines = []
    ext_lines.append('[ext_resource type="Shader" path="res://shaders/terrain_blend.gdshader" id="shader"]')
    res_id_for: dict[tuple[str, str], str] = {}
    counter = 1
    for slot in SLOTS:
        tex_id = slots[slot]
        tex_dir = runtime_dir_name(tex_id, catalog)
        for m in MAPS:
            res_id = f"r{counter}"
            counter += 1
            path = f"res://textures/wgv3/{tex_dir}/{m}.png"
            ext_lines.append(f'[ext_resource type="Texture2D" path="{path}" id="{res_id}"]')
            res_id_for[(slot, m)] = res_id

    n_steps = 1 + 5 * 3  # shader + 15 textures
    header = f'[gd_resource type="ShaderMaterial" load_steps={n_steps + 1} format=3]\n\n'
    body = "\n".join(ext_lines) + "\n\n[resource]\nshader = ExtResource(\"shader\")\n"

    # Bind shader_parameters
    binds = []
    for slot in SLOTS:
        for m in MAPS:
            uniform = f"{slot}_albedo" if m == "albedo" else (
                      f"{slot}_normal" if m == "normal" else f"{slot}_rough")
            binds.append(f'shader_parameter/{uniform} = ExtResource("{res_id_for[(slot, m)]}")')

    # Defaults / common uniforms (match terrain_blend.gdshader uniform defaults).
    binds += [
        "shader_parameter/world_uv_scale = 0.1",
        "shader_parameter/hex_strength = 1.0",
        "shader_parameter/blend_sharpness = 8.0",
        "shader_parameter/normal_strength = 1.0",
        "shader_parameter/macro_scale = 80.0",
        "shader_parameter/macro_value_strength = 0.15",
        # elev_min_m / elev_range_m get pushed at runtime by Terrain.gd.
        "shader_parameter/elev_min_m = 0.0",
        "shader_parameter/elev_range_m = 1.0",
        f"shader_parameter/slope_threshold = {slope}",
        "shader_parameter/slope_softness = 0.15",
        f'shader_parameter/h_grass_dirt = {float(bands.get("h_grass_dirt", 0.20))}',
        f'shader_parameter/h_dirt_rockdark = {float(bands.get("h_dirt_rockdark", 0.55))}',
        f'shader_parameter/h_rockdark_snow = {float(bands.get("h_rockdark_snow", 0.85))}',
        "shader_parameter/h_band_softness = 0.08",
    ]
    return header + body + "\n".join(binds) + "\n"


def main():
    data = json.loads(BIOME_KITS.read_text(encoding="utf-8"))
    catalog = load_catalog()
    kits = data["kits"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for kit_name, kit in kits.items():
        body = material_tres(kit_name, kit, catalog)
        out = OUT_DIR / f"terrain_blend_{kit_name}.tres"
        out.write_text(body, encoding="utf-8")
        print(f"  wrote {out.relative_to(ROOT)} (slots: {list(kit['slots'].values())})")


if __name__ == "__main__":
    main()
