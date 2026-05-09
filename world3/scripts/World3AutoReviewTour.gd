extends Node3D


@export var material_path: String = "res://textures/wgv3/terrain_source_stack_gloss_grassland_comfy_v3_source_stack.tres"
@export var heightmap_path: String = "res://toporeview/gloss_mountain_textured_master/heightmap.png"
@export var meta_path: String = "res://toporeview/gloss_mountain_textured_master/meta.json"
@export var source_valid_mask_path: String = ""
@export var source_macro_albedo_override_path: String = ""
@export var source_macro_valid_mask_override_path: String = ""
@export var transition_rule_id: String = "opentopo_scrub_sparse__dry_wash_neighbor"
@export var start_x_m: float = 64.0
@export var start_z_m: float = 128.0
@export var boundary_z_m: float = 128.0
@export var chunk_size_m: float = 256.0
@export var chunk_resolution_m: float = 8.0
@export var view_radius_chunks: int = 2
@export_enum("mirror", "wrap", "blend_wrap", "clamp") var source_repeat_mode: String = "mirror"
@export var source_repeat_blend_width_m: float = 96.0
@export var source_repeat_blend_macro_color: bool = true
@export_range(0.0, 1.0, 0.01) var source_repeat_blend_macro_fade: float = 0.0
@export var clip_to_source_bounds: bool = false
@export var transition_width_m: float = 72.0
@export var transition_repeat_m: float = 128.0
@export_range(0.0, 1.0, 0.01) var transition_strength: float = 0.28
@export var enable_transition_boundary: bool = false
@export var show_footprint_debug_views: bool = false
@export var review_use_source_macro_valid_mask: bool = true
@export var review_normal_strength: float = 0.06
@export var review_detail_normal_strength: float = 0.025
@export var review_detail_rough_strength: float = 0.025
@export_enum("standard", "full_map_fast", "same_source_blend", "seam_integration") var tour_profile: String = "standard"
@export var initial_tour_index: int = 0
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
	_apply_command_line_overrides()
	_setup_environment()
	_build_tour()
	_tour_index = clampi(initial_tour_index, 0, _tour.size() - 1)
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


func _apply_command_line_overrides() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i in range(args.size()):
		if args[i] == "--tour-index" and i + 1 < args.size():
			initial_tour_index = int(args[i + 1])
		if args[i] == "--tour-profile" and i + 1 < args.size():
			tour_profile = args[i + 1]


func _advance_tour(dir: int) -> void:
	_tour_index = posmod(_tour_index + dir, _tour.size())
	_tour_time = 0.0


func _build_tour() -> void:
	if tour_profile == "full_map_fast":
		_build_full_map_fast_tour()
		return
	if tour_profile == "same_source_blend":
		_build_same_source_blend_tour()
		return
	if tour_profile == "seam_integration":
		_build_seam_integration_tour()
		return
	_tour = [
		{
			"name": "3D close ground pass",
			"mode": "perspective",
			"duration": 8.0,
			"focus": Vector2(-36.0, -30.0),
			"focus_end": Vector2(8.0, 18.0),
			"camera": Vector3(-62.0, 82.0, -94.0),
			"camera_end": Vector3(-46.0, 90.0, -82.0),
			"fov": 42.0
		},
		{
			"name": "3D medium terrain read",
			"mode": "perspective",
			"duration": 8.0,
			"focus": Vector2(-28.0, -18.0),
			"focus_end": Vector2(32.0, 32.0),
			"camera": Vector3(-112.0, 150.0, -164.0),
			"camera_end": Vector3(-96.0, 156.0, -144.0),
			"fov": 40.0
		},
		{
			"name": "Iso close material read",
			"mode": "ortho",
			"duration": 8.0,
			"focus": Vector2(-10.0, -8.0),
			"focus_end": Vector2(42.0, 26.0),
			"camera": Vector3(-150.0, 205.0, -172.0),
			"camera_end": Vector3(-138.0, 205.0, -160.0),
			"size": 175.0
		},
		{
			"name": "Topdown local material map",
			"mode": "topdown",
			"duration": 8.0,
			"focus": Vector2(-8.0, -8.0),
			"focus_end": Vector2(56.0, 0.0),
			"camera": Vector3(0.0, 780.0, 0.01),
			"camera_end": Vector3(0.0, 780.0, 0.01),
			"size": 245.0
		},
		{
			"name": "Controlled overview",
			"mode": "topdown",
			"duration": 8.0,
			"focus": Vector2(-8.0, -8.0),
			"focus_end": Vector2(56.0, 0.0),
			"camera": Vector3(0.0, 780.0, 0.01),
			"camera_end": Vector3(0.0, 780.0, 0.01),
			"size": 245.0
		},
		{
			"name": "3D final near-field sweep",
			"mode": "perspective",
			"duration": 8.0,
			"focus": Vector2(32.0, 18.0),
			"focus_end": Vector2(-22.0, 44.0),
			"camera": Vector3(58.0, 96.0, -98.0),
			"camera_end": Vector3(76.0, 108.0, -86.0),
			"fov": 42.0
		}
	]
	if show_footprint_debug_views:
		_tour.append(
			{
				"name": "Diagnostic finite-footprint view",
				"mode": "ortho",
				"duration": 8.0,
				"focus": Vector2(0.0, 0.0),
				"focus_end": Vector2(160.0, 160.0),
				"camera": Vector3(-360.0, 700.0, -420.0),
				"camera_end": Vector3(-330.0, 700.0, -390.0),
				"size": 760.0
			}
		)


