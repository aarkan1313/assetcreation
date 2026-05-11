extends Node3D

# Phase F.7 walk smoke — slides a camera across the 2x2 starter world,
# letting MultiBundleStreamer load/unload bundles as the player moves.
# Used by the F.7 capture scene to produce review evidence.

const StreamerScript = preload("res://scripts/MultiBundleStreamer.gd")

@export var world_map_path: String = "res://worlds/starter_2x2_procedural/world_map.json"
@export var sweep_duration_sec: float = 6.0
@export var start_world: Vector3 = Vector3(64.0, 0.0, 64.0)
@export var end_world: Vector3 = Vector3(448.0, 0.0, 448.0)
@export var camera_height: float = 80.0
@export var camera_pitch_deg: float = -42.0
@export var auto_quit_after_sweep: bool = false

var _streamer: Node3D
var _anchor: Node3D
var _camera: Camera3D
var _t: float = 0.0


func _ready() -> void:
	_setup_environment()
	_setup_anchor()
	_setup_camera()
	_setup_streamer()
	_setup_overlay()


func _process(delta: float) -> void:
	_t += delta
	var u: float = clampf(_t / sweep_duration_sec, 0.0, 1.0)
	var pos: Vector3 = start_world.lerp(end_world, _smoothstep01(u))
	_anchor.global_position = pos
	if auto_quit_after_sweep and u >= 1.0:
		get_tree().quit(0)


func _smoothstep01(x: float) -> float:
	return x * x * (3.0 - 2.0 * x)


func _setup_anchor() -> void:
	_anchor = Node3D.new()
	_anchor.name = "PlayerAnchor"
	add_child(_anchor)
	_anchor.global_position = start_world


func _setup_camera() -> void:
	_camera = Camera3D.new()
	_camera.name = "Camera3D"
	_camera.current = true
	_camera.near = 0.5
	_camera.far = 4000.0
	_camera.fov = 60.0
	add_child(_camera)


func _setup_streamer() -> void:
	_streamer = StreamerScript.new()
	_streamer.name = "Streamer"
	_streamer.world_map_path = world_map_path
	_streamer.target_path = _anchor.get_path()
	# F.3.4: match M11 fourway's chunk tuning. One ChunkLoader per
	# bundle, chunk_size=128 means each 256m bundle is a 4-chunk patch;
	# chunk_resolution=2.0 gives 64 verts per chunk side = 256 verts
	# per bundle side, dense enough that splat-weight sampling
	# interpolates smoothly without striping artifacts.
	_streamer.chunk_size_m = 128.0
	_streamer.chunk_resolution_m = 2.0
	_streamer.view_radius_chunks = 2
	_streamer.bundle_keep_radius_m = 384.0
	_streamer.bundle_drop_radius_m = 640.0
	add_child(_streamer)


func _setup_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.50, 0.62, 0.68)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.55, 0.56, 0.54)
	env.ambient_light_energy = 0.42
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 0.94

	var world_env := WorldEnvironment.new()
	world_env.name = "WorldEnv"
	world_env.environment = env
	add_child(world_env)

	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = Color(1.0, 0.97, 0.90)
	sun.light_energy = 1.35
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 2000.0
	add_child(sun)
	sun.look_at(Vector3(-0.42, -0.86, -0.25), Vector3.UP)


func _setup_overlay() -> void:
	var layer := CanvasLayer.new()
	layer.name = "Overlay"
	add_child(layer)
	var panel := ColorRect.new()
	panel.color = Color(0.02, 0.025, 0.02, 0.62)
	panel.position = Vector2(14, 14)
	panel.size = Vector2(820, 96)
	layer.add_child(panel)
	var label := Label.new()
	label.name = "OverlayLabel"
	label.position = Vector2(28, 24)
	label.size = Vector2(800, 80)
	label.add_theme_font_size_override("font_size", 18)
	label.add_theme_color_override("font_color", Color.WHITE)
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	label.add_theme_constant_override("outline_size", 6)
	label.text = "F.7 multi-bundle sweep: 2x2 starter world (4 bundles, tundra)\nCamera slides SW->NE across all 4 tiles."
	layer.add_child(label)


func _physics_process(_delta: float) -> void:
	if _camera == null or _anchor == null:
		return
	# Iso-ish camera framing the player anchor — sample the actual
	# terrain Y at the player position via the streamer.
	var look_target: Vector3 = _anchor.global_position
	var terrain_y: float = 0.0
	if _streamer != null and _streamer.has_method("sample_height_global"):
		terrain_y = float(_streamer.sample_height_global(look_target.x, look_target.z))
	var cam_pos: Vector3 = Vector3(look_target.x, terrain_y + camera_height,
								   look_target.z + camera_height * 1.6)
	_camera.global_position = cam_pos
	_camera.look_at(Vector3(look_target.x, terrain_y, look_target.z), Vector3.UP)

	# Update overlay with streamer diagnostics
	var overlay_layer := get_node_or_null("Overlay")
	if overlay_layer == null:
		return
	var label := overlay_layer.get_node_or_null("OverlayLabel") as Label
	if label == null or _streamer == null:
		return
	var pos: Vector3 = _anchor.global_position
	var bundle_count: int = int(_streamer.loaded_bundles_count)
	label.text = "F.7 multi-bundle sweep | tick %0.1fs | pos (%0.0f, %0.0f) | bundles loaded: %d" % [
		_t, pos.x, pos.z, bundle_count
	]
