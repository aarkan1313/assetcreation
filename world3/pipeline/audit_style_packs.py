"""Audit every style pack under world3/jobs/style_packs/.

Beyond `validate_style_pack.py --schema-self-test` (which only checks
schema conformance), this script checks each pack for semantic issues:

- Render field values within reasonable real-world ranges (warn, not fail)
- material_suffix references a buildable material variant (if non-empty)
- pack id is unique across all packs

Usage:
    python world3/pipeline/audit_style_packs.py
    python world3/pipeline/audit_style_packs.py --json

Exit codes:
    0  all packs audit cleanly
    1  one or more packs have issues
    2  internal error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORLD3 = Path(__file__).resolve().parents[1]
PACKS_DIR = WORLD3 / "jobs" / "style_packs"
WGV3_DIR = WORLD3 / "textures" / "wgv3"


def audit_pack(path: Path) -> dict:
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"id": path.stem, "ok": False, "errors": [f"JSON parse: {e}"], "warnings": []}

    errors: list[str] = []
    warnings: list[str] = []

    render = pack.get("render", {})

    # Semantic warnings — values that pass schema but are likely wrong
    if render.get("sun_energy", 1.0) > 4.0:
        warnings.append(f"sun_energy={render['sun_energy']} is unusually high (>4.0)")
    if render.get("tonemap_exposure", 1.0) < 0.3:
        warnings.append(f"tonemap_exposure={render['tonemap_exposure']} is very dark (<0.3)")
    if render.get("roughness_floor", 0.04) > 0.95:
        warnings.append(f"roughness_floor={render['roughness_floor']} essentially eliminates specular")

    # material_suffix consistency check
    suffix = pack.get("material_suffix", "")
    if suffix:
        # Look for any terrain_blend_<kit>_<mode>_<suffix>.tres anywhere
        # under wgv3/ — if zero matches exist, suffix is unused/typo
        matches = list(WGV3_DIR.glob(f"terrain_blend_*_{suffix}.tres"))
        if not matches:
            errors.append(
                f"material_suffix={suffix!r} has no matching variants under "
                f"{WGV3_DIR.relative_to(WORLD3)} (looking for terrain_blend_*_{suffix}.tres)"
            )

    return {
        "id": pack.get("id", path.stem),
        "path": str(path.relative_to(WORLD3)),
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON result")
    args = ap.parse_args()

    if not PACKS_DIR.exists():
        print(f"ERROR: packs dir not found at {PACKS_DIR}", file=sys.stderr)
        return 2

    pack_files = sorted(p for p in PACKS_DIR.glob("*.json")
                        if p.name != "style_pack_schema.json")

    results = [audit_pack(p) for p in pack_files]

    # Cross-pack: id uniqueness
    ids: dict[str, list[str]] = {}
    for r in results:
        ids.setdefault(r["id"], []).append(r["path"])
    cross_errors: list[str] = []
    for pid, paths in ids.items():
        if len(paths) > 1:
            cross_errors.append(f"id {pid!r} declared in multiple packs: {paths}")

    all_ok = all(r["ok"] for r in results) and not cross_errors

    if args.json:
        print(json.dumps({
            "ok": all_ok,
            "packs": results,
            "cross_errors": cross_errors,
        }, indent=2))
        return 0 if all_ok else 1

    print(f"=== Style pack audit ({len(results)} packs) ===\n")
    for r in results:
        sym = "OK  " if r["ok"] else "FAIL"
        print(f"  [{sym}] {r['id']}  ({r['path']})")
        for err in r["errors"]:
            print(f"         ERROR: {err}")
        for warn in r["warnings"]:
            print(f"         warn:  {warn}")
    if cross_errors:
        print("\n=== Cross-pack errors ===")
        for err in cross_errors:
            print(f"  {err}")

    print()
    if all_ok:
        print("=== All style packs audit cleanly. ===")
        return 0
    print("=== One or more style packs have errors. ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())