func _build_same_source_blend_tour() -> void:
	var source_size: Vector2 = _review_source_size_m()
	var seam_x: float = source_size.x * 0.5
	var seam_z: float = source_size.y * 0.5
	var x_span: float = clamp(source_size.x * 0.48, 120.0, 220.0)
	var z_span: float = clamp(source_size.y * 0.34, 140.0, 240.0)
	var topdown_size: float = clamp(max(source_size.x, source_size.y) * 0.36, 240.0, 420.0)
	var corner_size: float = clamp(max(source_size.x, source_size.y) * 0.54, 300.0, 560.0)
	_tour = [
		{
			"name": "X seam topdown blend",
			"mode": "topdown",
			"duration": 5.0,
			"focus": Vector2(seam_x - x_span * 0.5, 0.0),
			"focus_end": Vector2(seam_x + x_span * 0.5, 0.0),
			"camera": Vector3(0.0, 820.0, 0.01),
			"camera_end": Vector3(0.0, 820.0, 0.01),
			"size": topdown_size
		},
		{
			"name": "Z seam topdown blend",
			"mode": "topdown",
			"duration": 5.0,
			"focus": Vector2(0.0, seam_z - z_span * 0.5),
			"focus_end": Vector2(0.0, seam_z + z_span * 0.5),
			"camera": Vector3(0.0, 860.0, 0.01),
			"camera_end": Vector3(0.0, 860.0, 0.01),
			"size": topdown_size
		},
		{
			"name": "2x2 corner overview",
			"mode": "topdown",
			"duration": 5.0,
			"focus": Vector2(seam_x, seam_z),
			"focus_end": Vector2(seam_x, seam_z),
			"camera": Vector3(0.0, 980.0, 0.01),
			"camera_end": Vector3(0.0, 980.0, 0.01),
			"size": corner_size
		},
		{
			"name": "3D X seam traverse",
			"mode": "perspective",
			"duration": 5.0,
			"focus": Vector2(seam_x - x_span * 0.5, 20.0),
			"focus_end": Vector2(seam_x + x_span * 0.5, 20.0),
			"camera": Vector3(-190.0, 150.0, -230.0),
			"camera_end": Vector3(-160.0, 150.0, -210.0),
			"fov": 48.0
		},
		{
			"name": "3D Z seam traverse",
			"mode": "perspective",
			"duration": 5.0,
			"focus": Vector2(40.0, seam_z - z_span * 0.5),
			"focus_end": Vector2(40.0, seam_z + z_span * 0.5),
			"camera": Vector3(-220.0, 170.0, -250.0),
			"camera_end": Vector3(-200.0, 170.0, -230.0),
			"fov": 48.0
		},
		{
			"name": "2x2 corner 3D pass",
			"mode": "perspective",
			"duration": 5.0,
			"focus": Vector2(seam_x - x_span * 0.3, seam_z - z_span * 0.3),
			"focus_end": Vector2(seam_x + x_span * 0.3, seam_z + z_span * 0.3),
			"camera": Vector3(-260.0, 230.0, -320.0),
			"camera_end": Vector3(-230.0, 230.0, -300.0),
			"fov": 46.0
		}
	]


