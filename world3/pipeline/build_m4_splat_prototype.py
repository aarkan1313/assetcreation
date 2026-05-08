"""Build the M4 unified splat-shader prototype assets.

Outputs:
  - world3/textures/m4_splat/alpine_height_slope_weights_rgba.png
  - world3/textures/m4_splat/alpine_height_slope_weights_debug.png
  - world3/textures/wgv3/terrain_splat_alpine.tres
  - world3/textures/wgv3/terrain_splat_alpine_fallback.tres
  - world3/textures/wgv3/terrain_splat_scrub_sparse_single.tres
  - world3/textures/wgv3/terrain_hex_detail_scrub_sparse_reference.tres

The splat texture uses RGBA for the first four semantic kit slots:
grass, dirt, rock_light, rock_dark. The snow slot is reconstructed in
the shader as max(1 - rgba_sum, 0).
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
CATALOG = ROOT / "materials" / "catalog.json"
BIOME_KITS = ROOT / "jobs" / "biome_kits.json"
HEIGHTMAP = ROOT / "heightmap" / "heightmap.png"
META = ROOT / "heightmap" / "meta.json"
OUT_TEXTURES = ROOT / "textures" / "m4_splat"
OUT_MATERIALS = ROOT / "textures" / "wgv3"

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


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    if abs(edge1 - edge0) < 1e-8:
        return 1.0 if value >= edge1 else 0.0
    x = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return x * x * (3.0 - 2.0 * x)


def load_catalog() -> dict[str, dict]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data.get("materials", [])}


def load_kits() -> dict:
    return json.loads(BIOME_KITS.read_text(encoding="utf-8"))["kits"]


def load_meta() -> dict:
    return json.loads(META.read_text(encoding="utf-8"))


def res_path(raw_path: str | Path) -> str:
    path = Path(str(raw_path).replace("\\", "/"))
    if path.is_absolute():
        rel = path.relative_to(ROOT)
        return "res://" + rel.as_posix()
    parts = path.parts
    if parts and parts[0] == "world3":
        return "res://" + Path(*parts[1:]).as_posix()
    return "res://" + path.as_posix()


def catalog_map(entry: dict, kind: str, fallback_kind: str | None = None) -> str:
    maps = entry.get("pbr_maps", {})
    raw = maps.get(kind)
    if raw is None and fallback_kind is not None:
        raw = maps.get(fallback_kind)
    if raw is None:
        raise KeyError(f"{entry.get('id')} is missing pbr map {kind}")
    return res_path(raw)


def material_slot_maps(material_id: str, catalog: dict[str, dict]) -> dict[str, str]:
    entry = catalog[material_id]
    return {
        "albedo": catalog_map(entry, "albedo"),
        "normal": catalog_map(entry, "normal"),
        "roughness": catalog_map(entry, "roughness"),
        "ao": catalog_map(entry, "ao", "albedo"),
        "detail_albedo": catalog_map(entry, "detail_albedo", "albedo"),
        "detail_normal": catalog_map(entry, "detail_normal", "normal"),
        "detail_roughness": catalog_map(entry, "detail_roughness", "roughness"),
    }


def height_slope_weights(h: float, slope: float, kit: dict) -> tuple[float, float, float, float, float]:
    bands = kit.get("height_bands", {})
    slope_threshold = float(kit.get("slope_threshold", 0.45))
    slope_softness = 0.15
    h_grass_dirt = float(bands.get("h_grass_dirt", 0.20))
    h_dirt_rockdark = float(bands.get("h_dirt_rockdark", 0.55))
    h_rockdark_snow = float(bands.get("h_rockdark_snow", 0.85))
    h_band_softness = 0.08

    w_slope = smoothstep(slope_threshold - slope_softness, slope_threshold + slope_softness, slope)
    gd = h_band_softness
    band_grass = 1.0 - smoothstep(h_grass_dirt - gd, h_grass_dirt + gd, h)
    band_snow = smoothstep(h_rockdark_snow - gd, h_rockdark_snow + gd, h)
    low_dirt = smoothstep(h_grass_dirt - gd, h_grass_dirt + gd, h)
    high_dirt = 1.0 - smoothstep(h_dirt_rockdark - gd, h_dirt_rockdark + gd, h)
    band_dirt = low_dirt * high_dirt
    low_rd = smoothstep(h_dirt_rockdark - gd, h_dirt_rockdark + gd, h)
    high_rd = 1.0 - smoothstep(h_rockdark_snow - gd, h_rockdark_snow + gd, h)
    band_rockdark = low_rd * high_rd

    keep = 1.0 - w_slope
    weights = [
        band_grass * keep,
        band_dirt * keep,
        w_slope,
        band_rockdark * keep,
        band_snow * keep,
    ]
    total = sum(weights) + 1e-6
    return tuple(w / total for w in weights)


def load_height_norms() -> list[list[float]]:
    img = Image.open(HEIGHTMAP)
    if img.mode not in ("I", "I;16", "I;16B", "I;16L", "F"):
        img = img.convert("F")
    width, height = img.size
    px = img.load()
    max_value = 65535.0 if "16" in img.mode or img.mode == "I" else 1.0
    rows: list[list[float]] = []
    for y in range(height):
        row: list[float] = []
        for x in range(width):
            value = float(px[x, y])
            if value > 1.0:
                value /= max_value
            row.append(max(0.0, min(1.0, value)))
        rows.append(row)
    return rows


def generate_splat_weights(kit_name: str, kit: dict) -> tuple[Path, Path, dict[str, float]]:
    meta = load_meta()
    rows = load_height_norms()
    height = len(rows)
    width = len(rows[0])
    world_size = float(meta.get("world_size_m", 1024.0))
    world_x = float(meta.get("world_size_x_m", world_size))
    world_z = float(meta.get("world_size_z_m", world_size))
    elev_range = float(meta.get("elevation_range_m", 1.0))
    dx = world_x / max(1.0, float(width - 1))
    dz = world_z / max(1.0, float(height - 1))

    rgba = Image.new("RGBA", (width, height))
    debug = Image.new("RGB", (width, height))
    rgba_px = rgba.load()
    dbg_px = debug.load()
    totals = [0.0, 0.0, 0.0, 0.0, 0.0]
    colors = [
        (52, 145, 68),
        (137, 99, 51),
        (166, 155, 137),
        (78, 76, 72),
        (230, 235, 238),
    ]

    for y in range(height):
        ym = max(y - 1, 0)
        yp = min(y + 1, height - 1)
        for x in range(width):
            xm = max(x - 1, 0)
            xp = min(x + 1, width - 1)
            h = rows[y][x]
            dhx = ((rows[y][xp] - rows[y][xm]) * elev_range) / max(float(xp - xm), 1.0) / dx
            dhz = ((rows[yp][x] - rows[ym][x]) * elev_range) / max(float(yp - ym), 1.0) / dz
            normal_y = 1.0 / math.sqrt(dhx * dhx + dhz * dhz + 1.0)
            slope = 1.0 - max(0.0, min(1.0, normal_y))
            weights = height_slope_weights(h, slope, kit)
            for idx, value in enumerate(weights):
                totals[idx] += value
            rgba_px[x, y] = tuple(int(round(max(0.0, min(1.0, weights[i])) * 255.0)) for i in range(4))
            dbg_px[x, y] = tuple(
                int(round(sum(weights[i] * colors[i][channel] for i in range(5))))
                for channel in range(3)
            )

    out_rgba = OUT_TEXTURES / f"{kit_name}_height_slope_weights_rgba.png"
    out_debug = OUT_TEXTURES / f"{kit_name}_height_slope_weights_debug.png"
    OUT_TEXTURES.mkdir(parents=True, exist_ok=True)
    rgba.save(out_rgba)
    debug.save(out_debug)
    total_px = float(width * height)
    stats = {SLOTS[i]: totals[i] / total_px for i in range(5)}
    return out_rgba, out_debug, stats


def make_ext_resource(kind: str, path: str, ident: str) -> str:
    return f'[ext_resource type="{kind}" path="{path}" id="{ident}"]'


def material_tres(
    *,
    slot_materials: dict[str, str],
    kit: dict,
    catalog: dict[str, dict],
    use_splat: bool,
    splat_path: Path | None,
    settings: dict[str, float] | None = None,
) -> str:
    settings = settings or {}
    ext_lines: list[str] = [
        make_ext_resource("Shader", "res://shaders/terrain_splat_unified.gdshader", "shader")
    ]

    res_id_for: dict[tuple[str, str], str] = {}
    for slot in SLOTS:
        maps = material_slot_maps(slot_materials[slot], catalog)
        for kind in [*BASE_MAPS, *DETAIL_MAPS]:
            ident = f"{slot}_{SHORT_MAP[kind]}"
            ext_lines.append(make_ext_resource("Texture2D", maps[kind], ident))
            res_id_for[(slot, kind)] = ident

    lines = [
        f'[gd_resource type="ShaderMaterial" load_steps={len(ext_lines) + 1} format=3]',
        "",
        *ext_lines,
        "",
        "[resource]",
        'shader = ExtResource("shader")',
    ]
    for slot in SLOTS:
        for kind in [*BASE_MAPS, *DETAIL_MAPS]:
            uniform = f"{slot}_{SHORT_MAP[kind]}"
            lines.append(f'shader_parameter/{uniform} = ExtResource("{res_id_for[(slot, kind)]}")')

    bands = kit.get("height_bands", {})
    common: list[str] = [
        f"shader_parameter/use_splat_weights = {'true' if use_splat else 'false'}",
        "shader_parameter/splat_uv_scale = 1.0",
        "shader_parameter/splat_weight_power = 1.0",
        f"shader_parameter/world_uv_scale = {float(settings.get('world_uv_scale', 0.1))}",
        f"shader_parameter/hex_strength = {float(settings.get('hex_strength', 1.0))}",
        f"shader_parameter/blend_sharpness = {float(settings.get('blend_sharpness', 8.0))}",
        f"shader_parameter/roughness_strength = {float(settings.get('roughness_strength', 1.0))}",
        f"shader_parameter/normal_strength = {float(settings.get('normal_strength', 1.0))}",
        f"shader_parameter/macro_scale = {float(settings.get('macro_scale', 80.0))}",
        f"shader_parameter/macro_value_strength = {float(settings.get('macro_value_strength', 0.15))}",
        f"shader_parameter/macro_hue_strength = {float(settings.get('macro_hue_strength', 0.0))}",
        f"shader_parameter/detail_uv_scale_mult = {float(settings.get('detail_uv_scale_mult', 8.0))}",
        f"shader_parameter/detail_albedo_strength = {float(settings.get('detail_albedo_strength', 0.0))}",
        f"shader_parameter/detail_normal_strength = {float(settings.get('detail_normal_strength', 0.0))}",
        f"shader_parameter/detail_rough_strength = {float(settings.get('detail_rough_strength', 0.0))}",
        f"shader_parameter/detail_fade_start_m = {float(settings.get('detail_fade_start_m', 8.0))}",
        f"shader_parameter/detail_fade_end_m = {float(settings.get('detail_fade_end_m', 30.0))}",
        "shader_parameter/elev_min_m = 0.0",
        "shader_parameter/elev_range_m = 1.0",
        f"shader_parameter/slope_threshold = {float(kit.get('slope_threshold', 0.45))}",
        "shader_parameter/slope_softness = 0.15",
        f"shader_parameter/h_grass_dirt = {float(bands.get('h_grass_dirt', 0.20))}",
        f"shader_parameter/h_dirt_rockdark = {float(bands.get('h_dirt_rockdark', 0.55))}",
        f"shader_parameter/h_rockdark_snow = {float(bands.get('h_rockdark_snow', 0.85))}",
        "shader_parameter/h_band_softness = 0.08",
    ]
    lines.extend(common)
    return "\n".join(lines) + "\n"


def hex_detail_reference_tres(material_id: str, catalog: dict[str, dict]) -> str:
    entry = catalog[material_id]
    maps = material_slot_maps(material_id, catalog)
    settings = entry.get("provenance", {}).get("settings", {})
    ext_lines = [
        make_ext_resource("Shader", "res://shaders/terrain_hex_detail.gdshader", "shader"),
        make_ext_resource("Texture2D", maps["albedo"], "albedo"),
        make_ext_resource("Texture2D", maps["normal"], "normal"),
        make_ext_resource("Texture2D", maps["roughness"], "rough"),
        make_ext_resource("Texture2D", maps["ao"], "ao"),
        make_ext_resource("Texture2D", maps["detail_albedo"], "detail_albedo"),
        make_ext_resource("Texture2D", maps["detail_normal"], "detail_normal"),
        make_ext_resource("Texture2D", maps["detail_roughness"], "detail_rough"),
    ]
    lines = [
        f'[gd_resource type="ShaderMaterial" load_steps={len(ext_lines) + 1} format=3]',
        "",
        *ext_lines,
        "",
        "[resource]",
        'shader = ExtResource("shader")',
        'shader_parameter/albedo_tex = ExtResource("albedo")',
        'shader_parameter/normal_tex = ExtResource("normal")',
        'shader_parameter/rough_tex = ExtResource("rough")',
        'shader_parameter/ao_tex = ExtResource("ao")',
        'shader_parameter/detail_albedo_tex = ExtResource("detail_albedo")',
        'shader_parameter/detail_normal_tex = ExtResource("detail_normal")',
        'shader_parameter/detail_rough_tex = ExtResource("detail_rough")',
    ]
    for key in [
        "world_uv_scale",
        "hex_strength",
        "blend_sharpness",
        "roughness_strength",
        "normal_strength",
        "macro_scale",
        "macro_value_strength",
        "macro_hue_strength",
        "detail_uv_scale_mult",
        "detail_albedo_strength",
        "detail_normal_strength",
        "detail_rough_strength",
        "detail_fade_start_m",
        "detail_fade_end_m",
    ]:
        lines.append(f"shader_parameter/{key} = {float(settings[key])}")
    return "\n".join(lines) + "\n"


def write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    print(f"wrote {path.relative_to(REPO)}")


def build(kit_name: str, single_material: str) -> None:
    catalog = load_catalog()
    kits = load_kits()
    kit = kits[kit_name]
    splat_path, debug_path, stats = generate_splat_weights(kit_name, kit)
    print(f"wrote {splat_path.relative_to(REPO)}")
    print(f"wrote {debug_path.relative_to(REPO)}")
    print("average weights: " + ", ".join(f"{slot}={stats[slot]:.3f}" for slot in SLOTS))

    slot_materials = dict(kit["slots"])
    write_text(
        OUT_MATERIALS / f"terrain_splat_{kit_name}.tres",
        material_tres(
            slot_materials=slot_materials,
            kit=kit,
            catalog=catalog,
            use_splat=True,
            splat_path=splat_path,
        ),
    )
    write_text(
        OUT_MATERIALS / f"terrain_splat_{kit_name}_fallback.tres",
        material_tres(
            slot_materials=slot_materials,
            kit=kit,
            catalog=catalog,
            use_splat=False,
            splat_path=splat_path,
        ),
    )

    single_entry = catalog[single_material]
    single_settings = single_entry.get("provenance", {}).get("settings", {})
    single_slots = {slot: single_material for slot in SLOTS}
    write_text(
        OUT_MATERIALS / f"terrain_splat_{single_material}_single.tres",
        material_tres(
            slot_materials=single_slots,
            kit=kit,
            catalog=catalog,
            use_splat=False,
            splat_path=None,
            settings=single_settings,
        ),
    )
    write_text(
        OUT_MATERIALS / f"terrain_hex_detail_{single_material}_reference.tres",
        hex_detail_reference_tres(single_material, catalog),
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kit", default="alpine")
    parser.add_argument("--single-material", default="scrub_sparse")
    args = parser.parse_args(argv)
    build(args.kit, args.single_material)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
