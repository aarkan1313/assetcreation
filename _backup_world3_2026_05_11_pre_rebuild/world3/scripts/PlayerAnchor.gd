extends Node3D
class_name PlayerAnchor

# Phase C: a "where the player is right now" marker that the iso/topdown
# cameras can frame relative to. Snaps Y to the actual terrain surface by
# sampling the same heightmap + meta the Terrain mesh uses.
#
# When `snap_to_terrain` is true, the anchor:
#   1. Reads heightmap_path + meta_path (defaults match Terrain.gd)
#   2. Clamps anchor XZ into the terrain footprint
#   3. Samples the heightmap at the anchor's XZ
#   4. Sets Y to the sampled elevation + snap_offset_m
#
# We can't query the Terrain mesh's vertices directly because Terrain.rebuild
# is async-ish (deferred to first frame). Reading the source heightmap is
# both more reliable and matches the elevation Terrain uses 1:1.

@export var snap_to_terrain: bool = true
@export var snap_offset_m: float = 0.0  # add to Y after snap (e.g. eye height)
@export var heightmap_path: String = "res://heightmap/heightmap.png"
@export var heightmap_cache_path: String = ""
@export var meta_path: String = "res://heightmap/meta.json"


func _ready() -> void:
	if not snap_to_terrain:
		return
	var meta := _load_meta()
	if meta.is_empty():
		push_warning("PlayerAnchor: failed to read meta.json, leaving Y unchanged")
		return
	var img: Image = RuntimeImageCache.load_image(heightmap_cache_path, heightmap_path)
	if img == null:
		push_warning("PlayerAnchor: failed to read heightmap, leaving Y unchanged")
		return

	var world_size: float = float(meta.get("world_size_m", 1024.0))
	var world_size_x: float = float(meta.get("world_size_x_m", world_size))
	var world_size_z: float = float(meta.get("world_size_z_m", world_size))
	var elev_min: float = float(meta.get("elevation_min_m", 0.0))
	var elev_range: float = float(meta.get("elevation_range_m", 1.0))

	var half_x: float = world_size_x * 0.5
	var half_z: float = world_size_z * 0.5

	# Clamp anchor XZ into terrain footprint.
	var x: float = clamp(global_position.x, -half_x, half_x)
	var z: float = clamp(global_position.z, -half_z, half_z)

	# Sample heightmap at (x, z). Terrain.gd places verts so that
	#   wx = fx * world_size_x - half_x  (fx in [0..1])
	#   sx = fx * (img_w - 1)
	# Invert: fx = (x + half_x) / world_size_x → sx
	var fx: float = clamp((x + half_x) / world_size_x, 0.0, 1.0)
	var fz: float = clamp((z + half_z) / world_size_z, 0.0, 1.0)
	var sx: int = clampi(int(round(fx * float(img.get_width() - 1))), 0, img.get_width() - 1)
	var sz: int = clampi(int(round(fz * float(img.get_height() - 1))), 0, img.get_height() - 1)
	var nrm: float = img.get_pixel(sx, sz).r
	var y: float = elev_min + nrm * elev_range + snap_offset_m

	global_position = Vector3(x, y, z)
	print("[PlayerAnchor] snapped to (", x, ", ", y, ", ", z, ") elev=", y - snap_offset_m)


func _load_meta() -> Dictionary:
	var f := FileAccess.open(meta_path, FileAccess.READ)
	if f == null:
		return {}
	var txt := f.get_as_text()
	f.close()
	var parsed = JSON.parse_string(txt)
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	return parsed
