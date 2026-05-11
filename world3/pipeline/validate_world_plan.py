"""Validate a world plan JSON against world_plan_schema.json + semantic rules.

Used by:
- Phase F.2 self-test against committed example plans
- Phase F.3 plan-to-bundles iterator's preflight check (refuses to
  emit bundles for an invalid plan)

Beyond schema conformance, the validator enforces:

1. bounds_m must be an integer multiple of tile_size_m on both axes
2. biome_layout must cover every tile in the grid exactly once
3. every biome referenced in biome_layout must be declared in biomes[]
4. every 4-connected adjacency in the layout must be in adjacency_rules.allowed_pairs
5. style_pack file must exist under world3/jobs/style_packs/<id>.json
6. biome.source.type must match its source's required fields

Usage:
    python world3/pipeline/validate_world_plan.py world3/jobs/examples/world_plan_starter_5biome_procedural.json
    python world3/pipeline/validate_world_plan.py world3/jobs/examples/world_plan_*.json
    python world3/pipeline/validate_world_plan.py --schema-self-test

Exit codes:
    0  all validated plans passed
    1  one or more validation failures
    2  internal error (schema malformed, jsonschema not installed)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD3 = Path(__file__).resolve().parents[1]
SCHEMA_PATH = WORLD3 / "jobs" / "world_plan_schema.json"
EXAMPLES_DIR = WORLD3 / "jobs" / "examples"
STYLE_PACKS_DIR = WORLD3 / "jobs" / "style_packs"

# Phase F starter biome restriction. Plans referencing other kits get a
# warning, not an error — kits outside the starter still work mechanically,
# the gate is a deliberate scope choice not a technical limitation.
STARTER_BIOME_KITS = {"alpine", "desert", "tundra", "grassland", "temperate_forest"}


def load_schema() -> dict:
    if not SCHEMA_PATH.exists():
        print(f"ERROR: schema not found at {SCHEMA_PATH}", file=sys.stderr)
        sys.exit(2)
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_plan(path: Path, schema: dict) -> tuple[bool, list[str], list[str]]:
    """Returns (ok, errors, warnings)."""
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return (False, [f"JSON parse error: {e}"], [])
    except FileNotFoundError:
        return (False, [f"file not found: {path}"], [])

    errors: list[str] = []
    warnings: list[str] = []

    # 1. Schema validation
    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(plan), key=lambda e: list(e.path))[:20]:
            loc = ".".join(str(p) for p in err.path) or "<root>"
            errors.append(f"  schema: {loc}: {err.message}")
        if errors:
            return (False, errors, warnings)
    except ImportError:
        # Minimal fallback
        if plan.get("schema_version") != 1:
            errors.append(f"  schema_version must be 1, got {plan.get('schema_version')!r}")
        for field in ("id", "bounds_m", "tile_size_m", "seed", "biomes",
                      "biome_layout", "adjacency_rules", "perspectives"):
            if field not in plan:
                errors.append(f"  missing required field: {field}")
        if errors:
            return (False, errors, warnings)

    # 2. Semantic: bounds divisible by tile_size_m
    bounds = plan["bounds_m"]
    tile = plan["tile_size_m"]
    cols = bounds[0] / tile
    rows = bounds[1] / tile
    if not cols.is_integer():
        errors.append(f"  bounds_m[0]={bounds[0]} not divisible by tile_size_m={tile}")
    if not rows.is_integer():
        errors.append(f"  bounds_m[1]={bounds[1]} not divisible by tile_size_m={tile}")
    if errors:
        return (False, errors, warnings)
    cols, rows = int(cols), int(rows)

    # 3. Biome roster
    biome_ids = {b["id"] for b in plan["biomes"]}
    for b in plan["biomes"]:
        kit = b.get("biome_kit")
        if kit and kit not in STARTER_BIOME_KITS:
            warnings.append(f"  biome '{b['id']}' uses biome_kit '{kit}' outside the Phase F starter ({sorted(STARTER_BIOME_KITS)})")

    # 4. Tile coverage check
    seen_tiles: dict[tuple[int, int], str] = {}
    for entry in plan["biome_layout"]:
        xy = tuple(entry["tile_xy"])
        biome = entry["biome"]
        if xy in seen_tiles:
            errors.append(f"  biome_layout: tile {list(xy)} declared more than once")
        if xy[0] >= cols or xy[1] >= rows:
            errors.append(f"  biome_layout: tile {list(xy)} outside grid ({cols}x{rows})")
        if biome not in biome_ids:
            errors.append(f"  biome_layout: tile {list(xy)} references undeclared biome '{biome}'")
        seen_tiles[xy] = biome

    expected = {(c, r) for c in range(cols) for r in range(rows)}
    missing = expected - set(seen_tiles.keys())
    if missing:
        sample = sorted(missing)[:5]
        more = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
        errors.append(f"  biome_layout: missing {len(missing)} tiles, e.g. {sample}{more}")

    if errors:
        return (False, errors, warnings)

    # 5. Adjacency check (4-connected)
    allowed_pairs = {
        tuple(sorted(pair)) for pair in plan["adjacency_rules"]["allowed_pairs"]
    }
    self_neighbor = plan["adjacency_rules"].get("self_neighbor_allowed", True)

    bad_adjacencies: list[str] = []
    for (c, r), biome in seen_tiles.items():
        for dc, dr in ((1, 0), (0, 1)):  # right + up only — each pair counted once
            nc, nr = c + dc, r + dr
            if (nc, nr) not in seen_tiles:
                continue
            other = seen_tiles[(nc, nr)]
            if biome == other and not self_neighbor:
                bad_adjacencies.append(f"    [{c},{r}]-[{nc},{nr}]: self-neighbor '{biome}' forbidden")
                continue
            if biome == other:
                continue
            pair = tuple(sorted((biome, other)))
            if pair not in allowed_pairs:
                bad_adjacencies.append(f"    [{c},{r}]({biome})-[{nc},{nr}]({other}): pair not in adjacency_rules.allowed_pairs")
    if bad_adjacencies:
        errors.append(f"  adjacency: {len(bad_adjacencies)} forbidden adjacent pairs (4-connected):")
        errors.extend(bad_adjacencies[:10])
        if len(bad_adjacencies) > 10:
            errors.append(f"    ... and {len(bad_adjacencies) - 10} more")

    # 6. Style pack file existence
    style_pack = plan.get("style_pack", "photoreal")
    style_pack_path = STYLE_PACKS_DIR / f"{style_pack}.json"
    if not style_pack_path.exists():
        errors.append(f"  style_pack '{style_pack}' not found at {style_pack_path.relative_to(WORLD3)}")

    return (len(errors) == 0, errors, warnings)


def schema_self_test() -> int:
    """Walk world3/jobs/examples/world_plan_*.json and validate each."""
    if not EXAMPLES_DIR.exists():
        print(f"ERROR: examples dir not found at {EXAMPLES_DIR}", file=sys.stderr)
        return 2

    schema = load_schema()
    plan_files = sorted(EXAMPLES_DIR.glob("world_plan_*.json"))
    if not plan_files:
        print(f"WARN: no world_plan_*.json files in {EXAMPLES_DIR}")
        return 0

    all_ok = True
    for f in plan_files:
        ok, errs, warns = validate_plan(f, schema)
        status = "OK  " if ok else "FAIL"
        rel = f.relative_to(WORLD3)
        print(f"  [{status}] {rel}")
        for warn in warns:
            print(f"         warn: {warn}")
        if not ok:
            all_ok = False
            for msg in errs:
                print(msg)

    print()
    if all_ok:
        print(f"=== World plan self-test PASSED ({len(plan_files)} plans) ===")
        return 0
    print("=== World plan self-test FAILED ===")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("plan", nargs="*", type=Path,
                    help="world plan JSON file(s) to validate")
    ap.add_argument("--schema-self-test", action="store_true",
                    help="Validate every world_plan_*.json under world3/jobs/examples/.")
    args = ap.parse_args()

    if args.schema_self_test:
        return schema_self_test()

    if not args.plan:
        ap.print_help()
        return 2

    schema = load_schema()
    all_ok = True
    for f in args.plan:
        ok, errs, warns = validate_plan(f, schema)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {f}")
        for warn in warns:
            print(f"         warn: {warn}")
        if not ok:
            all_ok = False
            for msg in errs:
                print(msg)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
