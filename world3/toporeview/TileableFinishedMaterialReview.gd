extends Node3D

@export var index_path: String = "res://opentopo/processed/textures/Guadalupe_Cypress_finished_materials_index.json"
@export var focus_class: String = "dry_wash"
@export var repeat_count: float = 3.0
@export var tile_size_m: float = 64.0
@export var gap_m: float = 28.0
@export var camera_preset: String = "overview"
@export_node_path("Camera3D") var camera_path: NodePath
@export_node_path("Label") var label_path: NodePath

var _products: Array[Dictionary] = []
var _focus_index: int = 0
var _root: Node3D


func _ready() -> void:
	_load_index()
	_root = Node3D.new()
	_root.name = "Panels"
	add_child(_root)
	_focus_index = _index_for_class(focus_class)
	_rebuild()
	await get_tree().process_frame
	_reset_camera()


func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	if event.keycode == KEY_BRACKETLEFT:
		_focus_index = posmod(_focus_index - 1, max(1, _products.size()))
		_rebuild()
	elif event.keycode == KEY_BRACKETRIGHT:
		_focus_index = posmod(_focus_index + 1, max(1, _products.size()))
		_rebuild()
	elif event.keycode == KEY_R:
		_reset_camera()


func _load_index() -> void:
	_products.clear()
	var data: Dictionary = _read_json(index_path)
	for item in data.get("products", []):
		if typeof(item) == TYPE_DICTIONARY:
			_products.append(item)


func _index_for_class(name: String) -> int:
	for idx in range(_products.size()):
		if String(_products[idx].get("material_class", "")) == name:
			return idx
	return 0


func _rebuild() -> void:
	for child in _root.get_children():
		child.queue_free()
	if _products.is_empty():
		_update_label()
		return

	var product: Dictionary = _products[_focus_index]
	var plane_size: float = tile_size_m * repeat_count
	var labels := ["source soft repeat", "balanced repeat", "finished hex/detail"]
	for col in range(labels.size()):
		var x: float = (float(col) - 1.0) * (plane_size + gap_m)
		var mat: Material
		if col == 0:
			mat = _make_plain_material(product.get("source_tileable_soft", {}), repeat_count)
		elif col == 1:
			mat = _make_plain_material(product.get("outputs", {}), repeat_count)
		else:
			mat = _make_finished_material(product)
		_add_plane(Vector3(x, 0.0, 0.0), plane_size, labels[col], mat)
	_update_label()


func _add_plane(pos: Vector3, size: float, panel_label: String, mat: Material) -> void:
	var mesh_instance := MeshInstance3D.new()
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(size, size)
	mesh.subdivide_width = 48
	mesh.subdivide_depth = 48
	mesh_instance.mesh = mesh
	mesh_instance.position = pos
	mesh_instance.material_override = mat
	_root.add_child(mesh_instance)

	var label := Label3D.new()
	label.text = panel_label
	label.font_size = 44
	label.outline_size = 9
	label.modulate = Color.WHITE
	label.outline_modulate = Color(0, 0, 0, 0.85)
	label.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
	label.no_depth_test = true
	label.position = pos + Vector3(0.0, 4.0, -size * 0.57)
	_root.add_child(label)


func _make_plain_material(outputs: Dictionary, uv_repeat: float) -> Material:
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = _load_texture(String(outputs.get("albedo", "")))
	mat.roughness = 0.88
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.texture_repeat = 1
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	mat.uv1_scale = Vector3(uv_repeat, uv_repeat, 1.0)
	var normal_tex: Texture2D = _load_texture(String(outputs.get("normal", "")))
	if normal_tex != null:
		mat.normal_enabled = true
		mat.normal_texture = normal_tex
		mat.normal_scale = 0.22
	var rough_tex: Texture2D = _load_texture(String(outputs.get("roughness", "")))
	if rough_tex != null:
		mat.roughness_texture = rough_tex
	return mat


func _make_finished_material(product: Dictionary) -> Material:
	var outputs: Dictionary = product.get("outputs", {})
	var settings: Dictionary = product.get("settings", {})
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/terrain_hex_detail.gdshader") as Shader
	mat.set_shader_parameter("albedo_tex", _load_texture(String(outputs.get("albedo", ""))))
	mat.set_shader_parameter("normal_tex", _load_texture(String(outputs.get("normal", ""))))
	mat.set_shader_parameter("rough_tex", _load_texture(String(outputs.get("roughness", ""))))
	mat.set_shader_parameter("ao_tex", _load_texture(String(outputs.get("ao", ""))))
	mat.set_shader_parameter("detail_albedo_tex", _load_texture(String(outputs.get("detail_albedo", ""))))
	mat.set_shader_parameter("detail_normal_tex", _load_texture(String(outputs.get("detail_normal", ""))))
	mat.set_shader_parameter("detail_rough_tex", _load_texture(String(outputs.get("detail_roughness", ""))))
	for key in settings.keys():
		mat.set_shader_parameter(String(key), settings[key])
	return mat


func _reset_camera() -> void:
	var cam: Camera3D = get_node_or_null(camera_path) as Camera3D
	if cam == null:
		return
	var plane_size: float = tile_size_m * repeat_count
	var width: float = plane_size * 3.0 + gap_m * 2.0
	cam.near = 0.05
	cam.far = 4000.0
	cam.projection = Camera3D.PROJECTION_PERSPECTIVE	
	if camera_preset == "close_finished":
		var right_center := Vector3(plane_size + gap_m, 0.0, 0.0)
		cam.fov = 44.0
		cam.global_position = right_center + Vector3(42.0, 88.0, 118.0)
		cam.look_at(right_center + Vector3(0.0, 0.0, -8.0), Vector3.UP)
	else:
		cam.fov = 44.0
		cam.global_position = Vector3(width * 0.02, max(560.0, width * 0.86), plane_size * 1.05)
		cam.look_at(Vector3(0.0, 0.0, 0.0), Vector3.UP)
	if cam.has_method("sync_from_transform"):
		cam.call("sync_from_transform")
	if cam.get_script() != null:
		cam.set("move_speed", 85.0)
		cam.set("fast_mult", 8.0)


func _update_label() -> void:
	var label: Label = get_node_or_null(label_path) as Label
	if label == null:
		return
	if _products.is_empty():
		label.text = "OpenTopo Finished Material Review\nNo products loaded"
		return
	var product: Dictionary = _products[_focus_index]
	var cls: String = String(product.get("material_class", ""))
	var metrics: Dictionary = product.get("edge_metrics", {}).get("balanced_albedo", {})
	label.text = "OpenTopo Finished Material Review - %s (%d/%d)\n%.0f m tile period | %.1fx visible repeat | balanced edge MSE %.6f\nLeft source soft | Middle balanced | Right finished hex/detail | [/] class, R reset" % [
		cls,
		_focus_index + 1,
		_products.size(),
		tile_size_m,
		repeat_count,
		float(metrics.get("edge_mse_mean", 0.0))
	]


func _load_texture(raw_path: String) -> Texture2D:
	if raw_path == "":
		return null
	var path: String = raw_path.replace("\\", "/")
	if path.begins_with("D:/assets/world3/"):
		path = "res://" + path.trim_prefix("D:/assets/world3/")
	var img: Image = Image.load_from_file(path)
	if img == null:
		return load(path) as Texture2D
	return ImageTexture.create_from_image(img)


func _read_json(path: String) -> Dictionary:
	var f: FileAccess = FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("Could not open " + path)
		return {}
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}
