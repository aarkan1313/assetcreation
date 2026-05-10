extends Node3D

const WalkerScript := preload("res://scripts/Walker.gd")

@export var material_path: String = "res://textures/wgv3/terrain_m11_fourway_corner.tres"
@export var heightmap_path: String = "res://toporeview/m11_fourway_corner_proof/heightmap.png"
@export var meta_path: String = "res://toporeview/m11_fourway_corner_proof/meta.json"
@export var source_valid_mask_path: String = "res://textures/source_stack/m11_fourway_corner_proof/source_macro_valid_mask.png"
@export var splat_weights_path: String = "res://textures/source_stack/m11_fourway_corner_proof/layers/splat_weights_rgba.png"
@export var splat_weights_cache_path: String = ""
@export var source_macro_albedo_override_path: String = "res://textures/source_stack/m11_fourway_corner_proof/source_macro_albedo.png"
@export var source_macro_valid_mask_override_path: String = "res://textures/source_stack/m11_fourway_corner_proof/source_macro_weight_mask.png"
@export var start_x_m: float = 0.0
@export var start_z_m: float = 0.0
@export var chunk_size_m: float = 128.0
@export var chunk_resolution_m: float = 4.0
@export var view_radius_chunks: int = 2
@export var build_collision_chunks: bool = true
@export_enum("mirror", "wrap", "blend_wrap", "clamp") var source_repeat_mode: String = "clamp"
@export var clip_to_source_bounds: bool = true
@export var review_source_macro_strength: float = 0.84
@export var review_normal_strength: float = 0.050
@export var review_detail_normal_strength: float = 0.014
@export var review_detail_rough_strength: float = 0.018
@export_range(0.0, 2.0, 0.01) var review_roughness_strength: float = 1.0
@export_range(0.04, 1.0, 0.01) var review_roughness_floor: float = 0.87
@export_range(0.0, 1.0, 0.01) var review_specular_strength: float = 0.0
@export_range(0.0, 1.25, 0.01) var review_albedo_gain: float = 1.0
@export var review_background_color: Color = Color(0.08, 0.095, 0.10, 1.0)
@export var review_tonemap_exposure: float = 0.66
@export var review_sun_energy: float = 0.62
@export var review_ambient_energy: float = 0.34
@export var initial_view_index: int = 0
@export_range(0.0, 0.99, 0.01) var initial_view_progress: float = 0.0
@export var auto_play: bool = true

var _player: CharacterBody3D
var _loader: ChunkLoader
var _camera: Camera3D
var _overlay_panel: ColorRect
var _overlay_label: Label
var _views: Array[Dictionary] = []
var _view_index: int = 0
var _view_time: float = 0.0
var _paused: bool = false
var _ui_visible: bool = true


func _ready() -> void:
	_apply_command_line_overrides()
	_setup_environment()
	_setup_player()
	_setup_terrain()
	_setup_camera()
	_setup_overlay()
	_build_views()
	_view_index = clampi(initial_view_index, 0, _views.size() - 1)
	_view_time = max(float(_views[_view_index].get("duration", 6.0)), 0.001) * clampf(initial_view_progress, 0.0, 0.99)
	_apply_view_frame(0.0)


func _process(delta: float) -> void:
	if _player == null or _loader == null or _camera == null:
		return
	if auto_play and not _paused:
		_view_time += delta
		var duration: float = float(_views[_view_index].get("duration", 6.0))
		if _view_time >= duration:
			_view_index = (_view_index + 1) % _views.size()
			_view_time = 0.0
	_apply_view_frame(delta)


func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	match event.keycode:
		KEY_SPACE:
			_paused = not _paused
		KEY_N:
			_step_view(1)
		KEY_B:
			_step_view(-1)
		KEY_R:
			_view_index = 0
			_view_time = 0.0
			_paused = false
		KEY_H:
			_ui_visible = not _ui_visible
			if _overlay_panel != null:
				_overlay_panel.visible = _ui_visible
			if _overlay_label != null:
				_overlay_label.visible = _ui_visible


func _apply_command_line_overrides() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i in range(args.size()):
		if args[i] == "--view-index" and i + 1 < args.size():
			initial_view_index = int(args[i + 1])
		if args[i] == "--view-progress" and i + 1 < args.size():
			initial_view_progress = float(args[i + 1])


func _step_view(dir: int) -> void:
	_view_index = posmod(_view_index + dir, _views.size())
	_view_time = 0.0


func _setup_player() -> void:
	_player = CharacterBody3D.new()
	_player.name = "Player"
	_player.set_script(WalkerScript)
	_player.set("fly_mode", true)
	_player.set("fly_speed", 175.0)
	_player.set("walk_speed", 18.0)

	var shape := CapsuleShape3D.new()
	shape.height = 1.8
	shape.radius = 0.4
	var collider := CollisionShape3D.new()
	collider.name = "Collider"
	collider.shape = shape
	_player.add_child(collider)

	var player_cam := Camera3D.new()
	player_cam.name = "Camera3D"
	player_cam.current = false
	player_cam.near = 0.5
	player_cam.far = 12000.0
	_player.add_child(player_cam)

	add_child(_player)


