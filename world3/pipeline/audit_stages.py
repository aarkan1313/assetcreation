"""Audit world3/jobs/stages.json against actual scripts on disk.

For each stage declared in stages.json:
  - Verify the script path resolves to a real file
  - For Python stages, verify the script runs `--help` cleanly
  - Surface broken declarations (typo in path, deleted script, etc.)

Used by:
  - Phase E.2 to verify the initial stages.json is correct
  - CI/sanity check before world3_make.py runs (catches stale manifest entries)

Usage:
  python world3/pipeline/audit_stages.py
  python world3/pipeline/audit_stages.py --json

Exit codes:
  0  all stages resolve cleanly
  1  one or more stages broken
  2  internal error (manifest malformed)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # D:/assets
WORLD3_ROOT = Path(__file__).resolve().parents[1]  # D:/assets/world3
STAGES_PATH = WORLD3_ROOT / "jobs" / "stages.json"


def load_stages() -> dict:
    if not STAGES_PATH.exists():
        print(f"ERROR: stages manifest not found at {STAGES_PATH}", file=sys.stderr)
        sys.exit(2)
    return json.loads(STAGES_PATH.read_text(encoding="utf-8"))


def check_stage(stage: dict) -> tuple[bool, str]:
    """Verify a single stage's script exists and can run --help. Some
    stages are non-Python (e.g. Godot scene captures) and only check
    the path exists."""
    stage_id = stage.get("id", "<no id>")
    script = stage.get("script", "")

    # Skip pseudo-stages that don't have a real script (e.g. Phase E.4
    # render driver work that hasn't shipped yet).
    if not script or " " in script.split("/")[-1]:  # "<X> (something)" placeholder
        return (True, "placeholder (no script path)")

    script_path = ROOT / script
    if not script_path.exists():
        return (False, f"script not found at {script_path}")

    if not script.endswith(".py"):
        return (True, f"non-Python; existence verified")

    # Try `python <script> --help` to verify argparse + imports work.
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode == 0:
            return (True, f"--help OK ({len(result.stdout.splitlines())} lines)")
        # Some scripts (positional-args, no --help) may exit non-zero;
        # surface the stderr summary.
        err_summary = result.stderr.strip().split("\n")[-1][:120] if result.stderr else ""
        return (False, f"--help exit={result.returncode}: {err_summary}")
    except subprocess.TimeoutExpired:
        return (False, "--help timed out (>20s)")
    except Exception as e:
        return (False, f"{type(e).__name__}: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON result")
    args = ap.parse_args()

    manifest = load_stages()
    stages = manifest.get("stages", [])
    if not stages:
        print("ERROR: stages.json has no 'stages' array", file=sys.stderr)
        return 2

    results = []
    all_ok = True
    for stage in stages:
        ok, detail = check_stage(stage)
        results.append({
            "id": stage.get("id", "?"),
            "script": stage.get("script", ""),
            "ok": ok,
            "detail": detail,
        })
        if not ok:
            all_ok = False

    if args.json:
        print(json.dumps({"ok": all_ok, "stages": results}, indent=2))
        return 0 if all_ok else 1

    print(f"=== Stages audit ({len(results)} declared) ===\n")
    for r in results:
        sym = "OK  " if r["ok"] else "FAIL"
        print(f"  [{sym}] {r['id']}")
        print(f"         script: {r['script'] or '<placeholder>'}")
        print(f"         {r['detail']}")
    print()

    # Also audit stage_dependencies — every "after"/"before" must reference
    # a known stage id.
    declared_ids = {s.get("id") for s in stages}
    bad_deps = []
    for dep in manifest.get("stage_dependencies", []):
        for key in ("after", "before"):
            if dep.get(key) not in declared_ids:
                bad_deps.append(f"  dependency '{dep.get(key)}' not in stages list ({dep})")
    if bad_deps:
        print("=== Stage dependency errors ===")
        for msg in bad_deps:
            print(msg)
        all_ok = False

    if all_ok:
        print("=== All stages and dependencies resolve cleanly. ===")
        return 0
    print("=== One or more stages broken or dependency errors. ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())
