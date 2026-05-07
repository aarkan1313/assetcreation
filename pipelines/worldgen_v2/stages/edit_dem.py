"""Stage 2: optional fantasy/style pass on the heightmap.
Milestone 1: realistic = passthrough. Other styles raise NotImplementedError."""
from __future__ import annotations
import shutil
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job


def run(job: Job) -> None:
    out = paths.job_output_dir(job.id)
    src = out / "height_16.png"
    dst = out / "height_16_edited.png"
    if not src.exists():
        raise FileNotFoundError(f"edit_dem: missing upstream artifact {src}")

    if job.edit.style == "realistic":
        shutil.copyfile(src, dst)
        print(f"[edit_dem] realistic passthrough -> {dst.name}")
        return

    raise NotImplementedError(
        f"edit_dem style {job.edit.style!r} is not implemented in milestone 1; "
        "use 'realistic' or extend this stage."
    )