func _setup_terrain() -> void:
	var material_res := load(material_path)
	if not material_res is ShaderMaterial:
		push_error("M12 parity failed to load ShaderMaterial: " + material_path)
		return
	var mat: ShaderMaterial = (material_res as ShaderMaterial).duplicate()
	_configure_review_material(mat)

	_loader = ChunkLoader.new()
	_loader.name = "ChunkLoader"
	_loader.auto_update = true
	_loader.heightmap_path = heightmap_path
	_loader.meta_path = meta_path
	_loader.source_valid_mask_path = source_valid_mask_path
	_loader.splat_weights_path = splat_weights_path
	_loader.splat_weights_cache_path = splat_weights_cache_path
	_loader.terrain_material = mat
	_loader.chunk_size_m = chunk_size_m
	_loader.chunk_resolution_m = chunk_resolution_m
	_loader.view_radius_chunks = view_radius_chunks
	_loader.max_subdivisions_per_chunk = 96
	_loader.source_repeat_mode = source_repeat_mode
	_loader.source_repeat_blend_width_m = 0.0
	_loader.source_repeat_blend_macro_color = false
	_loader.source_repeat_blend_macro_fade = 0.0
	_loader.clip_to_source_bounds = clip_to_source_bounds
	_loader.build_collision_chunks = build_collision_chunks
	_loader.enable_transition_boundaries = false
	add_child(_loader)
	_loader.target_path = _loader.get_path_to(_player)
	_loader.update_for_position(Vector3(start_x_m, 0.0, start_z_m))


func _configure_review_material(mat: ShaderMaterial) -> void:
	mat.set_shader_parameter("use_transition_strip", false)
	mat.set_shader_parameter("use_transition_mask", false)
	mat.set_shader_parameter("use_source_macro_valid_mask", true)
	mat.set_shader_parameter("source_macro_strength", review_source_macro_strength)
	mat.set_shader_parameter("normal_strength", review_normal_strength)
	mat.set_shader_parameter("detail_normal_strength", review_detail_normal_strength)
	mat.set_shader_parameter("detail_rough_strength", review_detail_rough_strength)
	mat.set_shader_parameter("roughness_strength", review_roughness_strength)
	mat.set_shader_parameter("roughness_floor", review_roughness_floor)
	mat.set_shader_parameter("specular_strength", review_specular_strength)
	mat.set_shader_parameter("albedo_gain", review_albedo_gain)
	if source_macro_albedo_override_path != "":
		var albedo_tex: Texture2D = RuntimeImageCache.load_texture("", source_macro_albedo_override_path)
		if albedo_tex != null:
			mat.set_shader_parameter("source_macro_albedo", albedo_tex)
			mat.set_shader_parameter("use_source_macro_albedo", true)
		else:
			push_warning("M12 parity failed to load source macro: " + source_macro_albedo_override_path)
	if source_macro_valid_mask_override_path != "":
		var mask_tex: Texture2D = RuntimeImageCache.load_texture("", source_macro_valid_mask_override_path)
		if mask_tex != null:
			mat.set_shader_parameter("source_macro_valid_mask", mask_tex)
		else:
			push_warning("M12 parity failed to load source macro mask: " + source_macro_valid_mask_override_path)


func _build_views() -> void:
	var source_size: Vector2 = _source_size_m()
	var x_span: float = clamp(source_size.x * 0.54, 185.0, 300.0)
	var z_span: float = clamp(source_size.y * 0.48, 185.0, 310.0)
	var iso_size: float = clamp(max(source_size.x, source_size.y) * 0.78, 380.0, 590.0)
	var topdown_size: float = clamp(max(source_size.x, source_size.y) * 0.90, 450.0, 640.0)
	_views = [
		{
			"name": "True walk close play",
			"band": "close",
			"mode": "perspective",
			"duration": 6.0,
			"focus": Vector2(-x_span * 0.32, -z_span * 0.18),
			"focus_end": Vector2(x_span * 0.22, z_span * 0.10),
			"camera": Vector3(-62.0, 34.0, -78.0),
			"camera_end": Vector3(-46.0, 38.0, -66.0),
			"fov": 56.0,
			"player_clearance": 5.0
		},
		{
			"name": "True walk medium play",
			"band": "medium",
			"mode": "perspective",
			"duration": 6.0,
			"focus": Vector2(-x_span * 0.42, -z_span * 0.16),
			"focus_end": Vector2(x_span * 0.38, z_span * 0.20),
			"camera": Vector3(-168.0, 116.0, -205.0),
			"camera_end": Vector3(-138.0, 124.0, -176.0),
			"fov": 49.0,
			"player_clearance": 8.0
		},
		{
			"name": "Gallery iso parity",
			"band": "iso",
			"mode": "ortho",
			"duration": 6.0,
			"focus": Vector2(-x_span * 0.20, -z_span * 0.12),
			"focus_end": Vector2(x_span * 0.24, z_span * 0.14),
			"camera": Vector3(-390.0, 455.0, -455.0),
			"camera_end": Vector3(-360.0, 455.0, -425.0),
			"size": iso_size,
			"player_clearance": 36.0
		},
		{
			"name": "Gallery topdown parity",
			"band": "topdown",
			"mode": "topdown",
			"duration": 6.0,
			"focus": Vector2(-x_span * 0.06, -z_span * 0.04),
			"focus_end": Vector2(x_span * 0.08, z_span * 0.05),
			"camera": Vector3(0.0, 820.0, 0.01),
			"camera_end": Vector3(0.0, 820.0, 0.01),
			"size": topdown_size,
			"player_clearance": 36.0
		}
	]


