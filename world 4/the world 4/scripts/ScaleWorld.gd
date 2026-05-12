extends Node3D
class_name ScaleWorld

# W4 scale demo — multi-tile world root.
#
# Reads worlds/scale_demo/meta.json, instantiates TileTerrain children for
# the grid. Two modes:
#   - load_all (CP2): spawn all 16 tiles at scene-load. Simple. Use this
#     to verify the slicing and seam continuity in isolation.
#   - radius   (CP3): only spawn tiles within `view_radius` of camera_path,
#     unload outside. Pages tiles in/out as camera moves.
#
# load_all is the default until radius mode is wired up.

enum LoadMode { LOAD_ALL, RADIUS }

@export var bundle_dir: String = "res://worlds/scale_demo/"
# Override the per-tile material. If empty, uses {bundle_dir}/material.tres.
# Diagnostic use: point at material_minimal.tres to test with a stripped-
# down shader, or at a custom .tres to test alternate shader/texture sets.
@export var material_override_path: String = ""

# Per-biome material map. When a tile's meta.json has a "biome" field and
# the value is a key in this dict, the tile gets the matching .tres at
# spawn instead of material_override_path. Empty dict = old single-material
# behavior. Hard borders only — soft blending is Axis 6.
@export var biome_materials: Dictionary = {}

# When set, switches scale_demo to the texture-array + splat path
# (Axis 6 transitions). The material at this path is loaded once,
# texture arrays are constructed from the layer manifest at scene init,
# and per-tile uniforms (splat texture + splat_*_indices + tile_origin_m
# + tile_size_m) are set on per-tile duplicates of the material.
@export var world_v2_material_path: String = ""

# Per-view materials. When set, AnchorCameraRig (or anyone else) calls
# set_view_mode("walk"/"iso"/"topdown") to swap the per-tile material
# at runtime. If a view's path is empty, the active material doesn't
# change when that view becomes current — useful for a partial rollout.
@export var view_material_walk: String = ""
@export var view_material_iso: String = ""
@export var view_material_topdown: String = ""

# Per-view radius overrides. -1 = use the default view_radius_tiles.
# Iso and topdown want to see the whole world (or close to it), so they
# default to a value large enough to load every tile. Walk uses the
# default narrow radius for streaming.
@export var view_radius_walk: int = -1
@export var view_radius_iso: int = -1
@export var view_radius_topdown: int = -1
@export var load_mode: LoadMode = LoadMode.LOAD_ALL
# Subset for the 2-tile seam test (CP2a). Empty array = all tiles.
# Each entry is "X,Z" e.g. "0,0".
@export var tile_subset: PackedStringArray = PackedStringArray()
# Mesh quad size in meters. 0.5 = 512x512 quads per 256m tile, supersamples
# the 1m/pixel heightmap so bilinear filtering can smooth out per-pixel
# terracing on steep crops.
@export var tile_resolution_m: float = 2.0
# Radius-mode settings (active when load_mode = RADIUS).
# view_radius_tiles = 1 means a 3x3 window of tiles around the camera.
# Larger = wider view + more vertices loaded.
@export var view_radius_tiles: int = 1
@export var camera_path: NodePath
# Throttle for the repaging check. The camera typically only crosses
# tile boundaries once every few seconds at walk speeds; reading the
# camera position every frame and diffing the tile set is cheap but
# unnecessary. 0.25s gives a snappy response without thrash.
@export var repage_interval_s: float = 0.25

var _grid_n: int = 4
var _tile_size_m: float = 256.0
var _world_size_m: float = 1024.0
var _elev_min_m: float = 0.0
var _elev_range_m: float = 1.0
var _tiles: Dictionary = {}  # Vector2i -> TileTerrain
var _tile_script: Script

# Shared world heightmap, decoded once and passed by reference to every
# tile. Tiles that have a reference sample with WORLD coordinates which
# means finite-difference normals at tile boundaries naturally read into
# the neighboring tile's data — no white-seam artifact.
var _world_height_data: PackedFloat32Array
var _world_height_w: int = 0
var _world_height_h: int = 0

# Subset filter parsed from tile_subset for fast lookup.
var _subset_filter: Dictionary = {}
var _has_subset: bool = false

