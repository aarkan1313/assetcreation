extends Camera3D

# Isometric camera that auto-frames the terrain in the same scene tree.
# Uses Terrain's meta.json to read world_size_m and elevation range,
# then positions itself to fully contain the terrain.

@export var target_path: NodePath
@export var pad: float = 1.15  # extra framing room


func _ready() -> void:
	# Defer two frames so Terrain has run _ready() and the mesh is in the tree.
	await get_tree().process_frame
	await get_tree().process_frame
	var terrain := _find_terrain()
	if terrain == null:
		push_warning("IsoCam: no Terrain node found")
		return
	var aabb: AABB = terrain.get_aabb()
	print("[IsoCam] terrain aabb pos=", aabb.position, " size=", aabb.size)
	var center: Vector3 = aabb.position + aabb.size * 0.5
	# Place camera on the +X+Y+Z direction far enough out.
	var dir := Vector3(1, 1, 1).normalized()
	var dist: float = aabb.size.length() * 1.5
	transform.origin = center + dir * dist
	look_at(center, Vector3.UP)
	# Ortho size = vertical extent. Use the larger horizontal footprint.
	# Project the AABB corners onto the camera's right & up axes for tight fit.
	var basis_inv := transform.basis.inverse()
	var min_u := INF; var max_u := -INF
	var min_v := INF; var max_v := -INF
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
		var local: Vector3 = basis_inv * (c - transform.origin)
		min_u = min(min_u, local.x); max_u = max(max_u, local.x)
		min_v = min(min_v, local.y); max_v = max(max_v, local.y)
	var height_extent: float = (max_v - min_v) * pad
	var width_extent: float = (max_u - min_u) * pad
	# Godot ortho `size` is the vertical extent; horizontal scales by aspect.
	# Choose vertical large enough that horizontal also fits at 16:9.
	var aspect := 16.0 / 9.0
	size = max(height_extent, width_extent / aspect)
	print("[IsoCam] size=", size, " pos=", transform.origin)


func _find_terrain() -> MeshInstance3D:
	if target_path != NodePath(""):
		var n := get_node_or_null(target_path)
		if n is MeshInstance3D: return n
	# Walk siblings for a MeshInstance3D named "Terrain".
	if get_parent() != null:
		for child in get_parent().get_children():
			if child is MeshInstance3D and (child.name == "Terrain" or child.get_script() != null):
				return child
	return null
