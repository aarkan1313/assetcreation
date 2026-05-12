"""Validate a region_request.json against world3/jobs/region_request_schema.json.

Used by:
- Phase E.1 to verify the schema is well-formed (validates the 3 examples)
- Phase E.3 orchestrator (world3_make.py) as its first step — refuses
  malformed requests before running any pipeline stages

Usage:
    python world3/pipeline/validate_region_request.py jobs/examples/gloss_real.json
    python world3/pipeline/validate_region_request.py jobs/examples/*.json
    python world3/pipeline/validate_region_request.py --schema-self-test

Exit codes:
    0  all validated requests passed
    1  one or more validation failures
    2  internal error (schema malformed, jsonschema not installed, etc.)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # D:/assets
WORLD3_ROOT = Path(__file__).resolve().parents[1]  # D:/assets/world3
SCHEMA_PATH = WORLD3_ROOT / "jobs" / "region_request_schema.json"


def load_schema() -> dict:
    if not SCHEMA_PATH.exists():
        print(f"ERROR: schema not found at {SCHEMA_PATH}", file=sys.stderr)
        sys.exit(2)
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_request(request_path: Path, schema: dict) -> tuple[bool, list[str]]:
    """Returns (ok, list_of_error_messages)."""
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return (False, [f"JSON parse error: {e}"])
    except FileNotFoundError:
        return (False, [f"file not found: {request_path}"])

    # Use jsonschema if available; otherwise do a minimal subset check.
    try:
        import jsonschema
    except ImportError:
        return _minimal_validate(request, schema)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(request), key=lambda e: e.path)
    if not errors:
        return (True, [])
    msgs = []
    for err in errors[:20]:  # cap at 20 to keep output readable
        path = ".".join(str(p) for p in err.path) or "<root>"
        msgs.append(f"  {path}: {err.message}")
    if len(errors) > 20:
        msgs.append(f"  ... and {len(errors) - 20} more errors")
    return (False, msgs)


def _minimal_validate(request: dict, schema: dict) -> tuple[bool, list[str]]:
    """Fallback validation when jsonschema isn't installed.

    Checks the most load-bearing constraints by hand: required top-level
    fields, schema_version, source.type discriminator. Not exhaustive;
    real validation needs the jsonschema package."""
    errors = []
    required = schema.get("required", [])
    for key in required:
        if key not in request:
            errors.append(f"  <root>: missing required '{key}'")
    if request.get("schema_version") != 1:
        errors.append(f"  schema_version: must be 1, got {request.get('schema_version')!r}")
    src = request.get("source")
    if isinstance(src, dict):
        stype = src.get("type")
        if stype not in ("real", "procedural", "hybrid"):
            errors.append(f"  source.type: must be one of real/procedural/hybrid, got {stype!r}")
    return (len(errors) == 0, errors)


def schema_self_test() -> int:
    """Walk world3/jobs/examples/*.json and validate each. Used by
    Phase E.1 to confirm the schema is well-formed against the
    handcrafted examples that map to real existing bundles."""
    examples_dir = WORLD3_ROOT / "jobs" / "examples"
    if not examples_dir.exists():
        print(f"ERROR: examples dir not found at {examples_dir}", file=sys.stderr)
        return 2

    schema = load_schema()
    # Skip world_plan_*.json — those are world plans (F.2), validated by
    # validate_world_plan.py against a different schema. The region_request
    # self-test only covers single-bundle requests.
    example_files = sorted(
        p for p in examples_dir.glob("*.json")
        if not p.name.startswith("world_plan_")
    )
    if not example_files:
        print(f"WARN: no example files in {examples_dir}")
        return 0

    all_ok = True
    for f in example_files:
        ok, errors = validate_request(f, schema)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {f.relative_to(WORLD3_ROOT)}")
        if not ok:
            all_ok = False
            for msg in errors:
                print(msg)

    print()
    if all_ok:
        print(f"=== Schema self-test PASSED ({len(example_files)} examples) ===")
        return 0
    print(f"=== Schema self-test FAILED ===")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("request", nargs="*", type=Path,
                    help="region_request.json file(s) to validate")
    ap.add_argument("--schema-self-test", action="store_true",
                    help="Validate all files in world3/jobs/examples/. "
                         "Exit 0 if all pass; 1 if any fail.")
    args = ap.parse_args()

    if args.schema_self_test:
        return schema_self_test()

    if not args.request:
        ap.print_help()
        return 2

    schema = load_schema()
    all_ok = True
    for f in args.request:
        ok, errors = validate_request(f, schema)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {f}")
        if not ok:
            all_ok = False
            for msg in errors:
                print(msg)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
