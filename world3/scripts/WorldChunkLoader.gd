extends Node3D
class_name WorldChunkLoader

# Phase F.3.6 — single-loader, bundle-paged streaming renderer.
#
# Replaces MultiBundleStreamer's "N loaders, one per bundle" approach
# with the M11-tour pattern scaled to a multi-bundle world: ONE chunk
# grid in world space, each chunk samples whichever bundle owns its
# world center.
#
# See F36_M11_STREAMING_ARCHITECTURE_2026_05_11.md for the design note.
#
# Usage (tour scene):
#   var loader := WorldChunkLoader.new()
#   loader.world_map_path = "res://worlds/starter_5biome_procedural/world_map.json"
#   loader.target_path = loader.get_path_to(anchor)
#   add_child(loader)
#
# Mirrors World3AutoReviewTour's _setup_terrain / _apply_source_macro_overrides
# pattern per chunk's owning bundle. Every chunk renders via the same
# material binding sequence the M11 tour uses (which is the only path
# proven to make the macro visible).

const WorldMapServiceScript = preload("res://scripts/WorldMapService.gd")

@export var world_map_path: String = ""
@export var target_path: NodePath
@export var chunk_size_m: float = 64.0
@export var chunk_resolution_m: float = 4.0
@export var view_radius_chunks: int = 6
@export var max_subdivisions_per_chunk: int = 96
@export var auto_update: bool = true
@export var build_collision_chunks: bool = false

# M11-tour render-quality params (mirror World3AutoReviewTour's review_*).
# Apply to every per-chunk material so all chunks render with the M11
# tour's known-good shader-parameter setup.
@export var review_use_source_macro_valid_mask: bool = true
@export_range(0.0, 1.0, 0.01) var review_source_macro_strength: float = 0.84
@export var review_normal_strength: float = 0.050
@export var review_detail_normal_strength: float = 0.014
@export var review_detail_rough_strength: float = 0.018
@export_range(0.0, 2.0, 0.01) var review_roughness_strength: float = 1.0
@export_range(0.04, 1.0, 0.01) var review_roughness_floor: float = 0.87
@export_range(0.0, 1.0, 0.01) var review_specular_strength: float = 0.0
@export_range(0.0, 1.25, 0.01) var review_albedo_gain: float = 0.95

# Per-bundle cache. Keyed by bundle_id, holds resolved textures + meta
# so each bundle's source data is loaded exactly once.
class BundleSources extends RefCounted:
	var bundle_id: String = ""
	var bundle_dir_res: String = ""
	var tile_xy: Vector2i = Vector2i.ZERO
	var origin_world: Vector2 = Vector2.ZERO
	var heightmap_img: Image
	var heightmap_w: int = 0
	var heightmap_h: int = 0
	var elev_min_m: float = 0.0
	var elev_range_m: float = 1.0
	var tile_size_m: float = 256.0
	var macro_tex: Texture2D
	var valid_mask_tex: Texture2D
	var splat_tex: Texture2D
	var material_template: ShaderMaterial


var _map: WorldMapService
var _target: Node3D
var _chunks: Dictionary = {}                 # "cx_cz" -> MeshInstance3D
var _bundles: Dictionary = {}                # bundle_id -> BundleSources
var _last_center: Vector2i = Vector2i(99999999, 99999999)
var _loaded: bool = false

# Diagnostics
var chunks_built: int = 0
var chunks_removed: int = 0
var bundles_loaded: int = 0


func _ready() -> void:
	_map = WorldMapServiceScript.new()
	_map.world_map_path = world_map_path
	add_child(_map)
	if not _map.load_map():
		push_error("WorldChunkLoader: failed to load world_map " + world_map_path)
		return
	_loaded = true
	if auto_update and target_path != NodePath(""):
		_target = get_node_or_null(target_path) as Node3D
		if _target != null:
			update_for_position(_target.global_position)


func _process(_delta: float) -> void:
	if not auto_update or not _loaded:
		return
	if target_path == NodePath(""):
		return
	if _target == null:
		_target = get_node_or_null(target_path) as Node3D
		if _target == null:
			return
	var pos: Vector3 = _target.global_position
	var center: Vector2i = _chunk_coords_for(pos)
	if center != _last_center:
		update_for_position(pos)