func _build_seam_integration_tour() -> void:
	var source_size: Vector2 = _review_source_size_m()
	var x_span: float = clamp(source_size.x * 0.30, 90.0, 150.0)
	var z_span: float = clamp(source_size.y * 0.36, 140.0, 240.0)
	var band_topdown_size: float = clamp(source_size.x * 0.62, 220.0, 270.0)
	var footprint_topdown_size: float = clamp(source_size.y * 1.02, 420.0, 600.0)
	var iso_size: float = clamp(max(source_size.x, source_size.y) * 0.74, 320.0, 560.0)
	_tour = [
		{
			"name": "Seam integration topdown band",
			"mode": "topdown",
			"duration": 6.0,
			"focus": Vector2(-x_span * 0.25, 0.0),
			"focus_end": Vector2(x_span * 0.25, 0.0),
			"camera": Vector3(0.0, 860.0, 0.01),
			"camera_end": Vector3(0.0, 860.0, 0.01),
			"size": band_topdown_size
		},
		{
			"name": "Seam integration iso sweep",
			"mode": "ortho",
			"duration": 6.0,
			"focus": Vector2(-x_span * 0.5, -z_span * 0.4),
			"focus_end": Vector2(x_span * 0.5, z_span * 0.4),
			"camera": Vector3(-360.0, 430.0, -430.0),
			"camera_end": Vector3(-340.0, 430.0, -410.0),
			"size": iso_size
		},
		{
			"name": "Close 3D seam traverse",
			"mode": "perspective",
			"duration": 6.0,
			"focus": Vector2(-x_span * 0.5, 18.0),
			"focus_end": Vector2(x_span * 0.5, 18.0),
			"camera": Vector3(-150.0, 115.0, -185.0),
			"camera_end": Vector3(-120.0, 115.0, -165.0),
			"fov": 46.0
		},
		{
			"name": "Medium 3D seam and landform read",
			"mode": "perspective",
			"duration": 6.0,
			"focus": Vector2(-x_span * 0.4, -z_span * 0.35),
			"focus_end": Vector2(x_span * 0.4, z_span * 0.35),
			"camera": Vector3(-245.0, 190.0, -300.0),
			"camera_end": Vector3(-225.0, 195.0, -280.0),
			"fov": 48.0
		},
		{
			"name": "Full integrated source footprint",
			"mode": "topdown",
			"duration": 5.0,
			"focus": Vector2(0.0, 0.0),
			"focus_end": Vector2(0.0, 0.0),
			"camera": Vector3(0.0, 900.0, 0.01),
			"camera_end": Vector3(0.0, 900.0, 0.01),
			"size": footprint_topdown_size
		}
	]


func _review_source_size_m() -> Vector2:
	var f: FileAccess = FileAccess.open(meta_path, FileAccess.READ)
	if f == null:
		return Vector2(619.0, 1075.0)
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		return Vector2(619.0, 1075.0)
	var meta: Dictionary = parsed
	var world_size: float = float(meta.get("world_size_m", 1024.0))
	return Vector2(
		float(meta.get("world_size_x_m", world_size)),
		float(meta.get("world_size_z_m", world_size))
	)


