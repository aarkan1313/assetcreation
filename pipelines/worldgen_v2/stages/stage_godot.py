"""Stage 6: orchestrate the Godot writers to land everything in the project."""
from __future__ import annotations
from pathlib import Path
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job
from pipelines.worldgen_v2.godot_writers import (
    shader_files,
    heightmap_image,
    material_tres,
    collision_tres,
    player_controller,
    iso_cam_script,
    scene_tscn,
)


def run(job: Job, godot_project: Path | None = None) -> None:
    target = godot_project or paths.DEFAULT_GODOT_PROJECT
    target = Path(target)
    if not target.exists():
        raise FileNotFoundError(
            f"stage_godot: Godot project dir not found: {target}\n"
            "Create the project (or pass --godot-project)."
        )
    shader_files.write(job, target)
    heightmap_image.write(job, target)
    material_tres.write(job, target)
    collision_tres.write(job, target)
    player_controller.write(job, target)
    iso_cam_script.write(target)
    scene_tscn.write(job, target)
    print(f"[stage_godot] complete -> {target}")
