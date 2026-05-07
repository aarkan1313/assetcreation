"""Path helpers for worldgen_v2. Single source of truth for filesystem layout."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
JOBS_DIR = ROOT / "jobs"
SHADERS_DIR = ROOT / "shaders"
PRESETS_DIR = ROOT / "presets"
TEXTURES_DIR = ROOT / "textures"

DEFAULT_GODOT_PROJECT = Path("D:/assets/worldgen2")


def job_output_dir(job_id: str) -> Path:
    """Return (and create) the output dir for a given job id."""
    d = OUTPUT_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d