# Radius-mode state.
var _last_camera_tile: Vector2i = Vector2i(-9999, -9999)
var _repage_clock: float = 0.0
var _radius_active: bool = false
# FIFO of tile coords waiting to be spawned. Boundary crossings push
# 3 new tiles in (at radius 1); we drain at most one per frame so the
# per-tile mesh build cost doesn't all happen on one frame.
var _pending_spawn: Array[Vector2i] = []
# Persistent cache of unloaded tile nodes, keyed by Vector2i coord.
# When a tile leaves the radius we detach + hide instead of freeing
# (cache hit when the player walks back is ~0ms; otherwise rebuild
# would cost ~77ms). Trade-off is memory — at 16 tiles × ~16K verts
# × 32 bytes = ~30MB max. Bounded by world size, not by play time.
var _tile_cache: Dictionary = {}  # Vector2i -> Node3D


func _ready() -> void:
	if not _load_world_meta():
		push_error("ScaleWorld: failed to load world meta")
		return

	_tile_script = load("res://scripts/TileTerrain.gd") as Script
	if _tile_script == null:
		push_error("ScaleWorld: cannot load TileTerrain.gd")
		return

	_load_world_heightmap()
	_parse_subset()

	match load_mode:
		LoadMode.LOAD_ALL:
			_spawn_all_tiles()
		LoadMode.RADIUS:
			_radius_active = true
			# Force initial repage so the camera-adjacent tiles are queued
			# before the first frame renders. We drain the queue immediately
			# at scene-load so the player never sees a black world on F6.
			# Subsequent repages (boundary crossings) drain one per frame.
			_repage(true)
			_drain_pending_now()
	print("[ScaleWorld] world=%dm grid=%dx%d tile=%dm  load_mode=%s  spawned %d tiles" % [
		int(_world_size_m), _grid_n, _grid_n, int(_tile_size_m),
		"RADIUS" if _radius_active else "LOAD_ALL",
		_tiles.size()
	])


func _exit_tree() -> void:
	# Free any cached-but-detached tile nodes so we don't leak their
	# meshes/materials on scene exit. Active children get freed by Godot's
	# normal exit walk; cache entries are detached and would leak.
	for coord in _tile_cache.keys():
		var node: Node = _tile_cache[coord]
		if is_instance_valid(node):
			node.queue_free()
	_tile_cache.clear()


func _process(delta: float) -> void:
	if not _radius_active:
		return
	# Drain one pending tile per frame so boundary-cross hitches amortize
	# from one ~1s freeze into three ~325ms stutters across three frames.
	if not _pending_spawn.is_empty():
		var coord: Vector2i = _pending_spawn.pop_front()
		if not _tiles.has(coord):
			_spawn_tile(coord)
		# Don't run the repage tick this frame — we already have work to
		# do, and re-evaluating the tile set when the queue is non-empty
		# just adds more work to the pile. Wait until the current spawn
		# wave finishes before checking for the next.
		return
	_repage_clock += delta
	if _repage_clock < repage_interval_s:
		return
	_repage_clock = 0.0
	_repage(false)


# Drain every queued tile spawn synchronously. Used at scene-load so the
# initial 3x3 window is fully populated before the first frame renders.
func _drain_pending_now() -> void:
	while not _pending_spawn.is_empty():
		var coord: Vector2i = _pending_spawn.pop_front()
		if not _tiles.has(coord):
			_spawn_tile(coord)


