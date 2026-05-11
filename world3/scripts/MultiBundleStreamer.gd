extends Node3D
class_name MultiBundleStreamer

const WorldMapServiceScript = preload("res://scripts/WorldMapService.gd")

# Phase F.7b — multi-bundle streamer.
#
# Reads a world_map.json via WorldMapService and instantiates one
# ChunkLoader per nearby bundle. Each ChunkLoader handles its bundle's
# internal chunks; the streamer is the layer above that decides
# which bundles to keep alive.
#
# Each per-bundle ChunkLoader is offset in world space so its origin
# (0, 0) is the bundle's SW corner. ChunkLoader's existing world-coord
# sampling then maps cleanly into the global world frame.

@export var world_map_path: String = ""
@export var target_path: NodePath
@export var biome_material_template: String = "res://textures/wgv3/terrain_blend_{kit}.tres"
# F.3.2: use M11 fourway material as the shared base. Its shader is
# terrain_splat_unified.gdshader with 4 material slots (grass / dirt /
# rock_light / rock_dark in the shader's nomenclature; in practice
# whatever 4 textures the .tres binds). ChunkLoader will then read each
# bundle's splat_weights_rgba.png and macro/mask, producing the M11
# fourway look on every bundle.
@export var shared_material_path: String = "res://textures/wgv3/terrain_m11_fourway_corner.tres"
@export var chunk_size_m: float = 64.0
@export var chunk_resolution_m: float = 4.0
@export var view_radius_chunks: int = 2
@export var bundle_keep_radius_m: float = 384.0
@export var bundle_drop_radius_m: float = 512.0
@export var preload_ahead_m: float = 256.0
@export var build_collision_chunks: bool = false

# Diagnostics
var loaded_bundles_count: int = 0
var bundles_loaded: int = 0
var bundles_unloaded: int = 0
var last_update_usec: int = 0

var _map: Node = null  # WorldMapService instance
var _target: Node3D
var _bundle_loaders: Dictionary = {}   # bundle_id -> ChunkLoader Node3D
var _last_target_pos: Vector3 = Vector3.ZERO
var _last_target_velocity: Vector3 = Vector3.ZERO


func _ready() -> void:
	_map = WorldMapServiceScript.new()
	_map.world_map_path = world_map_path
	add_child(_map)
	if not _map.load_map():
		push_error("MultiBundleStreamer: failed to load world map " + world_map_path)
		return
	print("[MultiBundleStreamer] target_path=", target_path)
	if target_path != NodePath(""):
		_target = get_node(target_path) as Node3D
	print("[MultiBundleStreamer] _target=", _target)
	if _target != null:
		_last_target_pos = _target.global_position
		print("[MultiBundleStreamer] initial pos=", _target.global_position)
		update_for_position(_target.global_position)
		print("[MultiBundleStreamer] after first update: loaded=", _bundle_loaders.size())


func _process(_delta: float) -> void:
	if _map == null or not _map.is_loaded() or _target == null:
		return
	var pos := _target.global_position
	var velocity := pos - _last_target_pos
	# Smooth velocity over time for direction-aware preload
	_last_target_velocity = _last_target_velocity * 0.7 + velocity * 0.3
	if pos.distance_to(_last_target_pos) > 4.0:
		update_for_position(pos)
		_last_target_pos = pos


