extends Node3D
class_name TransitionStripReview

@export var transition_index_path: String = "res://textures/transitions/index.json"
@export var catalog_path: String = "res://materials/catalog.json"
@export var tile_size_m: float = 42.0
@export var row_gap_m: float = 34.0
@export var group_gap_m: float = 50.0
@export var initial_camera_preset: String = "overview"
@export var show_hud: bool = true
@export_node_path("Camera3D") var camera_path: NodePath
@export_node_path("Label") var label_path: NodePath

var _root: Node3D
var _materials: Dictionary = {}
var _row_count: int = 0
var _total_width: float = 1.0
var _total_depth: float = 1.0


func _ready() -> void:
	_root = Node3D.new()
	_root.name = "TransitionRows"
	add_child(_root)
	_materials = _load_catalog_materials()
	_build_scene()
	await get_tree().process_frame
	_reset_camera(initial_camera_preset)


func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	if event.keycode == KEY_R or event.keycode == KEY_1:
		_reset_camera("overview")
	elif event.keycode == KEY_2:
		_reset_camera("close")
	elif event.keycode == KEY_H:
		var label: Label = get_node_or_null(label_path) as Label
		if label != null:
			label.visible = not label.visible


func _build_scene() -> void:
	for child in _root.get_children():
		child.queue_free()

	var index: Dictionary = _read_json(transition_index_path)
	var pairs: Array = index.get("pairs", [])
	_row_count = pairs.size()

	var current_z: float = tile_size_m * 1.35
	for item in pairs:
		if typeof(item) == TYPE_DICTIONARY:
			_add_pair_row(item, current_z)
			current_z += tile_size_m + row_gap_m

	_total_depth = max(current_z - row_gap_m + tile_size_m * 0.35, tile_size_m)
	_add_ground()
	_update_label()


func _add_pair_row(pair: Dictionary, z: float) -> void:
	var pair_ids: Array = pair.get("pair", [])
	if pair_ids.size() < 2:
		return

	var a_id := String(pair_ids[0])
	var b_id := String(pair_ids[1])
	var tiles_wide := int(pair.get("tiles_wide", 6))
	var strip_width := tile_size_m * float(tiles_wide)
	var hard_width := tile_size_m * 2.0
	_total_width = max(_total_width, hard_width + group_gap_m + strip_width)

	var start_x := -_total_width * 0.5
	var a_x := start_x + tile_size_m * 0.5
	var b_x := start_x + tile_size_m * 1.5
	var strip_x := start_x + hard_width + group_gap_m + strip_width * 0.5

	_add_tile(Vector3(a_x, 0.0, z), Vector2(tile_size_m, tile_size_m), _make_catalog_material(a_id, 1.0), 10)
	_add_tile(Vector3(b_x, 0.0, z), Vector2(tile_size_m, tile_size_m), _make_catalog_material(b_id, 1.0), 10)
	_add_tile(Vector3(strip_x, 0.01, z), Vector2(strip_width, tile_size_m), _make_plain_material(pair.get("outputs", {}), 1.0), 18 * tiles_wide)

	_add_label(Vector3(a_x, 3.0, z - tile_size_m * 0.43), a_id.replace("_", "\n"), 17, 0.105, Color.WHITE)
	_add_label(Vector3(b_x, 3.0, z - tile_size_m * 0.43), b_id.replace("_", "\n"), 17, 0.105, Color.WHITE)
	_add_label(Vector3(a_x + tile_size_m * 0.5, 4.6, z + tile_size_m * 0.62), "hard cut", 18, 0.095, Color(0.95, 0.82, 0.66, 1.0))
	_add_label(Vector3(strip_x, 4.6, z + tile_size_m * 0.62), "generated transition strip", 18, 0.095, Color(0.78, 0.96, 0.82, 1.0))
	_add_label(Vector3(start_x, 6.6, z - tile_size_m * 0.70), _pair_score_label(pair, a_id, b_id), 26, 0.085, Color(0.92, 0.96, 1.0, 1.0))


func _add_tile(pos: Vector3, size: Vector2, mat: Material, subdivisions: int) -> void:
	var mesh_instance := MeshInstance3D.new()
	var mesh := PlaneMesh.new()
	mesh.size = size
	mesh.subdivide_width = maxi(1, subdivisions)
	mesh.subdivide_depth = 10
	mesh_instance.mesh = mesh
	mesh_instance.position = pos
	mesh_instance.material_override = mat
	_root.add_child(mesh_instance)


func _add_label(pos: Vector3, text: String, font_size: int, pixel_size: float, color: Color) -> void:
	var label := Label3D.new()
	label.text = text
	label.font_size = font_size
	label.pixel_size = pixel_size
	label.outline_size = 6
	label.modulate = color
	label.outline_modulate = Color(0.0, 0.0, 0.0, 0.92)
	label.no_depth_test = true
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = pos
	_root.add_child(label)


