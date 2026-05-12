extends Node

# Quick capture helper for the W4 anchor demo. Waits N frames for the
# scene to warm up, snapshots the viewport, writes a PNG, quits.

@export var output_path: String = "res://capture.png"
@export var warmup_frames: int = 60
@export var viewport_size: Vector2i = Vector2i(1280, 800)
@export_enum("walk", "iso", "topdown") var force_camera_mode: String = "iso"

var _frames_waited: int = 0


func _ready() -> void:
	get_viewport().size = viewport_size
	# Find the camera rig and switch to the requested mode for the capture
	var rig: Node = get_tree().get_root().find_child("CameraRig", true, false)
	if rig != null and rig.has_method("_set_mode"):
		var mode_int: int = 0
		match force_camera_mode:
			"walk":    mode_int = 0
			"iso":     mode_int = 1
			"topdown": mode_int = 2
		rig.call_deferred("_set_mode", mode_int)


func _process(_delta: float) -> void:
	_frames_waited += 1
	if _frames_waited < warmup_frames:
		return
	var img: Image = get_viewport().get_texture().get_image()
	if img == null:
		push_error("[capture] viewport image is null")
		get_tree().quit(1)
		return
	var disk_path: String = ProjectSettings.globalize_path(output_path)
	# Ensure parent dir exists
	var parent_dir: String = disk_path.get_base_dir()
	DirAccess.make_dir_recursive_absolute(parent_dir)
	var err = img.save_png(disk_path)
	if err != OK:
		push_error("[capture] save_png failed: " + str(err))
		get_tree().quit(1)
		return
	print("[capture] wrote ", output_path)
	get_tree().quit(0)
