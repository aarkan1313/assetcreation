extends Camera3D

@export var pad: float = 1.05


func _ready() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	var terrain := _find_terrain()
	if terrain == null: return
	var aabb: AABB = terrain.get_aabb()
	var center: Vector3 = aabb.position + aabb.size * 0.5
	transform.origin = Vector3(center.x, aabb.position.y + aabb.size.y + 5000.0, center.z)
	look_at(center, Vector3.FORWARD)
	var aspect := 16.0 / 9.0
	size = max(aabb.size.z * pad, aabb.size.x * pad / aspect)


func _find_terrain() -> MeshInstance3D:
	if get_parent() != null:
		for child in get_parent().get_children():
			if child is MeshInstance3D and child.name == "Terrain":
				return child
	return null