# Re-evaluate which tiles should be loaded. `force = true` skips the
# "did camera tile change?" early-out (used on first frame).
func _repage(force: bool) -> void:
	var cam_xz: Vector2 = _camera_world_xz()
	# Convert world XZ to tile indices. World X = world_origin + tile_x*tile_size,
	# world is centered on origin → world X range is -world_size/2 .. +world_size/2.
	var tile_x: int = int(floor((cam_xz.x + _world_size_m * 0.5) / _tile_size_m))
	var tile_z: int = int(floor((cam_xz.y + _world_size_m * 0.5) / _tile_size_m))
	# Clamp to world grid so the camera can stand at the very edge and we
	# still page the corner tile rather than a phantom out-of-bounds tile.
	tile_x = clampi(tile_x, 0, _grid_n - 1)
	tile_z = clampi(tile_z, 0, _grid_n - 1)
	var current_tile: Vector2i = Vector2i(tile_x, tile_z)
	if not force and current_tile == _last_camera_tile:
		return
	_last_camera_tile = current_tile

	# Compute the set of tiles that should be loaded.
	var needed: Dictionary = {}
	for dz in range(-view_radius_tiles, view_radius_tiles + 1):
		for dx in range(-view_radius_tiles, view_radius_tiles + 1):
			var coord: Vector2i = Vector2i(tile_x + dx, tile_z + dz)
			if coord.x < 0 or coord.x >= _grid_n: continue
			if coord.y < 0 or coord.y >= _grid_n: continue
			needed[coord] = true

	# Free tiles no longer in range. Freeing is cheap — do it immediately.
	var to_free: Array = []
	for coord in _tiles.keys():
		if not needed.has(coord):
			to_free.append(coord)
	for coord in to_free:
		_free_tile(coord)

	# Queue missing tiles. _process drains the queue at one per frame so
	# boundary-crossing spawns don't all hit one frame.
	# Drop any stale queued coords that are no longer needed (e.g. you
	# crossed two boundaries in quick succession).
	var new_pending: Array[Vector2i] = []
	for coord in _pending_spawn:
		if needed.has(coord) and not _tiles.has(coord):
			new_pending.append(coord)
	_pending_spawn = new_pending
	for coord in needed.keys():
		if _tiles.has(coord):
			continue
		if coord in _pending_spawn:
			continue
		_pending_spawn.append(coord)


func _camera_world_xz() -> Vector2:
	# Resolve the camera by either the inspector NodePath, or by finding
	# the current Camera3D in the viewport (handles the AnchorCameraRig
	# pattern where the active camera switches between walk/iso/topdown).
	var node: Node = null
	if not camera_path.is_empty():
		node = get_node_or_null(camera_path)
	if node == null:
		var vp: Viewport = get_viewport()
		if vp != null:
			node = vp.get_camera_3d()
	if node is Node3D:
		var n3: Node3D = node
		return Vector2(n3.global_position.x, n3.global_position.z)
	return Vector2.ZERO


func _free_tile(coord: Vector2i) -> void:
	if not _tiles.has(coord):
		return
	var tile_node: Node = _tiles[coord]
	_tiles.erase(coord)
	if not is_instance_valid(tile_node):
		return
	# Detach + hide instead of free. If the player walks back into this
	# tile's coordinate, _spawn_tile sees the cache hit and re-attaches
	# in ~0ms instead of rebuilding for ~77ms. Memory cost is bounded by
	# total world tile count (16 here), not play time.
	remove_child(tile_node)
	tile_node.visible = false
	_tile_cache[coord] = tile_node


func _load_world_meta() -> bool:
	var meta_path: String = bundle_dir + "meta.json"
	var f: FileAccess = FileAccess.open(meta_path, FileAccess.READ)
	if f == null:
		push_error("ScaleWorld: cannot open " + meta_path)
		return false
	var meta: Variant = JSON.parse_string(f.get_as_text())
	f.close()
	if not meta is Dictionary:
		return false
	_grid_n = int(meta.get("grid_n", 4))
	_tile_size_m = float(meta.get("tile_size_m", 256.0))
	_world_size_m = float(meta.get("world_size_m", 1024.0))
	_elev_min_m = float(meta.get("elevation_min_m", 0.0))
	_elev_range_m = float(meta.get("elevation_range_m", 1.0))
	return true


# Load the world's full heightmap into a flat float array. This is the
# slicer's post-smoothing output; each pixel = 0..1 normalized elevation.
# Used by tiles for cross-tile-boundary sampling so finite-difference
# normals don't collapse at seams.
func _load_world_heightmap() -> void:
	var path: String = bundle_dir + "world_heightmap.png"
	var img: Image = Image.load_from_file(ProjectSettings.globalize_path(path))
	if img == null:
		push_warning("ScaleWorld: cannot load world heightmap " + path + " — tiles will sample locally only")
		return
	_world_height_w = img.get_width()
	_world_height_h = img.get_height()
	img.convert(Image.FORMAT_RF)
	var raw: PackedByteArray = img.get_data()
	var n: int = _world_height_w * _world_height_h
	_world_height_data = raw.to_float32_array()
	if _world_height_data.size() != n:
		push_error("ScaleWorld: world heightmap size mismatch %d vs %d" % [_world_height_data.size(), n])
		_world_height_data = PackedFloat32Array()
		return
	print("[ScaleWorld] loaded world heightmap %dx%d for cross-tile sampling" % [_world_height_w, _world_height_h])


