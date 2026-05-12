extends Node3D

# Phase F.3.6 — minimal driver for the WorldChunkLoader. Spawns one
# loader pointed at a world_map.json, sweeps a camera over the world,
# and exposes the same review_* tuning the M11 tour exposes so this
# scene shares the M11 rendering knobs.

const WorldChunkLoaderScript = preload("res://scripts/WorldChunkLoader.gd")

@export var world_map_path: String = ""
@export var sweep_duration_sec: float = 6.0
@export var start_world: Vector3 = Vector3.ZERO
@export var end_world: Vector3 = Vector3.ZERO
@export var camera_height: float = 160.0
@export var camera_pitch_deg: float = -42.0
@export var auto_quit_after_sweep: bool = false
@export var chunk_size_m: float = 64.0
@export var chunk_resolution_m: float = 4.0
@export var view_radius_chunks: int = 6

# M11-tour render params (mirror World3AutoReviewTour's review_*).
@export var review_use_source_macro_valid_mask: bool = true
@export_range(0.0, 1.0, 0.01) var review_source_macro_strength: float = 0.84
@export var review_normal_strength: float = 0.050
@export var review_detail_normal_strength: float = 0.014
@export var review_detail_rough_strength: float = 0.018
@export_range(0.0, 2.0, 0.01) var review_roughness_strength: float = 1.0
@export_range(0.04, 1.0, 0.01) var review_roughness_floor: float = 0.87
@export_range(0.0, 1.0, 0.01) var review_specular_strength: float = 0.0
@export_range(0.0, 1.25, 0.01) var review_albedo_gain: float = 0.95
@export var review_background_color: Color = Color(0.08, 0.095, 0.1, 1)
@export var review_tonemap_exposure: float = 0.58
@export var review_sun_energy: float = 0.55
@export var review_ambient_energy: float = 0.20

var _loader: WorldChunkLoader
var _anchor: Node3D
var _camera: Camera3D
var _t: float = 0.0


func _ready() -> void:
	_setup_environment()
	_setup_anchor()
	_setup_camera()
	_setup_loader()


func _process(delta: float) -> void:
	_t += delta
	var u: float = clampf(_t / max(sweep_duration_sec, 0.001), 0.0, 1.0)
	var pos: Vector3 = start_world.lerp(end_world, _smoothstep01(u))
	_anchor.global_position = pos
	if _camera != null:
		var look_offset: Vector3 = Vector3(0.0, camera_height, camera_height * 0.7)
		_camera.global_position = pos + look_offset
		_camera.look_at(pos, Vector3.UP)
	if auto_quit_after_sweep and u >= 1.0:
		get_tree().quit(0)


func _smoothstep01(x: float) -> float:
	return x * x * (3.0 - 2.0 * x)


func _setup_anchor() -> void:
	_anchor = Node3D.new()
	_anchor.name = "Anchor"
	add_child(_anchor)
	_anchor.global_position = start_world


func _setup_camera() -> void:
	_camera = Camera3D.new()
	_camera.name = "Camera3D"
	_camera.current = true
	_camera.near = 0.5
	_camera.far = 6000.0
	_camera.fov = 60.0
	add_child(_camera)


func _setup_loader() -> void:
	_loader = WorldChunkLoaderScript.new()
	_loader.name = "WorldChunkLoader"
	_loader.world_map_path = world_map_path
	_loader.chunk_size_m = chunk_size_m
	_loader.chunk_resolution_m = chunk_resolution_m
	_loader.view_radius_chunks = view_radius_chunks
	_loader.auto_update = true
	_loader.review_use_source_macro_valid_mask = review_use_source_macro_valid_mask
	_loader.review_source_macro_strength = review_source_macro_strength
	_loader.review_normal_strength = review_normal_strength
	_loader.review_detail_normal_strength = review_detail_normal_strength
	_loader.review_detail_rough_strength = review_detail_rough_strength
	_loader.review_roughness_strength = review_roughness_strength
	_loader.review_roughness_floor = review_roughness_floor
	_loader.review_specular_strength = review_specular_strength
	_loader.review_albedo_gain = review_albedo_gain
	add_child(_loader)
	_loader.target_path = _loader.get_path_to(_anchor)


func _setup_environment() -> void:
	# Sun
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_energy = review_sun_energy
	sun.rotation_degrees = Vector3(-55.0, -32.0, 0.0)
	sun.shadow_enabled = true
	add_child(sun)

	# World environment
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = review_background_color
	env.ambient_light_source = Environment.AMBIENT_SOURCE_BG
	env.ambient_light_energy = review_ambient_energy
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = review_tonemap_exposure
	var we: WorldEnvironment = WorldEnvironment.new()
	we.name = "WorldEnvironment"
	we.environment = env
	add_child(we)
