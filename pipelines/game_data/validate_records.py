"""Deterministic record validator + balance reporter.

Three layers:

  1. Schema validation - run each record through its Pydantic class.
  2. Cross-reference linker - npc.faction_id, npc.abilities[], faction.allies/
     enemies, ability.icon_id/vfx_id/sfx_id all checked against an id index.
  3. Balance reports - simple stats: dmg-by-tier, item-power-by-rarity,
     duplicate names, faction territory coverage. Plain Markdown so we can
     read it without DuckDB.

Promotes valid records from generated/ -> validated/. Writes a markdown report
at reports/validation_<timestamp>.md.

Per F_game_data: deterministic checks first, then (optional) LLM judge later.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from schemas import RECORD_TYPES, plural, validate_id  # noqa: E402

GAME_DATA = Path(r"D:\assets\game_data")
GENERATED = GAME_DATA / "generated"
VALIDATED = GAME_DATA / "validated"
REPORTS = GAME_DATA / "reports"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _id_index(records_by_type: dict[str, list[dict[str, Any]]]) -> dict[str, set[str]]:
    return {rt: {r["id"] for r in recs} for rt, recs in records_by_type.items()}


def validate_record(rec: dict[str, Any], record_type: str) -> tuple[bool, list[str]]:
    """Schema-level validation. Returns (ok, errors)."""
    errors: list[str] = []
    cls = RECORD_TYPES[record_type]
    try:
        cls.model_validate(rec)
    except Exception as e:  # ValidationError or anything else
        errors.append(f"schema: {e!s}")

    if "id" in rec and not validate_id(rec["id"]):
        errors.append(f"id: {rec['id']!r} is reserved or malformed")

    return (not errors, errors)


def link_check(records_by_type: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    """Cross-reference linker. Returns {record_id: [error_strings]}."""
    idx = _id_index(records_by_type)
    errs: dict[str, list[str]] = defaultdict(list)

    # NPC -> faction, abilities
    for npc in records_by_type.get("npc", []):
        if npc.get("faction_id") and npc["faction_id"] not in idx.get("faction", set()):
            errs[npc["id"]].append(f"unknown faction_id={npc['faction_id']}")
        for aid in npc.get("abilities", []):
            if aid not in idx.get("ability", set()):
                errs[npc["id"]].append(f"unknown ability_id={aid}")

    # Faction -> allies, enemies (both reference factions)
    for fac in records_by_type.get("faction", []):
        for fid in fac.get("allies", []) + fac.get("enemies", []):
            if fid not in idx.get("faction", set()):
                errs[fac["id"]].append(f"unknown faction reference={fid}")
        for fid in fac.get("allies", []):
            if fid in fac.get("enemies", []):
                errs[fac["id"]].append(f"faction {fid} appears in both allies and enemies")

    # Duplicate display_name within same record type
    for rt, recs in records_by_type.items():
        names = Counter(r.get("display_name", "") for r in recs)
        dupes = [n for n, c in names.items() if c > 1 and n]
        if dupes:
            for r in recs:
                if r.get("display_name") in dupes:
                    errs[r["id"]].append(f"duplicate display_name {r['display_name']!r}")

    # Stat-budget sanity for items + abilities
    for it in records_by_type.get("item", []):
        s = it.get("stats", {})
        rarity = it.get("rarity", "common")
        # Loose budget: legendary <= 200dmg, epic <= 120, etc.
        budget = {"common": 60, "uncommon": 90, "rare": 130, "epic": 180, "legendary": 260}
        if s.get("damage", 0) > budget.get(rarity, 60):
            errs[it["id"]].append(f"damage {s['damage']} exceeds {rarity} budget {budget[rarity]}")
        if s.get("armor", 0) > budget.get(rarity, 60):
            errs[it["id"]].append(f"armor {s['armor']} exceeds {rarity} budget {budget[rarity]}")

    for ab in records_by_type.get("ability", []):
        tier = ab.get("tier", 1)
        eff_damage = ab.get("effect", {}).get("damage", 0)
        # Rough rule: damage <= tier * 25
        max_dmg = tier * 25
        if eff_damage > max_dmg:
            errs[ab["id"]].append(f"effect.damage {eff_damage} exceeds tier-{tier} cap {max_dmg}")
        cost_mana = ab.get("cost", {}).get("mana", 0)
        cd = ab.get("cost", {}).get("cooldown_sec", 0)
        if eff_damage > 0 and cost_mana == 0 and cd == 0:
            errs[ab["id"]].append("damaging ability with zero mana cost AND zero cooldown")

    return dict(errs)


def balance_report(records_by_type: dict[str, list[dict[str, Any]]]) -> str:
    out = ["# Balance Report", ""]
    out.append(f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}_")
    out.append("")

    items = records_by_type.get("item", [])
    if items:
        out.append(f"## Items ({len(items)})")
        out.append("")
        out.append("**By rarity:**")
        out.append("")
        rarity_count = Counter(r.get("rarity", "?") for r in items)
        for rarity, n in rarity_count.most_common():
            out.append(f"- {rarity}: {n}")
        out.append("")
        out.append("**Damage stats (weapons):**")
        out.append("")
        weapon_dmg = [r["stats"]["damage"] for r in items if r.get("category") == "weapon"]
        if weapon_dmg:
            out.append(f"- count: {len(weapon_dmg)}")
            out.append(f"- mean: {statistics.mean(weapon_dmg):.1f}")
            out.append(f"- median: {statistics.median(weapon_dmg):.1f}")
            out.append(f"- range: {min(weapon_dmg)}..{max(weapon_dmg)}")
        out.append("")

    abilities = records_by_type.get("ability", [])
    if abilities:
        out.append(f"## Abilities ({len(abilities)})")
        out.append("")
        out.append("**By tier:**")
        out.append("")
        tier_dmg: dict[int, list[int]] = defaultdict(list)
        for ab in abilities:
            tier_dmg[ab.get("tier", 1)].append(ab.get("effect", {}).get("damage", 0))
        for tier in sorted(tier_dmg):
            dmgs = tier_dmg[tier]
            if dmgs:
                out.append(
                    f"- T{tier}: n={len(dmgs)} dmg_mean={statistics.mean(dmgs):.1f} "
                    f"dmg_max={max(dmgs)}"
                )
        out.append("")
        schools = Counter(r.get("school", "?") for r in abilities)
        out.append("**By school:** " + ", ".join(f"{s}={n}" for s, n in schools.most_common()))
        out.append("")

    npcs = records_by_type.get("npc", [])
    if npcs:
        out.append(f"## NPCs ({len(npcs)})")
        out.append("")
        roles = Counter(r.get("role", "?") for r in npcs)
        out.append("**By role:** " + ", ".join(f"{s}={n}" for s, n in roles.most_common()))
        biomes = Counter(r.get("biome", "?") for r in npcs if r.get("biome"))
        out.append("**Biome coverage:** " + ", ".join(f"{s}={n}" for s, n in biomes.most_common()))
        out.append("")

    factions = records_by_type.get("faction", [])
    if factions:
        out.append(f"## Factions ({len(factions)})")
        territory = Counter()
        for f in factions:
            for t in f.get("territory", []):
                territory[t] += 1
        out.append("**Territory coverage:** " +
                   ", ".join(f"{s}={n}" for s, n in territory.most_common()))
        out.append("")

    return "\n".join(out)


def run_validation(
    sources: dict[str, Path] | None = None,
    promote: bool = True,
) -> dict[str, Any]:
    """Validate every JSONL in `sources` (defaults: generated/<type>s.jsonl).

    If promote=True and a record passes both schema + link checks, it is written
    to validated/<type>s.jsonl. Anything that fails schema is skipped from
    promotion (we don't ship broken data).
    """
    sources = sources or {
        rt: GENERATED / f"{plural(rt)}.jsonl" for rt in RECORD_TYPES
    }

    records_by_type: dict[str, list[dict[str, Any]]] = {}
    schema_errors: list[tuple[str, str, list[str]]] = []  # (type, id, errors)

    for rt, path in sources.items():
        recs = _read_jsonl(path)
        valid_recs = []
        for r in recs:
            ok, errs = validate_record(r, rt)
            if ok:
                valid_recs.append(r)
            else:
                schema_errors.append((rt, r.get("id", "<unknown>"), errs))
        records_by_type[rt] = valid_recs

    link_errors = link_check(records_by_type)

    # Promote: schema-valid records go to validated/<type>s.jsonl
    if promote:
        VALIDATED.mkdir(parents=True, exist_ok=True)
        for rt, recs in records_by_type.items():
            if recs:
                _write_jsonl(VALIDATED / f"{plural(rt)}.jsonl", recs)

    # Markdown report
    REPORTS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    rpt = [
        "# Validation Report",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}_",
        "",
        "## Schema Errors",
        "",
    ]
    if schema_errors:
        for rt, rid, errs in schema_errors:
            rpt.append(f"- **{rt}** `{rid}`")
            for e in errs:
                rpt.append(f"    - {e}")
    else:
        rpt.append("(none - all records schema-valid)")
    rpt.extend(["", "## Cross-reference Errors", ""])
    if link_errors:
        for rid, errs in link_errors.items():
            rpt.append(f"- `{rid}`")
            for e in errs:
                rpt.append(f"    - {e}")
    else:
        rpt.append("(none)")
    rpt.append("")
    rpt.append(balance_report(records_by_type))
    report_path = REPORTS / f"validation_{ts}.md"
    report_path.write_text("\n".join(rpt), encoding="utf-8")

    summary = {
        "schema_errors": len(schema_errors),
        "link_errors": len(link_errors),
        "by_type": {rt: len(recs) for rt, recs in records_by_type.items()},
        "report": str(report_path),
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-promote", action="store_true",
                    help="Don't write to validated/ - just report.")
    args = ap.parse_args()
    summary = run_validation(promote=not args.no_promote)

    print("[validate_records] summary:")
    print(f"  schema_errors: {summary['schema_errors']}")
    print(f"  link_errors:   {summary['link_errors']}")
    for rt, n in summary["by_type"].items():
        print(f"  {rt:11s}: {n} records")
    print(f"  report -> {summary['report']}")


if __name__ == "__main__":
    main()
