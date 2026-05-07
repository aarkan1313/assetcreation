"""Batch-run AnimateAnyMesh on multiple (mesh, prompt) pairs.

Usage:
    python batch_animate.py <jobs.json>

jobs.json format:
[
  {"mesh": "D:\\\\assets\\\\meshy\\\\preprocessed\\\\goblin_p.glb", "prompt": "the creature walks forward", "name": "goblin_walk", "seed": 42},
  {"mesh": "D:\\\\assets\\\\meshy\\\\preprocessed\\\\goblin_p.glb", "prompt": "the creature attacks with claws", "name": "goblin_attack", "seed": 99},
  {"mesh": "D:\\\\assets\\\\meshy\\\\preprocessed\\\\dragon_p.glb", "prompt": "the object is flying", "name": "dragon_fly"}
]

Each entry runs AnimateAnyMesh inside WSL. Output FBX lands in:
    D:\\assets\\animators\\AnimateAnyMesh\\output_videos\\rf_model\\<name>.fbx

Optional fields per job:
    seed         (default 42)
    duration     (mapped to AAM's max_length, default 16 frames)
    export_format ("fbx" default, or "abc" or "none")

Logs land in D:\\assets\\meshy\\batch_logs\\<name>.log.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
LOG_DIR = ROOT / "batch_logs"


WSL_TEMPLATE = """\
set -e
source /opt/miniconda3/bin/activate animateanymesh
cd /mnt/d/assets/animators/AnimateAnyMesh
INPUT_DIR=/tmp/aam_batch_{name}
rm -rf "$INPUT_DIR"
mkdir -p "$INPUT_DIR"
cp "{mesh_wsl}" "$INPUT_DIR/{name}.glb"
python test_drive.py \\
  --data_dir "$INPUT_DIR" \\
  --vae_dir ./checkpoints \\
  --rf_model_dir ./checkpoints \\
  --json_dir ./checkpoints/dvae_factors \\
  --rf_exp rf_model \\
  --rf_epoch f \\
  --seed {seed} \\
  --test_name {name} \\
  --prompt "{prompt}" \\
  --export_format {export_format}
"""


def to_wsl_path(p: Path | str) -> str:
    s = str(p).replace("\\", "/")
    if len(s) > 1 and s[1] == ":":
        drive = s[0].lower()
        s = f"/mnt/{drive}{s[2:]}"
    return s


def run_one(job: dict, log_dir: Path) -> tuple[bool, float]:
    name = job["name"]
    mesh = Path(job["mesh"])
    if not mesh.exists():
        print(f"[{name}] SKIP — mesh not found: {mesh}")
        return False, 0.0

    log_path = log_dir / f"{name}.log"
    err_path = log_dir / f"{name}.err.log"

    script = WSL_TEMPLATE.format(
        name=name,
        mesh_wsl=to_wsl_path(mesh),
        seed=job.get("seed", 42),
        prompt=job["prompt"].replace('"', '\\"'),
        export_format=job.get("export_format", "fbx"),
    )
    script_path = log_dir / f"{name}.sh"
    # Write with LF line endings — bash chokes on CRLF (set -\r\ne -> "set -" + literal CR)
    with open(script_path, "w", encoding="ascii", newline="\n") as f:
        f.write(script)

    print(f"[{name}] running (prompt: '{job['prompt']}')...")
    t0 = time.time()
    with open(log_path, "w", encoding="utf-8") as out, open(err_path, "w", encoding="utf-8") as err:
        r = subprocess.run(
            ["wsl", "-d", "Ubuntu-24.04", "--", "bash", to_wsl_path(script_path)],
            stdout=out, stderr=err
        )
    dt = time.time() - t0
    if r.returncode == 0:
        print(f"[{name}] OK in {dt:.1f}s")
        return True, dt
    else:
        print(f"[{name}] FAILED (exit {r.returncode}) — see {log_path}")
        return False, dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", type=Path, help="path to jobs JSON")
    ap.add_argument("--dry-run", action="store_true", help="print plan, don't run")
    args = ap.parse_args()

    if not args.jobs.exists():
        raise SystemExit(f"jobs file not found: {args.jobs}")
    jobs = json.loads(args.jobs.read_text())
    if not isinstance(jobs, list):
        raise SystemExit("jobs file must be a JSON array")

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        for j in jobs:
            print(f"PLAN: {j.get('name')}: '{j.get('prompt')}' on {j.get('mesh')}")
        return

    results = []
    total_time = 0.0
    for job in jobs:
        ok, dt = run_one(job, LOG_DIR)
        total_time += dt
        results.append({"name": job.get("name"), "ok": ok, "duration_sec": dt})

    summary_path = LOG_DIR / "batch_summary.json"
    summary_path.write_text(json.dumps({"jobs": results, "total_sec": total_time}, indent=2))
    ok_count = sum(1 for r in results if r["ok"])
    print(f"\n{ok_count}/{len(results)} succeeded in {total_time:.1f}s total. Summary: {summary_path}")


if __name__ == "__main__":
    main()
