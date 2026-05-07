"""Shared helpers for the local-first prop kit pipeline.

This module is intentionally dependency-free and CPU-only. It validates JSON
contracts and prepares work queues; it does not call Blender, CUDA, Godot, or
any cloud service.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ASSET_ROOT = Path(__file__).resolve().parents[3]
PROPS_ROOT = ASSET_ROOT / "art_lab" / "props"
KIT_ROOT = PROPS_ROOT / "kits"
RECIPE_ROOT = PROPS_ROOT / "recipes"
OUTPUT_ROOT = PROPS_ROOT / "output"
LIBRARY_ROOT = ASSET_ROOT / "world" / "props" / "library"
BIOME_KIT_ROOT = ASSET_ROOT / "art_lab" / "biomes" / "kits"


ALLOWED_RENDER_CLASSES = {
    "scatter_multimesh",
    "scene_prop",
    "hero_prop",
    "decal",
    "billboard_only",
    "terrain3d_instance",
}

ALLOWED_COLLISION = {"none", "simple", "convex", "authored"}

ALLOWED_SOURCE_LANES = {
    "blender_procedural",
    "texture_cards",
    "texture_pipeline",
    "shader_template",
    "local_ai_optional",
    "cc0_reference_optional",
    "cloud_baseline_optional",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ASSET_ROOT).as_posix()
    except ValueError:
        return str(path)


def resolve_declared_path(base_file: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (base_file.parent / path).resolve()


def is_range(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(v, (int, float)) for v in value)
        and value[0] <= value[1]
    )


def ensure_fields(obj: dict, fields: list[str], where: str, issues: list[str]) -> None:
    for field in fields:
        if field not in obj:
            issues.append(f"{where}: missing field '{field}'")


def validate_recipe(recipe: dict, path: Path | None = None) -> list[str]:
    where = rel(path) if path else f"recipe:{recipe.get('family', '<unknown>')}"
    issues: list[str] = []
    ensure_fields(
        recipe,
        ["schema", "family", "kit", "generator", "count", "source_lanes", "style", "budgets", "scale_m", "placement", "outputs"],
        where,
        issues,
    )
    if recipe.get("schema") != "prop_recipe.v1":
        issues.append(f"{where}: schema must be prop_recipe.v1")
    if not isinstance(recipe.get("family"), str) or not recipe.get("family"):
        issues.append(f"{where}: family must be a non-empty string")
    if not isinstance(recipe.get("count"), int) or recipe.get("count", 0) <= 0:
        issues.append(f"{where}: count must be a positive integer")

    lanes = recipe.get("source_lanes", [])
    if not isinstance(lanes, list) or not lanes:
        issues.append(f"{where}: source_lanes must be a non-empty list")
    else:
        for lane in lanes:
            if lane not in ALLOWED_SOURCE_LANES:
                issues.append(f"{where}: unsupported source lane '{lane}'")

    placement = recipe.get("placement", {})
    if not isinstance(placement, dict):
        issues.append(f"{where}: placement must be an object")
    else:
        render_class = placement.get("render_class")
        collision = placement.get("collision")
        if render_class not in ALLOWED_RENDER_CLASSES:
            issues.append(f"{where}: invalid render_class '{render_class}'")
        if collision not in ALLOWED_COLLISION:
            issues.append(f"{where}: invalid collision '{collision}'")
        radius = placement.get("footprint_radius_m")
        if not (isinstance(radius, (int, float)) or is_range(radius)):
            issues.append(f"{where}: footprint_radius_m must be a number or [min,max]")

    scale = recipe.get("scale_m", {})
    if not isinstance(scale, dict):
        issues.append(f"{where}: scale_m must be an object")
    else:
        for axis in ["x", "y", "z"]:
            if axis not in scale or not is_range(scale[axis]):
                issues.append(f"{where}: scale_m.{axis} must be [min,max]")

    budgets = recipe.get("budgets", {})
    if not isinstance(budgets, dict) or not budgets:
        issues.append(f"{where}: budgets must be a non-empty object")
    elif not any(k.endswith("_max") or k in {"texture_px", "alpha_edge_px"} for k in budgets):
        issues.append(f"{where}: budgets should include *_max or texture_px fields")

    return issues


def validate_kit(kit: dict, kit_path: Path) -> tuple[list[str], list[dict]]:
    where = rel(kit_path)
    issues: list[str] = []
    loaded_recipes: list[dict] = []
    ensure_fields(kit, ["schema", "id", "families"], where, issues)
    if kit.get("schema") != "prop_kit.v1":
        issues.append(f"{where}: schema must be prop_kit.v1")

    seen: set[str] = set()
    for section in ["families", "decal_families"]:
        entries = kit.get(section, [])
        if section == "families" and not isinstance(entries, list):
            issues.append(f"{where}: families must be a list")
            continue
        if entries is None:
            continue
        if not isinstance(entries, list):
            issues.append(f"{where}: {section} must be a list")
            continue
        for i, entry in enumerate(entries):
            entry_where = f"{where}:{section}[{i}]"
            ensure_fields(entry, ["family", "recipe", "variants_required"], entry_where, issues)
            family = entry.get("family")
            if family in seen:
                issues.append(f"{entry_where}: duplicate family '{family}'")
            seen.add(family)
            if not isinstance(entry.get("variants_required"), int) or entry.get("variants_required", 0) <= 0:
                issues.append(f"{entry_where}: variants_required must be a positive integer")
            recipe_raw = entry.get("recipe")
            if not recipe_raw:
                continue
            recipe_path = resolve_declared_path(kit_path, recipe_raw)
            if not recipe_path.exists():
                issues.append(f"{entry_where}: recipe not found: {rel(recipe_path)}")
                continue
            recipe = load_json(recipe_path)
            loaded_recipes.append({"entry": entry, "section": section, "path": recipe_path, "recipe": recipe})
            issues.extend(validate_recipe(recipe, recipe_path))
            if recipe.get("family") != family:
                issues.append(f"{entry_where}: recipe family '{recipe.get('family')}' does not match '{family}'")
            if recipe.get("kit") != kit.get("id"):
                issues.append(f"{entry_where}: recipe kit '{recipe.get('kit')}' does not match '{kit.get('id')}'")
            if isinstance(recipe.get("count"), int) and isinstance(entry.get("variants_required"), int):
                if recipe["count"] < entry["variants_required"]:
                    issues.append(f"{entry_where}: recipe count {recipe['count']} is below variants_required {entry['variants_required']}")

    issues.extend(validate_against_biome_kit(kit, kit_path, seen))
    return issues, loaded_recipes


def validate_against_biome_kit(kit: dict, kit_path: Path, prop_families: set[str]) -> list[str]:
    issues: list[str] = []
    source = kit.get("source_biome_kit")
    if not source:
        return issues
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = (ASSET_ROOT / source_path).resolve()
    if not source_path.exists():
        issues.append(f"{rel(kit_path)}: source_biome_kit not found: {rel(source_path)}")
        return issues
    biome = load_json(source_path)
    scatter_assets = {r.get("asset") for r in biome.get("scatter", []) if isinstance(r, dict)}
    decal_ids = {r.get("id") for r in biome.get("decals", []) if isinstance(r, dict)}
    for name in sorted((scatter_assets | decal_ids) - prop_families):
        if name:
            issues.append(f"{rel(kit_path)}: source biome references '{name}' but prop kit has no family for it")
    return issues


def variant_id(family: str, index: int) -> str:
    return f"{family}_{index:02d}"


def expected_files(render_class: str) -> list[str]:
    base = ["prop.json", "qa.json", "thumbnail.png"]
    if render_class == "decal":
        return base + ["decal.png"]
    if render_class == "billboard_only":
        return base + ["billboard.png"]
    return base + ["model_lod0.glb"]


def asset_status(prop_id: str, render_class: str, library_root: Path = LIBRARY_ROOT) -> dict:
    prop_dir = library_root / prop_id
    files = expected_files(render_class)
    present = [name for name in files if (prop_dir / name).exists()]
    missing = [name for name in files if name not in present]
    if not prop_dir.exists():
        status = "missing"
    elif missing:
        status = "partial"
    else:
        status = "ready"
    return {
        "status": status,
        "library_dir": rel(prop_dir),
        "expected_files": files,
        "present_files": present,
        "missing_files": missing,
    }


def build_plan(kit_path: Path, out_id: str | None = None, library_root: Path = LIBRARY_ROOT) -> dict:
    kit = load_json(kit_path)
    issues, loaded = validate_kit(kit, kit_path)
    kit_id = kit.get("id", kit_path.stem)
    plan_id = out_id or f"{kit_id}_plan"
    variants: list[dict] = []
    families: list[dict] = []
    blender_queue: list[dict] = []
    local_ai_queue: list[dict] = []
    decal_queue: list[dict] = []
    godot_queue: list[dict] = []

    for item in loaded:
        entry = item["entry"]
        recipe = item["recipe"]
        recipe_path = item["path"]
        family = recipe["family"]
        required = max(entry.get("variants_required", 0), recipe.get("count", 0))
        placement = recipe.get("placement", {})
        render_class = placement.get("render_class", "scatter_multimesh")
        collision = placement.get("collision", "none")
        lanes = recipe.get("source_lanes", [])
        generator = recipe.get("generator")
        variant_ids = [variant_id(family, i) for i in range(1, required + 1)]
        families.append({
            "family": family,
            "section": item["section"],
            "recipe": rel(recipe_path),
            "variants_required": required,
            "generator": generator,
            "render_class": render_class,
            "collision": collision,
            "source_lanes": lanes,
            "variant_ids": variant_ids,
        })
        for i, prop_id in enumerate(variant_ids, start=1):
            status = asset_status(prop_id, render_class, library_root)
            record = {
                "id": prop_id,
                "family": family,
                "kit": kit_id,
                "variant_index": i,
                "recipe": rel(recipe_path),
                "generator": generator,
                "source_lanes": lanes,
                "render_class": render_class,
                "collision": collision,
                "placement_tags": placement.get("placement_tags", []),
                **status,
            }
            if status["status"] == "ready":
                record["next_action"] = "review_or_export"
                godot_queue.append(record)
            elif render_class == "decal" or generator == "texture_decal_v1":
                record["next_action"] = "generate_decal_texture"
                decal_queue.append(record)
            elif "blender_procedural" in lanes or str(generator).startswith("blender_"):
                record["next_action"] = "run_blender_generator"
                blender_queue.append(record)
            elif any(lane.startswith("local_ai") for lane in lanes):
                record["next_action"] = "run_local_ai_generator"
                local_ai_queue.append(record)
            else:
                record["next_action"] = "manual_source_needed"
            variants.append(record)

    summary = {
        "families": len(families),
        "variants": len(variants),
        "ready": sum(1 for v in variants if v["status"] == "ready"),
        "partial": sum(1 for v in variants if v["status"] == "partial"),
        "missing": sum(1 for v in variants if v["status"] == "missing"),
        "blender_tasks": len(blender_queue),
        "local_ai_tasks": len(local_ai_queue),
        "decal_tasks": len(decal_queue),
        "godot_export_tasks": len(godot_queue),
        "validation_issues": len(issues),
    }
    return {
        "schema": "prop_plan.v1",
        "id": plan_id,
        "created_utc": utc_now(),
        "kit": kit_id,
        "kit_path": rel(kit_path),
        "library_root": rel(library_root),
        "validation_issues": issues,
        "summary": summary,
        "families": families,
        "variants": variants,
        "queues": {
            "blender": blender_queue,
            "local_ai": local_ai_queue,
            "decal": decal_queue,
            "godot_export": godot_queue,
        },
    }


def queue_command_hint(task: dict) -> str:
    if task.get("next_action") == "run_blender_generator":
        return (
            "blender -b --python art_lab/props/tools/prop_make_blender.py -- "
            f"--recipe {task['recipe']} --variant-id {task['id']} --out {task['library_dir']}"
        )
    if task.get("next_action") == "generate_decal_texture":
        return (
            "python art_lab/props/tools/prop_make_decal.py "
            f"--recipe {task['recipe']} --variant-id {task['id']} --out {task['library_dir']}"
        )
    if task.get("next_action") == "run_local_ai_generator":
        return (
            "python art_lab/props/tools/prop_import_ai.py "
            f"--recipe {task['recipe']} --variant-id {task['id']} --out {task['library_dir']}"
        )
    return "no command yet"

