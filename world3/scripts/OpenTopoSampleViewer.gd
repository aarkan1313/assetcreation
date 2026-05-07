extends Node

@export_node_path("MeshInstance3D") var terrain_path: NodePath
@export_node_path("Camera3D") var camera_path: NodePath
@export_node_path("Label") var label_path: NodePath
@export var samples_root: String = "res://opentopo/processed/heightmaps"
@export var start_site: String = "guadalupe_cypress_dtm_2016"

var _samples: Array[Dictionary] = []
var _index: int = 0
var _layer_index: int = 0
var _fallback_material: Material

const LAYER_ORDER: Array[String] = [
	"orthophoto_rgb",
	"orthophoto_nir_false",
	"pointcloud_rgb_topdown",
	"pointcloud_nir_source_topdown",
	"canopy_height_mosaic",
	"chm_vegetation_mosaic",
	"canopy_height_mask",
	"canopy_height_mask_nir_source",
	"chm_vegetation_mask",
	"chm_vegetation_mask_nir_source",
]


func _ready() -> void:
	var terrain := get_node_or_null(terrain_path) as Terrain
	if terrain != null:
		_fallback_material = terrain.material_override
	_samples = _scan_samples(samples_root)
	if _samples.is_empty():
		push_warning("OpenTopoSampleViewer: no processed samples found")
		return
	for i in range(_samples.size()):
		if String(_samples[i].get("site", "")) == start_site:
			_index = i
			break
	_load_current()


func _unhandled_input(event: InputEvent) -> void:
	if _samples.is_empty() or not event is InputEventKey or not event.pressed or event.echo:
		return
	if event.keycode == KEY_RIGHT or event.keycode == KEY_N:
		_index = (_index + 1) % _samples.size()
		_layer_index = 0
		_load_current()
	elif event.keycode == KEY_LEFT or event.keycode == KEY_P:
		_index = (_index - 1 + _samples.size()) % _samples.size()
		_layer_index = 0
		_load_current()
	elif event.keycode == KEY_L:
		_cycle_layer(1)


func _load_current() -> void:
	var terrain := get_node_or_null(terrain_path) as Terrain
	if terrain == null:
		push_warning("OpenTopoSampleViewer: missing Terrain node")
		return
	var sample := _samples[_index]
	terrain.load_dataset(sample["heightmap"], sample["meta_path"])
	await get_tree().process_frame
	await get_tree().process_frame
	_apply_layer_material(terrain, sample)
	_frame_camera(terrain)
	_update_label(sample)


func _scan_samples(root: String) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var root_path := ProjectSettings.globalize_path(root)
	_scan_dir(root_path, found)
	found.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return String(a.get("sort_key", "")) < String(b.get("sort_key", ""))
	)
	return found


func _scan_dir(abs_dir: String, found: Array[Dictionary]) -> void:
	var dir := DirAccess.open(abs_dir)
	if dir == null:
		return
	dir.list_dir_begin()
	while true:
		var name := dir.get_next()
		if name == "":
			break
		if name.begins_with("."):
			continue
		var child := abs_dir.path_join(name)
		if dir.current_is_dir():
			_scan_dir(child, found)
		elif name == "meta.json":
			var meta_res := ProjectSettings.localize_path(child)
			var h_res := ProjectSettings.localize_path(abs_dir.path_join("heightmap.png"))
			var meta := _read_json(meta_res)
			if not meta.is_empty() and FileAccess.file_exists(h_res):
				var parts := meta_res.trim_prefix("res://opentopo/processed/heightmaps/").split("/")
				var site := parts[0] if parts.size() > 0 else "unknown"
				var source := parts[1] if parts.size() > 1 else "unknown"
				found.append({
					"site": site,
					"source": source,
					"heightmap": h_res,
					"meta_path": meta_res,
					"meta": meta,
					"layers": _scan_layers(abs_dir.path_join("layers")),
					"sort_key": site + "/" + source,
				})
	dir.list_dir_end()


func _scan_layers(abs_dir: String) -> Dictionary:
	var layers := {}
	var dir := DirAccess.open(abs_dir)
	if dir == null:
		return layers
	dir.list_dir_begin()
	while true:
		var name := dir.get_next()
		if name == "":
			break
		if dir.current_is_dir() or not name.ends_with(".png"):
			continue
		var key := name.trim_suffix(".png")
		layers[key] = ProjectSettings.localize_path(abs_dir.path_join(name))
	dir.list_dir_end()
	return layers


