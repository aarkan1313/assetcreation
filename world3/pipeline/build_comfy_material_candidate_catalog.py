"""Inventory ComfyUI/aaa_texture material candidates for world3.

This does not generate textures. It audits the procedural material lane by
linking world3 catalog ids to their source folders under world/textures/library,
then writes a machine-readable inventory plus a short markdown report.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


WORLD3_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WORLD3_ROOT.parent
CATALOG_PATH = WORLD3_ROOT / "materials" / "catalog.json"
LIBRARY_ROOT = REPO_ROOT / "world" / "textures" / "library"
OUT_JSON = WORLD3_ROOT / "materials" / "comfy_texture_workflow_inventory.json"
OUT_MD = WORLD3_ROOT / "docs" / "COMFYUI_TEXTURE_WORKFLOW_INVENTORY_2026_05_08.md"

MAP_NAMES = ("albedo", "normal", "roughness", "height", "ao", "metallic")
CORE_LIBRARY_MAPS = ("albedo", "normal", "roughness", "height")
CORE_RUNTIME_MAPS = ("albedo", "normal", "roughness", "height", "ao")

PRIORITY_REGEN_IDS = {
    "grassland_grass",
    "grass",
    "temperate_forest_grass",
    "tundra_moss",
    "tundra_lichen",
}

ORGANIC_HINTS = ("grass", "moss", "lichen", "leaf", "fern", "thatch", "brush")


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_error": "json_decode_failed"}


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def map_status_from_library(library_dir: Path, source_id: str) -> dict[str, bool]:
    return {
        name: (library_dir / f"{source_id}_{name}.png").exists()
        for name in MAP_NAMES
    }


def map_status_from_catalog(material: dict[str, Any]) -> dict[str, bool]:
    pbr_maps = material.get("pbr_maps", {})
    status: dict[str, bool] = {}
    for name in MAP_NAMES:
        map_path = pbr_maps.get(name)
        status[name] = bool(map_path and (REPO_ROOT / map_path).exists())
    return status


def missing(status: dict[str, bool], names: tuple[str, ...]) -> list[str]:
    return [name for name in names if not status.get(name, False)]


def qa_summary(library_dir: Path) -> dict[str, Any]:
    qa_dir = library_dir / "qa"
    summary = read_json(qa_dir / "summary.json") or {}
    seam = read_json(qa_dir / "seam_score.json") or {}
    sanity = read_json(qa_dir / "sanity.json") or {}
    pipeline = read_json(library_dir / "aaa_pipeline.json") or {}

    seam_block = summary.get("seam", {}) if isinstance(summary, dict) else {}
    return {
        "summary_exists": (qa_dir / "summary.json").exists(),
        "seam_score_exists": (qa_dir / "seam_score.json").exists(),
        "sanity_exists": (qa_dir / "sanity.json").exists(),
        "tile_2x2_exists": (qa_dir / "tile_2x2.png").exists(),
        "summary_grade": seam_block.get("grade") or summary.get("grade"),
        "summary_passed": seam_block.get("passed") or summary.get("passed"),
        "pipeline_grade": pipeline.get("grade"),
        "pipeline_passed_gate": pipeline.get("passed_gate"),
        "pipeline_quality": pipeline.get("quality"),
        "pipeline_pbr_method": next(
            (
                stage.get("method")
                for stage in pipeline.get("stages", [])
                if isinstance(stage, dict) and stage.get("stage") == "pbr"
            ),
            None,
        ),
        "pipeline_n_variants": pipeline.get("n_variants"),
        "pipeline_seed_base": pipeline.get("seed_base"),
        "seam_grade": seam.get("grade"),
        "sanity_ok": sanity.get("ok"),
    }


def recommend_action(
    material: dict[str, Any],
    library_exists: bool,
    library_missing: list[str],
    runtime_missing: list[str],
    qa: dict[str, Any],
) -> str:
    material_id = material.get("id", "")
    close_state = material.get("validated_views", {}).get("close")
    passed_gate = material.get("provenance", {}).get("passed_gate")

    if material_id in PRIORITY_REGEN_IDS:
        return "regenerate_with_comfy_prompt_and_terrain_gate"
    if not library_exists:
        return "recover_or_regenerate_library_source"
    if library_missing:
        return "recover_or_regenerate_library_maps"
    if runtime_missing:
        return "restage_runtime_maps_from_library"
    if not qa.get("summary_exists") or not qa.get("seam_score_exists"):
        return "rerun_texture_qa"
    if passed_gate is False:
        return "rerun_aaa_texture_with_strict_gate"
    if close_state != "ok":
        return "terrain_context_review_required"
    return "eligible_for_source_stack_detail_trial"


def is_comfy_material(material: dict[str, Any]) -> bool:
    provenance = material.get("provenance", {})
    tool = str(provenance.get("tool", "")).replace("\\", "/")
    source_id = provenance.get("source_asset_id") or material.get("id")
    return "pipelines/textures/aaa_texture.py" in tool or (LIBRARY_ROOT / source_id).exists()


def build_inventory() -> dict[str, Any]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    materials: list[dict[str, Any]] = []

    for material in catalog.get("materials", []):
        if not is_comfy_material(material):
            continue

        provenance = material.get("provenance", {})
        material_id = material.get("id")
        source_id = provenance.get("source_asset_id") or material_id
        library_dir = LIBRARY_ROOT / source_id
        library_exists = library_dir.exists()
        library_maps = map_status_from_library(library_dir, source_id)
        runtime_maps = map_status_from_catalog(material)
        qa = qa_summary(library_dir) if library_exists else {}
        library_missing = missing(library_maps, CORE_LIBRARY_MAPS)
        runtime_missing = missing(runtime_maps, CORE_RUNTIME_MAPS)

        color_family = str(material.get("color_family", "")).lower()
        prompt = str(provenance.get("prompt", "")).lower()
        organic = any(hint in f"{material_id} {source_id} {color_family} {prompt}" for hint in ORGANIC_HINTS)

        materials.append(
            {
                "id": material_id,
                "source": material.get("source"),
                "asset_status": material.get("asset_status"),
                "source_asset_id": source_id,
                "color_family": material.get("color_family"),
                "prompt": provenance.get("prompt"),
                "catalog_qa_grade": provenance.get("qa_grade"),
                "catalog_passed_gate": provenance.get("passed_gate"),
                "validated_views": material.get("validated_views", {}),
                "runtime": {
                    "dir": material.get("runtime_texture_dir"),
                    "map_status": runtime_maps,
                    "missing_core_maps": runtime_missing,
                },
                "library": {
                    "dir": rel(library_dir),
                    "exists": library_exists,
                    "map_status": library_maps,
                    "missing_core_maps": library_missing,
                    "qa": qa,
                },
                "flags": {
                    "organic_or_vegetation_like": organic,
                    "priority_regen": material_id in PRIORITY_REGEN_IDS,
                    "close_needs_review": material.get("validated_views", {}).get("close") == "needs_review",
                },
                "recommended_action": recommend_action(
                    material,
                    library_exists,
                    library_missing,
                    runtime_missing,
                    qa,
                ),
            }
        )

    summary = {
        "catalog_materials_total": len(catalog.get("materials", [])),
        "comfy_materials_total": len(materials),
        "library_sets_present": sum(1 for item in materials if item["library"]["exists"]),
        "runtime_core_complete": sum(
            1 for item in materials if not item["runtime"]["missing_core_maps"]
        ),
        "library_core_complete": sum(
            1 for item in materials if item["library"]["exists"] and not item["library"]["missing_core_maps"]
        ),
        "qa_summary_present": sum(
            1 for item in materials if item["library"]["qa"].get("summary_exists")
        ),
        "priority_regen_total": sum(1 for item in materials if item["flags"]["priority_regen"]),
        "close_needs_review_total": sum(1 for item in materials if item["flags"]["close_needs_review"]),
    }

    return {
        "version": 1,
        "generated_at": date.today().isoformat(),
        "purpose": "Audit ComfyUI/aaa_texture procedural materials as peer inputs to the source-stack remediation lane.",
        "library_root": rel(LIBRARY_ROOT),
        "catalog_path": rel(CATALOG_PATH),
        "promotion_gate": [
            "source library maps and staged runtime maps are present",
            "aaa_texture.py quality gate and seam QA pass",
            "2x2 tile and Blender preview do not show object-like repetition",
            "Godot terrain-context captures pass close, mid, and far views",
            "source-stack detail use starts albedo-only/low-strength until normal/detail review passes",
        ],
        "summary": summary,
        "materials": materials,
    }


def write_markdown(inventory: dict[str, Any]) -> None:
    summary = inventory["summary"]
    rows = inventory["materials"]
    priority = [item for item in rows if item["flags"]["priority_regen"]]
    needs_context = [
        item
        for item in rows
        if item["recommended_action"] == "terrain_context_review_required"
    ]
    missing_library = [
        item for item in rows if not item["library"]["exists"] or item["library"]["missing_core_maps"]
    ]
    restage_runtime = [
        item
        for item in rows
        if item["recommended_action"] == "restage_runtime_maps_from_library"
    ]

    lines = [
        "# ComfyUI Texture Workflow Inventory",
        "",
        "Date: 2026-05-08",
        "",
        "## Purpose",
        "",
        "This inventory makes the ComfyUI/`aaa_texture.py` lane explicit in the",
        "M1-M7 visual remediation work. OpenTopo source stacks and ComfyUI-generated",
        "materials are peer inputs: OpenTopo gives real macro terrain truth; ComfyUI",
        "gives scalable biome/material coverage, controlled variants, and fantasy or",
        "missing-biome fill.",
        "",
        "The current goal is workflow quality, not silent production promotion.",
        "Generated texture candidates must pass the same terrain-context review bar",
        "before they can drive close-detail or transition evidence.",
        "",
        "## Inventory Summary",
        "",
        f"- Catalog materials total: {summary['catalog_materials_total']}",
        f"- ComfyUI/aaa_texture materials: {summary['comfy_materials_total']}",
        f"- Library source folders present: {summary['library_sets_present']}/{summary['comfy_materials_total']}",
        f"- Runtime core map sets complete: {summary['runtime_core_complete']}/{summary['comfy_materials_total']}",
        f"- Library core map sets complete: {summary['library_core_complete']}/{summary['comfy_materials_total']}",
        f"- QA summaries present: {summary['qa_summary_present']}/{summary['comfy_materials_total']}",
        f"- Priority regeneration blockers: {summary['priority_regen_total']}",
        f"- Close-view materials still marked `needs_review`: {summary['close_needs_review_total']}",
        "",
        "## Shared Promotion Gate",
        "",
        "A ComfyUI material can participate in M5/M7/M8 visual closure only after:",
        "",
        "- source library maps and staged runtime maps are present;",
        "- `aaa_texture.py` quality gate and seam QA pass;",
        "- 2x2 tile and Blender preview do not show object-like repetition;",
        "- Godot terrain-context captures pass close, mid, and far views;",
        "- source-stack detail use starts albedo-only/low-strength until normal/detail review passes.",
        "",
        "## Priority Regeneration Queue",
        "",
    ]

    if priority:
        lines.extend(
            [
                "| Material | Source asset | Catalog QA | Close view | Recommended action |",
                "|----------|--------------|------------|------------|--------------------|",
            ]
        )
        for item in priority:
            lines.append(
                "| {id} | {source} | {qa} | {close} | {action} |".format(
                    id=item["id"],
                    source=item["source_asset_id"],
                    qa=item.get("catalog_qa_grade"),
                    close=item["validated_views"].get("close"),
                    action=item["recommended_action"],
                )
            )
    else:
        lines.append("No priority regeneration blockers were found.")

    lines.extend(
        [
            "",
            "Use `world3/jobs/comfy_texture_regen_candidates.json` as the first M8",
            "work queue. The first pass should regenerate these from prompt/variant",
            "control, not rely only on deterministic blur/filter repair.",
            "",
            "## Context-Review Queue",
            "",
        ]
    )

    if needs_context:
        lines.extend(
            [
                "| Material | Source asset | Catalog QA | Action |",
                "|----------|--------------|------------|--------|",
            ]
        )
        for item in needs_context:
            lines.append(
                "| {id} | {source} | {qa} | {action} |".format(
                    id=item["id"],
                    source=item["source_asset_id"],
                    qa=item.get("catalog_qa_grade"),
                    action=item["recommended_action"],
                )
            )
    else:
        lines.append("No non-priority ComfyUI materials are ready for context review.")

    lines.extend(
        [
            "",
            "## Runtime Staging Gaps",
            "",
        ]
    )

    if restage_runtime:
        lines.extend(
            [
                "| Material | Source asset | Missing runtime maps |",
                "|----------|--------------|----------------------|",
            ]
        )
        for item in restage_runtime:
            missing_maps = item["runtime"]["missing_core_maps"]
            missing_text = ", ".join(missing_maps) if missing_maps else "none"
            lines.append(f"| {item['id']} | {item['source_asset_id']} | {missing_text} |")
    else:
        lines.append("All ComfyUI runtime folders have the required core maps.")

    lines.extend(
        [
            "",
            "## Missing Or Incomplete Library Sets",
            "",
        ]
    )

    if missing_library:
        lines.extend(
            [
                "| Material | Source asset | Missing |",
                "|----------|--------------|---------|",
            ]
        )
        for item in missing_library:
            missing_maps = item["library"]["missing_core_maps"]
            missing_text = ", ".join(missing_maps) if missing_maps else "source folder missing"
            lines.append(f"| {item['id']} | {item['source_asset_id']} | {missing_text} |")
    else:
        lines.append("All ComfyUI source library folders have the required core maps.")

    lines.extend(
        [
            "",
            "## Rebuild",
            "",
            "```powershell",
            "python world3/pipeline/build_comfy_material_candidate_catalog.py",
            "```",
            "",
            "Machine-readable output:",
            "`world3/materials/comfy_texture_workflow_inventory.json`.",
        ]
    )

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    inventory = build_inventory()
    OUT_JSON.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    write_markdown(inventory)
    summary = inventory["summary"]
    print(
        "ComfyUI inventory: "
        f"{summary['comfy_materials_total']} materials, "
        f"{summary['priority_regen_total']} priority regen blockers, "
        f"{summary['close_needs_review_total']} close-view reviews."
    )
    print(rel(OUT_JSON))
    print(rel(OUT_MD))


if __name__ == "__main__":
    main()
