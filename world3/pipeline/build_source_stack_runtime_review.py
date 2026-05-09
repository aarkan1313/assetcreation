#!/usr/bin/env python3
"""Build source-stack runtime review assets.

This is the first visual-remediation bridge between the OpenTopo source-stack
work and the streamed runtime shader path:

- source-derived macro albedo anchors the terrain color;
- clean tileable OpenTopo material maps provide close detail;
- the output material still uses terrain_splat_unified.gdshader so M4/M5/M7 can
  reuse the same runtime contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
CATALOG = ROOT / "materials" / "catalog.json"
CANDIDATE_CATALOG = ROOT / "materials" / "catalog_repair_candidates.json"
OUT_TEXTURES = ROOT / "textures" / "source_stack"
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


def load_catalog(extra_catalogs: list[Path]) -> dict[str, dict]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog = {entry["id"]: entry for entry in data.get("materials", [])}
    for path in extra_catalogs:
        if not path.exists():
            continue
        extra = json.loads(path.read_text(encoding="utf-8"))
        for entry in extra.get("materials", []):
            catalog[entry["id"]] = entry
    return catalog


def res_path(raw_path: str | Path) -> str:
    path = Path(str(raw_path).replace("\\", "/"))
    if path.is_absolute():
        rel = path.resolve().relative_to(ROOT.resolve())
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


def material_maps(material_id: str, catalog: dict[str, dict]) -> dict[str, str]:
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


def ext_resource(kind: str, path: str, ident: str) -> str:
    return f'[ext_resource type="{kind}" path="{path}" id="{ident}"]'


def downsample_macro(source: Path, out_path: Path, max_side: int) -> None:
    img = Image.open(source).convert("RGB")
    width, height = img.size
    scale = min(1.0, float(max_side) / float(max(width, height)))
    out_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    if out_size != img.size:
        img = img.resize(out_size, Image.Resampling.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def material_tres(
    *,
    macro_albedo: Path,
    detail_material: str,
    catalog: dict[str, dict],
    source_macro_strength: float = 1.0,
    normal_strength_override: float | None = None,
    detail_albedo_strength_override: float | None = None,
    detail_normal_strength_override: float | None = None,
    detail_rough_strength_override: float | None = None,
) -> str:
    ext_lines = [
        ext_resource("Shader", "res://shaders/terrain_splat_unified.gdshader", "shader"),
        ext_resource("Texture2D", res_path(macro_albedo), "source_macro_albedo"),
    ]
    maps = material_maps(detail_material, catalog)
    res_id_for: dict[tuple[str, str], str] = {}
    for slot in SLOTS:
        for kind in [*BASE_MAPS, *DETAIL_MAPS]:
            ident = f"{slot}_{SHORT_MAP[kind]}"
            ext_lines.append(ext_resource("Texture2D", maps[kind], ident))
            res_id_for[(slot, kind)] = ident

    lines = [
        f'[gd_resource type="ShaderMaterial" load_steps={len(ext_lines) + 1} format=3]',
        "",
        *ext_lines,
        "",
        "[resource]",
        'shader = ExtResource("shader")',
        'shader_parameter/source_macro_albedo = ExtResource("source_macro_albedo")',
        "shader_parameter/use_source_macro_albedo = true",
        f"shader_parameter/source_macro_strength = {source_macro_strength}",
    ]
    for slot in SLOTS:
        for kind in [*BASE_MAPS, *DETAIL_MAPS]:
            uniform = f"{slot}_{SHORT_MAP[kind]}"
            lines.append(f'shader_parameter/{uniform} = ExtResource("{res_id_for[(slot, kind)]}")')

    settings = catalog[detail_material].get("provenance", {}).get("settings", {})
    values = {
        "use_splat_weights": "false",
        "splat_uv_scale": 1.0,
        "splat_weight_power": 1.0,
        "world_uv_scale": float(settings.get("world_uv_scale", 0.015625)),
        "hex_strength": float(settings.get("hex_strength", 1.0)),
        "blend_sharpness": float(settings.get("blend_sharpness", 8.0)),
        "roughness_strength": float(settings.get("roughness_strength", 1.0)),
        "normal_strength": (
            normal_strength_override
            if normal_strength_override is not None
            else min(float(settings.get("normal_strength", 0.20)), 0.14)
        ),
        "macro_scale": 180.0,
        "macro_value_strength": 0.0,
        "macro_hue_strength": 0.0,
        "detail_uv_scale_mult": float(settings.get("detail_uv_scale_mult", 8.0)),
        "detail_albedo_strength": (
            detail_albedo_strength_override
            if detail_albedo_strength_override is not None
            else min(float(settings.get("detail_albedo_strength", 0.14)), 0.075)
        ),
        "detail_normal_strength": (
            detail_normal_strength_override
            if detail_normal_strength_override is not None
            else min(float(settings.get("detail_normal_strength", 0.16)), 0.09)
        ),
        "detail_rough_strength": (
            detail_rough_strength_override
            if detail_rough_strength_override is not None
            else min(float(settings.get("detail_rough_strength", 0.12)), 0.06)
        ),
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
        if isinstance(value, str):
            lines.append(f"shader_parameter/{key} = {value}")
        else:
            lines.append(f"shader_parameter/{key} = {value}")
    return "\n".join(lines) + "\n"


def write_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--stack",
        default=str(ROOT / "toporeview/gloss_mountain_textured_master"),
        type=Path,
    )
    ap.add_argument("--detail-material", default="scrub_sparse")
    ap.add_argument("--id", default="gloss_scrub_source_stack")
    ap.add_argument("--max-macro-side", type=int, default=2048)
    ap.add_argument("--source-macro-strength", type=float, default=1.0)
    ap.add_argument("--normal-strength", type=float, default=None)
    ap.add_argument("--detail-albedo-strength", type=float, default=None)
    ap.add_argument("--detail-normal-strength", type=float, default=None)
    ap.add_argument("--detail-rough-strength", type=float, default=None)
    ap.add_argument(
        "--extra-catalog",
        action="append",
        default=[str(CANDIDATE_CATALOG)],
        help="Optional sidecar material catalog; defaults to repair candidates if present.",
    )
    args = ap.parse_args()

    catalog = load_catalog([Path(p) for p in args.extra_catalog])
    stack = args.stack
    source_macro = stack / "layers" / "render_albedo.png"
    if not source_macro.exists():
        raise FileNotFoundError(source_macro)
    if args.detail_material not in catalog:
        raise KeyError(args.detail_material)

    macro_out = OUT_TEXTURES / args.id / "source_macro_albedo.png"
    material_out = OUT_MATERIALS / f"terrain_source_stack_{args.id}.tres"
    manifest_out = OUT_TEXTURES / args.id / "manifest.json"
    downsample_macro(source_macro, macro_out, args.max_macro_side)
    material_out.parent.mkdir(parents=True, exist_ok=True)
    material_out.write_text(
        material_tres(
            macro_albedo=macro_out,
            detail_material=args.detail_material,
            catalog=catalog,
            source_macro_strength=args.source_macro_strength,
            normal_strength_override=args.normal_strength,
            detail_albedo_strength_override=args.detail_albedo_strength,
            detail_normal_strength_override=args.detail_normal_strength,
            detail_rough_strength_override=args.detail_rough_strength,
        ),
        encoding="utf-8",
    )
    write_manifest(
        manifest_out,
        {
            "version": 1,
            "kind": "source_stack_runtime_review",
            "id": args.id,
            "source_stack": res_path(stack),
            "source_macro": res_path(source_macro),
            "runtime_macro": res_path(macro_out),
            "material": res_path(material_out),
            "detail_material": args.detail_material,
            "target": "70_percent_of_best_photo_topo_stack_reference",
            "policy": "source_macro_albedo_first_tileable_detail_second",
            "source_macro_strength": args.source_macro_strength,
            "detail_albedo_strength_override": args.detail_albedo_strength,
            "detail_normal_strength_override": args.detail_normal_strength,
            "detail_rough_strength_override": args.detail_rough_strength,
            "normal_strength_override": args.normal_strength,
        },
    )
    print(f"wrote {macro_out.relative_to(REPO)}")
    print(f"wrote {material_out.relative_to(REPO)}")
    print(f"wrote {manifest_out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
