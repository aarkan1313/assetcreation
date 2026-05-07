"""Bind existing AAA PBR texture sets to procedural prop material slots.

This is the CPU-only bridge between the prop contract and the texture
pipeline. It does not generate textures and it does not rewrite GLB bytes.
Instead it records deterministic PBR bindings in each prop.json:

  pbr_material_bindings.slots[] -> material slot name + texture set + maps

`export_godot.py` consumes that metadata and emits shared StandardMaterial3D
resources plus a small binder script that applies them to imported GLB
MeshInstance3D descendants at runtime.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ASSETS = Path(r"D:\assets")
LIBRARY = ASSETS / "world" / "props" / "library"
TEXTURE_LIBRARY = ASSETS / "world" / "textures" / "library"
KIT_OUT = ASSETS / "world" / "props" / "kits"

MAP_SUFFIXES = ("albedo", "normal", "roughness", "metallic", "ao", "height")

DEFAULT_SLOT_TEXTURES = {
    "stone": "biome_lava_field",
    "rock": "biome_lava_field",
    "mushroom_cap": "biome_swamp",
    "mushroom_stem": "biome_grassland",
    "wood": "forest_floor_oak_bark",
    "bark": "forest_floor_oak_bark",
    "bone": "biome_tundra",
    "iron": "biome_charred_wasteland",
    "brass": "biome_charred_wasteland",
    "glass": "biome_mana_crystal",
    "cloth": "biome_grassland",
}

FAMILY_TEXTURES = {
    "rock_small": "biome_lava_field",
    "ruin_block": "biome_charred_wasteland",
    "tombstone": "biome_tundra",
    "log": "forest_floor_oak_bark",
    "stump": "forest_floor_oak_bark",
    "bone_pile": "biome_tundra",
    "mushroom_lantern": "biome_swamp",
}


def texture_maps(texture_set: str, texture_library: Path = TEXTURE_LIBRARY) -> dict[str, str]:
    tex_dir = texture_library / texture_set
    if not tex_dir.exists():
        raise FileNotFoundError(f"texture set not found: {tex_dir}")
    maps: dict[str, str] = {}
    for suffix in MAP_SUFFIXES:
        path = tex_dir / f"{texture_set}_{suffix}.png"
        if path.exists():
            maps[suffix] = str(path.relative_to(ASSETS)).replace("\\", "/")
    if "albedo" not in maps:
        raise FileNotFoundError(f"texture set {texture_set!r} has no albedo map")
    return maps


def parse_slot_overrides(values: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"--slot override must be slot=texture_set, got {value!r}")
        slot, texture = value.split("=", 1)
        out[slot.strip()] = texture.strip()
    return out


def choose_texture(slot: str, family: str, overrides: dict[str, str]) -> str:
    if slot in overrides:
        return overrides[slot]
    if f"{family}.{slot}" in overrides:
        return overrides[f"{family}.{slot}"]
    if slot in DEFAULT_SLOT_TEXTURES:
        return DEFAULT_SLOT_TEXTURES[slot]
    return FAMILY_TEXTURES.get(family, "biome_grassland")


def bind_prop(
    prop_dir: Path,
    *,
    overrides: dict[str, str],
    texture_library: Path = TEXTURE_LIBRARY,
    dry_run: bool = False,
) -> dict[str, Any]:
    prop_path = prop_dir / "prop.json"
    if not prop_path.exists():
        return {"id": prop_dir.name, "ok": False, "err": "missing prop.json"}
    data = json.loads(prop_path.read_text(encoding="utf-8"))
    slots = data.get("material_slots") or []
    if not slots or not isinstance(slots, list):
        return {"id": data.get("id", prop_dir.name), "ok": False, "err": "no material_slots"}
    if not (prop_dir / "model_lod0.glb").exists():
        return {"id": data.get("id", prop_dir.name), "ok": False, "err": "no model_lod0.glb"}

    family = data.get("family", "")
    bound_slots: list[dict[str, Any]] = []
    for idx, raw_slot in enumerate(slots):
        slot = str(raw_slot)
        texture_set = choose_texture(slot, family, overrides)
        maps = texture_maps(texture_set, texture_library=texture_library)
        bound_slots.append({
            "material_index": idx,
            "slot": slot,
            "texture_set": texture_set,
            "maps": maps,
            "tiling": 1.0,
            "source": "existing_aaa_texture",
        })

    binding = {
        "schema": "prop_pbr_bindings.v1",
        "bound_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "texture_library": str(texture_library.relative_to(ASSETS)).replace("\\", "/"),
        "slots": bound_slots,
    }
    if not dry_run:
        data["pbr_material_bindings"] = binding
        prop_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {
        "id": data.get("id", prop_dir.name),
        "ok": True,
        "slots": len(bound_slots),
        "textures": sorted({slot["texture_set"] for slot in bound_slots}),
        "dry_run": dry_run,
    }


def candidates(library: Path, ids: list[str], all_props: bool) -> list[Path]:
    if ids:
        return [library / pid for pid in ids]
    if all_props:
        return [
            d for d in sorted(library.iterdir())
            if d.is_dir() and (d / "prop.json").exists() and (d / "model_lod0.glb").exists()
        ]
    raise ValueError("pass --all or at least one --id")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="prop ids to bind")
    ap.add_argument("--all", action="store_true", help="bind all mesh props in the library")
    ap.add_argument("--library", type=Path, default=LIBRARY)
    ap.add_argument("--texture-library", type=Path, default=TEXTURE_LIBRARY)
    ap.add_argument("--slot", action="append", default=None,
                    help="override slot mapping, e.g. --slot stone=biome_desert")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args()

    overrides = parse_slot_overrides(args.slot)
    rows = []
    for prop_dir in candidates(args.library, args.ids, args.all):
        row = bind_prop(
            prop_dir,
            overrides=overrides,
            texture_library=args.texture_library,
            dry_run=args.dry_run,
        )
        rows.append(row)
        if row["ok"]:
            print(f"[pbr_material_bind] {row['id']} slots={row['slots']} textures={','.join(row['textures'])}")
        else:
            print(f"[pbr_material_bind] {row['id']} SKIP {row.get('err')}")

    report = {
        "schema": "pbr_material_bind_report.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dry_run": args.dry_run,
        "rows": rows,
        "ok": sum(1 for r in rows if r.get("ok")),
        "total": len(rows),
    }
    report_path = args.report or (KIT_OUT / "first_party_proc" / "pbr_bind_report.json")
    if not args.dry_run:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[pbr_material_bind] report -> {report_path}")

    return 0 if all(r.get("ok") for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