func _parse_subset() -> void:
	_subset_filter.clear()
	_has_subset = tile_subset.size() > 0
	if not _has_subset:
		return
	for s in tile_subset:
		var parts: PackedStringArray = s.split(",")
		if parts.size() == 2:
			var k: Vector2i = Vector2i(int(parts[0].strip_edges()), int(parts[1].strip_edges()))
			_subset_filter[k] = true


func _spawn_all_tiles() -> void:
	for tz in range(_grid_n):
		for tx in range(_grid_n):
			var coord: Vector2i = Vector2i(tx, tz)
			if _has_subset and not _subset_filter.has(coord):
				continue
			_spawn_tile(coord)


func _resolve_tile_material_path(tile_dir: String) -> String:
	# Per-biome route: read this tile's meta.json biome label and look up the
	# matching material .tres in biome_materials. Falls back to override / world
	# default if the biome isn't mapped (e.g. existing pre-biome tiles).
	if not biome_materials.is_empty():
		var meta_path: String = tile_dir + "meta.json"
		var file: FileAccess = FileAccess.open(meta_path, FileAccess.READ)
		if file != null:
			var text: String = file.get_as_text()
			file.close()
			var parsed: Variant = JSON.parse_string(text)
			if typeof(parsed) == TYPE_DICTIONARY and parsed.has("biome"):
				var biome: String = String(parsed["biome"])
				if biome_materials.has(biome):
					return String(biome_materials[biome])
				else:
					push_warning("ScaleWorld: tile %s biome %s not in biome_materials" % [tile_dir, biome])
	# Legacy single-material path: explicit override > world default.
	if not material_override_path.is_empty():
		return material_override_path
	return bundle_dir + "material.tres"


# ---- v2 (Axis 6 transitions) path ----
#
# Single global terrain material. 8 PBR Texture2DArrays (2 tiers × 4
# maps) + one world-spanning splat Texture2DArray (one layer per biome)
# all bound at scene init. Per-biome (tier, layer) packed ints for the
# 3 slots set as fixed-size shader uniforms (cap MAX_BIOMES=16 — bump
# in shader to scale higher). Every tile shares the SAME material —
# no per-tile duplication, no per-tile splat lookup. Splat sampling at
# world XZ guarantees continuous boundaries by construction.
var _v2_base_material: ShaderMaterial = null
var _v2_layer_manifest: Dictionary = {}
var _v2_world_splat_manifest: Dictionary = {}
var _v2_arrays_built: bool = false
const MAX_BIOMES_PER_WORLD: int = 16


