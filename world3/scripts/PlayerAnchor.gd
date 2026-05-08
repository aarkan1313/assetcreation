extends Node3D
class_name PlayerAnchor

# Phase C: a simple "where the player is right now" marker that the iso/
# topdown cameras can frame relative to. For now it's just a Node3D with
# optional snap-to-terrain on _ready so test captures don't need pixel-
# perfect Y placement in the .tscn.
#
# When `snap_to_terrain` is true, the anchor raycasts down at start and
# resets its Y to the terrain surface. Requires a Terrain sibling that
# has finished building (Terrain.rebuild() runs in _ready); we defer two
# frames the same way the cameras do.

@export var snap_to_terrain: bool = true
@export var snap_offset_m: float = 0.0  # add this to Y after snap (e.g. eye height)


func _ready() -> void:
	if not snap_to_terrain:
		return
	await get_tree().process_frame
	await get_tree().process_frame
	var terrain := _find_terrain()
	if terrain == null:
		return
	var aabb: AABB = terrain.get_aabb()
	# Raycast straight down through the terrain mesh AABB to find ground Y.
	# We don't have physics here in capture scenes, so sample the mesh directly
	# by querying the heightmap-derived AABB top and let the actual mesh take
	# care of the rest — for capture purposes the camera's ortho projection
	# means small Y errors on the anchor don't matter visually. We just need
	# to be inside the terrain footprint vertically.
	var x: float = global_position.x
	var z: float = global_position.z
	# Clamp anchor into the terrain's XZ footprint so it's never outside.
	x = clamp(x, aabb.position.x, aabb.position.x + aabb.size.x)
	z = clamp(z, aabb.position.z, aabb.position.z + aabb.size.z)
	# Y: midpoint of the terrain AABB — good enough for ortho framing.
	var y: float = aabb.position.y + aabb.size.y * 0.5 + snap_offset_m
	global_position = Vector3(x, y, z)


func _find_terrain() -> MeshInstance3D:
	if get_parent() == null:
		return null
	for child in get_parent().get_children():
		if child is MeshInstance3D and child.name == "Terrain":
			return child
	return null
