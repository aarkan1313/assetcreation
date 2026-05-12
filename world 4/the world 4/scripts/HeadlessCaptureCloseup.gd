extends Node
# Headless closeup capture: override the walk camera to a fixed
# position + orientation so a specific tile is the dominant subject.
# Used for Stage 5d (two-tier verification): point straight down into
# tile_1_1 (forest, with hero-tier ground + rock + standard-tier mid)
# to make hero-vs-standard sampling unmistakable.

@export var output_path: String = "res://captures/closeup.png"
@export var warmup_frames: int = 120
@export var viewport_size: Vector2i = Vector2i(1280, 800)
@export var camera_pos: Vector3 = Vector3(-128.0, 50.0, -128.0)  # mid of tile_1_1
@export var camera_look_at: Vector3 = Vector3(-128.0, 0.0, -128.0)

var _frames_waited: int = 0
var _did_capture: bool = false


func _ready() -> void:
	get_viewport().size = viewport_size
	# Find the camera rig and force walk mode.
	var rig: Node = _find_rig(get_tree().root)
	if rig != null and rig.has_method("_set_mode"):
		# AnchorCameraRig.CameraMode.WALK = 0
		rig._set_mode(0)
	# Wait one frame for the rig to set up cameras, then override.
	await get_tree().process_frame
	var cam: Camera3D = _find_active_camera(get_tree().root)
	if cam != null:
		cam.global_position = camera_pos
		cam.look_at(camera_look_at, Vector3.UP)
		print("[closeup] camera at %s looking at %s" % [camera_pos, camera_look_at])
	else:
		push_error("[closeup] no active camera found")


func _process(_delta: float) -> void:
	if _did_capture:
		return
	if _frames_waited < warmup_frames:
		_frames_waited += 1
		return
	_did_capture = true
	# Re-grab + re-aim the camera every frame the rig might have moved it.
	var cam: Camera3D = _find_active_camera(get_tree().root)
	if cam != null:
		cam.global_position = camera_pos
		cam.look_at(camera_look_at, Vector3.UP)
	await RenderingServer.frame_post_draw
	var img: Image = get_viewport().get_texture().get_image()
	if img != null:
		var dst: String = ProjectSettings.globalize_path(output_path)
		img.save_png(dst)
		print("[closeup] wrote ", output_path)
	get_tree().quit()


func _find_rig(node: Node) -> Node:
	if node.get_script() != null and node.has_method("_set_mode"):
		return node
	for c in node.get_children():
		var found: Node = _find_rig(c)
		if found != null:
			return found
	return null


func _find_active_camera(node: Node) -> Camera3D:
	if node is Camera3D and (node as Camera3D).current:
		return node
	for c in node.get_children():
		var found: Camera3D = _find_active_camera(c)
		if found != null:
			return found
	return null
