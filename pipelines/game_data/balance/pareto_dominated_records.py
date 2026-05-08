"""Pareto-dominance balance utility for game records (per brief #08, 2026-05-07).

Sibling to `duckdb_reports.py`. Where DuckDB reports answer "what are the
distributional stats per rarity / school / faction?", this answers
"which abilities/items are *strictly worse* than others on every measurable
axis?" — i.e. dominated points in the multi-objective design space.

Built on **pymoo NSGA-II non-dominated sorting** (Apache 2.0). Per brief #08
this is the single concrete "ML-driven balance" win at our current scale; RL
self-play / RuleSmith / Machinations.io are wrong-shaped or premature for
<1000 static records.

Writes:
  game_data/reports/pareto_<timestamp>.md         — designer-facing summary
  game_data/reports/pareto_<timestamp>_<kind>.csv — per-record-kind numeric matrix + rank

Run from the dedicated `pipelines/game_data/.venv` (has pymoo installed):

  D:\\assets\\pipelines\\game_data\\.venv\\Scripts\\python.exe \\
      pipelines\\game_data\\balance\\pareto_dominated_records.py

Per brief #08: "Surface the dominated abilities to the designer with their
dominators. Generalizes to N objectives without case-by-case SQL."
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GAME_DATA = Path(r"D:\assets\game_data")
VALIDATED = GAME_DATA / "validated"
REPORTS = GAME_DATA / "reports"


# ---------------------------------------------------------------------------
# Per-record-kind numeric extractors. Each maps a record dict to a numeric
# vector and the per-axis polarity:
#   "max" axes (player wants more — damage, healing, radius, duration)
#   "min" axes (player wants less — cost, cooldown)
#
# pymoo minimizes by convention, so we negate "max" axes before sorting.
# ---------------------------------------------------------------------------

def ability_axes(rec: dict) -> tuple[list[float], list[str], list[str]]:
    """Returns (values, labels, polarity). All abilities are scored on the
    same axis set so dominance is meaningful within a (school, tier) cohort.

    Caller should group by (school, tier) before sorting — comparing a tier-1
    nature ability to a tier-3 shadow ability is meaningless dominance-wise.
    """
    cost = rec.get("cost", {})
    effect = rec.get("effect", {})
    values = [
        float(effect.get("damage", 0)),
        float(effect.get("healing", 0)),
        float(effect.get("radius_m", 0)),
        float(effect.get("duration_sec", 0)),
        float(cost.get("mana", 0)),
        float(cost.get("stamina", 0)),
        float(cost.get("cooldown_sec", 0)),
    ]
    labels = ["damage", "healing", "radius_m", "duration_sec",
              "cost_mana", "cost_stamina", "cooldown_sec"]
    polarity = ["max", "max", "max", "max", "min", "min", "min"]
    return values, labels, polarity


def item_axes(rec: dict) -> tuple[list[float], list[str], list[str]]:
    """Items: more bonuses better, less weight/cost better."""
    bonuses = rec.get("bonuses", {})
    values = [
        float(bonuses.get("damage", 0) if isinstance(bonuses, dict) else 0),
        float(bonuses.get("armor", 0) if isinstance(bonuses, dict) else 0),
        float(bonuses.get("health", 0) if isinstance(bonuses, dict) else 0),
        float(rec.get("weight", 0) or 0),
        float(rec.get("value", 0) or 0),
    ]
    labels = ["bonus_damage", "bonus_armor", "bonus_health", "weight", "value"]
    # value is "min" because a strictly-cheaper item with same bonuses dominates.
    polarity = ["max", "max", "max", "min", "min"]
    return values, labels, polarity


# Registry: record-kind name -> (jsonl filename, axes function, group-by keys)
KINDS: dict[str, dict] = {
    "ability": {
        "filename": "abilities.jsonl",
        "axes": ability_axes,
        "group_by": ("school", "tier"),  # cohort dominance only meaningful within
    },
    "item": {
        "filename": "items.jsonl",
        "axes": item_axes,
        "group_by": ("rarity",),  # if items have rarity field; gracefully no-ops if missing
    },
}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def cohort_key(rec: dict, group_by: tuple[str, ...]) -> tuple:
    return tuple(rec.get(k, "_unset") for k in group_by)


def sort_dominance(records: list[dict], axes_fn) -> list[tuple[int, list[float], list[str], list[str]]]:
    """For one cohort: returns rows of (rank, values, labels, polarity).

    Rank 0 = non-dominated (Pareto frontier). Rank > 0 = dominated by at least
    one rank-(rank-1) record. Lower rank = better positioned.
    """
    if not records:
        return []
    import numpy as np
    from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting

    matrix = []
    labels = polarity = None
    for r in records:
        v, lab, pol = axes_fn(r)
        if labels is None:
            labels, polarity = lab, pol
        matrix.append(v)
    arr = np.array(matrix, dtype=float)
    # Negate "max" axes so pymoo's all-min interpretation gives correct dominance.
    for i, p in enumerate(polarity):
        if p == "max":
            arr[:, i] *= -1.0
    fronts = NonDominatedSorting().do(arr)
    rank = [0] * len(records)
    for r_idx, idxs in enumerate(fronts):
        for i in idxs:
            rank[i] = r_idx
    return [(rank[i], matrix[i], labels, polarity) for i in range(len(records))]


def find_dominators(records: list[dict], values: list[list[float]],
                    polarity: list[str], target_idx: int) -> list[int]:
    """For a dominated record, list which records dominate it (any rank lower).

    Record A dominates B iff A is no worse on all axes AND strictly better on
    at least one axis (under the appropriate min/max polarity).
    """
    target = values[target_idx]
    out = []
    for j, other in enumerate(values):
        if j == target_idx:
            continue
        no_worse_all = True
        strictly_better_any = False
        for i, p in enumerate(polarity):
            if p == "max":
                if other[i] < target[i]:
                    no_worse_all = False
                    break
                if other[i] > target[i]:
                    strictly_better_any = True
            else:  # min
                if other[i] > target[i]:
                    no_worse_all = False
                    break
                if other[i] < target[i]:
                    strictly_better_any = True
        if no_worse_all and strictly_better_any:
            out.append(j)
    return out


def build_report(validated: Path = VALIDATED, reports: Path = REPORTS) -> dict[str, Any]:
    reports.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    md_path = reports / f"pareto_{ts}.md"

    md_lines: list[str] = [
        f"# Pareto-Dominance Balance Report — {ts} UTC",
        "",
        "Per brief #08 (2026-05-07): records strictly worse than others on every",
        "measurable axis are surfaced as **dominated**. A record on the Pareto",
        "frontier (rank 0) is non-dominated — no other record beats it everywhere.",
        "",
        "**Cohort dominance only.** Comparing a tier-1 nature ability to a tier-3",
        "shadow ability is meaningless dominance-wise; records are grouped by",
        "design-meaningful axes (e.g. ability school+tier, item rarity) before",
        "sorting.",
        "",
        "Built on pymoo NSGA-II non-dominated sorting (Apache 2.0).",
        "",
    ]

    summary: dict[str, Any] = {"timestamp": ts, "kinds": {}}

    for kind_name, kind_spec in KINDS.items():
        path = validated / kind_spec["filename"]
        records = load_jsonl(path)
        if not records:
            md_lines.append(f"## {kind_name.title()}s")
            md_lines.append("")
            md_lines.append(f"_No validated `{kind_spec['filename']}` records — skipping._")
            md_lines.append("")
            continue

        group_by = kind_spec["group_by"]
        cohorts: dict[tuple, list[int]] = {}
        for i, r in enumerate(records):
            cohorts.setdefault(cohort_key(r, group_by), []).append(i)

        # Per-record output rows for the CSV.
        csv_rows: list[list] = []
        csv_header = ["id", "display_name", "cohort", "rank", "dominators"]

        kind_summary: dict[str, Any] = {
            "n_records": len(records),
            "n_cohorts": len(cohorts),
            "cohorts": {},
            "dominated_count": 0,
            "frontier_count": 0,
        }

        # Pluralize correctly: "ability" -> "abilities", "item" -> "items".
        plural = kind_name + "s" if not kind_name.endswith("y") else kind_name[:-1] + "ies"
        md_lines.append(f"## {plural.title()} — {len(records)} records, {len(cohorts)} cohorts")
        md_lines.append("")
        md_lines.append(f"Grouped by {' × '.join(group_by)}.")
        md_lines.append("")

        any_dominated = False
        for cohort, idxs in sorted(cohorts.items()):
            cohort_records = [records[i] for i in idxs]
            ranked = sort_dominance(cohort_records, kind_spec["axes"])
            if not ranked:
                continue
            labels = ranked[0][2]
            polarity = ranked[0][3]
            values = [row[1] for row in ranked]

            cohort_label = " / ".join(str(c) for c in cohort)
            frontier = [i for i, row in enumerate(ranked) if row[0] == 0]
            dominated = [i for i, row in enumerate(ranked) if row[0] > 0]

            kind_summary["cohorts"][cohort_label] = {
                "n": len(cohort_records),
                "frontier": len(frontier),
                "dominated": len(dominated),
            }
            kind_summary["dominated_count"] += len(dominated)
            kind_summary["frontier_count"] += len(frontier)

            for local_i, (rank, v, _, _) in enumerate(ranked):
                rec = cohort_records[local_i]
                if rank > 0:
                    dom_local = find_dominators(cohort_records, values, polarity, local_i)
                    dom_ids = [cohort_records[d]["id"] for d in dom_local]
                else:
                    dom_ids = []
                csv_rows.append([
                    rec.get("id", ""),
                    rec.get("display_name", ""),
                    cohort_label,
                    rank,
                    ";".join(dom_ids),
                ])

            if dominated:
                any_dominated = True
                md_lines.append(f"### Cohort `{cohort_label}` — {len(cohort_records)} records "
                                f"({len(frontier)} frontier, {len(dominated)} dominated)")
                md_lines.append("")
                md_lines.append("| Dominated record | Dominated by |")
                md_lines.append("|---|---|")
                for local_i, (rank, v, _, _) in enumerate(ranked):
                    if rank == 0:
                        continue
                    rec = cohort_records[local_i]
                    dom_local = find_dominators(cohort_records, values, polarity, local_i)
                    dom_ids = [cohort_records[d]["id"] for d in dom_local]
                    md_lines.append(
                        f"| `{rec.get('id','')}` ({rec.get('display_name','')}) "
                        f"| {', '.join(f'`{d}`' for d in dom_ids) or '_(none — error?)_'} |")
                md_lines.append("")

        if not any_dominated:
            md_lines.append("**No dominated records in any cohort.** Either every record is on")
            md_lines.append("its cohort's Pareto frontier (good — design space well-spread), or")
            md_lines.append("cohorts have <2 records each (the dominance check needs N≥2 per cohort).")
            md_lines.append("")

        md_lines.append(f"**{plural.title()} totals: {kind_summary['frontier_count']} on frontier, "
                        f"{kind_summary['dominated_count']} dominated across {len(cohorts)} cohorts.**")
        md_lines.append("")

        csv_path = reports / f"pareto_{ts}_{kind_name}.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(csv_header)
            w.writerows(csv_rows)

        kind_summary["csv"] = str(csv_path)
        summary["kinds"][kind_name] = kind_summary

    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("Generated by `pipelines/game_data/balance/pareto_dominated_records.py`.")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    summary["report"] = str(md_path)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validated", type=Path, default=VALIDATED,
                    help=f"Validated records dir (default: {VALIDATED})")
    ap.add_argument("--reports", type=Path, default=REPORTS,
                    help=f"Reports output dir (default: {REPORTS})")
    args = ap.parse_args()
    summary = build_report(args.validated, args.reports)
    print(f"[pareto] wrote {summary['report']}")
    for kind, ks in summary["kinds"].items():
        print(f"[pareto]   {kind}: {ks.get('frontier_count', 0)} on frontier, "
              f"{ks.get('dominated_count', 0)} dominated "
              f"({ks.get('n_cohorts', 0)} cohorts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
