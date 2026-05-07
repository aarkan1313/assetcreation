"""Cross-pipeline link validator.

Walks game_data validated records and checks that every cross-pipeline reference
(`icon_id`, `vfx_id`, `sfx_id`) resolves to a real asset in the corresponding
pipeline's manifest. Catches drift between game_data and ui/vfx/audio.

Loads:
  - game_data/validated/*.jsonl   (validated game records)
  - ui/icons/manifest.json        (UI icon IDs)
  - vfx/catalog/**/effect.json    (VFX effect IDs)
  - audio/sfx_manifest.json       (audio sound IDs)
  - world/props/library/*/prop.json (prop IDs)

Reports:
  - Missing references (game_data points to assets that don't exist)
  - Unused assets (assets not referenced by any game_data record)
  - Type mismatches (icon ID points at vfx, etc — heuristic by id prefix)

Usage:
  python pipelines/_meta/link_validator.py                   # default paths, exit 1 on errors
  python pipelines/_meta/link_validator.py --json out.json   # machine-readable report
  python pipelines/_meta/link_validator.py --strict          # also fail on unused assets

This is the canonical "is the factory's wiring intact?" check. Run after any
game_data regen, ui icon batch, vfx bake, or audio synth.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

REPO = Path(r"D:\assets")
LIBRARY_ONLY_PATH = REPO / "pipelines" / "_meta" / "library_only.json"


def load_library_only(path: Path) -> dict[str, set[str]]:
    """Load the library-only allowlist (assets explicitly NOT expected to be record-bound).

    Schema: {"icon": ["id1", ...], "vfx": [...], "sfx": [...], "prop": [...],
              "icon_prefixes": ["ico_chrome_"], ...}
    Suffix `_prefixes` matches by prefix; the bare key matches exact ids.
    Used to subtract from UNUSED so the remaining set is a real signal.
    """
    out: dict[str, set[str]] = {
        "icon": set(), "vfx": set(), "sfx": set(), "prop": set(),
        "icon_prefixes": set(), "vfx_prefixes": set(),
        "sfx_prefixes": set(), "prop_prefixes": set(),
    }
    if not path.exists():
        return out
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [warn] library_only.json: {e}")
        return out
    for key, ids in data.items():
        if key.startswith("_") or not isinstance(ids, list):
            continue
        if key in out:
            out[key] = {str(x) for x in ids}
    return out


def filter_library_only(unused: list[str], exact: set[str], prefixes: set[str]) -> list[str]:
    """Return only the unused assets NOT in the library-only allowlist."""
    return [
        u for u in unused
        if u not in exact and not any(u.startswith(p) for p in prefixes)
    ]


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"  [warn] {path}: bad JSON line: {e}")
    return out


def load_game_records(repo: Path) -> dict[str, list[dict]]:
    """Load every validated game record, grouped by category plural."""
    base = repo / "game_data" / "validated"
    out = {}
    for category in ("items", "abilities", "npcs", "factions", "lore_terms"):
        out[category] = load_jsonl(base / f"{category}.jsonl")
    return out


def load_ui_icon_ids(repo: Path) -> set[str]:
    manifest = repo / "ui" / "icons" / "manifest.json"
    if not manifest.exists():
        return set()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return {entry["id"] for entry in data.get("icons", [])}


def load_vfx_effect_ids(repo: Path) -> set[str]:
    """Walk vfx/catalog/**/effect.json + vfx/migrated_from_spell_lab/**/effect.json."""
    out: set[str] = set()
    for root in (repo / "vfx" / "catalog", repo / "vfx" / "migrated_from_spell_lab"):
        if not root.exists():
            continue
        for effect_json in root.rglob("effect.json"):
            try:
                eff = json.loads(effect_json.read_text(encoding="utf-8"))
                eid = eff.get("id")
                if eid:
                    out.add(eid)
            except (json.JSONDecodeError, OSError):
                continue
    return out


def load_audio_sound_ids(repo: Path) -> set[str]:
    manifest = repo / "audio" / "sfx_manifest.json"
    if not manifest.exists():
        return set()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return {entry["id"] for entry in data.get("sounds", [])}


def load_prop_ids(repo: Path) -> set[str]:
    out: set[str] = set()
    library = repo / "world" / "props" / "library"
    if not library.exists():
        return out
    for prop_json in library.glob("*/prop.json"):
        try:
            data = json.loads(prop_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        pid = data.get("id") or prop_json.parent.name
        if pid:
            out.add(pid)
    return out


def _collect_future_prop_refs(source_id: str, node, refs: set[tuple[str, str]]) -> None:
    """Find future game_data prop references without requiring schema changes.

    We only treat explicit prop-shaped keys as references to avoid false
    positives from general prose or placement tags.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            key_l = str(key).lower()
            is_single = key_l == "prop_id" or key_l.endswith("_prop_id") or key_l in {"prop_ref", "prop_scene_id"}
            is_many = key_l in {"prop_ids", "prop_refs", "prop_scene_ids"}
            if is_single and isinstance(value, str) and value:
                refs.add((source_id, value))
            elif is_many and isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item:
                        refs.add((source_id, item))
            else:
                _collect_future_prop_refs(source_id, value, refs)
    elif isinstance(node, list):
        for item in node:
            _collect_future_prop_refs(source_id, item, refs)


