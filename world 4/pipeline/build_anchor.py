"""W4 anchor demo — top-level build orchestrator.

Runs the 3-stage build in order:
  1. pick_dem_crop.py        (system Python: uses rasterio)
  2. build_splat_and_macro.py (terrain venv: uses richdem)
  3. write_material_tres.py  (system Python: simple)

Then prints next steps for the Godot side.

Run with system Python — it dispatches to the right venv per stage:
    python "D:/assets/world 4/pipeline/build_anchor.py"
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path("D:/assets")
PIPE = ROOT / "world 4" / "pipeline"
TERRAIN_PYTHON = ROOT / "pipelines" / "terrain" / ".venv" / "Scripts" / "python.exe"
SYSTEM_PYTHON = Path("C:/Program Files/Python312/python.exe")


def run_stage(label: str, python: Path, script: Path) -> int:
    print()
    print("=" * 64)
    print(f"  Stage: {label}")
    print(f"  Python: {python}")
    print(f"  Script: {script}")
    print("=" * 64)
    result = subprocess.run([str(python), str(script)], cwd=str(ROOT))
    if result.returncode != 0:
        print(f"\n[anchor] FAIL: {label} returned {result.returncode}")
        return result.returncode
    print(f"[anchor] {label} OK")
    return 0


def main() -> int:
    # Verify pythons exist
    if not SYSTEM_PYTHON.exists():
        print(f"ERROR: system Python not found at {SYSTEM_PYTHON}")
        return 1
    if not TERRAIN_PYTHON.exists():
        print(f"ERROR: terrain venv Python not found at {TERRAIN_PYTHON}")
        return 1

    stages = [
        ("1/3 DEM crop",                SYSTEM_PYTHON,  PIPE / "pick_dem_crop.py"),
        ("2/3 Splat + macro (drainage)", TERRAIN_PYTHON, PIPE / "build_splat_and_macro.py"),
        ("3/3 Material .tres",           SYSTEM_PYTHON,  PIPE / "write_material_tres.py"),
    ]

    for label, python, script in stages:
        rc = run_stage(label, python, script)
        if rc != 0:
            return rc

    print()
    print("=" * 64)
    print("  ANCHOR BUILD COMPLETE")
    print("=" * 64)
    print()
    print("Next steps:")
    print("  1. Open Godot:  C:/Godot/Godot_v4.5-stable_win64.exe")
    print('  2. Open project: "D:/assets/world 4/the world 4/"')
    print('  3. Run scene:   "res://scenes/anchor.tscn"')
    print()
    print("Controls in-game:")
    print("  [1] Walk (3D)   WASD + mouse")
    print("  [2] Iso (2.5D)")
    print("  [3] Topdown (2D)")
    print("  [Esc] release mouse  [F] re-capture mouse in walk mode")
    return 0


if __name__ == "__main__":
    sys.exit(main())
