extends Node3D

@export var opentopo_index_path: String = "res://opentopo/processed/textures/Guadalupe_Cypress_finished_materials_index.json"
@export var tile_size_m: float = 44.0
@export var repeat_per_tile: float = 1.25
@export var row_gap_m: float = 26.0
@export var section_gap_m: float = 52.0
@export var initial_camera_preset: String = "overview"
@export var show_hud: bool = true
@export_node_path("Camera3D") var camera_path: NodePath
@export_node_path("Label") var label_path: NodePath

var _root: Node3D
var _regular_rows: Array = [
	{
		"title": "Base / alpine regular",
		"items": ["snow", "grass", "dirt", "rock_light", "rock_dark"]
	},
	{
		"title": "Desert regular",
		"items": ["desert_sand", "desert_salt_pan", "desert_dry_brush", "desert_canyon_rock", "desert_dark_rock"]
	},
	{
		"title": "Grassland regular",
		"items": ["grassland_grass", "grassland_dirt", "grassland_rock_light", "grassland_rock_dark", "grassland_snow"]
	},
	{
		"title": "Temperate forest regular",
		"items": ["temperate_forest_grass", "temperate_forest_dirt", "temperate_forest_rock_light", "temperate_forest_rock_dark", "temperate_forest_snow"]
	},
	{
		"title": "Tundra regular",
		"items": ["tundra_moss", "tundra_lichen", "tundra_frost_rock", "tundra_dark_rock", "tundra_ice"]
	}
]
var _cross_biome_chain: Array = [
	"tundra_ice",
	"tundra_moss",
	"snow",
	"grassland_grass",
	"temperate_forest_grass",
	"forest_floor",
	"desert_sand",
	"desert_canyon_rock"
]


func _ready() -> void:
	_root = Node3D.new()
	_root.name = "TransitionPanels"
	add_child(_root)
	_build_scene()
	await get_tree().process_frame
	_reset_camera(initial_camera_preset)


func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	if event.keycode == KEY_R or event.keycode == KEY_1:
		_reset_camera("overview")
	elif event.keycode == KEY_2:
		_reset_camera("opentopo")
	elif event.keycode == KEY_3:
		_reset_camera("regular")
	elif event.keycode == KEY_H:
		var label: Label = get_node_or_null(label_path) as Label
		if label != null:
			label.visible = not label.visible


func _build_scene() -> void:
	for child in _root.get_children():
		child.queue_free()

	var current_z := 72.0
	var opentopo_products: Array = _load_opentopo_products()
	if not opentopo_products.is_empty():
		_add_section_title("OpenTopo photoreal real-source materials", current_z - tile_size_m * 0.88, 6)
		_add_material_row(
			opentopo_products.map(func(product): return String(product.get("material_class", ""))),
			opentopo_products.map(func(product): return _make_plain_material(product.get("outputs", {}), repeat_per_tile)),
			current_z
		)
		current_z += tile_size_m + section_gap_m

	_add_section_title("Regular generated biome kits", current_z - tile_size_m * 0.88, 5)
	for row in _regular_rows:
		var names: Array = row.get("items", [])
		var mats: Array = []
		for name in names:
			mats.append(_make_regular_material(String(name)))
		_add_row_title(String(row.get("title", "")), current_z, names.size())
		_add_material_row(names, mats, current_z)
		current_z += tile_size_m + row_gap_m

	current_z += section_gap_m * 0.3
	_add_section_title("Cross-biome hard-transition chain", current_z - tile_size_m * 0.88, _cross_biome_chain.size())
	var chain_mats: Array = []
	for name in _cross_biome_chain:
		chain_mats.append(_make_regular_material(String(name)))
	_add_material_row(_cross_biome_chain, chain_mats, current_z)

	_add_ground_shadow(current_z + tile_size_m * 0.85)
	_update_label(opentopo_products.size())


func _load_opentopo_products() -> Array:
	var data: Dictionary = _read_json(opentopo_index_path)
	var products: Array = []
	for item in data.get("products", []):
		if typeof(item) == TYPE_DICTIONARY:
			products.append(item)
	return products


func _add_material_row(names: Array, mats: Array, z: float) -> void:
	var count: int = names.size()
	var start_x: float = -float(count) * tile_size_m * 0.5 + tile_size_m * 0.5
	for idx in range(count):
		var pos := Vector3(start_x + float(idx) * tile_size_m, 0.0, z)
		_add_tile(pos, tile_size_m, mats[idx])
		_add_tile_label(pos, String(names[idx]))