func _add_ground() -> void:
	var mesh_instance := MeshInstance3D.new()
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(_total_width + tile_size_m * 1.6, _total_depth + tile_size_m * 1.9)
	mesh_instance.mesh = mesh
	mesh_instance.position = Vector3(0.0, -0.18, _total_depth * 0.5 - tile_size_m * 0.18)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.15, 0.17, 0.16, 1.0)
	mat.roughness = 1.0
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mesh_instance.material_override = mat
	_root.add_child(mesh_instance)


func _make_catalog_material(material_id: String, uv_repeat: float) -> Material:
	var entry: Dictionary = _materials.get(material_id, {})
	var pbr: Dictionary = entry.get("pbr_maps", {})
	return _make_plain_material(pbr, uv_repeat)


func _make_plain_material(outputs: Dictionary, uv_repeat: float) -> Material:
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = _load_texture(String(outputs.get("albedo", "")))
	mat.roughness = 0.86
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.texture_repeat = 1
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	mat.uv1_scale = Vector3(uv_repeat, uv_repeat, 1.0)

	var normal_tex: Texture2D = _load_texture(String(outputs.get("normal", "")))
	if normal_tex != null:
		mat.normal_enabled = true
		mat.normal_texture = normal_tex
		mat.normal_scale = 0.16

	var rough_tex: Texture2D = _load_texture(String(outputs.get("roughness", "")))
	if rough_tex != null:
		mat.roughness_texture = rough_tex
	return mat


func _pair_score_label(pair: Dictionary, a_id: String, b_id: String) -> String:
	var scores: Dictionary = pair.get("scores", {})
	var hints: Array = pair.get("review_hints", [])
	if scores.is_empty():
		return "%s -> %s\nscore pending" % [a_id, b_id]
	var improve_pct := float(scores.get("edge_delta_improvement_ratio", 0.0)) * 100.0
	return "%s -> %s\nedge %.3f | strip %.3f | improve %.0f%% | hints %d" % [
		a_id,
		b_id,
		float(scores.get("hard_edge_mean_abs_albedo_delta", 0.0)),
		float(scores.get("transition_center_albedo_delta", 0.0)),
		improve_pct,
		hints.size()
	]


func _reset_camera(preset: String) -> void:
	var cam: Camera3D = get_node_or_null(camera_path) as Camera3D
	if cam == null:
		return
	cam.near = 0.05
	cam.far = 5000.0
	if preset == "close":
		cam.projection = Camera3D.PROJECTION_PERSPECTIVE
		cam.fov = 43.0
		cam.global_position = Vector3(0.0, 165.0, max(-150.0, _total_depth * 0.35))
		cam.look_at(Vector3(0.0, 0.0, _total_depth * 0.42), Vector3.UP)
	else:
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = max(_total_depth + tile_size_m * 1.8, _total_width * 0.56)
		cam.global_position = Vector3(0.0, 850.0, _total_depth * 0.5)
		cam.rotation_degrees = Vector3(-90.0, 0.0, 0.0)
	if cam.has_method("sync_from_transform"):
		cam.call("sync_from_transform")
	if cam.get_script() != null:
		cam.set("move_speed", 95.0)
		cam.set("fast_mult", 8.0)


func _update_label() -> void:
	var label: Label = get_node_or_null(label_path) as Label
	if label == null:
		return
	if not show_hud:
		label.visible = false
		return
	label.text = "M2 Transition Strip Review\n%d catalog-driven pairs | hard cut beside generated strip | scores from transition manifest\nRMB+mouse look, WASD move, Space/Ctrl up/down, Shift fast | 1 overview | 2 close | R reset | H UI" % _row_count


func _load_catalog_materials() -> Dictionary:
	var data: Dictionary = _read_json(catalog_path)
	var out: Dictionary = {}
	for item in data.get("materials", []):
		if typeof(item) == TYPE_DICTIONARY and item.has("id"):
			out[String(item["id"])] = item
	return out


func _load_texture(raw_path: String) -> Texture2D:
	if raw_path == "":
		return null
	var path := _to_res_path(raw_path)
	if ResourceLoader.exists(path):
		var loaded := load(path) as Texture2D
		if loaded != null:
			return loaded
	var image_path := ProjectSettings.globalize_path(path) if path.begins_with("res://") else path
	var img: Image = Image.load_from_file(image_path)
	if img != null:
		return ImageTexture.create_from_image(img)
	return null


func _to_res_path(raw_path: String) -> String:
	var path := raw_path.replace("\\", "/")
	if path.begins_with("D:/assets/world3/"):
		return "res://" + path.trim_prefix("D:/assets/world3/")
	if path.begins_with("world3/"):
		return "res://" + path.trim_prefix("world3/")
	return path


func _read_json(path: String) -> Dictionary:
	var f: FileAccess = FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("TransitionStripReview could not open " + path)
		return {}
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}
