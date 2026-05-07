"""DuckDB balance reports for validated game data.

Writes:
  game_data/reports/balance_duckdb_<timestamp>.md
  game_data/reports/balance_duckdb_<timestamp>_ability_cost_effect.csv
  game_data/reports/balance_duckdb_<timestamp>_item_value_rarity.csv
  game_data/reports/balance_duckdb_<timestamp>_faction_ability_crosstab.csv
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

GAME_DATA = Path(r"D:\assets\game_data")
VALIDATED = GAME_DATA / "validated"
REPORTS = GAME_DATA / "reports"


def _rel(path: Path) -> str:
    return str(path).replace("\\", "/")


def _sql_path(path: Path) -> str:
    return _rel(path).replace("'", "''")


def _write_csv(path: Path, rows: list[tuple], header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def _table_exists(path: Path) -> bool:
    return path.exists() and path.read_text(encoding="utf-8").strip() != ""


def build_reports(validated: Path = VALIDATED, reports: Path = REPORTS) -> dict[str, Path | int]:
    import duckdb

    reports.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    md_path = reports / f"balance_duckdb_{ts}.md"
    ability_csv = reports / f"balance_duckdb_{ts}_ability_cost_effect.csv"
    item_csv = reports / f"balance_duckdb_{ts}_item_value_rarity.csv"
    faction_csv = reports / f"balance_duckdb_{ts}_faction_ability_crosstab.csv"

    con = duckdb.connect()
    paths = {
        "items": validated / "items.jsonl",
        "abilities": validated / "abilities.jsonl",
        "npcs": validated / "npcs.jsonl",
        "factions": validated / "factions.jsonl",
    }
    for table, path in paths.items():
        if _table_exists(path):
            con.execute(
                f"CREATE OR REPLACE VIEW {table} AS "
                f"SELECT * FROM read_json_auto('{_sql_path(path)}', format='newline_delimited')",
            )

    item_rows: list[tuple] = []
    if _table_exists(paths["items"]):
        item_rows = con.execute(
            """
            SELECT
              id,
              category,
              rarity,
              stats.damage::DOUBLE AS damage,
              stats.armor::DOUBLE AS armor,
              stats.value_gold::DOUBLE AS value_gold,
              CASE
                WHEN stats.damage > 0 THEN stats.value_gold::DOUBLE / NULLIF(stats.damage, 0)
                WHEN stats.armor > 0 THEN stats.value_gold::DOUBLE / NULLIF(stats.armor, 0)
                ELSE stats.value_gold::DOUBLE
              END AS value_per_power
            FROM items
            ORDER BY rarity, category, id
            """
        ).fetchall()
        _write_csv(
            item_csv,
            item_rows,
            ["id", "category", "rarity", "damage", "armor", "value_gold", "value_per_power"],
        )

    ability_rows: list[tuple] = []
    if _table_exists(paths["abilities"]):
        ability_rows = con.execute(
            """
            SELECT
              id,
              school,
              tier,
              cost.mana::DOUBLE AS mana,
              cost.cooldown_sec::DOUBLE AS cooldown_sec,
              effect.damage::DOUBLE AS damage,
              effect.damage_type AS damage_type,
              effect.damage::DOUBLE / NULLIF(cost.mana, 0) AS damage_per_mana,
              effect.damage::DOUBLE / NULLIF(cost.cooldown_sec, 0) AS damage_per_cooldown
            FROM abilities
            ORDER BY tier, school, id
            """
        ).fetchall()
        _write_csv(
            ability_csv,
            ability_rows,
            [
                "id", "school", "tier", "mana", "cooldown_sec", "damage",
                "damage_type", "damage_per_mana", "damage_per_cooldown",
            ],
        )

    faction_rows: list[tuple] = []
    if _table_exists(paths["npcs"]) and _table_exists(paths["abilities"]):
        faction_rows = con.execute(
            """
            WITH npc_ability AS (
              SELECT
                COALESCE(faction_id, 'unassigned') AS faction_id,
                UNNEST(abilities) AS ability_id
              FROM npcs
            )
            SELECT
              faction_id,
              a.school,
              a.tier,
              COUNT(*) AS linked_count
            FROM npc_ability na
            JOIN abilities a ON a.id = na.ability_id
            GROUP BY faction_id, a.school, a.tier
            ORDER BY faction_id, a.school, a.tier
            """
        ).fetchall()
        _write_csv(
            faction_csv,
            faction_rows,
            ["faction_id", "ability_school", "ability_tier", "linked_count"],
        )

    item_summary = []
    if _table_exists(paths["items"]):
        item_summary = con.execute(
            """
            SELECT rarity, category, COUNT(*) AS n,
                   ROUND(AVG(stats.value_gold), 2) AS avg_value,
                   ROUND(AVG(stats.damage), 2) AS avg_damage,
                   ROUND(AVG(stats.armor), 2) AS avg_armor
            FROM items
            GROUP BY rarity, category
            ORDER BY rarity, category
            """
        ).fetchall()

    ability_summary = []
    if _table_exists(paths["abilities"]):
        ability_summary = con.execute(
            """
            SELECT school, tier, COUNT(*) AS n,
                   ROUND(AVG(cost.mana), 2) AS avg_mana,
                   ROUND(AVG(cost.cooldown_sec), 2) AS avg_cd,
                   ROUND(AVG(effect.damage), 2) AS avg_damage
            FROM abilities
            GROUP BY school, tier
            ORDER BY school, tier
            """
        ).fetchall()

    lines = [
        "# DuckDB Balance Report",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}_",
        "",
        "## Item Value vs Rarity",
        "",
    ]
    if item_summary:
        lines.append("| Rarity | Category | N | Avg Value | Avg Damage | Avg Armor |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for rarity, category, n, avg_value, avg_damage, avg_armor in item_summary:
            lines.append(f"| {rarity} | {category} | {n} | {avg_value} | {avg_damage} | {avg_armor} |")
        lines.append("")
        lines.append(f"CSV: `{_rel(item_csv)}`")
    else:
        lines.append("(no item records)")

    lines.extend(["", "## Ability Cost vs Effect", ""])
    if ability_summary:
        lines.append("| School | Tier | N | Avg Mana | Avg Cooldown | Avg Damage |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for school, tier, n, avg_mana, avg_cd, avg_damage in ability_summary:
            lines.append(f"| {school} | {tier} | {n} | {avg_mana} | {avg_cd} | {avg_damage} |")
        lines.append("")
        lines.append(f"CSV: `{_rel(ability_csv)}`")
    else:
        lines.append("(no ability records)")

    lines.extend(["", "## Faction Ability Crosstab", ""])
    if faction_rows:
        lines.append("| Faction | School | Tier | Linked Count |")
        lines.append("|---|---|---:|---:|")
        for faction_id, school, tier, count in faction_rows:
            lines.append(f"| {faction_id} | {school} | {tier} | {count} |")
        lines.append("")
        lines.append(f"CSV: `{_rel(faction_csv)}`")
    else:
        lines.append("(no NPC ability/faction links found)")

    lines.extend([
        "",
        "## Notes",
        "",
        "- Current schemas do not attach items directly to factions, so rarity-by-faction is represented by NPC-linked ability coverage today.",
        "- The CSV outputs are intentionally flat so they can be plotted as scatter/crosstab views by a later dashboard.",
        "",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "markdown": md_path,
        "item_csv": item_csv if item_rows else None,
        "ability_csv": ability_csv if ability_rows else None,
        "faction_csv": faction_csv if faction_rows else None,
        "items": len(item_rows),
        "abilities": len(ability_rows),
        "faction_links": len(faction_rows),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validated", type=Path, default=VALIDATED)
    ap.add_argument("--reports", type=Path, default=REPORTS)
    args = ap.parse_args()

    result = build_reports(args.validated, args.reports)
    print(f"[duckdb_reports] markdown -> {result['markdown']}")
    print(f"[duckdb_reports] rows: items={result['items']} abilities={result['abilities']} faction_links={result['faction_links']}")
    for key in ("item_csv", "ability_csv", "faction_csv"):
        if result.get(key):
            print(f"[duckdb_reports] {key} -> {result[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
