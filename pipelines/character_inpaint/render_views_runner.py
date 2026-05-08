"""Thin wrapper that invokes Blender headless to render N orbit views of a GLB.

No bpy dependency — this runs in the pipeline venv (plain Python 3.11 stdlib only).

Usage example:
    from pipelines.character_inpaint.render_views_runner import render_views

    pngs = render_views(
        glb_path="d:/assets/meshy/preprocessed/goblin_p.glb",
        out_dir="d:/tmp/render_test",
        n_views=6,
        resolution=512,
    )
    # pngs -> [Path("d:/tmp/render_test/view_00.png"), ...]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_RENDER_SCRIPT = _THIS_DIR / "blender_scripts" / "render_views.py"

_DEFAULT_BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"


def render_views(
    glb_path: str | Path,
    out_dir: str | Path,
    n_views: int = 6,
    resolution: int = 512,
    camera_distance: float = 2.5,
    elevation_deg: float = 15.0,
    front_azimuth_deg: float = 270.0,
    blender_exe: str = _DEFAULT_BLENDER_EXE,
) -> list[Path]:
    """Render N orbit views of the GLB via Blender headless.

    Parameters
    ----------
    glb_path:
        Path to the source GLB file.
    out_dir:
        Directory where view_00.png … view_NN.png will be written (created if absent).
    n_views:
        Number of evenly-spaced azimuth views around the mesh.
    resolution:
        Square render resolution in pixels.
    camera_distance:
        Distance from origin to the camera (world units, post-normalization).
    elevation_deg:
        Camera elevation above the equatorial plane in degrees.
    front_azimuth_deg:
        Azimuth (deg) that faces the character's front. Default 270 = camera along -Y.
        Meshy/Trellis2 GLBs typically face +Y so front is at az=270.
    blender_exe:
        Absolute path to the Blender executable.

    Returns
    -------
    list[Path]
        Sorted list of output PNG paths (view_00.png, view_01.png, ...).

    Raises
    ------
    FileNotFoundError
        If the GLB or the Blender executable does not exist.
    RuntimeError
        If Blender exits with a non-zero return code.
    """
    glb_path = Path(glb_path).resolve()
    out_dir = Path(out_dir).resolve()

    if not Path(blender_exe).exists():
        raise FileNotFoundError(f"Blender executable not found: {blender_exe}")
    if not glb_path.exists():
        raise FileNotFoundError(f"GLB not found: {glb_path}")
    if not _RENDER_SCRIPT.exists():
        raise FileNotFoundError(f"render_views.py script not found: {_RENDER_SCRIPT}")

    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        blender_exe,
        "--background",
        "--factory-startup",
        "--python", str(_RENDER_SCRIPT),
        "--",
        "--glb", str(glb_path),
        "--out-dir", str(out_dir),
        "--n-views", str(n_views),
        "--resolution", str(resolution),
        "--camera-distance", str(camera_distance),
        "--elevation-deg", str(elevation_deg),
        "--front-azimuth-deg", str(front_azimuth_deg),
    ]

    print(f"[render_views_runner] Launching Blender headless for {n_views} views @ {resolution}px")
    print(f"[render_views_runner] cmd: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # Always echo Blender output so callers can see progress / errors
    if result.stdout:
        for line in result.stdout.splitlines():
            print(f"  [blender] {line}")

    if result.returncode != 0:
        raise RuntimeError(
            f"Blender exited with code {result.returncode}. "
            f"See above output for details."
        )

    # Collect output files
    pngs = sorted(out_dir.glob("view_*.png"))
    if len(pngs) != n_views:
        raise RuntimeError(
            f"Expected {n_views} PNG files in {out_dir}, found {len(pngs)}. "
            f"Check Blender output above."
        )
    return pngs


if __name__ == "__main__":
    # Quick CLI smoke test:
    #   python render_views_runner.py <glb> <out_dir> [n_views] [resolution]
    import argparse

    ap = argparse.ArgumentParser(description="Render GLB orbit views via Blender headless")
    ap.add_argument("glb", help="Input GLB path")
    ap.add_argument("out_dir", help="Output directory")
    ap.add_argument("--n-views", type=int, default=6)
    ap.add_argument("--resolution", type=int, default=512)
    ap.add_argument("--camera-distance", type=float, default=2.5)
    ap.add_argument("--elevation-deg", type=float, default=15.0)
    ap.add_argument("--blender-exe", default=_DEFAULT_BLENDER_EXE)
    args = ap.parse_args()

    pngs = render_views(
        glb_path=args.glb,
        out_dir=args.out_dir,
        n_views=args.n_views,
        resolution=args.resolution,
        camera_distance=args.camera_distance,
        elevation_deg=args.elevation_deg,
        blender_exe=args.blender_exe,
    )
    print(f"Done. {len(pngs)} views:")
    for p in pngs:
        print(f"  {p}")
