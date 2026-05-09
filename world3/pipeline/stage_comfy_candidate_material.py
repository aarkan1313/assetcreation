#!/usr/bin/env python3
"""Stage a ComfyUI/aaa_texture output as a quarantined world3 candidate.

The canonical material catalog is intentionally not modified here. This writes a
sidecar catalog that source-stack review tools can opt into.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
LIBRARY = REPO / "world" / "textures" / "library"
OUT_ROOT = ROOT / "textures" / "wgv3_comfy_candidates"
OUT_CATALOG = ROOT / "materials" / "catalog_comfy_candidates.json"
MAPS = ("albedo", "normal", "roughness", "metallic", "height", "ao")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO.resolve()).as_posix()


def copy_if_exists(src: Path, dst: Path) -> str | None:
    if not src.exists():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return rel(dst)


def load_existing_catalog() -> dict[str, Any]:
    if OUT_CATALOG.exists():
        return json.loads(OUT_CATALOG.read_text(encoding="utf-8"))
    return {
        "version": 1,
        "updated": date.today().isoformat(),
        "role": "quarantined_comfy_regeneration_candidates_not_canonical_catalog",
        "materials": [],
    }


def upsert_material(catalog: dict[str, Any], material: dict[str, Any]) -> None:
    materials = [m for m in catalog.get("materials", []) if m.get("id") != material["id"]]
    materials.append(material)
    catalog["materials"] = materials
    catalog["updated"] = date.today().isoformat()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--library-id", required=True)
    ap.add_argument("--material-id", default=None)
    ap.add_argument("--source-material-id", required=True)
    ap.add_argument("--color-family", default="comfy-candidate")
    ap.add_argument("--scale-m-per-repeat", type=float, default=10.0)
    args = ap.parse_args()

    library_id = args.library_id
    material_id = args.material_id or library_id
    src_dir = LIBRARY / library_id
    if not src_dir.exists():
        raise FileNotFoundError(src_dir)

    out_dir = OUT_ROOT / material_id
    pbr_maps: dict[str, str] = {}
    missing: list[str] = []
    for map_name in MAPS:
        src = src_dir / f"{library_id}_{map_name}.png"
        dst = out_dir / f"{map_name}.png"
        copied = copy_if_exists(src, dst)
        if copied is None:
            missing.append(map_name)
        else:
            pbr_maps[map_name] = copied

    if missing:
        raise FileNotFoundError(f"{library_id} missing maps: {', '.join(missing)}")

    qa_dir = src_dir / "qa"
    tile_2x2 = copy_if_exists(qa_dir / "tile_2x2.png", out_dir / "qa_tile_2x2.png")
    blender_combo = copy_if_exists(qa_dir / "blender_combo.png", out_dir / "qa_blender_combo.png")
    if tile_2x2:
        pbr_maps["tile_2x2"] = tile_2x2
    if blender_combo:
        pbr_maps["blender_combo"] = blender_combo

    # Detail maps intentionally reuse the same textures, but strength is kept
    # low in provenance settings until terrain-context review says otherwise.
    pbr_maps["detail_albedo"] = pbr_maps["albedo"]
    pbr_maps["detail_normal"] = pbr_maps["normal"]
    pbr_maps["detail_roughness"] = pbr_maps["roughness"]

    pipeline = read_json(src_dir / "aaa_pipeline.json")
    qa_summary = read_json(qa_dir / "summary.json")
    seam = qa_summary.get("seam", {})
    checks = seam.get("checks", {})

    material = {
        "id": material_id,
        "source": "procedural",
        "asset_status": "comfy_regen_candidate",
        "provenance": {
            "type": "comfy_regeneration_candidate",
            "source_material_id": args.source_material_id,
            "source_asset_id": library_id,
            "tool": "pipelines/textures/aaa_texture.py",
            "prompt": pipeline.get("prompt"),
            "quality": pipeline.get("quality"),
            "pbr_backend": pipeline.get("preset", {}).get("pbr"),
            "qa_grade": pipeline.get("grade") or seam.get("grade"),
            "passed_gate": pipeline.get("passed_gate"),
            "seam_checks": {
                "edge_continuity_mse": checks.get("edge_continuity", {}).get("overall_mse"),
                "junction_ratio": checks.get("junction_visibility", {}).get("ratio"),
                "periodic_locality": checks.get("periodic_artifact", {}).get("peak_locality_ratio"),
            },
            "policy": "sidecar_candidate_terrain_context_required",
            "settings": {
                "world_uv_scale": 0.015625,
                "hex_strength": 1.0,
                "blend_sharpness": 8.0,
                "roughness_strength": 1.0,
                "normal_strength": 0.0,
                "detail_uv_scale_mult": 10.0,
                "detail_albedo_strength": 0.05,
                "detail_normal_strength": 0.0,
                "detail_rough_strength": 0.015,
                "detail_fade_start_m": 4.0,
                "detail_fade_end_m": 42.0,
            },
        },
        "scale_m_per_repeat": args.scale_m_per_repeat,
        "color_family": args.color_family,
        "runtime_texture_dir": rel(out_dir),
        "pbr_maps": pbr_maps,
        "shader_binding": "terrain_hex_detail",
        "validated_views": {
            "close": "needs_review",
            "mid": "needs_review",
            "far": "needs_review",
        },
    }

    catalog = load_existing_catalog()
    upsert_material(catalog, material)
    OUT_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    OUT_CATALOG.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    print(f"staged {library_id} -> {rel(out_dir)}")
    print(f"wrote {rel(OUT_CATALOG)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