func _build_v2_arrays_if_needed() -> bool:
	# Returns true once arrays + biome indices are bound on _v2_base_material;
	# false if v2 path is disabled or any required resource is missing.
	if _v2_arrays_built:
		return true
	if world_v2_material_path.is_empty():
		return false
	# Load the base material (.tres has shader + lighting defaults; no arrays).
	var base_res: Resource = load(world_v2_material_path)
	if not (base_res is ShaderMaterial):
		push_error("ScaleWorld v2: world_v2_material_path is not a ShaderMaterial: " + world_v2_material_path)
		return false
	# Load the layer manifest (per-biome PBR layout per tier).
	var manifest_path: String = bundle_dir + "arrays/layer_manifest.json"
	var mf: FileAccess = FileAccess.open(manifest_path, FileAccess.READ)
	if mf == null:
		push_error("ScaleWorld v2: missing layer_manifest at " + manifest_path)
		return false
	var parsed: Variant = JSON.parse_string(mf.get_as_text())
	mf.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("ScaleWorld v2: layer_manifest is not a dict")
		return false
	_v2_layer_manifest = parsed
	# Load the world-splat manifest (per-biome world-spanning weight map).
	var ws_path: String = bundle_dir + "world_splat/manifest.json"
	var wsf: FileAccess = FileAccess.open(ws_path, FileAccess.READ)
	if wsf == null:
		push_error("ScaleWorld v2: missing world_splat manifest at " + ws_path + " (run pipeline/build_world_splat.py)")
		return false
	var ws_parsed: Variant = JSON.parse_string(wsf.get_as_text())
	wsf.close()
	if typeof(ws_parsed) != TYPE_DICTIONARY:
		push_error("ScaleWorld v2: world_splat manifest is not a dict")
		return false
	_v2_world_splat_manifest = ws_parsed
	# Build the 8 PBR arrays (2 tiers × 4 map types) — unchanged from 5a.
	var tiers: Dictionary = _v2_layer_manifest.get("tiers", {})
	for tier_name in ["standard", "hero"]:
		if not tiers.has(tier_name):
			continue
		var tdata: Dictionary = tiers[tier_name]
		var layers: Array = tdata.get("layers", [])
		if layers.is_empty():
			continue
		for map_name in ["albedo", "normal", "roughness", "ao"]:
			var sorted_layers: Array = layers.duplicate()
			sorted_layers.sort_custom(func(a, b): return int(a["layer"]) < int(b["layer"]))
			var imgs: Array = []
			for layer_rec in sorted_layers:
				var rel: String = String(layer_rec["maps"][map_name])
				var tex: Texture2D = load("res://" + rel) as Texture2D
				if tex == null:
					push_error("ScaleWorld v2: failed to load %s" % rel)
					return false
				var img: Image = tex.get_image()
				if img == null:
					push_error("ScaleWorld v2: texture has no image: %s" % rel)
					return false
				if img.is_compressed():
					var decomp_err: int = img.decompress()
					if decomp_err != OK:
						push_error("ScaleWorld v2: failed to decompress %s (err=%d)" % [rel, decomp_err])
						return false
				# Force uniform RGBA8 format + no mipmaps so create_from_images
				# doesn't err=31 from heterogeneous layer formats / mipmap states.
				# See PITFALLS #5.
				if img.get_format() != Image.FORMAT_RGBA8:
					img.convert(Image.FORMAT_RGBA8)
				if img.has_mipmaps():
					img.clear_mipmaps()
				imgs.append(img)
			var arr: Texture2DArray = Texture2DArray.new()
			var err: int = arr.create_from_images(imgs)
			if err != OK:
				push_error("ScaleWorld v2: create_from_images failed for %s_%s (err=%d, %d layers)" % [tier_name, map_name, err, imgs.size()])
				return false
			var uniform_name: String = map_name if map_name != "roughness" else "rough"
			base_res.set_shader_parameter("%s_%s" % [tier_name, uniform_name], arr)
	# Build the WORLD SPLAT Texture2DArray (one layer per biome). Loaded
	# from per-biome R8 PNGs at <bundle>/world_splat/layer_<biome>.png.
	var ws_layers: Array = _v2_world_splat_manifest.get("layers", [])
	if ws_layers.size() == 0:
		push_error("ScaleWorld v2: world_splat manifest has no layers")
		return false
	if ws_layers.size() > MAX_BIOMES_PER_WORLD:
		push_error("ScaleWorld v2: world_splat has %d layers but shader caps at %d (bump MAX_BIOMES in terrain_world_v2.gdshader + MAX_BIOMES_PER_WORLD here)" % [ws_layers.size(), MAX_BIOMES_PER_WORLD])
		return false
	# Same uniform-format + no-mipmap discipline as the PBR arrays.
	var splat_imgs: Array = []
	for layer_rec in ws_layers:
		var rel: String = "worlds/" + bundle_dir.replace("res://worlds/", "").replace("res://", "") + "world_splat/" + String(layer_rec["file"])
		# Simpler: just compose the path directly.
		var splat_path: String = bundle_dir + "world_splat/" + String(layer_rec["file"])
		var tex: Texture2D = load(splat_path) as Texture2D
		if tex == null:
			push_error("ScaleWorld v2: failed to load world splat layer " + splat_path)
			return false
		var img: Image = tex.get_image()
		if img == null:
			push_error("ScaleWorld v2: world splat layer has no image: " + splat_path)
			return false
		if img.is_compressed():
			var decomp_err2: int = img.decompress()
			if decomp_err2 != OK:
				push_error("ScaleWorld v2: failed to decompress world splat " + splat_path)
				return false
		if img.get_format() != Image.FORMAT_RGBA8:
			img.convert(Image.FORMAT_RGBA8)
		if img.has_mipmaps():
			img.clear_mipmaps()
		splat_imgs.append(img)
	var splat_arr: Texture2DArray = Texture2DArray.new()
	var splat_err: int = splat_arr.create_from_images(splat_imgs)
	if splat_err != OK:
		push_error("ScaleWorld v2: create_from_images failed for world_splat (err=%d, %d layers)" % [splat_err, splat_imgs.size()])
		return false
	base_res.set_shader_parameter("world_splat", splat_arr)
	base_res.set_shader_parameter("num_biomes", ws_layers.size())
	# Build per-biome packed-int slot indirection (fixed-size arrays).
	# For each catalog biome (matching world_splat layer order), look up
	# its ground/mid/rock (tier, layer) in the layer manifest.
	var ground_packed: Array[int] = []
	var mid_packed: Array[int] = []
	var rock_packed: Array[int] = []
	ground_packed.resize(MAX_BIOMES_PER_WORLD)
	mid_packed.resize(MAX_BIOMES_PER_WORLD)
	rock_packed.resize(MAX_BIOMES_PER_WORLD)
	for i in range(MAX_BIOMES_PER_WORLD):
		ground_packed[i] = -1
		mid_packed[i] = -1
		rock_packed[i] = -1
	for i in range(ws_layers.size()):
		var biome_name: String = String(ws_layers[i]["biome"])
		var found_g: int = -1
		var found_m: int = -1
		var found_r: int = -1
		for tier_name in ["standard", "hero"]:
			if not tiers.has(tier_name):
				continue
			var tdata2: Dictionary = tiers[tier_name]
			for layer_rec in tdata2.get("layers", []):
				if String(layer_rec["biome"]) != biome_name:
					continue
				var slot_name: String = String(layer_rec["slot"])
				var raw_layer: int = int(layer_rec["layer"])
				var packed: int = _v2_pack(tier_name, raw_layer)
				if slot_name == "ground":
					found_g = packed
				elif slot_name == "mid":
					found_m = packed
				elif slot_name == "rock":
					found_r = packed
		ground_packed[i] = found_g
		mid_packed[i] = found_m
		rock_packed[i] = found_r
		if found_g < 0 or found_m < 0 or found_r < 0:
			push_warning("ScaleWorld v2: biome %s missing one of ground/mid/rock in layer manifest" % biome_name)
	base_res.set_shader_parameter("biome_ground_packed", ground_packed)
	base_res.set_shader_parameter("biome_mid_packed", mid_packed)
	base_res.set_shader_parameter("biome_rock_packed", rock_packed)
	# World rect (in meters) for splat UV computation.
	var world_origin: Vector2 = Vector2(
		-_world_size_m * 0.5, -_world_size_m * 0.5
	)
	base_res.set_shader_parameter("world_origin_m", world_origin)
	base_res.set_shader_parameter("world_size_m", _world_size_m)
	_v2_base_material = base_res
	_v2_arrays_built = true
	print("[ScaleWorld v2] arrays built: %d tiers, %d biomes, world splat %d layers" % [
		tiers.size(), ws_layers.size(), splat_imgs.size(),
	])
	return true


