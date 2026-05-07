"""Validate prop kit recipes and optional generated prop assets."""
from __future__ import annotations

import argparse
from pathlib import Path

from prop_common import LIBRARY_ROOT, build_plan, load_json, validate_kit, write_json


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", type=Path, required=True)
    ap.add_argument("--library", type=Path, default=LIBRARY_ROOT)
    ap.add_argument("--strict-assets", action="store_true", help="fail if referenced prop assets are not generated yet")
    ap.add_argument("--report", type=Path, default=None, help="optional JSON validation report path")
    args = ap.parse_args()

    kit = load_json(args.kit)
    issues, recipes = validate_kit(kit, args.kit)
    plan = build_plan(args.kit, out_id=f"{kit.get('id', args.kit.stem)}_validation", library_root=args.library)

    asset_issues = []
    if args.strict_assets:
        for variant in plan["variants"]:
            if variant["status"] != "ready":
                asset_issues.append(f"{variant['id']}: asset status is {variant['status']} ({', '.join(variant['missing_files'])})")

    report = {
        "kit": kit.get("id"),
        "kit_path": str(args.kit),
        "recipes_loaded": len(recipes),
        "validation_issues": issues,
        "asset_issues": asset_issues,
        "summary": plan["summary"],
    }
    if args.report:
        write_json(args.report, report)

    print(f"kit: {kit.get('id')}")
    print(f"recipes loaded: {len(recipes)}")
    print(f"variants planned: {plan['summary']['variants']}")
    print(f"ready/partial/missing: {plan['summary']['ready']}/{plan['summary']['partial']}/{plan['summary']['missing']}")
    print(f"validation issues: {len(issues)}")
    for issue in issues:
        print(f"  - {issue}")
    if args.strict_assets:
        print(f"asset issues: {len(asset_issues)}")
        for issue in asset_issues[:50]:
            print(f"  - {issue}")
        if len(asset_issues) > 50:
            print(f"  ... {len(asset_issues) - 50} more")

    if issues or asset_issues:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

