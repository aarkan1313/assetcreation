"""Render shader candidates through Godot CLI when a Godot binary is available.

CPU proxy previews are good for fast exploration, but final acceptance should
use the engine. This wrapper discovers Godot, writes a tiny render runner into
each candidate project, captures PNG frames, builds a flipbook, and stores a
Godot review block in request.json.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

LAB_ROOT = Path(r"D:\assets\art_lab")
TOOLS_DIR = LAB_ROOT / "tools"

sys.path.append(str(TOOLS_DIR))
from shader_batch_review import candidate_review, make_flipbook  # noqa: E402


RUNNER_GD = r'''
extends SceneTree

func _arg_value(name: String, default_value: String) -> String:
    var args := OS.get_cmdline_user_args()
    for i in range(args.size()):
        if args[i] == name and i + 1 < args.size():
            return args[i + 1]
    return default_value

func _init() -> void:
    call_deferred("_run")

func _run() -> void:
    var scene_path := _arg_value("--scene", "")
    var output_dir := _arg_value("--output-dir", "godot_frames")
    var width := int(_arg_value("--width", "256"))
    var height := int(_arg_value("--height", "256"))
    var frames := max(1, int(_arg_value("--frames", "1")))
    var duration := max(0.1, float(_arg_value("--duration", "1.5")))

    var root_view := get_root()
    root_view.size = Vector2i(width, height)
    root_view.transparent_bg = true

    var scene_res := load(scene_path)
    if scene_res == null:
        push_error("Could not load scene: " + scene_path)
        quit(2)
        return

    var node := scene_res.instantiate()
    root_view.add_child(node)
    DirAccess.make_dir_recursive_absolute(output_dir)

    await process_frame
    await process_frame

    for i in range(frames):
        if i > 0:
            await create_timer(duration / float(max(1, frames - 1))).timeout
        await RenderingServer.frame_post_draw
        var image := root_view.get_texture().get_image()
        var path := output_dir.path_join("frame_%03d.png" % i)
        var err := image.save_png(path)
        if err != OK:
            push_error("Could not save frame: " + path)
            quit(3)
            return

    quit(0)
'''


def discover_godot(explicit: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get("GODOT_EXE")
    if env:
        candidates.append(Path(env))
    for name in ("godot", "godot4", "Godot_v4.5-stable_win64.exe", "Godot_v4.5-stable_mono_win64.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    candidates.extend([
        Path(r"C:\Program Files\Godot\Godot_v4.5-stable_win64.exe"),
        Path(r"C:\Program Files\Godot\Godot_v4.5-stable_mono_win64.exe"),
        Path(r"D:\Program Files\Godot\Godot_v4.5-stable_win64.exe"),
        Path(r"D:\Program Files\Godot\Godot_v4.5-stable_mono_win64.exe"),
    ])
    for path in candidates:
        if path.exists():
            return path
    return None


def candidate_dirs(args: argparse.Namespace) -> list[Path]:
    dirs: list[Path] = []
    dirs.extend(args.candidate or [])
    for batch_dir in args.batch_dir or []:
        summary_path = batch_dir / "batch_summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            for row in summary.get("rows", []):
                dirs.append(batch_dir / row["id"])
        else:
            dirs.extend(p for p in batch_dir.iterdir() if (p / "request.json").exists())
    seen: set[Path] = set()
    out: list[Path] = []
    for path in dirs:
        resolved = path.resolve()
        if resolved not in seen and (resolved / "request.json").exists():
            seen.add(resolved)
            out.append(resolved)
    return out


def request_data(candidate_dir: Path) -> dict[str, Any]:
    return json.loads((candidate_dir / "request.json").read_text(encoding="utf-8"))


def write_runner(candidate_dir: Path) -> Path:
    path = candidate_dir / "render_runner.gd"
    path.write_text(RUNNER_GD.strip() + "\n", encoding="utf-8")
    return path


def build_flipbook(frame_dir: Path, out_path: Path) -> list[Path]:
    frames = sorted(frame_dir.glob("frame_*.png"))
    if not frames:
        return []
    images = [Image.open(p).convert("RGBA") for p in frames]
    images[0].save(frame_dir.parent / "preview_godot.png")
    make_flipbook(images).save(out_path)
    return frames


def render_one(godot: Path, candidate_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    data = request_data(candidate_dir)
    shader_id = data["id"]
    scene_path = f"res://{shader_id}.tscn"
    preview = data.get("preview", {})
    size = preview.get("size", [args.size, args.size])
    width = int(args.width or size[0])
    height = int(args.height or size[1])
    frames = int(args.frames or preview.get("frames", 1))
    duration = float(args.duration or preview.get("duration_s", 1.5))
    frame_dir = candidate_dir / "godot_frames"
    if frame_dir.exists():
        shutil.rmtree(frame_dir)
    frame_dir.mkdir(parents=True, exist_ok=True)
    runner = write_runner(candidate_dir)

    cmd = [str(godot), "--path", str(candidate_dir), "--quiet"]
    if args.headless:
        cmd.append("--headless")
    if args.rendering_method:
        cmd.extend(["--rendering-method", args.rendering_method])
    cmd.extend([
        "--script", str(runner),
        "--",
        "--scene", scene_path,
        "--output-dir", str(frame_dir),
        "--width", str(width),
        "--height", str(height),
        "--frames", str(frames),
        "--duration", str(duration),
    ])

    started = datetime.now(timezone.utc).isoformat()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
    frame_paths = build_flipbook(frame_dir, candidate_dir / "flipbook_godot.png")
    status = "ok" if proc.returncode == 0 and frame_paths else "failed"
    review = None
    if frame_paths:
        review = candidate_review(candidate_dir, data.get("role", "aura"), data.get("params", {}))
        review["render_source"] = "godot"
        review["godot_frames"] = len(frame_paths)

    data["godot_render"] = {
        "status": status,
        "created": started,
        "godot": str(godot),
        "headless": args.headless,
        "rendering_method": args.rendering_method,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
        "frames": [str(p.relative_to(candidate_dir)) for p in frame_paths],
        "preview": "preview_godot.png" if (candidate_dir / "preview_godot.png").exists() else None,
        "flipbook": "flipbook_godot.png" if (candidate_dir / "flipbook_godot.png").exists() else None,
        "review": review,
    }
    (candidate_dir / "request.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"candidate": str(candidate_dir), "status": status, "returncode": proc.returncode, "frames": len(frame_paths)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", action="append", type=Path)
    ap.add_argument("--batch-dir", action="append", type=Path)
    ap.add_argument("--godot-exe", type=Path)
    ap.add_argument("--frames", type=int)
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--duration", type=float)
    ap.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--rendering-method", default="gl_compatibility",
                    help="Godot rendering method. Use empty string to omit.")
    ap.add_argument("--timeout", type=int, default=90)
    args = ap.parse_args()

    godot = discover_godot(args.godot_exe)
    if not godot:
        raise SystemExit(
            "Godot executable not found. Pass --godot-exe or set GODOT_EXE. "
            "The current CPU proxy previews are still usable for exploration."
        )
    if args.rendering_method == "":
        args.rendering_method = None

    dirs = candidate_dirs(args)
    if not dirs:
        raise SystemExit("provide --candidate or --batch-dir")

    results = []
    for candidate_dir in dirs:
        print(f"rendering {candidate_dir}")
        results.append(render_one(godot, candidate_dir, args))
    print(json.dumps({"godot": str(godot), "results": results}, indent=2))


if __name__ == "__main__":
    main()