func update_for_position(world_pos: Vector3) -> void:
	if not _loaded:
		return
	var center: Vector2i = _chunk_coords_for(world_pos)
	var wanted: Dictionary = {}
	for cz in range(center.y - view_radius_chunks, center.y + view_radius_chunks + 1):
		for cx in range(center.x - view_radius_chunks, center.x + view_radius_chunks + 1):
			wanted[_chunk_key(cx, cz)] = Vector2i(cx, cz)

	for key in _chunks.keys():
		if not wanted.has(key):
			var old: Node = _chunks[key] as Node
			if old != null:
				old.queue_free()
			_chunks.erase(key)
			chunks_removed += 1

	for key in wanted.keys():
		if not _chunks.has(key):
			var coords: Vector2i = wanted[key]
			var mi: MeshInstance3D = _build_world_chunk(coords.x, coords.y)
			if mi != null:
				_chunks[key] = mi
				chunks_built += 1

	_last_center = center


# ----------------------------------------------------------------------
# Per-chunk build
# ----------------------------------------------------------------------

func _build_world_chunk(cx: int, cz: int) -> MeshInstance3D:
	# Chunk's world rect
	var chunk_min_x: float = float(cx) * chunk_size_m
	var chunk_min_z: float = float(cz) * chunk_size_m
	var chunk_center_x: float = chunk_min_x + chunk_size_m * 0.5
	var chunk_center_z: float = chunk_min_z + chunk_size_m * 0.5

	# Which bundle owns this chunk's center?
	var tile: Dictionary = _map.tile_for_world_pos(chunk_center_x, chunk_center_z)
	if tile.is_empty():
		return null

	var bundle: BundleSources = _ensure_bundle_loaded(tile)
	if bundle == null:
		return null

	# Build mesh in world coords, sample heights from the owning bundle
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.name = "Chunk_%d_%d" % [cx, cz]
	# Place chunk so its local origin = chunk center; world position
	# = chunk center.
	mi.position = Vector3(chunk_center_x, 0.0, chunk_center_z)
	mi.mesh = _build_chunk_mesh(cx, cz, chunk_min_x, chunk_min_z)
	if mi.mesh.get_surface_count() == 0:
		mi.queue_free()
		return null
	mi.material_override = _build_chunk_material(bundle)
	add_child(mi)
	return mi


func _build_chunk_mesh(cx: int, cz: int, min_x: float, min_z: float) -> ArrayMesh:
	var n: int = _subdivisions_for_chunk()
	var vert_count: int = (n + 1) * (n + 1)
	var verts: PackedVector3Array = PackedVector3Array()
	var uvs: PackedVector2Array = PackedVector2Array()
	var uv2s: PackedVector2Array = PackedVector2Array()
	var normals: PackedVector3Array = PackedVector3Array()
	var indices: PackedInt32Array = PackedInt32Array()
	verts.resize(vert_count)
	uvs.resize(vert_count)
	uv2s.resize(vert_count)
	normals.resize(vert_count)

	var half_size: float = chunk_size_m * 0.5
	var mesh_step: float = chunk_size_m / float(n)

	for z in range(n + 1):
		for x in range(n + 1):
			var i: int = z * (n + 1) + x
			var fx: float = float(x) / float(n)
			var fz: float = float(z) / float(n)
			var world_x: float = min_x + fx * chunk_size_m
			var world_z: float = min_z + fz * chunk_size_m
			var elev: float = _sample_height_world(world_x, world_z)
			verts[i] = Vector3(fx * chunk_size_m - half_size, elev, fz * chunk_size_m - half_size)
			uv2s[i] = Vector2(fx, fz)
			# UV0 = world-relative source-UV inside the owning bundle.
			# Shader uses this for source_macro_albedo sampling; the
			# macro tiles seamlessly across chunks belonging to the
			# same bundle because every chunk binds that bundle's
			# macro and computes the same world-relative UV.
			var owning: Dictionary = _map.tile_for_world_pos(world_x, world_z)
			if owning.is_empty():
				uvs[i] = Vector2(0.0, 0.0)
			else:
				var owning_origin: Array = owning.get("world_xy_m", [0.0, 0.0])
				var local_x: float = world_x - float(owning_origin[0])
				var local_z: float = world_z - float(owning_origin[1])
				uvs[i] = Vector2(local_x / _map.tile_size_m(), local_z / _map.tile_size_m())
			normals[i] = _sample_normal_world(world_x, world_z, mesh_step)

	indices.resize(n * n * 6)
	var k: int = 0
	for z in range(n):
		for x in range(n):
			var i00: int = z * (n + 1) + x
			var i10: int = i00 + 1
			var i01: int = i00 + (n + 1)
			var i11: int = i01 + 1
			indices[k] = i00; k += 1
			indices[k] = i11; k += 1
			indices[k] = i01; k += 1
			indices[k] = i00; k += 1
			indices[k] = i10; k += 1
			indices[k] = i11; k += 1
	indices.resize(k)
	if k == 0:
		return ArrayMesh.new()

	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_TEX_UV2] = uv2s
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = indices

	var am: ArrayMesh = ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return am


