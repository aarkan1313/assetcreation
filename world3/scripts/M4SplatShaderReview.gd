extends Node3D

@export var old_terrain_material_path: String = "res://textures/wgv3/terrain_blend_alpine_iso.tres"
@export var splat_terrain_material_path: String = "res://textures/wgv3/terrain_splat_alpine.tres"
@export var splat_weight_path: String = "res://textures/m4_splat/alpine_height_slope_weights_rgba.png"
@export var old_opentopo_material_path: String = "res://textures/wgv3/terrain_hex_detail_scrub_sparse_reference.tres"
@export var unified_opentopo_material_path: String = "res://textures/wgv3/terrain_splat_scrub_sparse_single.tres"
@export var heightmap_path: String = "res://heightmap/heightmap.png"
@export var meta_path: String = "res://heightmap/meta.json"
@export var terrain_subdivisions: int = 192

var _camera: Camera3D


func _ready() -> void:
	_add_overlay()
	_add_terrain_panel(
		"terrain_blend fallback",
		old_terrain_material_path,
		Vector3(-620.0, 0.0, -600.0)
	)
	_add_terrain_panel(
		"unified splat weights",
		splat_terrain_material_path,
		Vector3(620.0, 0.0, -600.0)
	)
	_add_plane_panel(
		"OpenTopo terrain_hex_detail",
		old_opentopo_material_path,
		Vector3(-620.0, 0.0, 540.0),
		420.0
	)
	_add_plane_panel(
		"OpenTopo through unified shader",
		unified_opentopo_material_path,
		Vector3(620.0, 0.0, 540.0),
		420.0
	)
	_add_camera()


func _add_terrain_panel(label_text: String, material_path: String, pos: Vector3) -> void:
	var terrain := MeshInstance3D.new()
	terrain.name = label_text.replace(" ", "_")
	terrain.set_script(load("res://scripts/Terrain.gd"))
	terrain.set("heightmap_path", heightmap_path)
	terrain.set("meta_path", meta_path)
	terrain.set("subdivisions", terrain_subdivisions)
	terrain.material_override = _load_material(material_path)
	terrain.position = pos
	add_child(terrain)
	_add_label(label_text, pos + Vector3(0.0, 85.0, -600.0), 38)


func _add_plane_panel(label_text: String, material_path: String, pos: Vector3, size_m: float) -> void:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = label_text.replace(" ", "_")
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(size_m, size_m)
	mesh.subdivide_width = 64
	mesh.subdivide_depth = 64
	mesh_instance.mesh = mesh
	mesh_instance.material_override = _load_material(material_path)
	mesh_instance.position = pos
	add_child(mesh_instance)
	_add_label(label_text, pos + Vector3(0.0, 45.0, -270.0), 34)


func _add_label(text: String, pos: Vector3, size: int) -> void:
	var label := Label3D.new()
	label.text = text
	label.font_size = size
	label.outline_size = 8
	label.modulate = Color.WHITE
	label.outline_modulate = Color(0, 0, 0, 0.85)
	label.no_depth_test = true
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = pos
	add_child(label)


func _add_camera() -> void:
	_camera = Camera3D.new()
	_camera.name = "M4ReviewCamera"
	_camera.current = true
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_camera.size = 2450.0
	_camera.near = 1.0
	_camera.far = 10000.0
	_camera.position = Vector3(0.0, 5200.0, 0.1)
	add_child(_camera)
	_camera.rotation_degrees = Vector3(-90.0, 0.0, 0.0)


func _load_material(path: String) -> Material:
	var mat := load(path) as Material
	if mat == null:
		push_error("M4SplatShaderReview: failed to load material " + path)
	elif path == splat_terrain_material_path and mat is ShaderMaterial:
		var sm := mat as ShaderMaterial
		sm.set_shader_parameter("splat_weights", _load_texture(splat_weight_path))
	return mat


func _load_texture(path: String) -> Texture2D:
	if path == "":
		return null
	var img := Image.load_from_file(path)
	if img == null:
		return load(path) as Texture2D
	return ImageTexture.create_from_image(img)


func _add_overlay() -> void:
	var layer := CanvasLayer.new()
	layer.name = "Overlay"
	add_child(layer)
	var label := Label.new()
	label.text = "M4 terrain A/B - left: terrain_blend fallback | right: unified splat weights"
	label.position = Vector2(22.0, 18.0)
	label.add_theme_font_size_override("font_size", 26)
	label.add_theme_color_override("font_color", Color.WHITE)
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	label.add_theme_constant_override("outline_size", 8)
	layer.add_child(label)