func update_for_position(pos: Vector3) -> void:
	var started_usec: int = Time.get_ticks_usec()

	# Direction-aware center: bias the lookup ahead of motion if moving
	var lookup_center := pos
	var speed := _last_target_velocity.length()
	if speed > 0.5:
		var preload_dir := _last_target_velocity.normalized()
		lookup_center = pos + preload_dir * preload_ahead_m

	var nearby: Array = _map.tiles_in_radius(lookup_center, bundle_keep_radius_m)
	var keep_set: Dictionary = {}
	for tile_v: Variant in nearby:
		var tile: Dictionary = tile_v
		keep_set[tile["bundle_id"]] = tile

	# Drop bundles farther than bundle_drop_radius_m
	var drop_check: Array = _map.tiles_in_radius(pos, bundle_drop_radius_m)
	var drop_keep: Dictionary = {}
	for tile_v: Variant in drop_check:
		var tile: Dictionary = tile_v
		drop_keep[tile["bundle_id"]] = true

	# Unload bundles outside drop radius
	for bid in _bundle_loaders.keys():
		if not drop_keep.has(bid):
			var loader: Node = _bundle_loaders[bid]
			if loader != null:
				loader.queue_free()
			_bundle_loaders.erase(bid)
			bundles_unloaded += 1

	# Load bundles within keep radius
	for bid in keep_set.keys():
		if not _bundle_loaders.has(bid):
			_bundle_loaders[bid] = _instantiate_bundle_loader(keep_set[bid])
			bundles_loaded += 1

	# Drive each loaded bundle's chunk update. To make each ChunkLoader
	# render only its own bundle's footprint, we clamp the per-loader
	# "target" to the loader's local source-rect interior. This means a
	# loader near the player gets a normal view-radius around the player,
	# but a loader far from the player gets a target at its own corner,
	# so it only builds chunks in its own footprint.
	var tile_size: float = _map.tile_size_m()
	var half: float = tile_size * 0.5
	for bid_v: Variant in _bundle_loaders.keys():
		var bid: String = bid_v
		var loader: Node3D = _bundle_loaders.get(bid, null) as Node3D
		if loader == null:
			continue
		var loader_origin: Vector3 = loader.global_position
		var local: Vector3 = pos - loader_origin
		# Loader is centered on the bundle center; clamp the per-loader
		# target into the bundle interior so chunks stay inside source.
		var clamped_local: Vector3 = Vector3(
			clampf(local.x, -half, half),
			local.y,
			clampf(local.z, -half, half)
		)
		(loader as ChunkLoader).update_for_position(clamped_local)

	loaded_bundles_count = _bundle_loaders.size()
	last_update_usec = Time.get_ticks_usec() - started_usec


func _instantiate_bundle_loader(tile: Dictionary) -> Node3D:
	var bundle_dir_disk: String = tile.get("bundle_dir", "")
	# bundle_dir is a project-rooted path like "world3/worlds/.../bundles/<bid>"
	# Convert to res:// (we are running from world3/, so res:// strips
	# the leading "world3/").
	var bundle_dir_res := bundle_dir_disk
	if bundle_dir_res.begins_with("world3/"):
		bundle_dir_res = bundle_dir_res.substr(len("world3/"))
	bundle_dir_res = "res://" + bundle_dir_res

	var biome: String = tile.get("biome", "")
	var world_xy: Array = tile.get("world_xy_m", [0.0, 0.0])
	# ChunkLoader assumes the source is centered at the loader's local
	# origin (spans -half..+half in local space). To get that into world
	# space, position the loader at the bundle's CENTER, not its SW
	# corner. The tile's world_xy_m is the SW corner.
	var tile_size_m: float = _map.tile_size_m()
	var origin := Vector3(
		float(world_xy[0]) + tile_size_m * 0.5,
		0.0,
		float(world_xy[1]) + tile_size_m * 0.5
	)

	# F.3.3 — each bundle now emits its own ShaderMaterial .tres at
	# build time (mirroring M11 fourway's pattern). The streamer just
	# loads that .tres directly — no duplication, no manual texture
	# overrides, no runtime sRGB hacks. If a bundle's per-bundle .tres
	# doesn't exist, fall back to the shared template path.
	var per_bundle_material: String = bundle_dir_res + "/material.tres"
	var material_path: String = per_bundle_material
	if not ResourceLoader.exists(per_bundle_material):
		material_path = shared_material_path

	# Instantiate ChunkLoader for this bundle
	var loader: ChunkLoader = ChunkLoader.new()
	loader.name = "Bundle_" + tile.get("bundle_id", "?")
	loader.heightmap_path = bundle_dir_res + "/heightmap.png"
	loader.meta_path = bundle_dir_res + "/meta.json"
	var macro_path: String = bundle_dir_res + "/layers/render_albedo.png"
	var mask_path: String = bundle_dir_res + "/layers/source_valid_mask.png"
	var splat_path: String = bundle_dir_res + "/layers/splat_weights_rgba.png"
	if ResourceLoader.exists(mask_path) or FileAccess.file_exists(mask_path):
		loader.source_valid_mask_path = mask_path
	# F.3.2 — point ChunkLoader at the bundle's splat weights so the
	# shader can blend the 4 material slots per-pixel exactly like M11.
	var splat_exists: bool = ResourceLoader.exists(splat_path) or FileAccess.file_exists(splat_path)
	if splat_exists:
		loader.splat_weights_path = splat_path
	print("[Streamer/splat] bundle=", tile.get("bundle_id"),
		  "  splat_path=", splat_path, "  exists=", splat_exists)
	loader.chunk_size_m = chunk_size_m
	loader.chunk_resolution_m = chunk_resolution_m
	loader.view_radius_chunks = view_radius_chunks
	loader.source_repeat_mode = "clamp"
	# Use ChunkLoader's clip_to_source_bounds so each loader builds only
	# inside its own tile rect. Combined with view_radius_chunks sized to
	# match the tile, this gives clean per-bundle coverage.
	loader.clip_to_source_bounds = true
	# Extend the clip bounds by one full mesh-step so adjacent bundles'
	# edge cells overlap; eliminates sub-mesh-step gaps at boundaries.
	loader.clip_bounds_tolerance_m = chunk_resolution_m
	loader.build_collision_chunks = build_collision_chunks
	loader.auto_update = false  # we drive update_for_position manually

	# F.3.3 — load the per-bundle .tres. Already binds the bundle's
	# macro + weight_mask + splat_weights + 35 slot textures (5 mats × 7 maps),
	# so no manual shader_parameter sets needed. Just set the source-world
	# size so the shader's world-UV macro sampling maps cleanly across
	# the bundle's footprint.
	if ResourceLoader.exists(material_path):
		var base_mat: Resource = load(material_path)
		if base_mat is ShaderMaterial:
			var mat: ShaderMaterial = (base_mat as ShaderMaterial).duplicate()
			mat.set_shader_parameter("source_world_size_m",
									 Vector2(_map.tile_size_m(), _map.tile_size_m()))
			loader.terrain_material = mat
		else:
			loader.terrain_material = base_mat as Material

	# Place this loader at the bundle's world origin
	add_child(loader)
	loader.global_position = origin

	# Tell the loader to update against the player's position
	# (translated into the loader's local frame)
	loader.target_path = NodePath()  # we drive updates manually
	if _target != null:
		var raw_local: Vector3 = _target.global_position - origin
		# Now that loader is at bundle CENTER, source spans -half..+half.
		# Clamp target into the bundle interior so each loader only
		# builds chunks inside its own tile.
		var half: float = tile_size_m * 0.5
		var local: Vector3 = Vector3(
			clampf(raw_local.x, -half, half),
			raw_local.y,
			clampf(raw_local.z, -half, half)
		)
		loader.update_for_position(local)
		var first_chunk: Node = null
		for child in loader.get_children():
			if child is MeshInstance3D:
				first_chunk = child
				break
		var mesh_info: String = "no_mesh_children"
		if first_chunk != null:
			var mi: MeshInstance3D = first_chunk as MeshInstance3D
			var surf_count: int = mi.mesh.get_surface_count() if mi.mesh != null else -1
			var has_mat: bool = mi.material_override != null
			var aabb: AABB = mi.get_aabb()
			mesh_info = "first=%s pos=%s surf=%d mat=%s aabb=%s" % [
				mi.name, str(mi.position), surf_count, str(has_mat), str(aabb)
			]
		print("[Streamer] Bundle ", tile.get("bundle_id"), " at origin=", origin,
			  "  chunks=", loader.get_loaded_chunk_count(),
			  "  ", mesh_info)

	return loader


