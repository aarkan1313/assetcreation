extends Node3D


@export var material_path: String = "res://textures/wgv3/terrain_splat_alpine.tres"
@export var splat_cache_path: String = "res://runtime_cache/alpine_splat_rgba8.json"
@export var splat_path: String = "res://textures/m4_splat/alpine_height_slope_weights_rgba.png"
@export var transition_rule_id: String = "biome_desert__grassland_base"
@export var boundary_z_m: float = 1792.0


func _ready() -> void:
	_setup_environment()

	var anchor: Node3D = Node3D.new()
	anchor.name = "ReviewAnchor"
	anchor.position = Vector3(128.0, 0.0, boundary_z_m)
	add_child(anchor)

	var mat: ShaderMaterial = (load(material_path) as ShaderMaterial).duplicate()
	mat.set_shader_parameter("use_transition_strip", false)
	mat.set_shader_parameter("use_transition_mask", false)

	var loader: ChunkLoader = _new_boundary_loader(mat)
	add_child(loader)
	loader.target_path = loader.get_path_to(anchor)
	loader.update_for_position(anchor.global_position)

	var terrain_y: float = float(loader.sample_height_global(anchor.global_position.x, anchor.global_position.z))
	anchor.global_position.y = terrain_y + 64.0

	var cam: Camera3D = Camera3D.new()
	cam.name = "Camera3D"
	cam.current = true
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 680.0
	cam.near = 0.5
	cam.far = 12000.0
	cam.position = Vector3(anchor.global_position.x, terrain_y + 720.0, anchor.global_position.z - 380.0)
	add_child(cam)
	cam.look_at(Vector3(anchor.global_position.x, terrain_y, anchor.global_position.z), Vector3.UP)


func _new_boundary_loader(mat: ShaderMaterial) -> ChunkLoader:
	var loader: ChunkLoader = ChunkLoader.new()
	loader.name = "ChunkLoader"
	loader.auto_update = false
	loader.heightmap_cache_path = "res://runtime_cache/heightmap_rf32.json"
	loader.terrain_material = mat
	loader.splat_weights_path = splat_path
	loader.splat_weights_cache_path = splat_cache_path
	loader.chunk_size_m = 256.0
	loader.chunk_resolution_m = 8.0
	loader.view_radius_chunks = 1
	loader.enable_transition_boundaries = true
	loader.transition_rule_id = transition_rule_id
	loader.transition_boundary_axis = "z"
	loader.transition_boundary_world_m = boundary_z_m
	loader.transition_width_m = 192.0
	loader.transition_repeat_m = 128.0
	loader.transition_mask_resolution = 128
	loader.transition_strength = 0.92
	return loader


func _setup_environment() -> void:
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.55, 0.70, 0.90)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.45, 0.50, 0.56)
	env.ambient_light_energy = 0.25
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 0.8
	var world_env: WorldEnvironment = WorldEnvironment.new()
	world_env.name = "WorldEnv"
	world_env.environment = env
	add_child(world_env)

	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = Color(1.0, 0.97, 0.92)
	sun.light_energy = 1.15
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 20000.0
	add_child(sun)
	sun.look_at(Vector3(-0.5, -0.8, -0.25), Vector3.UP)
