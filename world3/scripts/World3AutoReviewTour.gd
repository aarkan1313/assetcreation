extends Node3D


@export var material_path: String = "res://textures/wgv3/terrain_source_stack_gloss_grassland_comfy_v3_source_stack.tres"
@export var heightmap_path: String = "res://toporeview/gloss_mountain_textured_master/heightmap.png"
@export var meta_path: String = "res://toporeview/gloss_mountain_textured_master/meta.json"
@export var transition_rule_id: String = "opentopo_scrub_sparse__dry_wash_neighbor"
@export var start_x_m: float = 64.0
@export var start_z_m: float = 128.0
@export var boundary_z_m: float = 128.0
@export var chunk_size_m: float = 256.0
@export var chunk_resolution_m: float = 8.0
@export var view_radius_chunks: int = 2
@export var transition_width_m: float = 72.0
@export var transition_repeat_m: float = 128.0
@export_range(0.0, 1.0, 0.01) var transition_strength: float = 0.28
@export var enable_transition_boundary: bool = false
@export var review_normal_strength: float = 0.06
@export var review_detail_normal_strength: float = 0.025
@export var review_detail_rough_strength: float = 0.025
@export var auto_play: bool = true

var _anchor: Node3D
var _loader: ChunkLoader
var _camera: Camera3D
var _overlay_label: Label
var _overlay_panel: ColorRect
var _tour: Array[Dictionary] = []
var _tour_index: int = 0
var _tour_time: float = 0.0
var _paused: bool = false
var _ui_visible: bool = true


func _ready() -> void:
	_setup_environment()
	_build_tour()
	_setup_terrain()
	_setup_camera()
	_setup_overlay()
	_apply_tour_frame(0.0)


func _process(delta: float) -> void:
	if _camera == null or _loader == null or _anchor == null:
		return
	if auto_play and not _paused:
		_tour_time += delta
		var duration: float = float(_tour[_tour_index].get("duration", 8.0))
		if _tour_time >= duration:
			_tour_index = (_tour_index + 1) % _tour.size()
			_tour_time = 0.0
	_apply_tour_frame(delta)


func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	match event.keycode:
		KEY_SPACE:
			_paused = not _paused
		KEY_N:
			_advance_tour(1)
		KEY_B:
			_advance_tour(-1)
		KEY_R:
			_tour_index = 0
			_tour_time = 0.0
			_paused = false
		KEY_H:
			_ui_visible = not _ui_visible
			_overlay_panel.visible = _ui_visible
			_overlay_label.visible = _ui_visible


func _advance_tour(dir: int) -> void:
	_tour_index = posmod(_tour_index + dir, _tour.size())
	_tour_time = 0.0


func _build_tour() -> void:
	_tour = [
		{
			"name": "3D close ground pass",
			"mode": "perspective",
			"duration": 9.0,
			"focus": Vector2(0.0, -56.0),
			"focus_end": Vector2(42.0, 24.0),
			"camera": Vector3(-86.0, 116.0, -128.0),
			"camera_end": Vector3(-62.0, 126.0, -112.0),
			"fov": 46.0
		},
		{
			"name": "3D medium boundary read",
			"mode": "perspective",
			"duration": 9.0,
			"focus": Vector2(-30.0, -18.0),
			"focus_end": Vector2(70.0, 72.0),
			"camera": Vector3(-182.0, 250.0, -280.0),
			"camera_end": Vector3(-146.0, 260.0, -236.0),
			"fov": 42.0
		},
		{
			"name": "Iso close material read",
			"mode": "ortho",
			"duration": 8.5,
			"focus": Vector2(0.0, 0.0),
			"focus_end": Vector2(96.0, 64.0),
			"camera": Vector3(-210.0, 260.0, -250.0),
			"camera_end": Vector3(-185.0, 260.0, -226.0),
			"size": 230.0
		},
		{
			"name": "Topdown source-stack footprint",
			"mode": "topdown",
			"duration": 8.5,
			"focus": Vector2(0.0, 0.0),
			"focus_end": Vector2(128.0, 0.0),
			"camera": Vector3(0.0, 780.0, 0.01),
			"camera_end": Vector3(0.0, 780.0, 0.01),
			"size": 430.0
		},
		{
			"name": "Far overview chunks",
			"mode": "ortho",
			"duration": 9.0,
			"focus": Vector2(-80.0, -80.0),
			"focus_end": Vector2(160.0, 160.0),
			"camera": Vector3(-360.0, 700.0, -420.0),
			"camera_end": Vector3(-330.0, 700.0, -390.0),
			"size": 760.0
		},
		{
			"name": "3D final near-field sweep",
			"mode": "perspective",
			"duration": 9.0,
			"focus": Vector2(76.0, 36.0),
			"focus_end": Vector2(-32.0, 112.0),
			"camera": Vector3(86.0, 128.0, -148.0),
			"camera_end": Vector3(118.0, 138.0, -126.0),
			"fov": 46.0
		}
	]


