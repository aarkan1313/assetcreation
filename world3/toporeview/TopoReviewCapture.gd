extends Node

# Sets a deterministic review camera, captures the real Godot viewport, then
# quits. This is for screenshot QA where the same camera must be reused across
# several toporeview scenes.
@export var review_path: NodePath = NodePath("../Inner")
@export var output_path: String = "user://toporeview_capture.png"
@export var warmup_frames: int = 12
@export var shot: String = "close_oblique"
@export var hide_ui: bool = false


func _ready() -> void:
	for i in range(warmup_frames):
		await get_tree().process_frame
	var review := get_node_or_null(review_path)
	if review != null:
		_apply_shot(review)
		if hide_ui:
			var label := review.get_node_or_null("CanvasLayer/ReviewLabel") as Label
			if label != null:
				label.visible = false
	for i in range(4):
		await get_tree().process_frame
	var img := get_viewport().get_texture().get_image()
	img.save_png(output_path)
	print("[toporeview_capture] wrote " + output_path)
	get_tree().quit(0)


func _apply_shot(review: Node) -> void:
	var terrain := review.get_node_or_null("Terrain") as MeshInstance3D
	var cam := review.get_node_or_null("Camera3D") as Camera3D
	if terrain == null or cam == null:
		return
	var aabb := terrain.get_aabb()
	var center := aabb.position + aabb.size * 0.5
	var span: float = max(aabb.size.x, aabb.size.z)
	var elev_span: float = max(aabb.size.y, 1.0)
	cam.near = 0.5
	cam.far = max(span * 8.0, 10000.0)
	cam.current = true
	if shot == "close_oblique":
		var target := center + Vector3(-span * 0.08, elev_span * 0.04, span * 0.15)
		cam.global_position = target + Vector3(-span * 0.045, elev_span * 0.08 + 35.0, -span * 0.075)
		cam.fov = 42.0
		cam.look_at(target, Vector3.UP)
	elif shot == "repair_edge":
		var target := center + Vector3(-span * 0.42, elev_span * 0.03, -span * 0.08)
		cam.global_position = target + Vector3(-span * 0.28, elev_span * 0.18 + 70.0, -span * 0.18)
		cam.fov = 44.0
		cam.look_at(target, Vector3.UP)
	elif shot == "mid_oblique":
		var target := center + Vector3(-span * 0.05, elev_span * 0.04, span * 0.10)
		cam.global_position = target + Vector3(-span * 0.14, elev_span * 0.20 + 90.0, -span * 0.22)
		cam.fov = 46.0
		cam.look_at(target, Vector3.UP)
	else:
		cam.global_position = center + Vector3(span * 0.85, elev_span * 1.2 + span * 0.35, span * 0.85)
		cam.fov = 48.0
		cam.look_at(center, Vector3.UP)
	if cam.has_method("sync_from_transform"):
		cam.call("sync_from_transform")
