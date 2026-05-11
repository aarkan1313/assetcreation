"""F.3.3 — per-bundle .tres material writer.

Following M11 fourway's pattern, emit a complete ShaderMaterial .tres
per bundle binding the biome kit's 5 slot materials. Each slot has
4 base maps + 3 detail maps from the catalog.

Public API:
  write_bundle_material(path, source_macro, source_macro_weight_mask,
                        splat_weights, biome_kit, catalog_path=None)

Output: a .tres file that uses terrain_splat_unified.gdshader and
binds 5 catalog materials to (grass, dirt, rock_light, rock_dark, snow)
shader slots, plus the bundle's macro + weight_mask + splat_weights.

Per-biome-kit slot assignments are defined in BIOME_KIT_SLOTS below.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]  # world3/
DEFAULT_CATALOG = ROOT / "materials" / "catalog.json"

SLOTS = ["grass", "dirt", "rock_light", "rock_dark", "snow"]
BASE_MAPS = ["albedo", "normal", "roughness", "ao"]
DETAIL_MAPS = ["detail_albedo", "detail_normal", "detail_roughness"]
SHORT_MAP = {
    "albedo": "albedo",
    "normal": "normal",
    "roughness": "rough",
    "ao": "ao",
    "detail_albedo": "detail_albedo",
    "detail_normal": "detail_normal",
    "detail_roughness": "detail_rough",
}

# Per-biome-kit slot material assignment. Each kit binds 5 catalog
# materials to the shader's 5 slots. The splat weights then decide
# which slot dominates per pixel (height/slope driven by default;
# crossfade with neighbor biome at tile boundaries when applicable).
BIOME_KIT_SLOTS: dict[str, dict[str, str]] = {
    "tundra": {
        "grass": "tundra_moss",
        "dirt": "tundra_lichen",
        "rock_light": "tundra_frost_rock",
        "rock_dark": "tundra_dark_rock",
        "snow": "tundra_ice",
    },
    "desert": {
        "grass": "desert_dry_brush",
        "dirt": "desert_sand",
        "rock_light": "desert_canyon_rock",
        "rock_dark": "desert_dark_rock",
        "snow": "desert_salt_pan",
    },
    "alpine": {
        "grass": "grass",
        "dirt": "dirt",
        "rock_light": "rock_light",
        "rock_dark": "rock_dark",
        "snow": "snow",
    },
    "grassland": {
        "grass": "grassland_grass",
        "dirt": "grassland_dirt",
        "rock_light": "grassland_rock_light",
        "rock_dark": "grassland_rock_dark",
        "snow": "grassland_snow",
    },
    "temperate_forest": {
        "grass": "temperate_forest_grass",
        "dirt": "temperate_forest_dirt",
        "rock_light": "temperate_forest_rock_light",
        "rock_dark": "temperate_forest_rock_dark",
        "snow": "temperate_forest_snow",
    },
}


def _res_path(raw_path: str | Path) -> str:
    path = Path(str(raw_path).replace("\\", "/"))
    if path.is_absolute():
        rel = path.resolve().relative_to(ROOT.resolve())
        return "res://" + rel.as_posix()
    parts = path.parts
    if parts and parts[0] == "world3":
        return "res://" + Path(*parts[1:]).as_posix()
    return "res://" + path.as_posix()


def _catalog_map(entry: dict, kind: str, fallback_kind: str | None = None) -> str:
    maps = entry.get("pbr_maps", {})
    raw = maps.get(kind)
    if raw is None and fallback_kind is not None:
        raw = maps.get(fallback_kind)
    if raw is None:
        raise KeyError(f"{entry.get('id')} is missing pbr map {kind}")
    return _res_path(raw)


def _material_maps(material_id: str, catalog: dict[str, dict]) -> dict[str, str]:
    if material_id not in catalog:
        raise KeyError(f"material '{material_id}' not in catalog")
    entry = catalog[material_id]
    return {
        "albedo": _catalog_map(entry, "albedo"),
        "normal": _catalog_map(entry, "normal"),
        "roughness": _catalog_map(entry, "roughness"),
        "ao": _catalog_map(entry, "ao", "albedo"),
        "detail_albedo": _catalog_map(entry, "detail_albedo", "albedo"),
        "detail_normal": _catalog_map(entry, "detail_normal", "normal"),
        "detail_roughness": _catalog_map(entry, "detail_roughness", "roughness"),
    }


def _load_catalog(catalog_path: Path | None) -> dict[str, dict]:
    path = catalog_path if catalog_path is not None else DEFAULT_CATALOG
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data.get("materials", [])}


def _ext_line(kind: str, path: str, ident: str) -> str:
    return f'[ext_resource type="{kind}" path="{path}" id="{ident}"]'


def write_bundle_material(
    out_path: Path,
    source_macro: Path,
    source_macro_weight_mask: Path,
    splat_weights: Path,
    biome_kit: str,
    catalog_path: Path | None = None,
) -> None:
    """Write a complete per-bundle ShaderMaterial .tres.

    The .tres binds:
    - The bundle's source_macro_albedo + source_macro_weight_mask + splat_weights
    - 5 catalog materials × 7 maps each (35 textures) bound to the shader's
      grass/dirt/rock_light/rock_dark/snow slots
    """
    if biome_kit not in BIOME_KIT_SLOTS:
        raise KeyError(f"biome_kit '{biome_kit}' not in BIOME_KIT_SLOTS")
    slot_materials = BIOME_KIT_SLOTS[biome_kit]
    catalog = _load_catalog(catalog_path)

    ext_lines: list[str] = [
        _ext_line("Shader", "res://shaders/terrain_splat_unified.gdshader", "shader"),
        _ext_line("Texture2D", _res_path(source_macro), "source_macro_albedo"),
        _ext_line("Texture2D", _res_path(source_macro_weight_mask), "source_macro_valid_mask"),
        _ext_line("Texture2D", _res_path(splat_weights), "splat_weights"),
    ]
    res_id_for: dict[tuple[str, str], str] = {}
    for slot in SLOTS:
        material_id = slot_materials[slot]
        maps = _material_maps(material_id, catalog)
        for kind in [*BASE_MAPS, *DETAIL_MAPS]:
            ident = f"{slot}_{SHORT_MAP[kind]}"
            ext_lines.append(_ext_line("Texture2D", maps[kind], ident))
            res_id_for[(slot, kind)] = ident

    lines = [
        f'[gd_resource type="ShaderMaterial" load_steps={len(ext_lines) + 1} format=3]',
        "",
        *ext_lines,
        "",
        "[resource]",
        'shader = ExtResource("shader")',
        # Source macro binding
        "shader_parameter/use_source_macro_albedo = true",
        'shader_parameter/source_macro_albedo = ExtResource("source_macro_albedo")',
        "shader_parameter/source_macro_strength = 0.76",
        "shader_parameter/use_source_macro_valid_mask = true",
        'shader_parameter/source_macro_valid_mask = ExtResource("source_macro_valid_mask")',
        "shader_parameter/use_source_macro_world_uv = true",
        # Splat weights
        "shader_parameter/use_splat_weights = true",
        'shader_parameter/splat_weights = ExtResource("splat_weights")',
        "shader_parameter/splat_uv_scale = 1.0",
        "shader_parameter/splat_weight_power = 1.48",
    ]
    # All 35 slot texture bindings
    for slot in SLOTS:
        for kind in [*BASE_MAPS, *DETAIL_MAPS]:
            uniform = f"{slot}_{SHORT_MAP[kind]}"
            lines.append(f'shader_parameter/{uniform} = ExtResource("{res_id_for[(slot, kind)]}")')

    # Standard scalar params from M11 fourway tuning
    values: dict[str, float] = {
        "world_uv_scale": 0.012,
        "hex_strength": 1.0,
        "blend_sharpness": 8.0,
        "roughness_strength": 1.0,
        "normal_strength": 0.054,
        "macro_scale": 180.0,
        "macro_value_strength": 0.0,
        "macro_hue_strength": 0.0,
        "detail_uv_scale_mult": 11.0,
        "detail_albedo_strength": 0.030,
        "detail_normal_strength": 0.030,
        "detail_rough_strength": 0.025,
        "detail_fade_start_m": 6.0,
        "detail_fade_end_m": 52.0,
        "elev_min_m": 0.0,
        "elev_range_m": 1.0,
        "slope_threshold": 1.0,
        "slope_softness": 0.15,
        "h_grass_dirt": 0.2,
        "h_dirt_rockdark": 0.55,
        "h_rockdark_snow": 0.85,
        "h_band_softness": 0.08,
    }
    for key, value in values.items():
        lines.append(f"shader_parameter/{key} = {value}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