func _add_tile(pos: Vector3, size: float, mat: Material) -> void:
	var mesh_instance := MeshInstance3D.new()
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(size, size)
	mesh.subdivide_width = 18
	mesh.subdivide_depth = 18
	mesh_instance.mesh = mesh
	mesh_instance.position = pos
	mesh_instance.material_override = mat
	_root.add_child(mesh_instance)


func _add_tile_label(pos: Vector3, text: String) -> void:
	var label := Label3D.new()
	label.text = text.replace("_", "\n")
	label.font_size = 20
	label.pixel_size = 0.14
	label.outline_size = 5
	label.modulate = Color(1, 1, 1, 0.92)
	label.outline_modulate = Color(0, 0, 0, 0.9)
	label.no_depth_test = true
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = pos + Vector3(0.0, 2.2, -tile_size_m * 0.36)
	_root.add_child(label)


func _add_section_title(text: String, z: float, columns: int) -> void:
	var label := Label3D.new()
	label.text = text
	label.font_size = 34
	label.pixel_size = 0.055
	label.outline_size = 8
	label.modulate = Color.WHITE
	label.outline_modulate = Color(0, 0, 0, 0.9)
	label.no_depth_test = true
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = Vector3(-float(columns) * tile_size_m * 0.5, 5.0, z)
	_root.add_child(label)


func _add_row_title(text: String, z: float, columns: int) -> void:
	var label := Label3D.new()
	label.text = text
	label.font_size = 22
	label.pixel_size = 0.085
	label.outline_size = 6
	label.modulate = Color(0.92, 0.96, 1.0, 0.95)
	label.outline_modulate = Color(0, 0, 0, 0.9)
	label.no_depth_test = true
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = Vector3(-float(columns) * tile_size_m * 0.5 - 50.0, 3.2, z)
	_root.add_child(label)


func _add_ground_shadow(max_z: float) -> void:
	var mesh_instance := MeshInstance3D.new()
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(460.0, max_z + tile_size_m * 1.6)
	mesh_instance.mesh = mesh
	mesh_instance.position = Vector3(0.0, -0.18, max_z * 0.5 - tile_size_m * 0.4)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.16, 0.18, 0.18, 1.0)
	mat.roughness = 1.0
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mesh_instance.material_override = mat
	_root.add_child(mesh_instance)
	mesh_instance.move_to_front()


func _make_regular_material(folder_name: String) -> Material:
	var base := "res://textures/wgv3/%s/" % folder_name
	return _make_plain_material({
		"albedo": base + "albedo.png",
		"normal": base + "normal.png",
		"roughness": base + "roughness.png"
	}, repeat_per_tile)


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
		mat.normal_scale = 0.18
	var rough_tex: Texture2D = _load_texture(String(outputs.get("roughness", "")))
	if rough_tex != null:
		mat.roughness_texture = rough_tex
	return mat


func _reset_camera(preset: String) -> void:
	var cam: Camera3D = get_node_or_null(camera_path) as Camera3D
	if cam == null:
		return
	cam.near = 0.05
	cam.far = 4000.0
	if preset == "opentopo":
		cam.projection = Camera3D.PROJECTION_PERSPECTIVE
		cam.fov = 43.0
		cam.global_position = Vector3(0.0, 150.0, -110.0)
		cam.look_at(Vector3(0.0, 0.0, 0.0), Vector3.UP)
	elif preset == "regular":
		cam.projection = Camera3D.PROJECTION_PERSPECTIVE
		cam.fov = 43.0
		cam.global_position = Vector3(0.0, 250.0, 255.0)
		cam.look_at(Vector3(0.0, 0.0, 230.0), Vector3.UP)
	else:
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = 690.0
		cam.global_position = Vector3(0.0, 900.0, 335.0)
		cam.rotation_degrees = Vector3(-90.0, 0.0, 0.0)
	if cam.has_method("sync_from_transform"):
		cam.call("sync_from_transform")
	if cam.get_script() != null:
		cam.set("move_speed", 105.0)
		cam.set("fast_mult", 8.0)


func _update_label(opentopo_count: int) -> void:
	var label: Label = get_node_or_null(label_path) as Label
	if label == null:
		return
	if not show_hud:
		label.visible = false
		return
	label.text = "Biome Tile Transition Review\nOpenTopo photoreal: %d real-source material classes | Regular: %d biome-kit rows | Cross-biome chain: %d tiles\nHard adjacency test: no blending, no gaps. Use this to find visible biome-to-biome seams before adding transition masks.\nRMB+mouse look, WASD move, Space/Ctrl up/down, Shift fast | 1 overview | 2 OpenTopo | 3 regular | R reset | H UI" % [
		opentopo_count,
		_regular_rows.size(),
		_cross_biome_chain.size()
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
