extends Camera3D

# Top-down camera with two framing modes (mirrors IsoCam Phase C).
#
# 1. Auto-AABB (default): frames the whole Terrain mesh in the same scene tree.
# 2. Anchor: frames around `anchor_path.global_position` at `visible_diameter_m`.
#    Fall-through to auto-AABB when anchor isn't set.

@export var pad: float = 1.05

# Anchor mode (Phase C).
@export var anchor_path: NodePath
@export var visible_diameter_m: float = 0.0

# Distance above the anchor in anchor mode. Far enough to clear elevation
# variation in mountain-class regions; ortho means the value doesn't change
# framing, only depth-clipping.
@export var anchor_height_m: float = 5000.0


func _ready() -> void:
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
		push_warning("TopDownCam: anchor_path set but node not found, falling back to auto-AABB")
		return false
	var center: Vector3 = anchor.global_position
	transform.origin = Vector3(center.x, center.y + anchor_height_m, center.z)
	look_at(center, Vector3.FORWARD)
	# Topdown looks straight down — visible footprint is square in world XZ;
	# match horizontal extent to visible_diameter_m on the longer axis (16:9).
	var aspect := 16.0 / 9.0
	size = visible_diameter_m / aspect
	print("[TopDownCam] anchor_mode center=", center, " diameter=", visible_diameter_m, " size=", size)
	return true


func _auto_aabb_mode() -> void:
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