func _apply_view_frame(delta: float) -> void:
	var frame: Dictionary = _views[_view_index]
	var duration: float = max(float(frame.get("duration", 6.0)), 0.001)
	var t: float = clamp(_view_time / duration, 0.0, 1.0)
	var eased: float = _smoothstep(t)
	var focus_a: Vector2 = frame.get("focus", Vector2.ZERO)
	var focus_b: Vector2 = frame.get("focus_end", focus_a)
	var focus_2d: Vector2 = focus_a.lerp(focus_b, eased)
	var focus_x: float = start_x_m + focus_2d.x
	var focus_z: float = start_z_m + focus_2d.y
	var terrain_y: float = float(_loader.sample_height_global(focus_x, focus_z))
	var player_clearance: float = float(frame.get("player_clearance", 8.0))
	_player.global_position = Vector3(focus_x, terrain_y + player_clearance, focus_z)
	if focus_b.distance_squared_to(focus_a) > 0.001:
		var travel: Vector2 = (focus_b - focus_a).normalized()
		_player.rotation.y = atan2(travel.x, travel.y)
	if delta >= 0.0:
		_loader.update_for_position(_player.global_position)

	var focus := Vector3(focus_x, terrain_y + 10.0, focus_z)
	var cam_a: Vector3 = frame.get("camera", Vector3(-120.0, 90.0, -160.0))
	var cam_b: Vector3 = frame.get("camera_end", cam_a)
	var cam_offset: Vector3 = cam_a.lerp(cam_b, eased)
	_camera.global_position = focus + cam_offset

	var mode: String = str(frame.get("mode", "perspective"))
	if mode == "topdown":
		_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		_camera.size = float(frame.get("size", 500.0))
		_camera.look_at(focus, Vector3(0.0, 0.0, -1.0))
	elif mode == "ortho":
		_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		_camera.size = float(frame.get("size", 450.0))
		_camera.look_at(focus, Vector3.UP)
	else:
		_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
		_camera.fov = float(frame.get("fov", 52.0))
		_camera.look_at(focus, Vector3.UP)
	_update_overlay(frame, t)


func _setup_camera() -> void:
	_camera = Camera3D.new()
	_camera.name = "ReviewCamera3D"
	_camera.current = true
	_camera.near = 0.5
	_camera.far = 14000.0
	add_child(_camera)


func _setup_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = review_background_color
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.55, 0.56, 0.54)
	env.ambient_light_energy = review_ambient_energy
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = review_tonemap_exposure
	env.glow_enabled = false
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
	sun.light_energy = review_sun_energy
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
	_overlay_panel.size = Vector2(980.0, 126.0)
	layer.add_child(_overlay_panel)

	_overlay_label = Label.new()
	_overlay_label.position = Vector2(28.0, 24.0)
	_overlay_label.size = Vector2(940.0, 108.0)
	_overlay_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_overlay_label.add_theme_font_size_override("font_size", 18)
	_overlay_label.add_theme_color_override("font_color", Color.WHITE)
	_overlay_label.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 0.9))
	_overlay_label.add_theme_constant_override("outline_size", 6)
	layer.add_child(_overlay_label)


func _update_overlay(frame: Dictionary, t: float) -> void:
	if _overlay_label == null:
		return
	var mode_text: String = "paused" if _paused else "auto"
	_overlay_label.text = (
		"world3 M12 Runtime Parity | same source/material/height/splat contract\n"
		+ "%d/%d  %s  |  %s  |  progress %d%%\n"
		+ "Views: true walk close/medium + gallery iso/topdown  |  Space pause  |  N/B step  |  H UI"
	) % [
		_view_index + 1,
		_views.size(),
		str(frame.get("name", "view")),
		mode_text,
		int(round(t * 100.0))
	]


func _source_size_m() -> Vector2:
	var f: FileAccess = FileAccess.open(meta_path, FileAccess.READ)
	if f == null:
		return Vector2(537.0, 537.0)
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		return Vector2(537.0, 537.0)
	var meta: Dictionary = parsed
	var world_size: float = float(meta.get("world_size_m", 537.0))
	return Vector2(
		float(meta.get("world_size_x_m", world_size)),
		float(meta.get("world_size_z_m", world_size))
	)


func _smoothstep(t: float) -> float:
	var x: float = clampf(t, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)