# Encode (tier, layer) into a packed int: tier in bit 30, layer in bits 0..29.
func _v2_pack(tier_name: String, layer: int) -> int:
	var tier_bit: int = 0 if tier_name == "standard" else 1
	return (tier_bit << 30) | (layer & 0x3FFFFFFF)


# Return the GLOBAL v2 material for a tile. Every tile uses the same
# instance now — the world splat is sampled at world XZ, so no per-tile
# uniforms are needed and there's no per-tile material duplication.
# Returns null if the v2 path is inactive or arrays haven't built.
func _make_v2_tile_material(tile_dir: String, coord: Vector2i) -> ShaderMaterial:
	if not _build_v2_arrays_if_needed():
		return null
	return _v2_base_material


func _spawn_tile(coord: Vector2i) -> void:
	if _tiles.has(coord):
		return
	# Cache hit: re-attach a previously-unloaded tile instead of rebuilding.
	if _tile_cache.has(coord):
		var cached: Node3D = _tile_cache[coord]
		_tile_cache.erase(coord)
		if is_instance_valid(cached):
			cached.visible = true
			add_child(cached)
			_tiles[coord] = cached
			print("[ScaleWorld] tile %d_%d  cache HIT (free re-attach)" % [coord.x, coord.y])
			return
	var tile_node: Node3D = Node3D.new()
	tile_node.name = "Tile_%d_%d" % [coord.x, coord.y]
	tile_node.set_script(_tile_script)
	var tile_dir: String = "%stiles/tile_%d_%d/" % [bundle_dir, coord.x, coord.y]
	tile_node.set("tile_dir", tile_dir)
	# v2 path: per-tile duplicate of the global terrain material with arrays
	# + splat + per-slot indices uniforms set. Falls through to the legacy
	# path-based binding if world_v2_material_path is empty.
	var v2_mat: ShaderMaterial = _make_v2_tile_material(tile_dir, coord)
	if v2_mat != null:
		tile_node.set("shared_material", v2_mat)
	else:
		var mat_path: String = _resolve_tile_material_path(tile_dir)
		tile_node.set("shared_material_path", mat_path)
	tile_node.set("resolution_m", tile_resolution_m)
	# Hand the world heightmap reference in so the tile can sample with
	# world coordinates and seamlessly read neighbor data at boundaries.
	tile_node.set("world_height_data", _world_height_data)
	tile_node.set("world_height_w", _world_height_w)
	tile_node.set("world_height_h", _world_height_h)
	tile_node.set("world_size_m", _world_size_m)
	add_child(tile_node)
	_tiles[coord] = tile_node


