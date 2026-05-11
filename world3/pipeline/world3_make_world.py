"""Phase F.8 — top-level world build.

One command to take a world plan from JSON to audited tile-able world:

    plan validate -> transition audit -> catalog demand -> emit bundles
                  -> in-context re-audit -> composite summary

Each step is a separate F-phase script invoked as a subprocess. F.8 is
the synthesis layer; the individual scripts remain the source of truth.

Usage:
    python world3/pipeline/world3_make_world.py world3/jobs/examples/world_plan_starter_5biome_procedural.json
    python world3/pipeline/world3_make_world.py <plan> --skip-in-context   # fast loop, no Godot
    python world3/pipeline/world3_make_world.py <plan> --from-step 4       # resume mid-flow
    python world3/pipeline/world3_make_world.py <plan> --only-step 2       # single step
    python world3/pipeline/world3_make_world.py <plan> --strict-catalog    # fail if any catalog gaps
    python world3/pipeline/world3_make_world.py <plan> --auto-requisition  # USER-GATED: run F.5b --run

Step numbering:
    1  validate_world_plan
    2  audit_transition_pairs
    3  derive_catalog_demand
    4  (optional) run_catalog_requisition --run   [--auto-requisition only]
    5  world_plan_to_bundles --run
    6  audit_materials_in_context

Exit codes: 0 all-ok / 1 any step failed / 2 internal
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD3 = Path(__file__).resolve().parents[1]
PIPELINE_DIR = WORLD3 / "pipeline"
SUMMARY_DIR = WORLD3 / "jobs" / "world_build_summaries"


STEPS = [
    (1, "validate_world_plan",       "Validate the plan schema + semantic rules"),
    (2, "audit_transition_pairs",    "F.4: catalog-time transition pair audit"),
    (3, "derive_catalog_demand",     "F.5a: derive catalog demand + work queue"),
    (4, "run_catalog_requisition",   "F.5b: dispatch catalog requisition (--auto-requisition only)"),
    (5, "world_plan_to_bundles",     "F.3: emit per-tile requests + world_map + build bundles"),
    (6, "audit_materials_in_context","F.6: in-context catalog->runtime drift audit"),
]


def step_filter(args, step_num: int) -> bool:
    """Decide whether to run this step given --from-step / --only-step / step 4 gating."""
    if args.only_step is not None:
        return step_num == args.only_step
    if args.from_step is not None and step_num < args.from_step:
        return False
    if step_num == 4 and not args.auto_requisition:
        return False
    return True


def run_step(step_num: int, name: str, cmd: list[str], dry_run: bool) -> dict:
    record = {
        "step": step_num,
        "name": name,
        "cmd": cmd,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    if dry_run:
        record["status"] = "dry_run"
        record["completed_at"] = datetime.now(timezone.utc).isoformat()
        return record
    print(f"\n--- Step {step_num}: {name} ---")
    print(f"  cmd: {' '.join(cmd)}")
    t0 = datetime.now(timezone.utc)
    result = subprocess.run(cmd, capture_output=False, text=True)
    record["exit"] = result.returncode
    record["elapsed_sec"] = (datetime.now(timezone.utc) - t0).total_seconds()
    record["completed_at"] = datetime.now(timezone.utc).isoformat()
    record["status"] = "ok" if result.returncode == 0 else "fail"
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("plan", type=Path, help="world plan JSON path")
    ap.add_argument("--dry-run", action="store_true", help="Print plan, don't execute")
    ap.add_argument("--from-step", type=int, default=None)
    ap.add_argument("--only-step", type=int, default=None)
    ap.add_argument("--skip-in-context", action="store_true",
                    help="Skip step 6 (Godot re-render loop); useful for fast iteration")
    ap.add_argument("--strict-catalog", action="store_true",
                    help="Abort after step 3 if catalog has any need/below items")
    ap.add_argument("--auto-requisition", action="store_true",
                    help="USER-GATED: execute step 4 (F.5b --run) to actually generate textures. "
                         "Otherwise step 4 is skipped (dry-run F.5b only).")
    args = ap.parse_args()

    if not args.plan.exists():
        print(f"ERROR: plan not found at {args.plan}", file=sys.stderr)
        return 2

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    plan_id = plan.get("id", "unknown")
    plan_abs = args.plan.resolve()

    print(f"=== world3_make_world ===")
    print(f"Plan:     {args.plan}  (id={plan_id})")
    print(f"Bounds:   {plan.get('bounds_m')}m  tile_size={plan.get('tile_size_m')}m")
    print(f"Biomes:   {len(plan.get('biomes', []))} ({[b['id'] for b in plan.get('biomes', [])]})")
    print(f"Tiles:    {len(plan.get('biome_layout', []))}")
    print(f"Mode:     {'DRY-RUN' if args.dry_run else 'EXECUTE'}")
    if args.only_step:
        print(f"Filter:   only step {args.only_step}")
    elif args.from_step:
        print(f"Filter:   from step {args.from_step}")
    if args.skip_in_context:
        print(f"Skip:     step 6 (in-context re-audit)")
    if args.strict_catalog:
        print(f"Gate:     --strict-catalog (abort on catalog gap)")
    if args.auto_requisition:
        print(f"Gate:     --auto-requisition (step 4 will RUN)")

    records: list[dict] = []
    overall_status = "ok"

    # Pre-resolve paths to the various JSONs the chain writes
    demand_path = WORLD3 / "jobs" / "catalog_demand" / f"{plan_id}.json"

    # Step 1 — validate plan
    if step_filter(args, 1):
        rec = run_step(1, "validate_world_plan",
                       [sys.executable, str(PIPELINE_DIR / "validate_world_plan.py"), str(plan_abs)],
                       args.dry_run)
        records.append(rec)
        if rec.get("status") == "fail":
            overall_status = "fail"
            print(f"\nFAIL at step 1: plan validation failed.", file=sys.stderr)
            return _finalize(plan_id, records, "fail")

    # Step 2 — transition audit
    if step_filter(args, 2):
        rec = run_step(2, "audit_transition_pairs",
                       [sys.executable, str(PIPELINE_DIR / "audit_transition_pairs.py"), str(plan_abs)],
                       args.dry_run)
        records.append(rec)
        # Non-fatal — audit is soft-gated by design

    # Step 3 — derive catalog demand
    if step_filter(args, 3):
        rec = run_step(3, "derive_catalog_demand",
                       [sys.executable, str(PIPELINE_DIR / "derive_catalog_demand.py"), str(plan_abs)],
                       args.dry_run)
        records.append(rec)
        if rec.get("status") == "fail":
            overall_status = "fail"
            return _finalize(plan_id, records, overall_status)

        if args.strict_catalog and demand_path.exists():
            demand = json.loads(demand_path.read_text(encoding="utf-8"))
            need = len({n["material_id"] for n in demand.get("need", [])})
            below = len({b["material_id"] for b in demand.get("below_promotion_bar", [])})
            if need or below:
                print(f"\nFAIL: --strict-catalog and demand reports need={need} below={below}", file=sys.stderr)
                print(f"      Run F.5b to remediate (--auto-requisition flag or manual `run_catalog_requisition.py --run`)", file=sys.stderr)
                return _finalize(plan_id, records, "fail")

    # Step 4 — catalog requisition (USER-GATED via --auto-requisition)
    if step_filter(args, 4):
        if not demand_path.exists():
            print(f"\nSkip step 4: no demand manifest at {demand_path}", file=sys.stderr)
        else:
            rec = run_step(4, "run_catalog_requisition (RUN MODE)",
                           [sys.executable, str(PIPELINE_DIR / "run_catalog_requisition.py"),
                            str(demand_path), "--run"],
                           args.dry_run)
            records.append(rec)
            if rec.get("status") == "fail":
                overall_status = "fail"
                return _finalize(plan_id, records, overall_status)

    # Step 5 — emit + build bundles
    if step_filter(args, 5):
        rec = run_step(5, "world_plan_to_bundles --run",
                       [sys.executable, str(PIPELINE_DIR / "world_plan_to_bundles.py"),
                        str(plan_abs), "--run"],
                       args.dry_run)
        records.append(rec)
        if rec.get("status") == "fail":
            overall_status = "fail"
            return _finalize(plan_id, records, overall_status)

    # Step 6 — in-context re-audit (skippable for fast iteration)
    if step_filter(args, 6) and not args.skip_in_context:
        rec = run_step(6, "audit_materials_in_context",
                       [sys.executable, str(PIPELINE_DIR / "audit_materials_in_context.py"),
                        str(plan_abs)],
                       args.dry_run)
        records.append(rec)
        # Non-fatal — audit findings don't gate build
    elif args.skip_in_context:
        print(f"\n--- Step 6: audit_materials_in_context (SKIPPED via --skip-in-context) ---")

    return _finalize(plan_id, records, overall_status)


def _finalize(plan_id: str, records: list[dict], overall_status: str) -> int:
    print(f"\n--- Summary ---")
    for r in records:
        sym = {"ok": "OK  ", "fail": "FAIL", "dry_run": "DRY ", "skipped": "SKIP"}.get(r.get("status", ""), "????")
        elapsed = r.get("elapsed_sec")
        et = f"  {elapsed:.1f}s" if elapsed else ""
        print(f"  [{sym}] step {r['step']}: {r['name']}{et}")
    print(f"  overall: {overall_status}")

    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary_path = SUMMARY_DIR / f"{plan_id}_{ts}.json"
    summary_path.write_text(json.dumps({
        "plan_id": plan_id,
        "generated_at": ts,
        "overall_status": overall_status,
        "step_count": len(records),
        "records": records,
    }, indent=2), encoding="utf-8")
    print(f"  written: {summary_path.relative_to(ROOT)}")
    print(f"\n=== world3_make_world DONE ===")
    return 0 if overall_status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
