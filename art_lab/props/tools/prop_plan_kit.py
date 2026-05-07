"""Build a CPU-only prop kit generation plan and future work queues."""
from __future__ import annotations

import argparse
from pathlib import Path

from prop_common import OUTPUT_ROOT, build_plan, queue_command_hint, write_json


def write_review_md(out_dir: Path, plan: dict) -> None:
    lines = [
        f"# Prop Kit Plan: {plan['kit']}",
        "",
        f"Created: {plan['created_utc']}",
        f"Kit: `{plan['kit_path']}`",
        f"Library: `{plan['library_root']}`",
        "",
        "## Summary",
        "",
        f"- Families: {plan['summary']['families']}",
        f"- Variants: {plan['summary']['variants']}",
        f"- Ready: {plan['summary']['ready']}",
        f"- Partial: {plan['summary']['partial']}",
        f"- Missing: {plan['summary']['missing']}",
        f"- Blender tasks: {plan['summary']['blender_tasks']}",
        f"- Local AI tasks: {plan['summary']['local_ai_tasks']}",
        f"- Decal tasks: {plan['summary']['decal_tasks']}",
        "",
        "## Validation Issues",
        "",
    ]
    if plan["validation_issues"]:
        lines.extend([f"- {issue}" for issue in plan["validation_issues"]])
    else:
        lines.append("- None")
    lines.extend(["", "## Family Plan", ""])
    for family in plan["families"]:
        lines.append(
            f"- `{family['family']}`: {family['variants_required']} variants, "
            f"`{family['generator']}`, `{family['render_class']}`, collision `{family['collision']}`"
        )
    lines.extend(["", "## First Commands To Run Later", ""])
    for queue_name in ["blender", "decal", "local_ai"]:
        queue = plan["queues"].get(queue_name, [])
        if not queue:
            continue
        lines.append(f"### {queue_name}")
        for task in queue[:8]:
            lines.append(f"- `{queue_command_hint(task)}`")
        if len(queue) > 8:
            lines.append(f"- ... {len(queue) - 8} more tasks in `{queue_name}_queue.json`")
        lines.append("")
    (out_dir / "review.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", type=Path, required=True)
    ap.add_argument("--out-id", default=None)
    ap.add_argument("--out-root", type=Path, default=OUTPUT_ROOT)
    args = ap.parse_args()

    plan = build_plan(args.kit, out_id=args.out_id)
    out_dir = args.out_root / plan["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "plan.json", plan)
    for name, queue in plan["queues"].items():
        write_json(out_dir / f"{name}_queue.json", {
            "schema": "prop_queue.v1",
            "kit": plan["kit"],
            "queue": name,
            "count": len(queue),
            "tasks": [
                {**task, "command_hint": queue_command_hint(task)}
                for task in queue
            ],
        })
    write_json(out_dir / "missing_assets.json", [
        v for v in plan["variants"] if v["status"] != "ready"
    ])
    write_review_md(out_dir, plan)

    print(f"plan: {out_dir / 'plan.json'}")
    print(f"variants: {plan['summary']['variants']}")
    print(f"missing: {plan['summary']['missing']}")
    print(f"blender tasks: {plan['summary']['blender_tasks']}")
    print(f"decal tasks: {plan['summary']['decal_tasks']}")
    print(f"validation issues: {plan['summary']['validation_issues']}")
    return 1 if plan["validation_issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

