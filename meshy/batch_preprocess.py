"""Batch-preprocess every Meshy output GLB into preprocessed/.

Usage:
    python batch_preprocess.py [options]

By default, finds all <output_dir>/*/model.glb files and runs preprocess.py on
each, with the asset name (parent folder name) used as the output stem.
Skips assets that already have a preprocessed file unless --force.

Options:
    --target-tris N        target triangle count (default 30000)
    --force                re-preprocess even if output already exists
    --dry-run              just print what would be done
    --asset NAME           process only a specific asset (parent folder name)
                           Can be repeated.
    --skip NAME            skip a specific asset. Can be repeated.
    --quad-remesh          pass through to preprocess.py
    --clean-internals      pass through to preprocess.py
    --normalize-scale      pass through to preprocess.py
    --unwrap-uvs           pass through to preprocess.py

Originals at meshy/output/<name>/model.glb are NEVER modified — preprocessed
output goes to meshy/preprocessed/<name>_p.glb.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "output"
PREPROCESS_DIR = ROOT / "preprocessed"


def discover_assets() -> list[tuple[str, Path]]:
    """Find all (asset_name, glb_path) pairs in output/."""
    assets = []
    if not OUTPUT_DIR.is_dir():
        return assets
    for sub in sorted(OUTPUT_DIR.iterdir()):
        if not sub.is_dir():
            continue
        if sub.name.startswith("_"):
            continue  # skip _archived_v1 etc.
        glb = sub / "model.glb"
        if glb.exists():
            assets.append((sub.name, glb))
    return assets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-tris", type=int, default=30000)
    ap.add_argument("--force", action="store_true",
                    help="re-preprocess even if output already exists")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--asset", action="append", default=[],
                    help="process only this asset (repeatable)")
    ap.add_argument("--skip", action="append", default=[],
                    help="skip this asset (repeatable)")
    ap.add_argument("--quad-remesh", action="store_true")
    ap.add_argument("--clean-internals", action="store_true")
    ap.add_argument("--normalize-scale", action="store_true")
    ap.add_argument("--unwrap-uvs", action="store_true")
    args = ap.parse_args()

    assets = discover_assets()
    if not assets:
        print(f"no assets found under {OUTPUT_DIR}")
        return

    if args.asset:
        wanted = set(args.asset)
        assets = [a for a in assets if a[0] in wanted]
    if args.skip:
        skip = set(args.skip)
        assets = [a for a in assets if a[0] not in skip]

    PREPROCESS_DIR.mkdir(parents=True, exist_ok=True)

    plan = []
    for name, glb in assets:
        out_path = PREPROCESS_DIR / f"{name}_p.glb"
        skip_reason = None
        if out_path.exists() and not args.force:
            skip_reason = "output exists (use --force to overwrite)"
        plan.append({"name": name, "input": glb, "output": out_path, "skip_reason": skip_reason})

    print(f"=== batch preprocess plan: {len(plan)} assets ===")
    for p in plan:
        marker = " [SKIP]" if p["skip_reason"] else ""
        print(f"  {p['name']:25s}  ->  {p['output'].name}{marker}")
    print()

    if args.dry_run:
        print("dry-run, exiting")
        return

    todo = [p for p in plan if not p["skip_reason"]]
    print(f"=== running {len(todo)} jobs ===\n")

    successes = []
    failures = []
    t0 = time.time()
    for i, job in enumerate(todo, 1):
        cmd = [sys.executable, str(ROOT / "preprocess.py"),
               str(job["input"]), str(job["output"]),
               "--target-tris", str(args.target_tris)]
        if args.quad_remesh:
            cmd.append("--quad-remesh")
        if args.clean_internals:
            cmd.append("--clean-internals")
        if args.normalize_scale:
            cmd.append("--normalize-scale")
        if args.unwrap_uvs:
            cmd.append("--unwrap-uvs")

        print(f"[{i}/{len(todo)}] {job['name']}...", end=" ", flush=True)
        t1 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        dt = time.time() - t1
        if r.returncode == 0 and job["output"].exists():
            print(f"OK ({dt:.1f}s, {job['output'].stat().st_size // 1024} KB)")
            successes.append(job["name"])
        else:
            print(f"FAILED (exit {r.returncode})")
            print(f"  last 5 stderr lines:")
            for line in r.stderr.splitlines()[-5:]:
                print(f"    {line}")
            failures.append({"name": job["name"], "exit": r.returncode, "stderr_tail": r.stderr.splitlines()[-5:]})

    total_dt = time.time() - t0
    print(f"\n=== done: {len(successes)}/{len(todo)} succeeded in {total_dt:.1f}s ===")
    if failures:
        print(f"failures:")
        for f in failures:
            print(f"  - {f['name']}: exit {f['exit']}")

    summary = {
        "total": len(todo),
        "succeeded": len(successes),
        "failed": len(failures),
        "duration_sec": round(total_dt, 1),
        "successes": successes,
        "failures": failures,
    }
    summary_path = PREPROCESS_DIR / "_batch_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"summary: {summary_path}")


if __name__ == "__main__":
    main()