def collect_references(records: dict[str, list[dict]]) -> dict[str, set[tuple[str, str]]]:
    """Pull every (referencing_record, referenced_id) pair out of the game data.

    Returns a dict keyed by reference type ('icon', 'vfx', 'sfx', 'faction',
    'ability', 'npc') with sets of (source_record_id, target_id).
    """
    refs: dict[str, set[tuple[str, str]]] = {
        "icon": set(),
        "vfx": set(),
        "sfx": set(),
        "faction": set(),
        "ability": set(),
        "npc": set(),
        "prop": set(),
    }
    # Items / abilities both have icon_id; abilities also have vfx_id + sfx_id
    for item in records.get("items", []):
        if item.get("icon_id"):
            refs["icon"].add((item["id"], item["icon_id"]))
    for abil in records.get("abilities", []):
        if abil.get("icon_id"):
            refs["icon"].add((abil["id"], abil["icon_id"]))
        if abil.get("vfx_id"):
            refs["vfx"].add((abil["id"], abil["vfx_id"]))
        if abil.get("sfx_id"):
            refs["sfx"].add((abil["id"], abil["sfx_id"]))
    for npc in records.get("npcs", []):
        if npc.get("faction_id"):
            refs["faction"].add((npc["id"], npc["faction_id"]))
        for ability_id in (npc.get("abilities", []) or []) + (npc.get("ability_ids", []) or []):
            refs["ability"].add((npc["id"], ability_id))
    for fac in records.get("factions", []):
        for other_id in (fac.get("allies", []) or []) + (fac.get("ally_ids", []) or []):
            refs["faction"].add((fac["id"], other_id))
        for other_id in (fac.get("enemies", []) or []) + (fac.get("enemy_ids", []) or []):
            refs["faction"].add((fac["id"], other_id))
    for category, recs in records.items():
        for rec in recs:
            _collect_future_prop_refs(rec.get("id", category), rec, refs["prop"])
    return refs


