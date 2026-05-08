extends Node3D

@export var manifest_path: String = "res://opentopo/processed/textures/Guadalupe_Cypress/manifest.json"
@export var crop_size_m: int = 64
@export var focus_crop_class: String = ""
@export var focus_policy: String = ""
@export var plane_size_m: float = 96.0
@export var repeat_count: float = 4.0
@export var gap_m: float = 22.0
@export var orthographic_overview: bool = false
@export_node_path("Camera3D") var camera_path: NodePath
@export_node_path("Label") var label_path: NodePath

const POLICIES := ["source", "tileable_real", "hex_anti_tile", "stylized_pixel"]
const POLICY_LABELS := {
	"source": "source repeated",
	"tileable_real": "plain tileable",
	"hex_anti_tile": "hex anti-tile",
	"stylized_pixel": "stylized pixel",
}

var _manifest: Dictionary = {}


func _ready() -> void:
	_manifest = _read_json(manifest_path)
	_build_grid()
	await get_tree().process_frame
	_reset_camera()
	_update_label()


func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	if event.keycode == KEY_R:
		_reset_camera()


func _build_grid() -> void:
	var products: Array = _manifest.get("products", [])
	var rows: Array = []
	for product in products:
		if product.get("kind", "") != "crop":
			continue
		if int(product.get("crop_size_m", -1)) != crop_size_m:
			continue
		if focus_crop_class != "" and String(product.get("crop_class", "")) != focus_crop_class:
			continue
		rows.append(product)
	rows.sort_custom(func(a, b): return String(a.get("crop_class", "")) < String(b.get("crop_class", "")))
	var policies := _active_policies()
	var cols := policies.size()
	for row_idx in range(rows.size()):
		var product: Dictionary = rows[row_idx]
		for col_idx in range(cols):
			var policy := String(policies[col_idx])
			var outputs: Dictionary = product.get("outputs", {})
			var output_policy := "tileable_real" if policy == "hex_anti_tile" else policy
			if not outputs.has(output_policy):
				continue
			var info: Dictionary = outputs[output_policy]
			var x := (float(col_idx) - float(cols - 1) * 0.5) * (plane_size_m + gap_m)
			var z := float(row_idx) * (plane_size_m + gap_m)
			_add_plane(
				Vector3(x, 0.0, z),
				String(product.get("crop_class", "")),
				policy,
				String(info.get("albedo", "")),
				String(info.get("normal", "")),
				String(info.get("roughness", ""))
			)
			_add_label(
				Vector3(x, 3.0, z - plane_size_m * 0.52),
				"%s\n%s" % [String(product.get("crop_class", "")), POLICY_LABELS.get(policy, policy)]
			)


func _add_plane(pos: Vector3, crop_class: String, policy: String, albedo_path: String, normal_path: String, roughness_path: String) -> void:
	var mesh_instance := MeshInstance3D.new()
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(plane_size_m, plane_size_m)
	mesh.subdivide_width = 32
	mesh.subdivide_depth = 32
	mesh_instance.mesh = mesh
	mesh_instance.position = pos
	mesh_instance.name = "%s_%s" % [crop_class, policy]
	var mat := StandardMaterial3D.new()
	if policy == "hex_anti_tile":
		mesh_instance.material_override = _make_hex_material(albedo_path, normal_path, roughness_path)
		add_child(mesh_instance)
		return
	mat.albedo_texture = _load_texture(albedo_path)
	mat.roughness = 0.88
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.texture_repeat = 1
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	mat.uv1_scale = Vector3(repeat_count, repeat_count, 1.0)
	var normal_tex := _load_texture(normal_path)
	if normal_tex != null:
		mat.normal_enabled = true
		mat.normal_texture = normal_tex
		mat.normal_scale = 0.35
	var rough_tex := _load_texture(roughness_path)
	if rough_tex != null:
		mat.roughness_texture = rough_tex
	mesh_instance.material_override = mat
	add_child(mesh_instance)


func _make_hex_material(albedo_path: String, normal_path: String, roughness_path: String) -> Material:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/terrain_hex.gdshader") as Shader
	mat.set_shader_parameter("albedo_tex", _load_texture(albedo_path))
	mat.set_shader_parameter("normal_tex", _load_texture(normal_path))
	mat.set_shader_parameter("rough_tex", _load_texture(roughness_path))
	mat.set_shader_parameter("world_uv_scale", repeat_count / plane_size_m)
	mat.set_shader_parameter("hex_strength", 1.0)
	mat.set_shader_parameter("blend_sharpness", 8.0)
	mat.set_shader_parameter("roughness_strength", 0.85)
	mat.set_shader_parameter("normal_strength", 0.45)
	mat.set_shader_parameter("macro_scale", 80.0)
	mat.set_shader_parameter("macro_value_strength", 0.08)
	mat.set_shader_parameter("macro_hue_strength", 0.02)
	return mat


func _add_label(pos: Vector3, text: String) -> void:
	var label := Label3D.new()
	label.text = text
	label.font_size = 42
	label.outline_size = 8
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
	var rows: int = _row_count()
	var cols := _active_policies().size()
	var total_w: float = float(cols) * plane_size_m + float(cols - 1) * gap_m
	var total_h: float = max(1.0, float(rows)) * plane_size_m + max(0.0, float(rows - 1)) * gap_m
	var center := Vector3(0.0, 0.0, total_h * 0.5 - plane_size_m * 0.5)
	cam.near = 0.05
	cam.far = max(3000.0, total_h * 6.0)
	if orthographic_overview:
		var aspect := 16.0 / 9.0
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = max(total_h * 1.12, total_w * 1.12 / aspect)
		cam.global_position = center + Vector3(0.0, max(400.0, total_h * 1.2), 0.01)
		cam.look_at(center, Vector3.FORWARD)
		if cam.has_method("sync_from_transform"):
			cam.call("sync_from_transform")
		return
	cam.projection = Camera3D.PROJECTION_PERSPECTIVE
	cam.fov = 48.0
	cam.global_position = center + Vector3(total_w * 0.42, max(120.0, total_h * 0.46), total_h * 0.56)
	cam.look_at(center, Vector3.UP)
	if cam.has_method("sync_from_transform"):
		cam.call("sync_from_transform")
	if cam.get_script() != null:
		cam.set("move_speed", 80.0)
		cam.set("fast_mult", 8.0)


func _row_count() -> int:
	var count := 0
	for product in _manifest.get("products", []):
		if product.get("kind", "") != "crop":
			continue
		if int(product.get("crop_size_m", -1)) != crop_size_m:
			continue
		if focus_crop_class != "" and String(product.get("crop_class", "")) != focus_crop_class:
			continue
		count += 1
	return count


func _update_label() -> void:
	var label := get_node_or_null(label_path) as Label
	if label == null:
		return
	var focus := "all crops" if focus_crop_class == "" else focus_crop_class
	var column_labels: Array = []
	for policy in _active_policies():
		column_labels.append(POLICY_LABELS.get(String(policy), String(policy)))
	label.text = "OpenTopo Tileable Real Texture Review\n%d m %s | %.0fx repeat | columns: %s\nRMB+mouse look, WASD move, Space/Ctrl up/down, Shift fast | R reset\nFull-map macro atlas is exported separately; it is not forced tileable." % [crop_size_m, focus, repeat_count, ", ".join(column_labels)]


func _active_policies() -> Array:
	if focus_policy == "":
		return POLICIES.duplicate()
	if POLICIES.has(focus_policy):
		return [focus_policy]
	push_warning("Unknown texture review policy: " + focus_policy)
	return POLICIES.duplicate()


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
