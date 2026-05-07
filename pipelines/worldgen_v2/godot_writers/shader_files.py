"""Writer: copy the v2 shaders into the Godot project's res://shaders/ dir.
This is the file that closes the 'shader not found' regression seen on first launch."""
from __future__ import annotations
import shutil
from pathlib import Path
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job


def write(job: Job, godot_project: Path) -> Path:
    src_dir = paths.SHADERS_DIR
    dst_dir = godot_project / "shaders"
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in src_dir.glob("*.gdshader"):
        dst = dst_dir / src.name
        shutil.copyfile(src, dst)
        copied.append(dst.name)
    print(f"[shader_files] copied {len(copied)} shader(s) to {dst_dir}: {copied}")
    return dst_dir
