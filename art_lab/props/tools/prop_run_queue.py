"""Run safe CPU-only tasks from a prop queue.

Currently supports decal generation. Blender/local-AI tasks are intentionally
skipped unless separate generator implementations are added later.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from prop_common import ASSET_ROOT, load_json, write_json
from prop_make_decal import generate_decal


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0, help="0 means no limit")
    ap.add_argument("--only", choices=["decal"], default="decal")
    args = ap.parse_args()

    queue = load_json(args.queue)
    tasks = queue.get("tasks", [])
    if args.limit:
        tasks = tasks[:args.limit]

    results = []
    skipped = []
    for task in tasks:
        action = task.get("next_action")
        if args.only == "decal" and action != "generate_decal_texture":
            skipped.append({"id": task.get("id"), "reason": f"unsupported action {action}"})
            continue
        recipe = ASSET_ROOT / task["recipe"]
        out = ASSET_ROOT / task["library_dir"]
        results.append(generate_decal(recipe, task["id"], out))

    report = {
        "queue": str(args.queue),
        "ran": len(results),
        "skipped": skipped,
        "results": results,
    }
    report_path = args.queue.parent / f"{queue.get('queue', 'queue')}_run_report.json"
    write_json(report_path, report)
    print(f"ran: {len(results)}")
    print(f"skipped: {len(skipped)}")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

