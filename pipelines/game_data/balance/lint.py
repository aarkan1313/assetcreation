"""Validate balance targets and compare them with current accepted records."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from balance.schema import DEFAULT_TARGETS, load_targets, sha256_file  # noqa: E402
from schemas import plural  # noqa: E402

GAME_DATA = Path(r"D:\assets\game_data")
VALIDATED = GAME_DATA / "validated"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _range(values: list[float]) -> str:
    if not values:
        return "no records"
    return f"n={len(values)} median={statistics.median(values):.1f} range={min(values):.1f}..{max(values):.1f}"


def current_range_report() -> list[str]:
    lines: list[str] = []
    items = _read_jsonl(VALIDATED / f"{plural('item')}.jsonl")
    by_rarity: dict[str, list[float]] = defaultdict(list)
    for rec in items:
        if rec.get("category") == "weapon":
            by_rarity[rec.get("rarity", "common")].append(float(rec.get("stats", {}).get("damage", 0)))
    if by_rarity:
        lines.append("Current weapon damage by rarity:")
        for rarity in ("common", "uncommon", "rare", "epic", "legendary"):
            lines.append(f"  {rarity:9s} {_range(by_rarity.get(rarity, []))}")

    abilities = _read_jsonl(VALIDATED / f"{plural('ability')}.jsonl")
    by_tier: dict[int, list[float]] = defaultdict(list)
    for rec in abilities:
        by_tier[int(rec.get("tier", 1))].append(float(rec.get("effect", {}).get("damage", 0)))
    if by_tier:
        lines.append("Current ability damage by tier:")
        for tier in sorted(by_tier):
            lines.append(f"  T{tier:<2d} {_range(by_tier[tier])}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", type=Path, default=DEFAULT_TARGETS)
    args = ap.parse_args()

    targets = load_targets(args.path)
    print(f"[balance.lint] ok schema_version={targets.schema_version}")
    print(f"[balance.lint] sha256={sha256_file(args.path)}")
    for line in current_range_report():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

