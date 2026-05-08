extends Node3D

@export var reference_material_path: String = "res://textures/wgv3/terrain_hex_detail_scrub_sparse_reference.tres"
@export var unified_material_path: String = "res://textures/wgv3/terrain_splat_scrub_sparse_single.tres"


func _ready() -> void:
	_add_overlay()
	_add_panel("terrain_hex_detail reference", reference_material_path, Vector3(-260.0, 0.0, 0.0))
	_add_panel("unified shader single material", unified_material_path, Vector3(260.0, 0.0, 0.0))
	_add_camera()


func _add_panel(label_text: String, material_path: String, pos: Vector3) -> void:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = label_text.replace(" ", "_")
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(420.0, 420.0)
	mesh.subdivide_width = 64
	mesh.subdivide_depth = 64
	mesh_instance.mesh = mesh
	mesh_instance.material_override = load(material_path) as Material
	mesh_instance.position = pos
	add_child(mesh_instance)

	var label := Label3D.new()
	label.text = label_text
	label.font_size = 34
	label.outline_size = 8
	label.modulate = Color.WHITE
	label.outline_modulate = Color(0, 0, 0, 0.85)
	label.no_depth_test = true
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = pos + Vector3(0.0, 35.0, -255.0)
	add_child(label)


func _add_camera() -> void:
	var camera := Camera3D.new()
	camera.name = "OpenTopoUnifiedReviewCamera"
	camera.current = true
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 760.0
	camera.near = 0.5
	camera.far = 3000.0
	camera.position = Vector3(0.0, 1300.0, 0.1)
	add_child(camera)
	camera.rotation_degrees = Vector3(-90.0, 0.0, 0.0)


func _add_overlay() -> void:
	var layer := CanvasLayer.new()
	layer.name = "Overlay"
	add_child(layer)
	var label := Label.new()
	label.text = "M4 OpenTopo compatibility - left: terrain_hex_detail | right: unified shader"
	label.position = Vector2(22.0, 18.0)
	label.add_theme_font_size_override("font_size", 26)
	label.add_theme_color_override("font_color", Color.WHITE)
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	label.add_theme_constant_override("outline_size", 8)
	layer.add_child(label)
