"""End-to-end batch: for each job, animate -> bake -> pack -> (optional) pixel-art.

Usage:
    python batch_pipeline.py <jobs.json> [options]

jobs.json format (same as batch_animate.py, plus optional bake settings):
[
  {
    "name": "goblin_walk",
    "mesh": "D:\\\\assets\\\\meshy\\\\preprocessed\\\\goblin_p.glb",
    "prompt": "the creature walks forward",
    "seed": 42,
    "bake": {"angles": 8, "frames": 16, "res": 512, "ortho": true, "elevation": 15},
    "pack": {"crop": true},
    "pixel_art": {"pixel_size": 64, "palette": 16, "outline": true}
  }
]

`bake`, `pack`, `pixel_art` are all optional. If omitted, defaults are used.
Set `pixel_art` to null/missing to skip the pixel-art stage.

Options:
    --skip-animate     reuse existing FBX from previous run (don't re-animate)
    --dry-run          print plan only
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PY = sys.executable

DEFAULT_BAKE = {"angles": 8, "frames": 16, "res": 512, "ortho": True, "elevation": 15}
DEFAULT_PACK = {"crop": True}


def run(cmd: list[str], desc: str) -> int:
    print(f"$ [{desc}] {' '.join(str(c) for c in cmd)}")
    r = subprocess.run([str(c) for c in cmd])
    return r.returncode


def step_animate(job: dict) -> int:
    # delegate to batch_animate by writing single-entry jobs file
    tmp = ROOT / "batch_logs" / f"_single_{job['name']}.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps([job]))
    return run([PY, str(ROOT / "batch_animate.py"), str(tmp)], f"animate {job['name']}")


def step_bake(job: dict, fbx_path: Path) -> int:
    cfg = {**DEFAULT_BAKE, **(job.get("bake") or {})}
    out_dir = ROOT / "sprites" / job["name"]
    cmd = [PY, str(ROOT / "bake.py"), str(fbx_path), str(out_dir),
           "--angles", cfg["angles"],
           "--frames", cfg["frames"],
           "--res", cfg["res"],
           "--padding", cfg.get("padding", 1.15),
           "--elevation", cfg["elevation"]]
    if cfg.get("ortho", True):
        cmd.append("--ortho")
    if cfg.get("no_alpha"):
        cmd.append("--no-alpha")
    return run(cmd, f"bake {job['name']}")


def step_pack(job: dict) -> int:
    cfg = {**DEFAULT_PACK, **(job.get("pack") or {})}
    sprite_dir = ROOT / "sprites" / job["name"]
    cmd = [PY, str(ROOT / "pack_sheet.py"), str(sprite_dir)]
    if cfg.get("crop", True):
        cmd.append("--crop")
    if "tile_size" in cfg:
        cmd += ["--tile-size", cfg["tile_size"]]
    return run(cmd, f"pack {job['name']}")


def step_pixel_art(job: dict) -> int:
    cfg = job.get("pixel_art")
    if not cfg:
        return 0
    sprite_dir = ROOT / "sprites" / job["name"]
    pix_dir = ROOT / "sprites" / f"{job['name']}_pix"
    cmd = [PY, str(ROOT / "pixel_art.py"), str(sprite_dir), str(pix_dir)]
    if "pixel_size" in cfg:
        cmd += ["--pixel-size", cfg["pixel_size"]]
    if "palette" in cfg:
        cmd += ["--palette", cfg["palette"]]
    if cfg.get("outline"):
        cmd.append("--outline")
    if cfg.get("no_dither"):
        cmd.append("--no-dither")
    if "upscale" in cfg:
        cmd += ["--upscale", cfg["upscale"]]
    rc = run(cmd, f"pixel-art {job['name']}")
    if rc != 0:
        return rc
    # Pack the pixel-art tree
    return run([PY, str(ROOT / "pack_sheet.py"), str(pix_dir), "--crop"],
               f"pack pixel-art {job['name']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", type=Path)
    ap.add_argument("--skip-animate", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.jobs.exists():
        raise SystemExit(f"jobs file not found: {args.jobs}")
    jobs = json.loads(args.jobs.read_text())

    if args.dry_run:
        for j in jobs:
            print(f"PLAN: {j['name']}")
            print(f"  animate: '{j['prompt']}' on {j['mesh']}")
            print(f"  bake: {DEFAULT_BAKE | (j.get('bake') or {})}")
            print(f"  pack: {DEFAULT_PACK | (j.get('pack') or {})}")
            if j.get("pixel_art"):
                print(f"  pixel-art: {j['pixel_art']}")
        return

    aam_out = Path("D:/assets/animators/AnimateAnyMesh/output_videos/rf_model")
    summary = []
    for job in jobs:
        name = job["name"]
        fbx_path = aam_out / f"{name}.fbx"
        ok = True

        if not args.skip_animate or not fbx_path.exists():
            if step_animate(job) != 0:
                summary.append({"name": name, "step": "animate", "ok": False})
                continue

        if not fbx_path.exists():
            print(f"[{name}] expected {fbx_path} but it doesn't exist after animate step — skipping bake")
            summary.append({"name": name, "step": "animate", "ok": False})
            continue

        if step_bake(job, fbx_path) != 0:
            summary.append({"name": name, "step": "bake", "ok": False})
            continue

        if step_pack(job) != 0:
            summary.append({"name": name, "step": "pack", "ok": False})
            continue

        if step_pixel_art(job) != 0:
            summary.append({"name": name, "step": "pixel_art", "ok": False})
            continue

        summary.append({"name": name, "ok": True})

    summary_path = ROOT / "batch_logs" / "pipeline_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2))
    ok_count = sum(1 for s in summary if s.get("ok"))
    print(f"\n{ok_count}/{len(summary)} succeeded. Summary: {summary_path}")


if __name__ == "__main__":
    main()
