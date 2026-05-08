extends Node3D

@export var plane_size_m: float = 76.0
@export var repeat_count: float = 2.0
@export var gap_m: float = 24.0
@export_node_path("Camera3D") var camera_path: NodePath
@export_node_path("Label") var label_path: NodePath

var manifest_paths: Array[String] = [
	"res://opentopo/processed/textures/Guadalupe_Cypress_variants_bare_soil/manifest.json",
	"res://opentopo/processed/textures/Guadalupe_Cypress_variants_bright_rock/manifest.json",
	"res://opentopo/processed/textures/Guadalupe_Cypress_variants_dry_wash/manifest.json",
	"res://opentopo/processed/textures/Guadalupe_Cypress_variants_rocky_slope/manifest.json",
	"res://opentopo/processed/textures/Guadalupe_Cypress_variants_scrub_dense/manifest.json",
	"res://opentopo/processed/textures/Guadalupe_Cypress_variants_scrub_sparse/manifest.json",
]

var _products: Array[Dictionary] = []


func _ready() -> void:
	_load_products()
	_build_gallery()
	await get_tree().process_frame
	_reset_camera()
	_update_label()


func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	if event.keycode == KEY_R:
		_reset_camera()


func _load_products() -> void:
	_products.clear()
	for path in manifest_paths:
		var manifest: Dictionary = _read_json(path)
		var soft: Dictionary = manifest.get("soft_composite", {})
		var outputs: Dictionary = soft.get("outputs", {})
		var tileable: Dictionary = outputs.get("tileable_soft", {})
		if tileable.is_empty():
			continue
		_products.append({
			"class": String(manifest.get("material_class", "")),
			"variant_count": int(manifest.get("variant_count", 0)),
			"edge_mse": float(soft.get("edge_metrics", {}).get("edge_mse_mean", 0.0)),
			"albedo": String(tileable.get("albedo", "")),
			"normal": String(tileable.get("normal", "")),
			"roughness": String(tileable.get("roughness", "")),
		})


func _build_gallery() -> void:
	var cols: int = 3
	for idx in range(_products.size()):
		var product: Dictionary = _products[idx]
		var col: int = idx % cols
		var row: int = idx / cols
		var x: float = (float(col) - 1.0) * (plane_size_m + gap_m)
		var z: float = (float(row) - 0.5) * (plane_size_m + gap_m)
		_add_plane(Vector3(x, 0.0, z), product)
		_add_label(
			Vector3(x, 3.0, z - plane_size_m * 0.54),
			"%s\nedge %.6f" % [String(product["class"]), float(product["edge_mse"])]
		)


func _add_plane(pos: Vector3, product: Dictionary) -> void:
	var mesh_instance: MeshInstance3D = MeshInstance3D.new()
	var mesh: PlaneMesh = PlaneMesh.new()
	mesh.size = Vector2(plane_size_m, plane_size_m)
	mesh.subdivide_width = 32
	mesh.subdivide_depth = 32
	mesh_instance.mesh = mesh
	mesh_instance.position = pos
	mesh_instance.name = String(product["class"]) + "_soft_composite"
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_texture = _load_texture(String(product["albedo"]))
	mat.roughness = 0.9
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.texture_repeat = 1
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	mat.uv1_scale = Vector3(repeat_count, repeat_count, 1.0)
	var normal_tex: Texture2D = _load_texture(String(product["normal"]))
	if normal_tex != null:
		mat.normal_enabled = true
		mat.normal_texture = normal_tex
		mat.normal_scale = 0.25
	var rough_tex: Texture2D = _load_texture(String(product["roughness"]))
	if rough_tex != null:
		mat.roughness_texture = rough_tex
	mesh_instance.material_override = mat
	add_child(mesh_instance)


func _add_label(pos: Vector3, text: String) -> void:
	var label: Label3D = Label3D.new()
	label.text = text
	label.font_size = 44
	label.outline_size = 9
	label.modulate = Color.WHITE
	label.outline_modulate = Color(0, 0, 0, 0.85)
	label.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
	label.no_depth_test = true
	label.position = pos
	add_child(label)


func _reset_camera() -> void:
	var cam: Camera3D = get_node_or_null(camera_path) as Camera3D
	if cam == null:
		return
	var total_w: float = 3.0 * plane_size_m + 2.0 * gap_m
	var total_h: float = 2.0 * plane_size_m + gap_m
	var center: Vector3 = Vector3(0.0, 0.0, total_h * 0.1)
	cam.near = 0.05
	cam.far = 3000.0
	cam.projection = Camera3D.PROJECTION_PERSPECTIVE
	cam.fov = 36.0
	cam.global_position = center + Vector3(total_w * 0.10, max(280.0, total_h * 1.75), total_h * 0.78)
	cam.look_at(center, Vector3.UP)
	if cam.has_method("sync_from_transform"):
		cam.call("sync_from_transform")
	if cam.get_script() != null:
		cam.set("move_speed", 70.0)
		cam.set("fast_mult", 8.0)


func _update_label() -> void:
	var label: Label = get_node_or_null(label_path) as Label
	if label == null:
		return
	label.text = "OpenTopo Seamless Soft Composite Gallery\n%d material classes | 4096 source-real composites | %.1fx repeat\nTop: bare_soil, bright_rock, dry_wash | Bottom: rocky_slope, scrub_dense, scrub_sparse\nRMB+mouse look, WASD move, Space/Ctrl up/down, Shift fast | R reset" % [
		_products.size(),
		repeat_count
	]


func _load_texture(raw_path: String) -> Texture2D:
	if raw_path == "":
		return null
	var path: String = raw_path.replace("\\", "/")
	if path.begins_with("D:/assets/world3/"):
		path = "res://" + path.trim_prefix("D:/assets/world3/")
	var img: Image = Image.load_from_file(path)
	if img == null:
		var tex: Texture2D = load(path) as Texture2D
		return tex
	return ImageTexture.create_from_image(img)


func _read_json(path: String) -> Dictionary:
	var f: FileAccess = FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("Could not open " + path)
		return {}
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}