func _load_srgb_texture(path: String) -> Texture2D:
	"""Load a PNG from disk and wrap as an ImageTexture.

	When the texture is sampled by a shader uniform tagged
	`: source_color`, Godot's sampler applies sRGB -> linear at sample
	time. So the texture data we pass in needs to STAY as raw sRGB
	(don't srgb_to_linear() it ourselves). The ImageTexture created
	from an Image with format RGB8 or RGBA8 has no colorspace tag — the
	shader uniform decides.
	"""
	var f: FileAccess = FileAccess.open(path, FileAccess.READ)
	if f == null:
		return null
	var bytes: PackedByteArray = f.get_buffer(f.get_length())
	f.close()
	var img: Image = Image.new()
	if img.load_png_from_buffer(bytes) != OK:
		return null
	return ImageTexture.create_from_image(img)


func sample_height_global(world_x: float, world_z: float) -> float:
	"""Lookup which bundle owns this position and sample its height."""
	if _map == null or not _map.is_loaded():
		return 0.0
	var tile: Dictionary = _map.tile_for_world_pos(world_x, world_z)
	if tile.is_empty():
		return 0.0
	var bid: String = tile.get("bundle_id", "")
	var loader = _bundle_loaders.get(bid, null)
	if loader == null:
		return 0.0
	var world_xy: Array = tile.get("world_xy_m", [0.0, 0.0])
	# loader.sample_height_global is in the loader's local coord; transform world pos to local
	return float(loader.sample_height_global(world_x - float(world_xy[0]), world_z - float(world_xy[1])))


func get_loaded_bundle_ids() -> Array:
	return _bundle_loaders.keys()
