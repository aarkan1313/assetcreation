"""Headless-render Godot scene(s) to PNG via Godot 4.5 CLI.

Strategy: temporarily attach a snap script to the scene's root Node3D, run Godot,
recover the PNG from the project root, restore the original .tscn. Non-destructive.

Usage:
  python pipelines/godot_export/screenshot_scenes.py \
      --project "C:\\Users\\josep\\test\\new-game-project" \
      --scenes biome_terrain_test/biome_terrain_yosemite_valley.tscn \
               biome_terrain_test/biome_yosemite_valley_iso.tscn \
               biome_terrain_test/biome_yosemite_valley_topdown.tscn \
      --out-dir d:/tmp/scene_shots
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

GODOT_EXE = Path(r"C:\Godot\Godot_v4.5-stable_win64.exe")

SNAP_SCRIPT_REL = Path("scripts") / "_codex_snap.gd"
SNAP_SCRIPT_RES = "res://scripts/_codex_snap.gd"
RUNNER_SCRIPT_REL = Path("scripts") / "_codex_render_runner.gd"
SNAP_RES = "res://_codex_snap.png"

SNAP_GD_BODY = '''extends Node3D

@export var out_path: String = "res://_codex_snap.png"
@export var wait_frames: int = 30

func _ready() -> void:
\tfor i in range(wait_frames):
\t\tawait get_tree().process_frame
\t\tawait RenderingServer.frame_post_draw
\tvar img := get_viewport().get_texture().get_image()
\tif img == null:
\t\tprint("[snap] image is null (likely headless without window)")
\t\tget_tree().quit()
\t\treturn
\tvar global_out := ProjectSettings.globalize_path(out_path)
\tvar rc := img.save_png(global_out)
\tprint("[snap] wrote ", global_out, " rc=", rc, " size=", img.get_size())
\tget_tree().quit()
'''

RUNNER_GD_BODY = '''extends SceneTree

func _arg_value(name: String, default_value: String) -> String:
\tvar args: PackedStringArray = OS.get_cmdline_user_args()
\tfor i in range(args.size()):
\t\tif args[i] == name and i + 1 < args.size():
\t\t\treturn args[i + 1]
\treturn default_value

func _init() -> void:
\tcall_deferred("_run")

func _run() -> void:
\tvar scene_path: String = _arg_value("--scene", "")
\tvar out_path: String = _arg_value("--out", "res://_codex_snap.png")
\tvar wait_frames: int = maxi(1, int(_arg_value("--wait-frames", "60")))
\tvar width: int = int(_arg_value("--width", "2560"))
\tvar height: int = int(_arg_value("--height", "1600"))

\tvar root_view: Window = get_root()
\troot_view.size = Vector2i(width, height)

\tvar scene_res: Resource = load(scene_path)
\tif scene_res == null:
\t\tpush_error("[snap] could not load scene: " + scene_path)
\t\tquit(2)
\t\treturn

\tvar scene: Node = scene_res.instantiate()
\troot_view.add_child(scene)

\tfor i in range(wait_frames):
\t\tawait process_frame
\t\tawait RenderingServer.frame_post_draw

\tvar img: Image = root_view.get_texture().get_image()
\tif img == null:
\t\tpush_error("[snap] image is null")
\t\tquit(3)
\t\treturn

\tvar global_out: String = ProjectSettings.globalize_path(out_path)
\tvar rc: int = img.save_png(global_out)
\tprint("[snap] wrote ", global_out, " rc=", rc, " size=", img.get_size())
\tquit(0 if rc == OK else 4)
'''


def ensure_snap_script(project_dir: Path) -> Path:
    """Ensure snap.gd exists; rewrite to known-good body (idempotent)."""
    snap_path = project_dir / SNAP_SCRIPT_REL
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(SNAP_GD_BODY, encoding="utf-8")
    return snap_path


def ensure_runner_script(project_dir: Path) -> Path:
    """Ensure the SceneTree render runner exists; rewrite idempotently."""
    runner_path = project_dir / RUNNER_SCRIPT_REL
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    runner_path.write_text(RUNNER_GD_BODY, encoding="utf-8")
    return runner_path


def attach_snap_to_scene(scene_path: Path) -> tuple[str, str]:
    """Patch the .tscn so its root Node3D loads snap.gd. Returns (orig_text, patched_text)."""
    text = scene_path.read_text(encoding="utf-8")
    orig = text

    # Append a sub_resource ext_resource for snap.gd, then attach 'script = ' to root node.
    # Simpler: inject ExtResource line in [gd_scene] header section, plus a script= line on first [node].
    # Find existing ext_resource ids to pick a free one.
    import re
    used_ids = re.findall(r'ExtResource\("([^"]+)"\)', text)
    used_ids += re.findall(r'id="([^"]+)"', text)
    snap_id = "snap_script_1"
    while snap_id in used_ids:
        snap_id += "_x"

    # Bump load_steps if present
    text = re.sub(
        r'\[gd_scene([^\]]*?)load_steps=(\d+)([^\]]*?)\]',
        lambda m: f'[gd_scene{m.group(1)}load_steps={int(m.group(2)) + 1}{m.group(3)}]',
        text,
        count=1,
    )

    # Insert ExtResource line right after the [gd_scene ...] header.
    ext_line = f'[ext_resource type="Script" path="{SNAP_SCRIPT_RES}" id="{snap_id}"]\n'
    text = re.sub(
        r'(\[gd_scene[^\]]*\]\n)',
        lambda m: m.group(1) + ext_line,
        text,
        count=1,
    )

    # Attach script to first [node ... type="Node3D" ...] (which is the root).
    def attach_script(m: re.Match) -> str:
        header = m.group(0)
        return header + f'script = ExtResource("{snap_id}")\n'

    text, n = re.subn(
        r'(\[node name="[^"]+" type="Node3D"[^\]]*\]\n)',
        attach_script,
        text,
        count=1,
    )
    if n != 1:
        raise RuntimeError(f"could not find root Node3D in {scene_path.name}")

    scene_path.write_text(text, encoding="utf-8")
    return orig, text


def render_one(scene_rel: str, out_png: Path, project_dir: Path, godot_exe: Path,
               headless: bool, rendering_method: str | None,
               timeout: int = 240) -> bool:
    project_snap = project_dir / Path(SNAP_RES.replace("res://", ""))
    if project_snap.exists():
        project_snap.unlink()
    runner = ensure_runner_script(project_dir)
    scene_res = f"res://{scene_rel.replace(chr(92), '/')}"

    # 600 frames = ~10s @ 60fps — gives heavy scenes (4096-source heightmap +
    # large scatter sets) time to load, bind shaders, and render.
    cmd = [str(godot_exe), "--path", str(project_dir), "--quiet"]
    if headless:
        cmd.append("--headless")
    if rendering_method:
        cmd.extend(["--rendering-method", rendering_method])
    cmd.extend([
        "--script", str(runner.resolve()),
        "--",
        "--scene", scene_res,
        "--out", SNAP_RES,
        "--wait-frames", "90",
    ])
    print(f"  > {' '.join(cmd[1:])}")
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout, text=True)
    except subprocess.TimeoutExpired:
        print("  godot timed out")
        return False

    if result.stdout:
        for line in result.stdout.splitlines()[-15:]:
            if "[snap]" in line or "ERROR" in line or "WARN" in line:
                print("  godot:", line)

    if project_snap.exists():
        out_png.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(project_snap), str(out_png))
        print(f"  saved {out_png}")
        return True

    print(f"  no snap.png produced (rc={result.returncode})")
    if result.stderr:
        print("  stderr:", result.stderr[:300])
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True,
                    help="Godot project directory")
    ap.add_argument("--scenes", nargs="+", required=True,
                    help="scene paths relative to project root")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--godot-exe", type=Path, default=GODOT_EXE,
                    help="Godot executable path")
    ap.add_argument("--rendering-method", default=None,
                    help="Optional Godot rendering method, e.g. gl_compatibility")
    ap.add_argument("--no-headless", action="store_true",
                    help="run with a real window (more reliable framebuffer)")
    args = ap.parse_args()

    if not args.godot_exe.exists():
        print(f"Godot not found at {args.godot_exe}", file=sys.stderr)
        return 2

    ensure_runner_script(args.project)

    successes = 0
    failures: list[str] = []
    for rel in args.scenes:
        scene_abs = args.project / rel
        if not scene_abs.exists():
            print(f"skip (missing): {rel}")
            failures.append(rel)
            continue
        print(f"\n[{rel}]")

        out_png = args.out_dir / (Path(rel).stem + ".png")
        ok = render_one(
            rel,
            out_png,
            args.project,
            args.godot_exe,
            headless=not args.no_headless,
            rendering_method=args.rendering_method,
        )

        if ok:
            successes += 1
        else:
            failures.append(rel)

    print(f"\n=== {successes}/{len(args.scenes)} rendered ===")
    if failures:
        print("failed:")
        for f in failures:
            print(f"  - {f}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
