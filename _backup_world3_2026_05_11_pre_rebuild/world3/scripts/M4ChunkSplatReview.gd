extends Node3D

@export_node_path("Node3D") var loader_path: NodePath
@export_node_path("Node3D") var target_path: NodePath
@export_node_path("Camera3D") var camera_path: NodePath


func _ready() -> void:
	_add_overlay()
	_configure_camera()
	call_deferred("_prime_loader")


func _prime_loader() -> void:
	var loader: Variant = get_node_or_null(loader_path)
	var target: Node3D = get_node_or_null(target_path) as Node3D
	if loader == null or target == null:
		push_error("M4ChunkSplatReview: loader or target path is invalid")
		return
	if loader.has_method("update_for_position"):
		loader.update_for_position(target.global_position)


func _configure_camera() -> void:
	var camera: Camera3D = get_node_or_null(camera_path) as Camera3D
	if camera == null:
		return
	camera.current = true
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 900.0
	camera.near = 1.0
	camera.far = 10000.0
	camera.position = Vector3(128.0, 5200.0, 128.0)
	camera.rotation_degrees = Vector3(-90.0, 0.0, 0.0)


func _add_overlay() -> void:
	var layer := CanvasLayer.new()
	layer.name = "Overlay"
	add_child(layer)
	var label := Label.new()
	label.text = "M4 chunk splat review - 256 m chunks, 3x3 loaded, unified splat material"
	label.position = Vector2(22.0, 18.0)
	label.add_theme_font_size_override("font_size", 26)
	label.add_theme_color_override("font_color", Color.WHITE)
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	label.add_theme_constant_override("outline_size", 8)
	layer.add_child(label)
