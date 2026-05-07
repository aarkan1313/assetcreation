"""End-to-end: image -> Meshy 3D model -> turnaround PNG.

Usage:
    python generate.py <image_path> [--name NAME] [--skip-render]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--name")
    ap.add_argument("--skip-render", action="store_true")
    ap.add_argument("--pose", choices=["t-pose", "a-pose", "none"])
    ap.add_argument("--symmetry", choices=["off", "auto", "on"])
    ap.add_argument("--texture-prompt")
    args = ap.parse_args()

    name = args.name or args.image.stem
    out_dir = ROOT / "output" / name
    glb_path = out_dir / "model.glb"

    if not glb_path.exists():
        cmd = [sys.executable, str(ROOT / "meshy_image_to_3d.py"), str(args.image), "--name", name]
        if args.pose:
            cmd += ["--pose", args.pose]
        if args.symmetry:
            cmd += ["--symmetry", args.symmetry]
        if args.texture_prompt:
            cmd += ["--texture-prompt", args.texture_prompt]
        print(f"$ {' '.join(cmd)}")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            sys.exit(r.returncode)
    else:
        print(f"reusing existing {glb_path}")

    if args.skip_render:
        return

    preview_dir = ROOT / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_png = preview_dir / f"{name}.png"

    cmd = [
        CONFIG["blender_exe"],
        "-b",
        "-P",
        str(ROOT / "render_preview.py"),
        "--",
        str(glb_path),
        str(preview_png),
    ]
    print(f"$ {' '.join(cmd[:1])} ... {preview_png.name}")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(r.returncode)

    print(f"\npreview: {preview_png}")


if __name__ == "__main__":
    main()
