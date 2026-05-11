"""Phase F.5b — catalog requisition runner.

Reads a demand manifest (from derive_catalog_demand.py) and dispatches
the per-material work queue to the texture pipeline:

  - action=regenerate    -> pipelines/textures/aaa_texture.py
  - action=palette_lock  -> pipelines/textures/palette_lock.py
  - action=fix_catalog   -> pipelines/textures/aaa_texture.py (new material)
  - action=shader_blend_band -> NO-OP (runtime work, not catalog)

By default the runner is DRY-RUN: it prints the commands it would run
plus a per-material rationale + driver path, but does NOT execute. Pass
--run to actually execute the dispatched subprocesses.

This is intentional. F.5b's job is to make the requisition machinery
auditable + scriptable before letting an LLM loose on potentially
expensive ComfyUI runs. Real catalog requisition is a user-gated
operation; the LLM can drive it once confirmed.

Usage:
    # Always show what would run first
    python world3/pipeline/run_catalog_requisition.py world3/jobs/catalog_demand/<plan_id>.json

    # Actually run (user-gated)
    python world3/pipeline/run_catalog_requisition.py <demand> --run

    # Filter to one action class
    python world3/pipeline/run_catalog_requisition.py <demand> --only-action palette_lock --run

    # Limit to first N items (smoke check)
    python world3/pipeline/run_catalog_requisition.py <demand> --max-items 2 --run

Exit codes:
    0  dispatch completed (dry-run or all real runs OK)
    1  one or more real runs failed
    2  demand manifest unreadable
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD3 = Path(__file__).resolve().parents[1]
PIPELINES_TEXTURES = ROOT / "pipelines" / "textures"
RECORDS_DIR = WORLD3 / "jobs" / "catalog_requisition_records"


def build_command(work_item: dict, catalog: dict[str, dict]) -> list[str] | None:
    """Build the subprocess command for a work_queue item.
    Returns None if the action is a no-op (runtime work)."""
    action = work_item["action"]
    mid = work_item["material_id"]

    if action == "shader_blend_band":
        return None  # runtime mitigation, not catalog work

    mat = catalog.get(mid, {})
    prov = mat.get("provenance", {})
    prompt = prov.get("prompt") or f"{mid.replace('_', ' ')}, photoreal, top-down"
    seed = prov.get("seed_base", 500)
    category = mat.get("category", "Ground")

    if action in ("regenerate", "fix_catalog"):
        cmd = [
            sys.executable, str(PIPELINES_TEXTURES / "aaa_texture.py"),
            "--prompt", prompt,
            "--id", mid,
            "--category", category,
            "--quality", "default",
            "--seed", str(seed),
        ]
        return cmd

    if action == "palette_lock":
        # palette_lock.py operates on a kit (multiple materials). We can't
        # know the full kit composition from a single work item; emit a
        # command that takes the work item's transition_pair as the kit
        # seed. Real palette_lock will need a separate kit-authoring step.
        pair = work_item.get("transition_pair", [])
        kit_name = "_".join(sorted(pair)) if pair else f"{mid}_kit"
        cmd = [
            sys.executable, str(PIPELINES_TEXTURES / "palette_lock.py"),
            "--kit", kit_name,
            "--anchor", mid,
        ]
        return cmd

    # Unknown action — surface but skip
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("demand", type=Path)
    ap.add_argument("--run", action="store_true",
                    help="Execute dispatched commands. Without this, runner is dry-run.")
    ap.add_argument("--only-action", default=None,
                    choices=["regenerate", "palette_lock", "fix_catalog"],
                    help="Filter work queue to only this action class.")
    ap.add_argument("--max-items", type=int, default=None,
                    help="Stop after this many dispatched items (useful for smoke).")
    args = ap.parse_args()

    if not args.demand.exists():
        print(f"ERROR: demand manifest not found at {args.demand}", file=sys.stderr)
        return 2

    demand = json.loads(args.demand.read_text(encoding="utf-8"))
    plan_id = demand.get("plan_id", "unknown")
    work_queue = demand.get("work_queue", [])

    # Need catalog to fill out prompts/categories
    catalog_path = WORLD3 / "materials" / "catalog.json"
    catalog_data = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog = {m["id"]: m for m in catalog_data.get("materials", [])}

    print(f"=== run_catalog_requisition ===")
    print(f"Demand:  {args.demand}")
    print(f"Plan:    {plan_id}")
    print(f"Queue:   {len(work_queue)} items")
    print(f"Mode:    {'RUN (executing)' if args.run else 'DRY-RUN (not executing)'}")
    if args.only_action:
        print(f"Filter:  --only-action {args.only_action}")
    if args.max_items:
        print(f"Limit:   --max-items {args.max_items}")
    print()

    dispatch_records = []
    dispatched = 0
    for item in work_queue:
        if args.only_action and item["action"] != args.only_action:
            continue
        if args.max_items is not None and dispatched >= args.max_items:
            break
        cmd = build_command(item, catalog)
        if cmd is None:
            print(f"  [skip ] {item['action']:<18} {item['material_id']}  (runtime work, no catalog action)")
            continue
        dispatched += 1
        print(f"  [{'run  ' if args.run else 'plan '}] {item['action']:<18} {item['material_id']}")
        print(f"           cmd: {' '.join(shlex.quote(c) for c in cmd)}")
        rec = {
            "material_id": item["material_id"],
            "action": item["action"],
            "cmd": cmd,
            "reason": item.get("reason", ""),
        }
        if args.run:
            t0 = datetime.now(timezone.utc)
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
                rec["exit"] = result.returncode
                rec["elapsed_sec"] = (datetime.now(timezone.utc) - t0).total_seconds()
                rec["stdout_tail"] = result.stdout[-500:] if result.stdout else ""
                rec["stderr_tail"] = result.stderr[-500:] if result.stderr else ""
                status = "OK" if result.returncode == 0 else f"FAIL exit={result.returncode}"
                print(f"           {status} ({rec['elapsed_sec']:.1f}s)")
            except subprocess.TimeoutExpired:
                rec["exit"] = -1
                rec["error"] = "timeout (1800s)"
                print(f"           TIMEOUT")
            except FileNotFoundError as e:
                rec["exit"] = -2
                rec["error"] = f"command not found: {e}"
                print(f"           ERROR: command not found")
        dispatch_records.append(rec)

    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record_path = RECORDS_DIR / f"{plan_id}_{ts}.json"
    record_doc = {
        "schema_version": 1,
        "plan_id": plan_id,
        "started_at": ts,
        "mode": "run" if args.run else "dry_run",
        "filter_action": args.only_action,
        "max_items": args.max_items,
        "dispatched": len(dispatch_records),
        "items": dispatch_records,
    }
    record_path.write_text(json.dumps(record_doc, indent=2), encoding="utf-8")

    print()
    print(f"--- Summary ---")
    print(f"  dispatched: {len(dispatch_records)}")
    if args.run:
        ok = sum(1 for r in dispatch_records if r.get("exit") == 0)
        fail = sum(1 for r in dispatch_records if r.get("exit", 0) != 0)
        print(f"  ok={ok}  fail={fail}")
    print(f"  record:     {record_path.relative_to(ROOT)}")
    print()
    print(f"=== run_catalog_requisition DONE ===")

    if args.run:
        any_fail = any(r.get("exit", 0) != 0 for r in dispatch_records)
        return 1 if any_fail else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
