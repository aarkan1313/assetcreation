extends Node

@export var material_overrides: Array[Material] = []

func _ready() -> void:
	_apply_materials(self)

func _apply_materials(node: Node) -> void:
	if node is MeshInstance3D and material_overrides.size() > 0:
		var mesh_instance := node as MeshInstance3D
		var surface_count := 0
		if mesh_instance.mesh != null:
			surface_count = mesh_instance.mesh.get_surface_count()
		for i in range(surface_count):
			var mat_index = min(i, material_overrides.size() - 1)
			mesh_instance.set_surface_override_material(i, material_overrides[mat_index])
	for child in node.get_children():
		_apply_materials(child)