func _build_chunk_material(bundle: BundleSources) -> Material:
	# Mirror World3AutoReviewTour._setup_terrain + _apply_source_macro_overrides
	# exactly. This is the only render path proven to make the baked
	# macro visible after duplicate().
	if bundle.material_template == null:
		return null
	var mat: ShaderMaterial = bundle.material_template.duplicate() as ShaderMaterial
	mat.set_shader_parameter("use_transition_strip", false)
	mat.set_shader_parameter("use_transition_mask", false)
	mat.set_shader_parameter("use_source_macro_valid_mask", review_use_source_macro_valid_mask)
	mat.set_shader_parameter("source_macro_strength", review_source_macro_strength)
	mat.set_shader_parameter("normal_strength", review_normal_strength)
	mat.set_shader_parameter("detail_normal_strength", review_detail_normal_strength)
	mat.set_shader_parameter("detail_rough_strength", review_detail_rough_strength)
	mat.set_shader_parameter("roughness_strength", review_roughness_strength)
	mat.set_shader_parameter("roughness_floor", review_roughness_floor)
	mat.set_shader_parameter("specular_strength", review_specular_strength)
	mat.set_shader_parameter("albedo_gain", review_albedo_gain)
	mat.set_shader_parameter("elev_min_m", bundle.elev_min_m)
	mat.set_shader_parameter("elev_range_m", bundle.elev_range_m)
	mat.set_shader_parameter("use_source_macro_world_uv", false)
	mat.set_shader_parameter("source_world_size_m", Vector2(bundle.tile_size_m, bundle.tile_size_m))
	if bundle.macro_tex != null:
		mat.set_shader_parameter("source_macro_albedo", bundle.macro_tex)
		mat.set_shader_parameter("use_source_macro_albedo", true)
	if bundle.valid_mask_tex != null:
		mat.set_shader_parameter("source_macro_valid_mask", bundle.valid_mask_tex)
	if bundle.splat_tex != null:
		mat.set_shader_parameter("splat_weights", bundle.splat_tex)
		mat.set_shader_parameter("use_splat_weights", true)
	return mat


# ----------------------------------------------------------------------
# Bundle cache
# ----------------------------------------------------------------------

func _ensure_bundle_loaded(tile: Dictionary) -> BundleSources:
	var bid: String = String(tile.get("bundle_id", ""))
	if bid == "":
		return null
	var cached = _bundles.get(bid, null)
	if cached != null:
		return cached

	var bundle_dir_raw: String = String(tile.get("bundle_dir", ""))
	if bundle_dir_raw == "":
		push_error("WorldChunkLoader: tile %s has no bundle_dir" % bid)
		return null
	var bundle_dir_res: String = _to_res_path(bundle_dir_raw)

	var b: BundleSources = BundleSources.new()
	b.bundle_id = bid
	b.bundle_dir_res = bundle_dir_res
	var xy: Array = tile.get("tile_xy", [0, 0])
	b.tile_xy = Vector2i(int(xy[0]), int(xy[1]))
	var origin: Array = tile.get("world_xy_m", [0.0, 0.0])
	b.origin_world = Vector2(float(origin[0]), float(origin[1]))
	b.tile_size_m = _map.tile_size_m()

	# Meta — elev range
	var meta: Dictionary = _load_json(bundle_dir_res + "/meta.json")
	b.elev_min_m = float(meta.get("elevation_min_m", 0.0))
	b.elev_range_m = float(meta.get("elevation_range_m", 1.0))

	# Heightmap as Image (CPU sampling) + load runtime textures for shader
	var hm_path: String = bundle_dir_res + "/heightmap.png"
	b.heightmap_img = RuntimeImageCache.load_image("", hm_path)
	if b.heightmap_img == null:
		push_error("WorldChunkLoader: failed to load heightmap " + hm_path)
		return null
	b.heightmap_w = b.heightmap_img.get_width()
	b.heightmap_h = b.heightmap_img.get_height()

	var macro_path: String = bundle_dir_res + "/layers/render_albedo.png"
	var mask_path: String = bundle_dir_res + "/layers/source_valid_mask.png"
	var splat_path: String = bundle_dir_res + "/layers/splat_weights_rgba.png"
	if ResourceLoader.exists(macro_path) or FileAccess.file_exists(macro_path):
		b.macro_tex = RuntimeImageCache.load_texture("", macro_path)
	if ResourceLoader.exists(mask_path) or FileAccess.file_exists(mask_path):
		b.valid_mask_tex = RuntimeImageCache.load_texture("", mask_path)
	if ResourceLoader.exists(splat_path) or FileAccess.file_exists(splat_path):
		b.splat_tex = RuntimeImageCache.load_texture("", splat_path)

	# Material template — load and keep the original; per-chunk we
	# duplicate this and apply review_* + texture bindings.
	var mat_path: String = bundle_dir_res + "/material.tres"
	if ResourceLoader.exists(mat_path):
		var base = load(mat_path)
		if base is ShaderMaterial:
			b.material_template = base as ShaderMaterial
		else:
			push_warning("WorldChunkLoader: %s is not ShaderMaterial" % mat_path)
	if b.material_template == null:
		push_error("WorldChunkLoader: no material template for bundle " + bid)
		return null

	_bundles[bid] = b
	bundles_loaded += 1
	return b