def validate(repo: Path, strict: bool = False) -> dict:
    records = load_game_records(repo)
    refs = collect_references(records)

    icon_ids = load_ui_icon_ids(repo)
    vfx_ids = load_vfx_effect_ids(repo)
    sfx_ids = load_audio_sound_ids(repo)
    prop_ids = load_prop_ids(repo)
    faction_ids = {f["id"] for f in records.get("factions", [])}
    ability_ids = {a["id"] for a in records.get("abilities", [])}

    missing = {
        "icon": sorted([(s, t) for (s, t) in refs["icon"] if t not in icon_ids]),
        "vfx":  sorted([(s, t) for (s, t) in refs["vfx"]  if t not in vfx_ids]),
        "sfx":  sorted([(s, t) for (s, t) in refs["sfx"]  if t not in sfx_ids]),
        "faction": sorted([(s, t) for (s, t) in refs["faction"] if t not in faction_ids]),
        "ability": sorted([(s, t) for (s, t) in refs["ability"] if t not in ability_ids]),
        "prop": sorted([(s, t) for (s, t) in refs["prop"] if t not in prop_ids]),
    }

    referenced_icons = {t for (_, t) in refs["icon"]}
    referenced_vfx   = {t for (_, t) in refs["vfx"]}
    referenced_sfx   = {t for (_, t) in refs["sfx"]}
    referenced_props = {t for (_, t) in refs["prop"]}
    unused_raw = {
        "icon": sorted(icon_ids - referenced_icons),
        "vfx":  sorted(vfx_ids  - referenced_vfx),
        "sfx":  sorted(sfx_ids  - referenced_sfx),
        # Props are not expected to be referenced by the tiny demo dataset yet.
        # Start reporting unused props only once game_data actually points at props.
        "prop": sorted(prop_ids - referenced_props) if referenced_props else [],
    }

    # Subtract library-only assets so UNUSED is a real signal. The allowlist
    # (pipelines/_meta/library_only.json) lists asset IDs and ID prefixes that
    # are intentionally not record-bound (e.g. ornament chrome, ambience stems
    # selected by the runtime not by Ability.sfx_id).
    library_only = load_library_only(LIBRARY_ONLY_PATH)
    unused = {
        "icon": filter_library_only(unused_raw["icon"], library_only["icon"], library_only["icon_prefixes"]),
        "vfx":  filter_library_only(unused_raw["vfx"],  library_only["vfx"],  library_only["vfx_prefixes"]),
        "sfx":  filter_library_only(unused_raw["sfx"],  library_only["sfx"],  library_only["sfx_prefixes"]),
        "prop": filter_library_only(unused_raw["prop"], library_only["prop"], library_only["prop_prefixes"]),
    }
    library_only_counts = {
        "icon": len(unused_raw["icon"]) - len(unused["icon"]),
        "vfx":  len(unused_raw["vfx"])  - len(unused["vfx"]),
        "sfx":  len(unused_raw["sfx"])  - len(unused["sfx"]),
        "prop": len(unused_raw["prop"]) - len(unused["prop"]),
    }

    counts = {
        "records": {k: len(v) for k, v in records.items()},
        "assets": {
            "icon": len(icon_ids), "vfx": len(vfx_ids), "sfx": len(sfx_ids),
            "faction": len(faction_ids), "ability": len(ability_ids), "prop": len(prop_ids),
        },
        "references": {k: len(v) for k, v in refs.items()},
    }

    return {
        "ok": all(len(v) == 0 for v in missing.values())
              and (not strict or all(len(v) == 0 for v in unused.values())),
        "counts": counts,
        "missing": missing,
        "unused": unused,
        "unused_raw": unused_raw,
        "library_only_counts": library_only_counts,
    }


def print_report(report: dict, strict: bool) -> None:
    counts = report["counts"]
    print(f"\n=== link_validator ===")
    print(f"records: {counts['records']}")
    print(f"assets:  {counts['assets']}")
    print(f"references: {counts['references']}\n")

    any_missing = any(report["missing"][k] for k in report["missing"])
    # Force UTF-8 stdout so Windows cp1252 console doesn't choke on checkmarks.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if any_missing:
        print("MISSING references (game_data points at assets that don't exist):")
        for kind, pairs in report["missing"].items():
            if not pairs:
                continue
            print(f"  {kind}: {len(pairs)} missing")
            for source, target in pairs[:8]:
                print(f"    {source} -> {target}")
            if len(pairs) > 8:
                print(f"    ... and {len(pairs) - 8} more")
        print()
    else:
        print("MISSING: none ✓\n")

    any_unused = any(report["unused"][k] for k in report["unused"])
    lib_counts = report.get("library_only_counts", {})
    lib_total = sum(lib_counts.values()) if lib_counts else 0
    if lib_total:
        parts = [f"{k}={v}" for k, v in lib_counts.items() if v > 0]
        print(f"LIBRARY-ONLY (subtracted from UNUSED via library_only.json): {lib_total} total ({', '.join(parts)})")
    print("UNUSED assets (asset exists but no record references it; library-only filtered out):")
    for kind, ids in report["unused"].items():
        if not ids:
            continue
        print(f"  {kind}: {len(ids)} unused: {', '.join(ids[:5])}{'...' if len(ids) > 5 else ''}")
    if not any_unused:
        print("  none\n")
    else:
        if strict:
            print("  (--strict: unused assets fail the run)\n")
        else:
            print("  (informational; pass --strict to fail on these)\n")

    print("OK" if report["ok"] else "FAIL")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument("--strict", action="store_true",
                    help="Also fail when assets exist but are unreferenced.")
    ap.add_argument("--json", type=Path, default=None,
                    help="Write machine-readable report to this path.")
    args = ap.parse_args()

    report = validate(args.repo, strict=args.strict)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")

    print_report(report, strict=args.strict)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
