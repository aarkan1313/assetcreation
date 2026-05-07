"""worldgen_v2 entry point.

Usage:
    python -m pipelines.worldgen_v2.batch_pipeline <job.json> [--godot-project PATH]
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from pipelines.worldgen_v2 import paths, job_schema
from pipelines.worldgen_v2.job_schema import Job
from pipelines.worldgen_v2.stages import (
    fetch_dem, edit_dem, paint_biomes, compile_splat, bind_textures, stage_godot
)


def load_job(path: Path) -> Job:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return job_schema.load_dict(data)


def run_one(job_path: Path, godot_project: Path | None = None) -> None:
    job = load_job(job_path)
    print(f"[batch_pipeline] running job {job.id} (quality={job.quality})")
    fetch_dem.run(job)
    edit_dem.run(job)
    paint_biomes.run(job)
    compile_splat.run(job)
    bind_textures.run(job)
    stage_godot.run(job, godot_project=godot_project)
    print(f"[batch_pipeline] DONE {job.id}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("job", type=Path, help="path to job.json")
    p.add_argument("--godot-project", type=Path, default=None,
                   help=f"Godot project dir (default: {paths.DEFAULT_GODOT_PROJECT})")
    args = p.parse_args(argv)
    run_one(args.job, godot_project=args.godot_project)
    return 0


if __name__ == "__main__":
    sys.exit(main())
