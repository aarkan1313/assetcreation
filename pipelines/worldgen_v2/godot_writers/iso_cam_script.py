"""Writer: IsoCam.gd — tiny script that runs `look_at` at scene-load.

Pre-computing the look-at basis in Python and writing it as a literal
Transform3D worked mathematically but produced no rendering (terrain mesh was
visible: true, current camera was set, AABB was inside the cull volume — yet
nothing drew). Using Godot's `look_at` API at runtime fixed it instantly.
This script is the proven path."""
from __future__ import annotations
from pathlib import Path

SCRIPT_NAME = "IsoCam.gd"
SCRIPT_BODY = '''extends Camera3D

# Look-at target in world coordinates. Set in the scene file (or via inspector).
@export var target: Vector3 = Vector3.ZERO


func _ready() -> void:
	# Defer one frame so the global_position is finalised before look_at.
	await get_tree().process_frame
	look_at(target, Vector3.UP)
'''


def write(godot_project: Path) -> Path:
    dst_dir = godot_project / "scripts"
    dst_dir.mkdir(parents=True, exist_ok=True)
    target = dst_dir / SCRIPT_NAME
    target.write_text(SCRIPT_BODY, encoding="utf-8")
    print(f"[iso_cam_script] wrote {target}")
    return target
