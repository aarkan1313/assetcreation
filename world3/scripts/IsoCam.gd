extends Camera3D

# Isometric camera with two framing modes.
#
# 1. Auto-AABB (default): frames the whole Terrain mesh in the same scene tree
#    by reading its AABB. Original behavior, used by review/gallery scenes.
# 2. Anchor: frames a fixed world position with a configurable visible diameter.
#    Used for game-mode scale review (Phase C). Set `anchor_path` to a Node3D
#    and `visible_diameter_m` to the desired diameter (e.g. 40 for ARPG, 300
#    for strategy). Falls through to auto-AABB if `anchor_path` is empty or the
#    node is missing.

@export var target_path: NodePath
@export var pad: float = 1.15  # extra framing room (auto-AABB only)

# Anchor mode (Phase C). If anchor_path is set AND visible_diameter_m > 0,
# the camera frames around anchor.global_position at that diameter instead of
# auto-fitting the terrain AABB.
@export var anchor_path: NodePath
@export var visible_diameter_m: float = 0.0

# Iso angle for anchor mode. Standard 45-degree azimuth, 30-degree elevation
# is closer to ARPG framing; 1,1,1 normalized matches the legacy auto-AABB
# direction. Default keeps continuity with auto-AABB framing.
@export var iso_dir: Vector3 = Vector3(1, 1, 1)


func _ready() -> void:
	# Defer two frames so Terrain has run _ready() and the mesh is in the tree.
	await get_tree().process_frame
	await get_tree().process_frame
	if _try_anchor_mode():
		return
	_auto_aabb_mode()


func _try_anchor_mode() -> bool:
	if anchor_path == NodePath("") or visible_diameter_m <= 0.0:
		return false
	var anchor: Node3D = get_node_or_null(anchor_path) as Node3D
	if anchor == null:
		push_warning("IsoCam: anchor_path set but node not found, falling back to auto-AABB")
		return false
	var center: Vector3 = anchor.global_position
	var dir: Vector3 = iso_dir.normalized()
	# Distance just needs to be far enough that ortho projection clears the
	# terrain at typical elevations. Tie to diameter for proportionality.
	var dist: float = visible_diameter_m * 2.0
	transform.origin = center + dir * dist
	look_at(center, Vector3.UP)
	# Ortho `size` is the vertical extent. We want `visible_diameter_m` to be
	# the diameter of what fills the frame on the longer screen axis (16:9 →
	# horizontal). Pick vertical so horizontal == visible_diameter_m.
	var aspect := 16.0 / 9.0
	size = visible_diameter_m / aspect
	print("[IsoCam] anchor_mode center=", center, " diameter=", visible_diameter_m, " size=", size)
	return true


func _auto_aabb_mode() -> void:
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
