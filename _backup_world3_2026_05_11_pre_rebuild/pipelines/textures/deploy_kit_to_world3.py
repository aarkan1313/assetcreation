"""Copy Phase-D kit textures from world/textures/library/<id>/ into
world3/textures/wgv3/<slot>/ so the terrain_blend_<kit>.tres ShaderMaterials
and catalog/runtime review tools can resolve them via Godot's res:// resource
path.

The .tres files use logical slot names (`grass`, `dirt`, `rock_light`,
`rock_dark`, `snow`) and reference fixed paths like
`res://textures/wgv3/grass/albedo.png`. To swap a kit, the .tres needs
new paths — but the simpler approach for new kits is to create
per-kit subdirectories so each kit owns its own slot folders
(e.g. `wgv3/temperate_forest_grass/albedo.png`) and rebuild the .tres
to point at them.

Usage:
    python pipelines/textures/deploy_kit_to_world3.py --kit temperate_forest
    python pipelines/textures/deploy_kit_to_world3.py --kit grassland
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIBRARY = REPO / "world" / "textures" / "library"
WGV3 = REPO / "world3" / "textures" / "wgv3"
KITS_JSON = REPO / "world3" / "jobs" / "biome_kits.json"
CATALOG_JSON = REPO / "world3" / "materials" / "catalog.json"

# Per-kit slot -> catalog-material-id mapping is read from biome_kits.json.
# Source generator ids and runtime dirs resolve through materials/catalog.json.
# The .tres generator below writes per-kit slot dirs with the full PBR map set:
#   world3/textures/wgv3/<kit>_<slot>/{albedo,normal,roughness,metallic,height,ao}.png
# This avoids clobbering the existing alpine slot dirs that other kits
# (alpine, desert, tundra) reference at fixed paths.

# Map .tres -> <kit>_<slot> dirs vs alpine-default dirs. Alpine/desert/tundra
# use the original paths; new kits get prefixed slots.
NEW_KITS = {"temperate_forest", "grassland"}
MAP_KINDS = ("albedo", "normal", "roughness", "metallic", "height", "ao")


def load_kit(kit_name: str) -> dict:
    data = json.loads(KITS_JSON.read_text(encoding="utf-8"))
    return data["kits"][kit_name]


def load_catalog() -> dict[str, dict]:
    if not CATALOG_JSON.exists():
        return {}
    data = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    return {m["id"]: m for m in data.get("materials", [])}


def source_asset_id(material_id: str, catalog: dict[str, dict]) -> str:
    entry = catalog.get(material_id, {})
    provenance = entry.get("provenance", {})
    return provenance.get("source_asset_id") or material_id


def runtime_dir_name(material_id: str, kit_name: str, slot: str, catalog: dict[str, dict]) -> str:
    entry = catalog.get(material_id, {})
    runtime_texture_dir = entry.get("runtime_texture_dir")
    if runtime_texture_dir:
        return Path(runtime_texture_dir).name
    return f"{kit_name}_{slot}"


def deploy_textures(kit_name: str, kit: dict, catalog: dict[str, dict]) -> dict[str, Path]:
    """Copy library/<source_id>/<source_id>_<map>.png into the catalog
    runtime dir. Returns mapping of slot -> runtime dir name."""
    out_dirs: dict[str, Path] = {}
    for slot, material_id in kit["slots"].items():
        source_id = source_asset_id(material_id, catalog)
        src_dir = LIBRARY / source_id
        if not src_dir.exists():
            print(f"  ! missing: {src_dir}", file=sys.stderr)
            continue
        # Target: catalog runtime dir (e.g. temperate_forest_grass)
        dst_slot = runtime_dir_name(material_id, kit_name, slot, catalog)
        dst_dir = WGV3 / dst_slot
        dst_dir.mkdir(parents=True, exist_ok=True)
        for map_kind in MAP_KINDS:
            src = src_dir / f"{source_id}_{map_kind}.png"
            if not src.exists():
                print(f"  ! missing map: {src}", file=sys.stderr)
                continue
            dst = dst_dir / f"{map_kind}.png"
            shutil.copy2(src, dst)
        print(f"  {slot} ({material_id} <= {source_id}) -> wgv3/{dst_slot}/")
        out_dirs[slot] = Path(dst_slot)
    return out_dirs


def write_tres(kit_name: str, kit: dict, slot_dirs: dict[str, Path]) -> Path:
    """Rewrite world3/textures/wgv3/terrain_blend_<kit>.tres with kit's
    height bands and the deployed slot-dir paths."""
    bands = kit["height_bands"]
    slot_threshold = kit.get("slope_threshold", 0.45)

    def slot_path(slot: str, kind: str) -> str:
        sub = slot_dirs[slot]
        return f"res://textures/wgv3/{sub.as_posix()}/{kind}.png"

    lines = [
        '[gd_resource type="ShaderMaterial" load_steps=17 format=3]',
        '',
        '[ext_resource type="Shader" path="res://shaders/terrain_blend.gdshader" id="shader"]',
    ]
    rid = 1
    res_ids: dict[tuple[str, str], str] = {}
    for slot in ("grass", "dirt", "rock_light", "rock_dark", "snow"):
        for kind in ("albedo", "normal", "roughness"):
            ident = f"r{rid}"
            res_ids[(slot, kind)] = ident
            lines.append(
                f'[ext_resource type="Texture2D" path="{slot_path(slot, kind)}" id="{ident}"]'
            )
            rid += 1
    lines += ['', '[resource]', 'shader = ExtResource("shader")']
    short = {"albedo": "albedo", "normal": "normal", "roughness": "rough"}
    for slot in ("grass", "dirt", "rock_light", "rock_dark", "snow"):
        for kind in ("albedo", "normal", "roughness"):
            lines.append(
                f'shader_parameter/{slot}_{short[kind]} = ExtResource("{res_ids[(slot, kind)]}")'
            )
    # Standard shader params (keep parity with alpine.tres defaults).
    lines += [
        'shader_parameter/world_uv_scale = 0.1',
        'shader_parameter/hex_strength = 1.0',
        'shader_parameter/blend_sharpness = 8.0',
        'shader_parameter/normal_strength = 1.0',
        'shader_parameter/macro_scale = 80.0',
        'shader_parameter/macro_value_strength = 0.15',
        'shader_parameter/elev_min_m = 0.0',
        'shader_parameter/elev_range_m = 1.0',
        f'shader_parameter/slope_threshold = {slot_threshold}',
        'shader_parameter/slope_softness = 0.15',
        f'shader_parameter/h_grass_dirt = {bands["h_grass_dirt"]}',
        f'shader_parameter/h_dirt_rockdark = {bands["h_dirt_rockdark"]}',
        f'shader_parameter/h_rockdark_snow = {bands["h_rockdark_snow"]}',
        'shader_parameter/h_band_softness = 0.08',
    ]
    out = WGV3 / f"terrain_blend_{kit_name}.tres"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {out.relative_to(REPO)}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True, choices=sorted(NEW_KITS))
    args = ap.parse_args()

    kit = load_kit(args.kit)
    catalog = load_catalog()
    print(f"deploying kit={args.kit}: {list(kit['slots'].items())}")
    slot_dirs = deploy_textures(args.kit, kit, catalog)
    if len(slot_dirs) != 5:
        print(f"  abort: only {len(slot_dirs)}/5 slots resolved", file=sys.stderr)
        return 2
    write_tres(args.kit, kit, slot_dirs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