func _setup_terrain() -> void:
	_anchor = Node3D.new()
	_anchor.name = "ReviewAnchor"
	_anchor.position = Vector3(start_x_m, 0.0, start_z_m)
	add_child(_anchor)

	var material_res := load(material_path)
	if not material_res is ShaderMaterial:
		push_error("World3AutoReviewTour failed to load ShaderMaterial: " + material_path)
		return
	var mat: ShaderMaterial = (material_res as ShaderMaterial).duplicate()
	mat.set_shader_parameter("use_transition_strip", false)
	mat.set_shader_parameter("use_transition_mask", false)
	mat.set_shader_parameter("normal_strength", review_normal_strength)
	mat.set_shader_parameter("detail_normal_strength", review_detail_normal_strength)
	mat.set_shader_parameter("detail_rough_strength", review_detail_rough_strength)

	_loader = ChunkLoader.new()
	_loader.name = "ChunkLoader"
	_loader.auto_update = true
	_loader.heightmap_path = heightmap_path
	_loader.meta_path = meta_path
	_loader.terrain_material = mat
	_loader.chunk_size_m = chunk_size_m
	_loader.chunk_resolution_m = chunk_resolution_m
	_loader.view_radius_chunks = view_radius_chunks
	_loader.max_subdivisions_per_chunk = 96
	_loader.enable_transition_boundaries = enable_transition_boundary
	_loader.transition_rule_id = transition_rule_id
	_loader.transition_boundary_axis = "z"
	_loader.transition_boundary_world_m = boundary_z_m
	_loader.transition_width_m = transition_width_m
	_loader.transition_repeat_m = transition_repeat_m
	_loader.transition_mask_resolution = 128
	_loader.transition_strength = transition_strength
	add_child(_loader)
	_loader.target_path = _loader.get_path_to(_anchor)
	_loader.update_for_position(_anchor.global_position)


func _setup_camera() -> void:
	_camera = Camera3D.new()
	_camera.name = "Camera3D"
	_camera.current = true
	_camera.near = 0.5
	_camera.far = 14000.0
	add_child(_camera)


func _setup_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.50, 0.62, 0.68)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.55, 0.56, 0.54)
	env.ambient_light_energy = 0.42
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 0.94
	env.ssao_enabled = true
	env.ssao_radius = 4.0
	env.ssao_intensity = 0.7

	var world_env := WorldEnvironment.new()
	world_env.name = "WorldEnv"
	world_env.environment = env
	add_child(world_env)

	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = Color(1.0, 0.97, 0.90)
	sun.light_energy = 1.35
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 5000.0
	add_child(sun)
	sun.look_at(Vector3(-0.42, -0.86, -0.25), Vector3.UP)


func _setup_overlay() -> void:
	var layer := CanvasLayer.new()
	layer.name = "Overlay"
	add_child(layer)

	_overlay_panel = ColorRect.new()
	_overlay_panel.color = Color(0.02, 0.025, 0.02, 0.62)
	_overlay_panel.position = Vector2(14.0, 14.0)
	_overlay_panel.size = Vector2(900.0, 136.0)
	layer.add_child(_overlay_panel)

	_overlay_label = Label.new()
	_overlay_label.position = Vector2(28.0, 24.0)
	_overlay_label.size = Vector2(870.0, 120.0)
	_overlay_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_overlay_label.add_theme_font_size_override("font_size", 18)
	_overlay_label.add_theme_color_override("font_color", Color.WHITE)
	_overlay_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	_overlay_label.add_theme_constant_override("outline_size", 6)
	layer.add_child(_overlay_label)


func _apply_tour_frame(delta: float) -> void:
	var frame: Dictionary = _tour[_tour_index]
	var duration: float = max(float(frame.get("duration", 8.0)), 0.001)
	var t: float = clamp(_tour_time / duration, 0.0, 1.0)
	var eased: float = _smoothstep(0.0, 1.0, t)

	var focus_a: Vector2 = frame.get("focus", Vector2.ZERO)
	var focus_b: Vector2 = frame.get("focus_end", focus_a)
	var focus_2d: Vector2 = focus_a.lerp(focus_b, eased)
	var focus_x: float = start_x_m + focus_2d.x
	var focus_z: float = start_z_m + focus_2d.y
	var terrain_y: float = float(_loader.sample_height_global(focus_x, focus_z))
	var focus: Vector3 = Vector3(focus_x, terrain_y + 10.0, focus_z)
	_anchor.global_position = Vector3(focus_x, terrain_y + 36.0, focus_z)
	if delta > 0.0:
		_loader.update_for_position(_anchor.global_position)

	var cam_a: Vector3 = frame.get("camera", Vector3(0.0, 120.0, -220.0))
	var cam_b: Vector3 = frame.get("camera_end", cam_a)
	var cam_offset: Vector3 = cam_a.lerp(cam_b, eased)
	_camera.global_position = focus + cam_offset

	var mode: String = str(frame.get("mode", "perspective"))
	if mode == "topdown":
		_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		_camera.size = float(frame.get("size", 430.0))
		_camera.look_at(focus, Vector3(0.0, 0.0, -1.0))
	elif mode == "ortho":
		_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		_camera.size = float(frame.get("size", 350.0))
		_camera.look_at(focus, Vector3.UP)
	else:
		_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
		_camera.fov = float(frame.get("fov", 50.0))
		_camera.look_at(focus, Vector3.UP)

	_update_overlay(frame, t)


func _update_overlay(frame: Dictionary, t: float) -> void:
	if _overlay_label == null:
		return
	var mode_text: String = "paused" if _paused else "auto"
	var workflow_text: String = "M4/M5 source-stack + M8 sidecar candidate"
	if enable_transition_boundary:
		workflow_text = "M7 boundary-enabled source-stack review"
	_overlay_label.text = (
		"world3 Source-Stack Auto Review | " + workflow_text + "\n"
		+ "%d/%d  %s  |  %s  |  progress %02d%%\n"
		+ "Views: close/medium 3D, iso, topdown, far, near sweep\n"
		+ "Keys: Space pause | N/B step | R reset | H UI"
	) % [
		_tour_index + 1,
		_tour.size(),
		str(frame.get("name", "")),
		mode_text,
		int(round(t * 100.0))
	]


func _smoothstep(edge0: float, edge1: float, x: float) -> float:
	var t: float = clamp((x - edge0) / max(edge1 - edge0, 0.000001), 0.0, 1.0)
	return t * t * (3.0 - 2.0 * t)
