extends Node3D


@export var heightmap_path: String = "res://toporeview/gloss_mountain_textured_master/heightmap.png"
@export var meta_path: String = "res://toporeview/gloss_mountain_textured_master/meta.json"
@export var material_path: String = "res://textures/wgv3/terrain_source_stack_gloss_scrub_source_stack.tres"
@export var chunk_size_m: float = 128.0
@export var chunk_resolution_m: float = 4.0
@export var view_radius_chunks: int = 1
@export_enum("mid_oblique", "close_oblique", "topdown") var review_shot: String = "mid_oblique"
@export var overlay_text: String = "Source-Stack Runtime Review | OpenTopo macro albedo + tileable real detail"


func _ready() -> void:
	_setup_environment()

	var anchor := Node3D.new()
	anchor.name = "ReviewAnchor"
	anchor.position = Vector3.ZERO
	add_child(anchor)

	var material_res := load(material_path)
	if not material_res is ShaderMaterial:
		push_error("SourceStackRuntimeReview failed to load ShaderMaterial: " + material_path)
		_add_overlay("ERROR: material failed to load | " + material_path)
		return
	var mat: ShaderMaterial = (material_res as ShaderMaterial).duplicate()
	var loader := ChunkLoader.new()
	loader.name = "ChunkLoader"
	loader.auto_update = false
	loader.heightmap_path = heightmap_path
	loader.meta_path = meta_path
	loader.terrain_material = mat
	loader.chunk_size_m = chunk_size_m
	loader.chunk_resolution_m = chunk_resolution_m
	loader.view_radius_chunks = view_radius_chunks
	loader.max_subdivisions_per_chunk = 96
	add_child(loader)
	loader.target_path = loader.get_path_to(anchor)
	loader.update_for_position(anchor.global_position)

	var terrain_y: float = float(loader.sample_height_global(anchor.global_position.x, anchor.global_position.z))
	anchor.global_position.y = terrain_y + 32.0

	_add_camera(anchor.global_position, terrain_y)
	_add_overlay(overlay_text)


func _add_camera(anchor_position: Vector3, terrain_y: float) -> void:
	var cam := Camera3D.new()
	cam.name = "Camera3D"
	cam.current = true
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.near = 0.5
	cam.far = 6000.0
	add_child(cam)
	var target := Vector3(anchor_position.x, terrain_y, anchor_position.z)
	if review_shot == "close_oblique":
		cam.size = 155.0
		cam.position = target + Vector3(-94.0, 168.0, -126.0)
		cam.look_at(target + Vector3(16.0, 0.0, 12.0), Vector3.UP)
	elif review_shot == "topdown":
		cam.size = 330.0
		cam.position = target + Vector3(0.0, 740.0, 0.01)
		cam.look_at(target, Vector3(0.0, 0.0, -1.0))
	else:
		cam.size = 460.0
		cam.position = target + Vector3(0.0, 420.0, -320.0)
		cam.look_at(target, Vector3.UP)


func _setup_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.55, 0.70, 0.90)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.50, 0.54, 0.58)
	env.ambient_light_energy = 0.28
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 0.82
	env.ssao_enabled = true
	env.ssao_radius = 5.0
	env.ssao_intensity = 1.0

	var world_env := WorldEnvironment.new()
	world_env.name = "WorldEnv"
	world_env.environment = env
	add_child(world_env)

	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = Color(1.0, 0.97, 0.92)
	sun.light_energy = 1.2
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 3000.0
	add_child(sun)
	sun.look_at(Vector3(-0.45, -0.85, -0.28), Vector3.UP)


func _add_overlay(text: String) -> void:
	var layer := CanvasLayer.new()
	layer.name = "Overlay"
	add_child(layer)
	var label := Label.new()
	label.text = text
	label.position = Vector2(18.0, 18.0)
	label.add_theme_font_size_override("font_size", 22)
	label.add_theme_color_override("font_color", Color.WHITE)
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	label.add_theme_constant_override("outline_size", 7)
	layer.add_child(label)
