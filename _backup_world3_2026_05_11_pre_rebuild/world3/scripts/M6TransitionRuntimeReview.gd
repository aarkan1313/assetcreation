extends Node3D


@export var material_path: String = "res://textures/wgv3/terrain_splat_alpine.tres"
@export var splat_cache_path: String = "res://runtime_cache/alpine_splat_rgba8.json"
@export var splat_path: String = "res://textures/m4_splat/alpine_height_slope_weights_rgba.png"
@export var transition_albedo_path: String = "res://textures/transitions/desert_sand__grassland_grass/albedo.png"
@export var transition_rough_path: String = "res://textures/transitions/desert_sand__grassland_grass/roughness.png"
@export var transition_ao_path: String = "res://textures/transitions/desert_sand__grassland_grass/ao.png"


func _ready() -> void:
	_setup_environment()

	var anchor: Node3D = Node3D.new()
	anchor.name = "ReviewAnchor"
	anchor.position = Vector3(128.0, 0.0, 1408.0)
	add_child(anchor)

	var mat: ShaderMaterial = (load(material_path) as ShaderMaterial).duplicate()
	mat.set_shader_parameter("use_transition_strip", true)
	mat.set_shader_parameter("transition_albedo", RuntimeImageCache.load_texture("", transition_albedo_path))
	mat.set_shader_parameter("transition_rough", RuntimeImageCache.load_texture("", transition_rough_path))
	mat.set_shader_parameter("transition_ao", RuntimeImageCache.load_texture("", transition_ao_path))
	mat.set_shader_parameter("transition_center_u", 0.625)
	mat.set_shader_parameter("transition_width_u", 0.18)
	mat.set_shader_parameter("transition_repeat_v", 0.75)
	mat.set_shader_parameter("transition_strength", 0.70)

	var loader: ChunkLoader = ChunkLoader.new()
	loader.name = "ChunkLoader"
	loader.auto_update = false
	loader.heightmap_cache_path = "res://runtime_cache/heightmap_rf32.json"
	loader.terrain_material = mat
	loader.splat_weights_path = splat_path
	loader.splat_weights_cache_path = splat_cache_path
	loader.chunk_size_m = 256.0
	loader.chunk_resolution_m = 8.0
	loader.view_radius_chunks = 0
	add_child(loader)
	loader.target_path = loader.get_path_to(anchor)
	loader.update_for_position(anchor.global_position)
	var terrain_y: float = float(loader.sample_height_global(anchor.global_position.x, anchor.global_position.z))
	anchor.global_position.y = terrain_y + 48.0

	var cam: Camera3D = Camera3D.new()
	cam.name = "Camera3D"
	cam.current = true
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 280.0
	cam.fov = 60.0
	cam.near = 0.5
	cam.far = 12000.0
	cam.position = Vector3(anchor.global_position.x, terrain_y + 420.0, anchor.global_position.z - 260.0)
	add_child(cam)
	cam.look_at(Vector3(anchor.global_position.x, terrain_y, anchor.global_position.z), Vector3.UP)


func _setup_environment() -> void:
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.55, 0.70, 0.90)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.55, 0.62, 0.75)
	env.ambient_light_energy = 0.35
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	var world_env: WorldEnvironment = WorldEnvironment.new()
	world_env.name = "WorldEnv"
	world_env.environment = env
	add_child(world_env)

	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = Color(1.0, 0.97, 0.92)
	sun.light_energy = 1.8
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 20000.0
	add_child(sun)
	sun.look_at(Vector3(-0.5, -0.8, -0.25), Vector3.UP)
