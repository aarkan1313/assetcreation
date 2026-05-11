extends Node
class_name WorldMapService

# Phase F.7a — reads a world_map.json once, exposes lookup APIs for
# the F.7b multi-bundle streamer.
#
# Coordinate convention (matches world_plan/world_map schemas):
#   tile_xy [col, row] integer grid, origin at world (0, 0)
#   world_xy_m = (col * tile_size_m, row * tile_size_m) — SW corner
#   The tile's world rect spans [world_xy_m, world_xy_m + tile_size_m]
#
# Usage:
#   var svc := WorldMapService.new()
#   svc.world_map_path = "res://worlds/starter_5biome_procedural/world_map.json"
#   svc.load_map()
#   var tile := svc.tile_for_world_pos(player_pos.x, player_pos.z)
#   var neighbors := svc.tiles_in_radius(player_pos, 256.0)

@export var world_map_path: String = ""

var _map: Dictionary = {}
var _tiles_by_xy: Dictionary = {}   # Vector2i -> tile dict
var _bounds_m: Vector2 = Vector2.ZERO
var _tile_size_m: float = 256.0
var _grid_cols: int = 0
var _grid_rows: int = 0
var _loaded: bool = false


func load_map() -> bool:
	if world_map_path == "":
		push_error("WorldMapService: world_map_path empty")
		return false
	if not FileAccess.file_exists(world_map_path):
		push_error("WorldMapService: world_map not found: " + world_map_path)
		return false
	var f := FileAccess.open(world_map_path, FileAccess.READ)
	if f == null:
		push_error("WorldMapService: cannot open: " + world_map_path)
		return false
	var text := f.get_as_text()
	f.close()
	var parsed: Variant = JSON.parse_string(text)
	if not parsed is Dictionary:
		push_error("WorldMapService: world_map is not an object")
		return false
	_map = parsed
	var bounds: Array = _map.get("bounds_m", [0.0, 0.0])
	_bounds_m = Vector2(float(bounds[0]), float(bounds[1]))
	_tile_size_m = float(_map.get("tile_size_m", 256.0))
	var grid: Array = _map.get("grid", [0, 0])
	_grid_cols = int(grid[0])
	_grid_rows = int(grid[1])

	_tiles_by_xy.clear()
	for t in _map.get("tiles", []):
		var xy: Array = t.get("tile_xy", [-1, -1])
		_tiles_by_xy[Vector2i(int(xy[0]), int(xy[1]))] = t

	_loaded = true
	print("[WorldMapService] loaded ", _tiles_by_xy.size(), " tiles  bounds=", _bounds_m, " tile_size=", _tile_size_m)
	return true


func bounds_m() -> Vector2:
	return _bounds_m


func tile_size_m() -> float:
	return _tile_size_m


func tile_xy_for_world_pos(world_x: float, world_z: float) -> Vector2i:
	"""Returns the integer tile xy containing world position (x, z).
	May be out of bounds for the loaded map; caller decides."""
	return Vector2i(
		int(floor(world_x / _tile_size_m)),
		int(floor(world_z / _tile_size_m))
	)


func tile_for_world_pos(world_x: float, world_z: float) -> Dictionary:
	"""Returns the tile dict (with biome, bundle_id, bundle_dir, etc.)
	for the given world position, or {} if no tile covers it."""
	var xy := tile_xy_for_world_pos(world_x, world_z)
	return _tiles_by_xy.get(xy, {})


func tiles_in_radius(center_world: Vector3, radius_m: float) -> Array:
	"""Returns the tiles whose rect intersects a square of side
	2*radius_m centered at center_world. Used by the streamer to
	decide which bundles to keep loaded."""
	var min_xy := tile_xy_for_world_pos(center_world.x - radius_m, center_world.z - radius_m)
	var max_xy := tile_xy_for_world_pos(center_world.x + radius_m, center_world.z + radius_m)
	var out: Array = []
	for r in range(min_xy.y, max_xy.y + 1):
		for c in range(min_xy.x, max_xy.x + 1):
			var t = _tiles_by_xy.get(Vector2i(c, r), null)
			if t != null:
				out.append(t)
	return out


func all_tiles() -> Array:
	return _map.get("tiles", [])


func plan_id() -> String:
	return _map.get("plan_id", "")


func is_loaded() -> bool:
	return _loaded
