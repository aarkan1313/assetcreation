extends Node3D

@export var board_texture_path: String = "res://docs/captures/m14/m14_tundra_lichen_runtime_ab_compare_sheet.png"
@export var board_width_m: float = 1200.0
@export var board_height_m: float = 800.0


func _ready() -> void:
	_setup_environment()
	_add_board()
	_add_overlay()
	_add_camera()


func _add_board() -> void:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = "M14LichenRuntimeABBoard"
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(board_width_m, board_height_m)
	mesh_instance.mesh = mesh
	mesh_instance.material_override = _make_unshaded_material(board_texture_path)
	add_child(mesh_instance)


func _make_unshaded_material(texture_path: String) -> Material:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.albedo_color = Color.WHITE
	material.albedo_texture = _load_texture(texture_path)
	return material


func _load_texture(path: String) -> Texture2D:
	var global_path := ProjectSettings.globalize_path(path)
	var img := Image.load_from_file(global_path)
	if img != null:
		return ImageTexture.create_from_image(img)
	var tex := load(path) as Texture2D
	if tex == null:
		push_error("M14LichenSidecarCompareBoard failed to load texture: " + path)
	return tex


func _add_camera() -> void:
	var camera := Camera3D.new()
	camera.name = "M14LichenCompareCamera"
	camera.current = true
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 860.0
	camera.near = 0.5
	camera.far = 3000.0
	camera.position = Vector3(0.0, 1300.0, 0.1)
	add_child(camera)
	camera.rotation_degrees = Vector3(-90.0, 0.0, 0.0)


func _setup_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.52, 0.62, 0.64)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.6, 0.64, 0.7)
	env.ambient_light_energy = 0.55
	var world_env := WorldEnvironment.new()
	world_env.name = "WorldEnv"
	world_env.environment = env
	add_child(world_env)


func _add_overlay() -> void:
	var layer := CanvasLayer.new()
	layer.name = "Overlay"
	add_child(layer)

	var panel := ColorRect.new()
	panel.color = Color(0.02, 0.025, 0.02, 0.64)
	panel.position = Vector2(14.0, 14.0)
	panel.size = Vector2(1180.0, 92.0)
	layer.add_child(panel)

	var label := Label.new()
	label.text = "M14 lichen sidecar A/B: source-only | runtime subtle | debug stress | raw generated 2x2"
	label.position = Vector2(28.0, 25.0)
	label.add_theme_font_size_override("font_size", 24)
	label.add_theme_color_override("font_color", Color.WHITE)
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	label.add_theme_constant_override("outline_size", 6)
	layer.add_child(label)

	var sub := Label.new()
	sub.text = "Purpose: show that M14 changed the texture sidecar workflow; the production-strength layer is intentionally subtle."
	sub.position = Vector2(28.0, 58.0)
	sub.add_theme_font_size_override("font_size", 18)
	sub.add_theme_color_override("font_color", Color(0.88, 0.9, 0.86))
	sub.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	sub.add_theme_constant_override("outline_size", 5)
	layer.add_child(sub)
