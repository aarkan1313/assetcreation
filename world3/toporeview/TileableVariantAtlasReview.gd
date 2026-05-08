extends Node3D

@export var manifest_path: String = "res://opentopo/processed/textures/Guadalupe_Cypress_variants/manifest.json"
@export var material_class: String = "dry_wash"
@export var crop_size_m: int = 64
@export var grid_count: int = 16
@export var cell_size_m: float = 7.0
@export var grid_gap_m: float = 28.0
@export var use_hex_inside_cells: bool = true
@export var variant_output_policy: String = "tileable_real_norm"
@export var show_soft_composite: bool = true
@export var soft_repeat_count: float = 2.0
@export_node_path("Camera3D") var camera_path: NodePath
@export_node_path("Label") var label_path: NodePath

var _manifest: Dictionary = {}
var _variant_materials: Array[Material] = []
var _panel_count: int = 2


func _ready() -> void:
	_manifest = _read_json(manifest_path)
	_build_variant_materials()
	_build_grids()
	await get_tree().process_frame
	_reset_camera()
	_update_label()


func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	if event.keycode == KEY_R:
		_reset_camera()


func _build_variant_materials() -> void:
	_variant_materials.clear()
	for product in _variant_products():
		var outputs: Dictionary = product.get("outputs", {})
		var policy := variant_output_policy
		if not outputs.has(policy):
			policy = "tileable_real"
		if not outputs.has(policy):
			continue
		var info: Dictionary = outputs[policy]
		var mat: Material
		if use_hex_inside_cells:
			mat = _make_hex_material(
				String(info.get("albedo", "")),
				String(info.get("normal", "")),
				String(info.get("roughness", ""))
			)
		else:
			var std := StandardMaterial3D.new()
			std.albedo_texture = _load_texture(String(info.get("albedo", "")))
			std.roughness = 0.88
			std.cull_mode = BaseMaterial3D.CULL_DISABLED
			std.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
			std.texture_repeat = 1
			std.uv1_scale = Vector3.ONE
			mat = std
		_variant_materials.append(mat)


func _build_grids() -> void:
	if _variant_materials.is_empty():
		push_error("No variant materials found for " + material_class)
		return
	var grid_span := float(grid_count) * cell_size_m
	_panel_count = 3 if show_soft_composite and _has_soft_composite() else 2
	var total_w := float(_panel_count) * grid_span + float(_panel_count - 1) * grid_gap_m
	var first_x := -total_w * 0.5
	var left_origin := Vector3(first_x, 0.0, -grid_span * 0.5)
	var mixed_origin := Vector3(first_x + grid_span + grid_gap_m, 0.0, -grid_span * 0.5)
	_build_grid(left_origin, false)
	_build_grid(mixed_origin, true)
	_add_label(Vector3(left_origin.x + grid_span * 0.5, 2.0, left_origin.z - 8.0), "one variant repeated")
	_add_label(Vector3(mixed_origin.x + grid_span * 0.5, 2.0, mixed_origin.z - 8.0), "hard mixed variants")
	if _panel_count == 3:
		var soft_origin := Vector3(first_x + (grid_span + grid_gap_m) * 2.0, 0.0, -grid_span * 0.5)
		_add_soft_plane(soft_origin + Vector3(grid_span * 0.5, 0.0, grid_span * 0.5), grid_span)
		_add_label(Vector3(soft_origin.x + grid_span * 0.5, 2.0, soft_origin.z - 8.0), "soft seamless composite")


func _build_grid(origin: Vector3, mixed: bool) -> void:
	for y in range(grid_count):
		for x in range(grid_count):
			var idx := _variant_index(x, y) if mixed else 0
			var pos := origin + Vector3((float(x) + 0.5) * cell_size_m, 0.0, (float(y) + 0.5) * cell_size_m)
			_add_cell(pos, idx)


func _add_cell(pos: Vector3, variant_index: int) -> void:
	var mesh_instance := MeshInstance3D.new()
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(cell_size_m, cell_size_m)
	mesh.subdivide_width = 1
	mesh.subdivide_depth = 1
	mesh_instance.mesh = mesh
	mesh_instance.position = pos
	mesh_instance.name = "cell_v%02d" % variant_index
	mesh_instance.material_override = _variant_materials[variant_index % _variant_materials.size()]
	add_child(mesh_instance)