func _build_full_map_fast_tour() -> void:
	_tour = [
		{
			"name": "Full map topdown sweep",
			"mode": "topdown",
			"duration": 4.5,
			"focus": Vector2(0.0, -360.0),
			"focus_end": Vector2(0.0, 360.0),
			"camera": Vector3(0.0, 900.0, 0.01),
			"camera_end": Vector3(0.0, 900.0, 0.01),
			"size": 348.0
		},
		{
			"name": "Full map iso diagonal",
			"mode": "ortho",
			"duration": 5.0,
			"focus": Vector2(-260.0, -460.0),
			"focus_end": Vector2(260.0, 460.0),
			"camera": Vector3(-410.0, 520.0, -470.0),
			"camera_end": Vector3(-390.0, 520.0, -450.0),
			"size": 520.0
		},
		{
			"name": "3D long northbound flyover",
			"mode": "perspective",
			"duration": 5.0,
			"focus": Vector2(-240.0, -460.0),
			"focus_end": Vector2(220.0, 470.0),
			"camera": Vector3(-260.0, 210.0, -320.0),
			"camera_end": Vector3(-220.0, 230.0, -300.0),
			"fov": 46.0
		},
		{
			"name": "3D reverse cross-map sweep",
			"mode": "perspective",
			"duration": 5.0,
			"focus": Vector2(260.0, -420.0),
			"focus_end": Vector2(-260.0, 420.0),
			"camera": Vector3(300.0, 230.0, -360.0),
			"camera_end": Vector3(260.0, 240.0, -330.0),
			"fov": 48.0
		},
		{
			"name": "Full source overview",
			"mode": "topdown",
			"duration": 4.0,
			"focus": Vector2(0.0, -320.0),
			"focus_end": Vector2(0.0, 320.0),
			"camera": Vector3(0.0, 900.0, 0.01),
			"camera_end": Vector3(0.0, 900.0, 0.01),
			"size": 348.0
		},
		{
			"name": "Low-altitude center traverse",
			"mode": "perspective",
			"duration": 4.5,
			"focus": Vector2(-290.0, -120.0),
			"focus_end": Vector2(290.0, 160.0),
			"camera": Vector3(-150.0, 120.0, -210.0),
			"camera_end": Vector3(-130.0, 130.0, -190.0),
			"fov": 50.0
		}
	]
	if show_footprint_debug_views:
		_tour.append(
			{
				"name": "Diagnostic finite-footprint view",
				"mode": "ortho",
				"duration": 5.0,
				"focus": Vector2(0.0, 0.0),
				"focus_end": Vector2(0.0, 0.0),
				"camera": Vector3(-480.0, 900.0, -520.0),
				"camera_end": Vector3(-480.0, 900.0, -520.0),
				"size": 1500.0
			}
		)


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
	mat.set_shader_parameter("use_source_macro_valid_mask", review_use_source_macro_valid_mask)
	mat.set_shader_parameter("normal_strength", review_normal_strength)
	mat.set_shader_parameter("detail_normal_strength", review_detail_normal_strength)
	mat.set_shader_parameter("detail_rough_strength", review_detail_rough_strength)
	_apply_source_macro_overrides(mat)

	_loader = ChunkLoader.new()
	_loader.name = "ChunkLoader"
	_loader.auto_update = true
	_loader.heightmap_path = heightmap_path
	_loader.meta_path = meta_path
	_loader.source_valid_mask_path = source_valid_mask_path
	_loader.terrain_material = mat
	_loader.chunk_size_m = chunk_size_m
	_loader.chunk_resolution_m = chunk_resolution_m
	_loader.view_radius_chunks = view_radius_chunks
	_loader.source_repeat_mode = source_repeat_mode
	_loader.source_repeat_blend_width_m = source_repeat_blend_width_m
	_loader.source_repeat_blend_macro_color = source_repeat_blend_macro_color
	_loader.source_repeat_blend_macro_fade = source_repeat_blend_macro_fade
	_loader.clip_to_source_bounds = clip_to_source_bounds
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


func _apply_source_macro_overrides(mat: ShaderMaterial) -> void:
	if source_macro_albedo_override_path != "":
		var albedo_tex: Texture2D = RuntimeImageCache.load_texture("", source_macro_albedo_override_path)
		if albedo_tex != null:
			mat.set_shader_parameter("source_macro_albedo", albedo_tex)
			mat.set_shader_parameter("use_source_macro_albedo", true)
		else:
			push_warning("World3AutoReviewTour failed to load source macro override: " + source_macro_albedo_override_path)
	if source_macro_valid_mask_override_path != "":
		var mask_tex: Texture2D = RuntimeImageCache.load_texture("", source_macro_valid_mask_override_path)
		if mask_tex != null:
			mat.set_shader_parameter("source_macro_valid_mask", mask_tex)
		else:
			push_warning("World3AutoReviewTour failed to load source macro valid-mask override: " + source_macro_valid_mask_override_path)


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
	var view_text: String = "close/medium 3D, iso, topdown, controlled overview, near sweep"
	if tour_profile == "full_map_fast":
		view_text = "fast full-map topdown, iso, long 3D traverses, overview"
	if tour_profile == "same_source_blend":
		view_text = "same-source 2x2 seam blend: X, Z, corner, 3D traverses"
	if tour_profile == "seam_integration":
		workflow_text = "M10 terrain seam-integration proof"
		view_text = "integration-band topdown, iso, close 3D, medium 3D, footprint"
	_overlay_label.text = (
		"world3 Source-Stack Auto Review | " + workflow_text + "\n"
		+ "%d/%d  %s  |  %s  |  progress %02d%%\n"
		+ "Views: " + view_text + "\n"
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