# Public accessors for camera rig + water plane.
func get_world_size() -> Vector2:
	return Vector2(_world_size_m, _world_size_m)

func get_elev_range() -> Vector2:
	return Vector2(_elev_min_m, _elev_min_m + _elev_range_m)


# View-mode switch. AnchorCameraRig calls this after swapping the
# active camera. Updates `material_override_path` and re-applies the
# matching material to every loaded tile + every cached tile. Cheap:
# Godot's `material_override` reassign is one ref bump per mesh.
# Also bumps `view_radius_tiles` per-view so iso/topdown can load the
# whole world while walk uses the streaming-friendly narrow radius.
func set_view_mode(mode_name: String) -> void:
	var path: String = ""
	var radius_override: int = -1
	match mode_name:
		"walk":
			path = view_material_walk
			radius_override = view_radius_walk
		"iso":
			path = view_material_iso
			radius_override = view_radius_iso
		"topdown":
			path = view_material_topdown
			radius_override = view_radius_topdown

	# Apply per-view radius if specified, and force a repage so the
	# loaded set adjusts. This is what makes iso/topdown show the whole
	# world while walk stays at the streaming radius.
	if radius_override >= 0 and _radius_active:
		view_radius_tiles = radius_override
		_repage(true)
		_drain_pending_now()

	if path.is_empty():
		return  # view not configured; leave whatever material is active
	# When per-biome materials are active, the walk view's per-biome
	# materials are what we want — don't clobber them with a single
	# walk-view material. iso/topdown intentionally still single-material
	# (per-view per-biome shading is a follow-up).
	if mode_name == "walk" and not biome_materials.is_empty():
		material_override_path = ""  # back to biome routing
		for coord in _tiles.keys():
			var tile: Node = _tiles[coord]
			if not is_instance_valid(tile) or not tile.has_method("set_shared_material"):
				continue
			var tdir: String = "%stiles/tile_%d_%d/" % [bundle_dir, coord.x, coord.y]
			var mp: String = _resolve_tile_material_path(tdir)
			var bmat: Resource = load(mp)
			if bmat != null:
				tile.set_shared_material(bmat)
		for coord in _tile_cache.keys():
			var tile: Node = _tile_cache[coord]
			if not is_instance_valid(tile) or not tile.has_method("set_shared_material"):
				continue
			var tdir2: String = "%stiles/tile_%d_%d/" % [bundle_dir, coord.x, coord.y]
			var mp2: String = _resolve_tile_material_path(tdir2)
			var bmat2: Resource = load(mp2)
			if bmat2 != null:
				tile.set_shared_material(bmat2)
		return
	material_override_path = path
	var mat: Resource = load(path)
	if mat == null:
		push_error("ScaleWorld.set_view_mode: cannot load " + path)
		return
	for coord in _tiles.keys():
		var tile: Node = _tiles[coord]
		if is_instance_valid(tile) and tile.has_method("set_shared_material"):
			tile.set_shared_material(mat)
	for coord in _tile_cache.keys():
		var tile: Node = _tile_cache[coord]
		if is_instance_valid(tile) and tile.has_method("set_shared_material"):
			tile.set_shared_material(mat)
