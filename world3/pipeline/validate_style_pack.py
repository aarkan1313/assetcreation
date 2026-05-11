"""Validate a style pack JSON against world3/jobs/style_packs/style_pack_schema.json.

Used by:
- Phase E.5 backfill (E.8) to verify the photoreal pack + any future pack
- Pre-flight check in run_orchestrator_capture.py (manual today)

Usage:
    python world3/pipeline/validate_style_pack.py world3/jobs/style_packs/photoreal.json
    python world3/pipeline/validate_style_pack.py world3/jobs/style_packs/*.json
    python world3/pipeline/validate_style_pack.py --schema-self-test

Exit codes:
    0  all validated packs passed
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
SCHEMA_PATH = WORLD3 / "jobs" / "style_packs" / "style_pack_schema.json"
PACKS_DIR = WORLD3 / "jobs" / "style_packs"


def load_schema() -> dict:
    if not SCHEMA_PATH.exists():
        print(f"ERROR: schema not found at {SCHEMA_PATH}", file=sys.stderr)
        sys.exit(2)
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_pack(path: Path, schema: dict) -> tuple[bool, list[str]]:
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return (False, [f"JSON parse error: {e}"])
    except FileNotFoundError:
        return (False, [f"file not found: {path}"])

    try:
        import jsonschema
    except ImportError:
        return _minimal_validate(pack, path)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(pack), key=lambda e: list(e.path))
    if errors:
        msgs = []
        for err in errors[:10]:
            loc = ".".join(str(p) for p in err.path) or "<root>"
            msgs.append(f"  {loc}: {err.message}")
        if len(errors) > 10:
            msgs.append(f"  ... and {len(errors) - 10} more")
        return (False, msgs)

    # Additional checks the schema can't express:
    # 1. id must match filename (without .json)
    expected_id = path.stem
    if pack.get("id") != expected_id:
        return (False, [f"id {pack.get('id')!r} does not match filename stem {expected_id!r}"])
    return (True, [])


def _minimal_validate(pack: dict, path: Path) -> tuple[bool, list[str]]:
    errors = []
    if pack.get("schema_version") != 1:
        errors.append(f"  schema_version: must be 1, got {pack.get('schema_version')!r}")
    if "id" not in pack:
        errors.append("  <root>: missing required 'id'")
    if "render" not in pack:
        errors.append("  <root>: missing required 'render'")
    if pack.get("id") != path.stem:
        errors.append(f"  id {pack.get('id')!r} does not match filename stem {path.stem!r}")
    return (len(errors) == 0, errors)


def schema_self_test() -> int:
    if not PACKS_DIR.exists():
        print(f"ERROR: packs dir not found at {PACKS_DIR}", file=sys.stderr)
        return 2

    schema = load_schema()
    pack_files = sorted(p for p in PACKS_DIR.glob("*.json")
                        if p.name != "style_pack_schema.json")
    if not pack_files:
        print(f"WARN: no pack files in {PACKS_DIR}")
        return 0

    all_ok = True
    for f in pack_files:
        ok, errs = validate_pack(f, schema)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {f.relative_to(WORLD3)}")
        if not ok:
            all_ok = False
            for msg in errs:
                print(msg)
    print()
    if all_ok:
        print(f"=== Style pack self-test PASSED ({len(pack_files)} packs) ===")
        return 0
    print("=== Style pack self-test FAILED ===")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("packs", nargs="*", type=Path,
                    help="style pack JSON file(s) to validate")
    ap.add_argument("--schema-self-test", action="store_true",
                    help="Validate every pack under world3/jobs/style_packs/. "
                         "Exit 0 if all pass; 1 if any fail.")
    args = ap.parse_args()

    if args.schema_self_test:
        return schema_self_test()

    if not args.packs:
        ap.print_help()
        return 2

    schema = load_schema()
    all_ok = True
    for f in args.packs:
        ok, errs = validate_pack(f, schema)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {f}")
        if not ok:
            all_ok = False
            for msg in errs:
                print(msg)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
