extends Node3D

@export var review_title: String = "Topo Review"
@export var heightmap_path: String = ""
@export var meta_path: String = ""
@export var layers_dir: String = ""
@export var layer_order: PackedStringArray = []
@export var start_layer: String = ""
@export_node_path("MeshInstance3D") var terrain_path: NodePath
@export_node_path("Camera3D") var camera_path: NodePath
@export_node_path("Label") var label_path: NodePath

var _meta: Dictionary = {}
var _layers: Array[Dictionary] = []
var _layer_index: int = 0
var _camera_preset: int = 0
var _ui_visible: bool = true
var _height_scale: float = 1.0


func _ready() -> void:
	_meta = _read_json(meta_path)
	_scan_layers()
	_select_start_layer()
	var terrain := _terrain()
	if terrain != null:
		terrain.height_scale = _height_scale
		terrain.load_dataset(heightmap_path, meta_path)
	await get_tree().process_frame
	await get_tree().process_frame
	_apply_layer()
	_reset_camera()
	_update_label()


func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	match event.keycode:
		KEY_L, KEY_TAB:
			_cycle_layer(1)
		KEY_BRACKETRIGHT:
			_cycle_layer(1)
		KEY_BRACKETLEFT:
			_cycle_layer(-1)
		KEY_R:
			_reset_camera()
		KEY_1:
			_camera_preset = 0
			_reset_camera()
		KEY_2:
			_camera_preset = 1
			_reset_camera()
		KEY_3:
			_camera_preset = 2
			_reset_camera()
		KEY_H:
			_ui_visible = not _ui_visible
			var label := _label()
			if label != null:
				label.visible = _ui_visible
		KEY_Z:
			_set_height_scale(max(_height_scale * 0.5, 0.125))
		KEY_X:
			_set_height_scale(min(_height_scale * 2.0, 8.0))


func _set_height_scale(value: float) -> void:
	_height_scale = value
	var terrain := _terrain()
	if terrain != null:
		terrain.height_scale = _height_scale
		terrain.rebuild()
		await get_tree().process_frame
		_apply_layer()
		_reset_camera()
	_update_label()


func _cycle_layer(delta: int) -> void:
	if _layers.is_empty():
		return
	_layer_index = (_layer_index + delta + _layers.size()) % _layers.size()
	_apply_layer()
	_update_label()


func _scan_layers() -> void:
	_layers.clear()
	var abs_dir := ProjectSettings.globalize_path(layers_dir)
	var seen := {}
	for layer_name in layer_order:
		var path := layers_dir.path_join(String(layer_name) + ".png")
		if FileAccess.file_exists(path):
			_layers.append({"name": String(layer_name), "path": path})
			seen[String(layer_name)] = true
	var dir := DirAccess.open(abs_dir)
	if dir == null:
		return
	var extras: Array[String] = []
	dir.list_dir_begin()
	while true:
		var name := dir.get_next()
		if name == "":
			break
		if dir.current_is_dir() or not name.ends_with(".png"):
			continue
		var key := name.trim_suffix(".png")
		if not seen.has(key):
			extras.append(key)
	dir.list_dir_end()
	extras.sort()
	for key in extras:
		_layers.append({"name": key, "path": layers_dir.path_join(key + ".png")})


func _select_start_layer() -> void:
	if start_layer == "":
		return
	for i in range(_layers.size()):
		if String(_layers[i].get("name", "")) == start_layer:
			_layer_index = i
			return


func _apply_layer() -> void:
	var terrain := _terrain()
	if terrain == null or _layers.is_empty():
		return
	_layer_index = clampi(_layer_index, 0, _layers.size() - 1)
	var layer := _layers[_layer_index]
	var layer_name := String(layer.get("name", ""))
	var tex := _load_texture(String(layer.get("path", "")))
	if tex == null:
		return
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = tex
	mat.roughness = 0.9
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	if _is_qa_layer(layer_name):
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	terrain.material_override = mat


func _is_qa_layer(layer_name: String) -> bool:
	return (
		layer_name.contains("coverage")
		or layer_name.contains("seam")
		or layer_name.contains("slope")
		or layer_name.contains("roughness")
		or layer_name.contains("vegetation")
		or layer_name.contains("canopy")
		or layer_name.contains("chm")
	)


func _reset_camera() -> void:
	var terrain := _terrain()
	var cam := _camera()
	if terrain == null or cam == null:
		return
	var aabb := terrain.get_aabb()
	var center := aabb.position + aabb.size * 0.5
	var span: float = max(aabb.size.x, aabb.size.z)
	var elev_span: float = max(aabb.size.y, 1.0)
	cam.near = 1.0
	cam.far = max(span * 8.0, 10000.0)
	cam.projection = Camera3D.PROJECTION_PERSPECTIVE
	cam.fov = 48.0
	if _camera_preset == 1:
		cam.global_position = Vector3(center.x, center.y + span * 1.2 + elev_span, center.z)
		cam.look_at(center, Vector3.FORWARD)
	elif _camera_preset == 2:
		cam.global_position = center + Vector3(-span * 0.7, elev_span * 0.8 + span * 0.12, -span * 0.85)
		cam.look_at(center + Vector3(0, elev_span * 0.15, 0), Vector3.UP)
	else:
		cam.global_position = center + Vector3(span * 0.85, elev_span * 1.2 + span * 0.35, span * 0.85)
		cam.look_at(center, Vector3.UP)
	if cam.has_method("sync_from_transform"):
		cam.call("sync_from_transform")
	if cam.get_script() != null:
		cam.set("move_speed", max(span * 0.14, 80.0))
		cam.set("fast_mult", 8.0)


func _update_label() -> void:
	var label := _label()
	if label == null:
		return
	var layer_name := "none"
	if not _layers.is_empty():
		layer_name = String(_layers[_layer_index].get("name", ""))
	var elev_min := float(_meta.get("elevation_min_m", 0.0))
	var elev_max := float(_meta.get("elevation_max_m", 0.0))
	var world_km := float(_meta.get("world_size_m", 0.0)) / 1000.0
	label.text = "%s\nLayer: %s (%d/%d)\nElevation: %.1f-%.1f m | %.2f km | height x %.2f\nRMB+mouse look, WASD move, Space/Ctrl up/down, Shift fast\nL/Tab layer | 1 iso | 2 top | 3 low | R reset | Z/X height | H UI" % [
		review_title,
		layer_name,
		_layer_index + 1,
		max(_layers.size(), 1),
		elev_min,
		elev_max,
		world_km,
		_height_scale,
	]


func _terrain() -> Terrain:
	return get_node_or_null(terrain_path) as Terrain


func _camera() -> Camera3D:
	return get_node_or_null(camera_path) as Camera3D


func _label() -> Label:
	return get_node_or_null(label_path) as Label


func _load_texture(path: String) -> Texture2D:
	var tex := load(path) as Texture2D
	if tex != null:
		return tex
	var img := Image.load_from_file(path)
	if img == null:
		return null
	return ImageTexture.create_from_image(img)


func _read_json(path: String) -> Dictionary:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return {}
	var txt := f.get_as_text()
	f.close()
	var parsed = JSON.parse_string(txt)
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}