# ----------------------------------------------------------------------
# Height + normal sampling
# ----------------------------------------------------------------------

func _sample_height_world(world_x: float, world_z: float) -> float:
	"""Sample height at any world XZ by routing to the owning bundle's
	heightmap. Bundles outside the map return 0 (out of bounds — F.3.1
	guarantees seam values agree, so chunks straddling bundle edges
	stitch cleanly without an explicit blend)."""
	var tile: Dictionary = _map.tile_for_world_pos(world_x, world_z)
	if tile.is_empty():
		return 0.0
	var bid: String = String(tile.get("bundle_id", ""))
	var bundle = _bundles.get(bid, null)
	if bundle == null:
		# Lazy-load on demand for vertex sampling at chunk edges
		bundle = _ensure_bundle_loaded(tile)
		if bundle == null:
			return 0.0
	var origin: Array = tile.get("world_xy_m", [0.0, 0.0])
	var local_x: float = world_x - float(origin[0])
	var local_z: float = world_z - float(origin[1])
	var fx: float = clamp(local_x / bundle.tile_size_m, 0.0, 1.0)
	var fz: float = clamp(local_z / bundle.tile_size_m, 0.0, 1.0)
	var px: int = clampi(int(round(fx * float(bundle.heightmap_w - 1))), 0, bundle.heightmap_w - 1)
	var pz: int = clampi(int(round(fz * float(bundle.heightmap_h - 1))), 0, bundle.heightmap_h - 1)
	var c: Color = bundle.heightmap_img.get_pixel(px, pz)
	# 16-bit single-channel PNG stores normalized in R
	var elev_norm: float = c.r
	return bundle.elev_min_m + elev_norm * bundle.elev_range_m


func _sample_normal_world(world_x: float, world_z: float, spacing_m: float) -> Vector3:
	var hl: float = _sample_height_world(world_x - spacing_m, world_z)
	var hr: float = _sample_height_world(world_x + spacing_m, world_z)
	var hd: float = _sample_height_world(world_x, world_z - spacing_m)
	var hu: float = _sample_height_world(world_x, world_z + spacing_m)
	var dhx: float = (hr - hl) / max(spacing_m * 2.0, 0.001)
	var dhz: float = (hu - hd) / max(spacing_m * 2.0, 0.001)
	return Vector3(-dhx, 1.0, -dhz).normalized()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

func _subdivisions_for_chunk() -> int:
	var n: int = int(round(chunk_size_m / max(chunk_resolution_m, 1.0)))
	return clampi(n, 8, max_subdivisions_per_chunk)


func _chunk_coords_for(pos: Vector3) -> Vector2i:
	return Vector2i(floori(pos.x / chunk_size_m), floori(pos.z / chunk_size_m))


func _chunk_key(cx: int, cz: int) -> String:
	return "%d_%d" % [cx, cz]


func _to_res_path(p: String) -> String:
	if p.begins_with("res://"):
		return p
	if p.begins_with("world3/"):
		return "res://" + p.substr(7)
	# Otherwise assume it's already valid
	return p


func _load_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var f: FileAccess = FileAccess.open(path, FileAccess.READ)
	if f == null:
		return {}
	var txt: String = f.get_as_text()
	f.close()
	var parsed: Variant = JSON.parse_string(txt)
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	return parsed


func sample_height_global(world_x: float, world_z: float) -> float:
	"""Public API — height lookup at any world position."""
	if not _loaded:
		return 0.0
	return _sample_height_world(world_x, world_z)


func get_loaded_chunk_count() -> int:
	return _chunks.size()


func get_loaded_bundle_count() -> int:
	return _bundles.size()