func _add_soft_plane(pos: Vector3, size_m: float) -> void:
	var info := _soft_composite_info()
	if info.is_empty():
		return
	var mesh_instance := MeshInstance3D.new()
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(size_m, size_m)
	mesh.subdivide_width = 32
	mesh.subdivide_depth = 32
	mesh_instance.mesh = mesh
	mesh_instance.position = pos
	mesh_instance.name = "soft_composite_repeated"
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = _load_texture(String(info.get("albedo", "")))
	mat.roughness = 0.9
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.texture_repeat = 1
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	mat.uv1_scale = Vector3(soft_repeat_count, soft_repeat_count, 1.0)
	var normal_tex := _load_texture(String(info.get("normal", "")))
	if normal_tex != null:
		mat.normal_enabled = true
		mat.normal_texture = normal_tex
		mat.normal_scale = 0.25
	var rough_tex := _load_texture(String(info.get("roughness", "")))
	if rough_tex != null:
		mat.roughness_texture = rough_tex
	mesh_instance.material_override = mat
	add_child(mesh_instance)


func _variant_index(x: int, y: int) -> int:
	var v: float = abs(sin(float(x + 1) * 12.9898 + float(y + 1) * 78.233) * 43758.5453)
	var count: int = _variant_materials.size()
	if count < 1:
		count = 1
	return int(floor(v * 1000.0)) % count


func _variant_products() -> Array:
	var rows: Array = []
	for product in _manifest.get("products", []):
		if product.get("kind", "") != "crop":
			continue
		if String(product.get("material_class", "")) != material_class:
			continue
		if int(product.get("crop_size_m", -1)) != crop_size_m:
			continue
		rows.append(product)
	rows.sort_custom(func(a, b): return int(a.get("variant_index", 0)) < int(b.get("variant_index", 0)))
	return rows


func _has_soft_composite() -> bool:
	return not _soft_composite_info().is_empty()


func _soft_composite_info() -> Dictionary:
	var soft: Dictionary = _manifest.get("soft_composite", {})
	var outputs: Dictionary = soft.get("outputs", {})
	return outputs.get("tileable_soft", {})


func _make_hex_material(albedo_path: String, normal_path: String, roughness_path: String) -> Material:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/terrain_hex.gdshader") as Shader
	mat.set_shader_parameter("albedo_tex", _load_texture(albedo_path))
	mat.set_shader_parameter("normal_tex", _load_texture(normal_path))
	mat.set_shader_parameter("rough_tex", _load_texture(roughness_path))
	mat.set_shader_parameter("world_uv_scale", 1.0 / cell_size_m)
	mat.set_shader_parameter("hex_strength", 1.0)
	mat.set_shader_parameter("blend_sharpness", 8.0)
	mat.set_shader_parameter("roughness_strength", 0.85)
	mat.set_shader_parameter("normal_strength", 0.35)
	mat.set_shader_parameter("macro_scale", 1000.0)
	mat.set_shader_parameter("macro_value_strength", 0.0)
	mat.set_shader_parameter("macro_hue_strength", 0.0)
	return mat


func _add_label(pos: Vector3, text: String) -> void:
	var label := Label3D.new()
	label.text = text
	label.font_size = 34
	label.outline_size = 7
	label.modulate = Color.WHITE
	label.outline_modulate = Color(0, 0, 0, 0.85)
	label.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
	label.no_depth_test = true
	label.position = pos
	add_child(label)


func _reset_camera() -> void:
	var cam := get_node_or_null(camera_path) as Camera3D
	if cam == null:
		return
	var grid_span := float(grid_count) * cell_size_m
	var total_w := float(_panel_count) * grid_span + float(_panel_count - 1) * grid_gap_m
	var center := Vector3(0.0, 0.0, 0.0)
	cam.near = 0.05
	cam.far = 3000.0
	cam.projection = Camera3D.PROJECTION_PERSPECTIVE
	cam.fov = 48.0
	cam.global_position = center + Vector3(total_w * 0.42, max(110.0, grid_span * 0.9), total_w * 0.34)
	cam.look_at(center, Vector3.UP)
	if cam.has_method("sync_from_transform"):
		cam.call("sync_from_transform")
	if cam.get_script() != null:
		cam.set("move_speed", 65.0)
		cam.set("fast_mult", 8.0)


func _update_label() -> void:
	var label := get_node_or_null(label_path) as Label
	if label == null:
		return
	label.text = "OpenTopo Variant Atlas Review\n%s | %d variants | %dx%d cells | policy: %s | soft repeat %.1fx\nLeft: one variant. Middle: hard mixed variants. Right: soft seamless composite.\nRMB+mouse look, WASD move, Space/Ctrl up/down, Shift fast | R reset" % [
		material_class,
		_variant_materials.size(),
		grid_count,
		grid_count,
		variant_output_policy,
		soft_repeat_count
	]


func _load_texture(raw_path: String) -> Texture2D:
	if raw_path == "":
		return null
	var path := raw_path.replace("\\", "/")
	if path.begins_with("D:/assets/world3/"):
		path = "res://" + path.trim_prefix("D:/assets/world3/")
	var img := Image.load_from_file(path)
	if img == null:
		var tex := load(path) as Texture2D
		return tex
	return ImageTexture.create_from_image(img)


func _read_json(path: String) -> Dictionary:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("Could not open " + path)
		return {}
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}
