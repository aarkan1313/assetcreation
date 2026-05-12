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

from PIL import Image, ImageChops, ImageFilter, ImageStat


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


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def discover_valid_mask(stack: Path, explicit_mask: Path | None, policy: str) -> Path | None:
    if policy == "none":
        return None
    if explicit_mask is not None:
        if not explicit_mask.exists():
            raise FileNotFoundError(explicit_mask)
        return explicit_mask

    layers = stack / "layers"
    for name in ["texture_coverage_mask.png", "source_valid_mask.png"]:
        candidate = layers / name
        if candidate.exists():
            return candidate

    fill_mask = layers / "render_fill_mask.png"
    if fill_mask.exists():
        return fill_mask
    return None


def _mask_for_runtime(mask_path: Path | None, size: tuple[int, int]) -> Image.Image | None:
    if mask_path is None:
        return None
    mask = Image.open(mask_path).convert("L")
    if mask_path.name == "render_fill_mask.png":
        mask = ImageChops.invert(mask)
    if mask.size != size:
        mask = mask.resize(size, Image.Resampling.LANCZOS)
    return mask


def _mask_coverage(mask: Image.Image | None) -> float | None:
    if mask is None:
        return None
    return float(ImageStat.Stat(mask).mean[0]) / 255.0


def _repair_invalid_macro_pixels(
    img: Image.Image,
    mask: Image.Image | None,
    edge_bleed_px: int,
) -> Image.Image:
    if mask is None:
        return img

    valid = mask.point(lambda v: 255 if v >= 128 else 0)
    if valid.getbbox() is None:
        return img

    invalid = ImageChops.invert(valid)
    if invalid.getbbox() is None:
        return img

    repaired = img.copy()
    grown = valid.copy()
    for _ in range(max(0, edge_bleed_px)):
        expanded = grown.filter(ImageFilter.MaxFilter(3))
        ring = ImageChops.subtract(expanded, grown)
        if ring.getbbox() is None:
            break
        neighbor_average = repaired.filter(ImageFilter.BoxBlur(1))
        repaired.paste(neighbor_average, mask=ring)
        grown = expanded
        if ImageChops.invert(grown).getbbox() is None:
            break

    remaining_invalid = ImageChops.invert(grown)
    if remaining_invalid.getbbox() is not None:
        stat = ImageStat.Stat(img, valid)
        mean = tuple(int(round(channel)) for channel in stat.mean[:3])
        repaired.paste(Image.new("RGB", img.size, mean), mask=remaining_invalid)
    return repaired


def downsample_macro(
    source: Path,
    out_path: Path,
    max_side: int,
    *,
    valid_mask_path: Path | None,
    valid_mask_out: Path | None,
    edge_bleed_px: int,
) -> dict:
    img = Image.open(source).convert("RGB")
    width, height = img.size
    scale = min(1.0, float(max_side) / float(max(width, height)))
    out_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    if out_size != img.size:
        img = img.resize(out_size, Image.Resampling.LANCZOS)
    runtime_mask = _mask_for_runtime(valid_mask_path, out_size)
    img = _repair_invalid_macro_pixels(img, runtime_mask, edge_bleed_px)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    if runtime_mask is not None and valid_mask_out is not None:
        valid_mask_out.parent.mkdir(parents=True, exist_ok=True)
        runtime_mask.save(valid_mask_out)
    coverage = _mask_coverage(runtime_mask)
    return {
        "width": out_size[0],
        "height": out_size[1],
        "valid_coverage": coverage,
        "invalid_coverage": None if coverage is None else 1.0 - coverage,
    }


def material_tres(
    *,
    macro_albedo: Path,
    macro_valid_mask: Path | None,
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
    if macro_valid_mask is not None:
        ext_lines.append(
            ext_resource("Texture2D", res_path(macro_valid_mask), "source_macro_valid_mask")
        )
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
    if macro_valid_mask is not None:
        lines.extend(
            [
                'shader_parameter/source_macro_valid_mask = ExtResource("source_macro_valid_mask")',
                "shader_parameter/use_source_macro_valid_mask = true",
            ]
        )
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
    write_text_lf(path, json.dumps(data, indent=2) + "\n")


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
        "--source-macro-mask-policy",
        choices=["auto", "none"],
        default="auto",
        help="Use source-stack validity masks for macro albedo contribution.",
    )
    ap.add_argument(
        "--source-macro-valid-mask",
        default=None,
        type=Path,
        help="Optional explicit validity mask. Defaults to texture coverage/source valid mask discovery.",
    )
    ap.add_argument(
        "--source-macro-edge-bleed-px",
        type=int,
        default=24,
        help="Pixels of valid-color bleed into invalid macro areas before save.",
    )
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
    macro_valid_mask = discover_valid_mask(
        stack,
        args.source_macro_valid_mask,
        args.source_macro_mask_policy,
    )
    macro_valid_mask_out = (
        OUT_TEXTURES / args.id / "source_macro_valid_mask.png"
        if macro_valid_mask is not None
        else None
    )
    material_out = OUT_MATERIALS / f"terrain_source_stack_{args.id}.tres"
    manifest_out = OUT_TEXTURES / args.id / "manifest.json"
    macro_stats = downsample_macro(
        source_macro,
        macro_out,
        args.max_macro_side,
        valid_mask_path=macro_valid_mask,
        valid_mask_out=macro_valid_mask_out,
        edge_bleed_px=args.source_macro_edge_bleed_px,
    )
    write_text_lf(
        material_out,
        material_tres(
            macro_albedo=macro_out,
            macro_valid_mask=macro_valid_mask_out,
            detail_material=args.detail_material,
            catalog=catalog,
            source_macro_strength=args.source_macro_strength,
            normal_strength_override=args.normal_strength,
            detail_albedo_strength_override=args.detail_albedo_strength,
            detail_normal_strength_override=args.detail_normal_strength,
            detail_rough_strength_override=args.detail_rough_strength,
        ),
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
            "source_macro_mask_policy": args.source_macro_mask_policy,
            "source_macro_valid_mask": res_path(macro_valid_mask) if macro_valid_mask else None,
            "runtime_source_macro_valid_mask": (
                res_path(macro_valid_mask_out) if macro_valid_mask_out else None
            ),
            "source_macro_valid_coverage": macro_stats["valid_coverage"],
            "source_macro_invalid_coverage": macro_stats["invalid_coverage"],
            "source_macro_runtime_size_px": [macro_stats["width"], macro_stats["height"]],
            "source_macro_edge_bleed_px": args.source_macro_edge_bleed_px,
            "material": res_path(material_out),
            "detail_material": args.detail_material,
            "target": "70_percent_of_best_photo_topo_stack_reference",
            "policy": "source_macro_albedo_valid_mask_first_tileable_detail_second",
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
