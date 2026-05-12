extends Node3D


@export var material_path: String = "res://textures/wgv3/terrain_splat_alpine.tres"
@export var heightmap_path: String = "res://heightmap/heightmap.png"
@export var heightmap_cache_path: String = "res://runtime_cache/heightmap_rf32.json"
@export var meta_path: String = "res://heightmap/meta.json"
@export var splat_cache_path: String = "res://runtime_cache/alpine_splat_rgba8.json"
@export var splat_path: String = "res://textures/m4_splat/alpine_height_slope_weights_rgba.png"
@export var transition_rule_id: String = "opentopo_scrub_sparse__dry_wash_neighbor"
@export var start_x_m: float = 128.0
@export var start_z_m: float = 1536.0
@export var boundary_z_m: float = 1792.0
@export var chunk_size_m: float = 256.0
@export var chunk_resolution_m: float = 8.0
@export var view_radius_chunks: int = 1
@export var transition_width_m: float = 192.0
@export var transition_repeat_m: float = 128.0
@export var transition_strength: float = 0.92

var _player: Node3D
var _loader: ChunkLoader
var _camera: Camera3D


func _ready() -> void:
	_setup_environment()

	_player = Node3D.new()
	_player.name = "Player"
	_player.position = Vector3(start_x_m, 0.0, start_z_m)
	add_child(_player)

	var mat: ShaderMaterial = (load(material_path) as ShaderMaterial).duplicate()
	mat.set_shader_parameter("use_transition_strip", false)
	mat.set_shader_parameter("use_transition_mask", false)

	_loader = _new_boundary_loader(mat)
	add_child(_loader)
	_loader.target_path = _loader.get_path_to(_player)
	_loader.update_for_position(_player.global_position)

	var terrain_y: float = float(_loader.sample_height_global(_player.global_position.x, _player.global_position.z))
	_player.global_position.y = terrain_y + 64.0

	_camera = Camera3D.new()
	_camera.name = "Camera3D"
	_camera.current = true
	_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
	_camera.fov = 55.0
	_camera.near = 0.5
	_camera.far = 12000.0
	add_child(_camera)
	_update_camera()


func _process(_delta: float) -> void:
	_update_camera()


func _new_boundary_loader(mat: ShaderMaterial) -> ChunkLoader:
	var loader: ChunkLoader = ChunkLoader.new()
	loader.name = "ChunkLoader"
	loader.auto_update = true
	loader.heightmap_path = heightmap_path
	loader.heightmap_cache_path = heightmap_cache_path
	loader.meta_path = meta_path
	loader.terrain_material = mat
	loader.splat_weights_path = splat_path
	loader.splat_weights_cache_path = splat_cache_path
	loader.chunk_size_m = chunk_size_m
	loader.chunk_resolution_m = chunk_resolution_m
	loader.view_radius_chunks = view_radius_chunks
	loader.enable_transition_boundaries = true
	loader.transition_rule_id = transition_rule_id
	loader.transition_boundary_axis = "z"
	loader.transition_boundary_world_m = boundary_z_m
	loader.transition_width_m = transition_width_m
	loader.transition_repeat_m = transition_repeat_m
	loader.transition_mask_resolution = 128
	loader.transition_strength = transition_strength
	return loader


func _update_camera() -> void:
	if _player == null or _camera == null or _loader == null:
		return
	var terrain_y: float = float(_loader.sample_height_global(_player.global_position.x, _player.global_position.z))
	var focus: Vector3 = Vector3(_player.global_position.x, terrain_y + 8.0, _player.global_position.z)
	_camera.global_position = Vector3(_player.global_position.x, terrain_y + 150.0, _player.global_position.z - 220.0)
	_camera.look_at(focus, Vector3.UP)


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
