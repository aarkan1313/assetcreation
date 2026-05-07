"""Writer: FlyCam.gd — Source/Quake-style noclip free camera for v2 scenes.
No physics, no collision, no gravity. WASD horizontal, Q/E down/up, mouse look,
Shift = sprint (10x), Ctrl = slow (0.2x), Esc to release mouse, click to capture."""
from __future__ import annotations
from pathlib import Path
from pipelines.worldgen_v2.job_schema import Job

SCRIPT_NAME = "FlyCam.gd"
SCRIPT_BODY = '''extends Node3D

@export var base_speed_m_s: float = 12.0
@export var sprint_multiplier: float = 5.0
@export var slow_multiplier: float = 0.2
@export var mouse_sensitivity: float = 0.0025

var _yaw := 0.0
var _pitch := 0.0
var _cam: Camera3D


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	_cam = get_node_or_null("Camera3D")
	# Initialize yaw/pitch from current transform so we don't snap on start
	_yaw = rotation.y
	if _cam:
		_pitch = _cam.rotation.x


func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_yaw -= event.relative.x * mouse_sensitivity
		_pitch = clamp(_pitch - event.relative.y * mouse_sensitivity, -1.4, 1.4)
		rotation.y = _yaw
		if _cam:
			_cam.rotation.x = _pitch
	if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if event is InputEventMouseButton and event.pressed:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _process(delta: float) -> void:
	# Build movement vector in camera-local space, then transform to world.
	var input_v := Vector3.ZERO
	if Input.is_key_pressed(KEY_W): input_v.z -= 1.0
	if Input.is_key_pressed(KEY_S): input_v.z += 1.0
	if Input.is_key_pressed(KEY_A): input_v.x -= 1.0
	if Input.is_key_pressed(KEY_D): input_v.x += 1.0
	if Input.is_key_pressed(KEY_E): input_v.y += 1.0
	if Input.is_key_pressed(KEY_Q): input_v.y -= 1.0
	if input_v == Vector3.ZERO:
		return
	input_v = input_v.normalized()

	var speed := base_speed_m_s
	if Input.is_key_pressed(KEY_SHIFT):
		speed *= sprint_multiplier
	if Input.is_key_pressed(KEY_CTRL):
		speed *= slow_multiplier

	# Use the camera's basis so movement aligns with where you are looking.
	# Q/E (vertical) uses world up so it always goes straight up/down.
	if _cam:
		var cam_basis := _cam.global_transform.basis
		var horiz := cam_basis * Vector3(input_v.x, 0.0, input_v.z)
		global_position += (horiz + Vector3.UP * input_v.y) * speed * delta
	else:
		global_position += input_v * speed * delta
'''


def write(job: Job, godot_project) -> Path:
    dst_dir = godot_project / "scripts"
    dst_dir.mkdir(parents=True, exist_ok=True)
    target = dst_dir / SCRIPT_NAME
    target.write_text(SCRIPT_BODY, encoding="utf-8")
    print(f"[player_controller] wrote {target}")
    return target