func _read_json(path: String) -> Dictionary:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return {}
	var txt := f.get_as_text()
	f.close()
	var parsed = JSON.parse_string(txt)
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}


func _frame_camera(terrain: MeshInstance3D) -> void:
	var cam := get_node_or_null(camera_path) as Camera3D
	if cam == null:
		return
	var aabb: AABB = terrain.get_aabb()
	var center := aabb.position + aabb.size * 0.5
	var dir := Vector3(1, 1, 1).normalized()
	cam.transform.origin = center + dir * aabb.size.length() * 1.5
	cam.look_at(center, Vector3.UP)
	var basis_inv := cam.transform.basis.inverse()
	var min_u := INF
	var max_u := -INF
	var min_v := INF
	var max_v := -INF
	for c in [
		aabb.position,
		aabb.position + Vector3(aabb.size.x, 0, 0),
		aabb.position + Vector3(0, aabb.size.y, 0),
		aabb.position + Vector3(0, 0, aabb.size.z),
		aabb.position + Vector3(aabb.size.x, aabb.size.y, 0),
		aabb.position + Vector3(aabb.size.x, 0, aabb.size.z),
		aabb.position + Vector3(0, aabb.size.y, aabb.size.z),
		aabb.position + aabb.size,
	]:
		var local: Vector3 = basis_inv * (c - cam.transform.origin)
		min_u = min(min_u, local.x)
		max_u = max(max_u, local.x)
		min_v = min(min_v, local.y)
		max_v = max(max_v, local.y)
	var aspect := 16.0 / 9.0
	cam.size = max((max_v - min_v) * 1.15, ((max_u - min_u) * 1.15) / aspect)


func _cycle_layer(delta: int) -> void:
	if _samples.is_empty():
		return
	var sample := _samples[_index]
	var names := _available_layer_names(sample)
	if names.is_empty():
		return
	_layer_index = (_layer_index + delta + names.size()) % names.size()
	var terrain := get_node_or_null(terrain_path) as Terrain
	if terrain != null:
		_apply_layer_material(terrain, sample)
	_update_label(sample)


func _available_layer_names(sample: Dictionary) -> Array[String]:
	var layers: Dictionary = sample.get("layers", {})
	var names: Array[String] = []
	for key in LAYER_ORDER:
		if layers.has(key):
			names.append(key)
	var extras: Array[String] = []
	for key in layers.keys():
		if not names.has(String(key)):
			extras.append(String(key))
	extras.sort()
	names.append_array(extras)
	return names


func _apply_layer_material(terrain: MeshInstance3D, sample: Dictionary) -> void:
	var names := _available_layer_names(sample)
	if names.is_empty():
		terrain.material_override = _fallback_material
		return
	_layer_index = clampi(_layer_index, 0, names.size() - 1)
	var layers: Dictionary = sample.get("layers", {})
	var layer_name := names[_layer_index]
	var layer_path := String(layers.get(layer_name, ""))
	var tex := _load_texture(layer_path)
	if tex == null:
		terrain.material_override = _fallback_material
		return
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = tex
	mat.roughness = 0.92
	mat.uv1_triplanar = false
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	terrain.material_override = mat


func _load_texture(path: String) -> Texture2D:
	var tex := load(path) as Texture2D
	if tex != null:
		return tex
	var img := Image.load_from_file(path)
	if img == null:
		return null
	return ImageTexture.create_from_image(img)


func _update_label(sample: Dictionary) -> void:
	var label := get_node_or_null(label_path) as Label
	if label == null:
		return
	var meta: Dictionary = sample.get("meta", {})
	var names := _available_layer_names(sample)
	var layer := "terrain material"
	if not names.is_empty():
		_layer_index = clampi(_layer_index, 0, names.size() - 1)
		layer = names[_layer_index]
	label.text = "%s / %s\n%s\n%.0f-%.0f m | %.1f km | %d/%d" % [
		String(sample.get("site", "")),
		String(sample.get("source", "")),
		layer,
		float(meta.get("elevation_min_m", 0.0)),
		float(meta.get("elevation_max_m", 0.0)),
		float(meta.get("world_size_m", 0.0)) / 1000.0,
		_index + 1,
		_samples.size(),
	]
