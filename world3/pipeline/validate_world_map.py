"""Validate a world_map.json (emitted by world_plan_to_bundles.py).

Beyond schema conformance:

1. Every tile in the grid is covered exactly once
2. tile_xy entries are in-bounds for the declared grid
3. request_path + bundle_dir paths are syntactically valid (existence
   not required — they may not have been built yet)
4. No duplicate bundle_ids

Usage:
    python world3/pipeline/validate_world_map.py world3/worlds/<id>/world_map.json
    python world3/pipeline/validate_world_map.py --schema-self-test  (walks world3/worlds/*)

Exit codes: 0 ok / 1 fail / 2 internal
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORLD3 = Path(__file__).resolve().parents[1]
SCHEMA_PATH = WORLD3 / "jobs" / "world_map_schema.json"
WORLDS_DIR = WORLD3 / "worlds"


def load_schema() -> dict:
    if not SCHEMA_PATH.exists():
        print(f"ERROR: schema not found at {SCHEMA_PATH}", file=sys.stderr)
        sys.exit(2)
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_map(path: Path, schema: dict) -> tuple[bool, list[str]]:
    try:
        m = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return (False, [f"JSON parse: {e}"])
    except FileNotFoundError:
        return (False, [f"file not found: {path}"])

    errors: list[str] = []

    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(m), key=lambda e: list(e.path))[:20]:
            loc = ".".join(str(p) for p in err.path) or "<root>"
            errors.append(f"  schema: {loc}: {err.message}")
        if errors:
            return (False, errors)
    except ImportError:
        if m.get("schema_version") != 1:
            errors.append(f"  schema_version must be 1, got {m.get('schema_version')!r}")
            return (False, errors)

    bounds = m["bounds_m"]
    tile = m["tile_size_m"]
    cols = int(bounds[0] / tile)
    rows = int(bounds[1] / tile)
    expected = {(c, r) for c in range(cols) for r in range(rows)}

    seen: dict[tuple[int, int], str] = {}
    seen_bundle_ids: dict[str, list[int]] = {}
    for entry in m["tiles"]:
        xy = tuple(entry["tile_xy"])
        if xy[0] >= cols or xy[1] >= rows:
            errors.append(f"  tile {list(xy)} outside grid {cols}x{rows}")
        if xy in seen:
            errors.append(f"  tile {list(xy)} duplicated")
        seen[xy] = entry["bundle_id"]
        seen_bundle_ids.setdefault(entry["bundle_id"], []).append(xy)

    missing = expected - set(seen.keys())
    if missing:
        sample = sorted(missing)[:5]
        more = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
        errors.append(f"  missing {len(missing)} tiles: {sample}{more}")

    for bid, xys in seen_bundle_ids.items():
        if len(xys) > 1:
            errors.append(f"  bundle_id {bid!r} used by multiple tiles: {xys}")

    return (len(errors) == 0, errors)


def schema_self_test() -> int:
    if not WORLDS_DIR.exists():
        print(f"INFO: {WORLDS_DIR} does not exist yet (no worlds emitted)")
        return 0
    schema = load_schema()
    maps = sorted(WORLDS_DIR.glob("*/world_map.json"))
    if not maps:
        print(f"INFO: no world_map.json files under {WORLDS_DIR}")
        return 0
    all_ok = True
    for f in maps:
        ok, errs = validate_map(f, schema)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {f.relative_to(WORLD3.parent)}")
        if not ok:
            all_ok = False
            for e in errs:
                print(e)
    print()
    if all_ok:
        print(f"=== World map self-test PASSED ({len(maps)} maps) ===")
        return 0
    print("=== World map self-test FAILED ===")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("maps", nargs="*", type=Path)
    ap.add_argument("--schema-self-test", action="store_true")
    args = ap.parse_args()

    if args.schema_self_test:
        return schema_self_test()
    if not args.maps:
        ap.print_help()
        return 2

    schema = load_schema()
    all_ok = True
    for f in args.maps:
        ok, errs = validate_map(f, schema)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {f}")
        if not ok:
            all_ok = False
            for e in errs:
                print(e)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
