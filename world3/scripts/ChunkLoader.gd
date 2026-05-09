extends Node3D
class_name ChunkLoader

# Runtime chunk streamer for the M3 size sweep.
#
# Chunks sample one source heightmap through a repeat policy. Mesh vertices are
# local to each chunk, but heights/normals are sampled from global XZ so
# adjacent chunks agree at shared borders. Normals sample one mesh step outside
# the chunk footprint, which avoids the one-sided finite-difference seam seen in
# the Phase F.3 static stitch test.

@export var heightmap_path: String = "res://heightmap/heightmap.png"
@export var heightmap_cache_path: String = ""
@export var meta_path: String = "res://heightmap/meta.json"
@export var source_valid_mask_path: String = ""
@export var source_valid_mask_cache_path: String = ""
@export var terrain_material: Material
@export var splat_weights_path: String = ""
@export var splat_weights_cache_path: String = ""
@export var chunk_size_m: float = 512.0
@export var view_radius_chunks: int = 1
@export var chunk_resolution_m: float = 8.0
@export var max_subdivisions_per_chunk: int = 160
@export var height_scale: float = 1.0
@export_enum("mirror", "wrap", "blend_wrap", "clamp") var source_repeat_mode: String = "mirror"
@export var source_repeat_blend_width_m: float = 96.0
@export var source_repeat_blend_macro_color: bool = true
@export_range(0.0, 1.0, 0.01) var source_repeat_blend_macro_fade: float = 0.0
@export var clip_to_source_bounds: bool = false
@export var target_path: NodePath
@export var auto_update: bool = true
@export var build_collision_chunks: bool = false
@export_flags_3d_physics var collision_layer: int = 1
@export_flags_3d_physics var collision_mask: int = 1
@export var enable_transition_boundaries: bool = false
@export var transition_rules_path: String = "res://jobs/biome_transition_rules.json"
@export var transition_rule_id: String = "biome_desert__grassland_base"
@export_enum("x", "z") var transition_boundary_axis: String = "z"
@export var transition_boundary_world_m: float = 1800.0
@export var transition_width_m: float = 96.0
@export var transition_repeat_m: float = 128.0
@export var transition_mask_resolution: int = 128
@export_range(0.0, 1.0, 0.01) var transition_strength: float = 0.75

var last_update_usec: int = 0
var peak_loaded_chunks: int = 0
var chunks_built: int = 0
var chunks_removed: int = 0
var collision_chunks_built: int = 0
var collision_build_usec_total: int = 0
var collision_build_usec_max: int = 0
var transition_masks_built: int = 0
var transition_mask_build_usec_total: int = 0
var transition_mask_build_usec_max: int = 0

var _chunks: Dictionary = {}
var _height_img: Image
var _source_valid_mask_img: Image
var _img_w: int = 0
var _img_h: int = 0
var _valid_mask_w: int = 0
var _valid_mask_h: int = 0
var _source_size_x_m: float = 1.0
var _source_size_z_m: float = 1.0
var _elev_min_m: float = 0.0
var _elev_range_m: float = 1.0
var _last_center: Vector2i = Vector2i(99999999, 99999999)
var _source_loaded: bool = false
var _transition_rule_loaded: bool = false
var _transition_rule_ok: bool = false
var _transition_rule: Dictionary = {}
var _transition_manifest: Dictionary = {}
var _transition_albedo: Texture2D
var _transition_rough: Texture2D
var _transition_ao: Texture2D
var _transition_from_maps: Dictionary = {}
var _transition_to_maps: Dictionary = {}
var _white_texture: Texture2D


func _ready() -> void:
	if auto_update:
		_load_source()


func _process(_delta: float) -> void:
	if not auto_update:
		return
	var target: Node3D = get_node_or_null(target_path) as Node3D
	if target == null:
		return
	var center: Vector2i = chunk_coords_for(target.global_position)
	if center != _last_center:
		update_for_position(target.global_position)


func configure_for_sweep(new_chunk_size_m: float, new_chunk_resolution_m: float) -> void:
	chunk_size_m = new_chunk_size_m
	chunk_resolution_m = new_chunk_resolution_m
	clear_chunks()
	reset_metrics()


func reset_metrics() -> void:
	last_update_usec = 0
	peak_loaded_chunks = _chunks.size()
	chunks_built = 0
	chunks_removed = 0
	collision_chunks_built = 0
	collision_build_usec_total = 0
	collision_build_usec_max = 0
	transition_masks_built = 0
	transition_mask_build_usec_total = 0
	transition_mask_build_usec_max = 0


func clear_chunks() -> void:
	for key in _chunks.keys():
		var node: Node = _chunks[key] as Node
		if node != null:
			node.queue_free()
	_chunks.clear()
	_last_center = Vector2i(99999999, 99999999)


func get_loaded_chunk_count() -> int:
	return _chunks.size()


func chunk_coords_for(pos: Vector3) -> Vector2i:
	return Vector2i(floori(pos.x / chunk_size_m), floori(pos.z / chunk_size_m))


func update_for_position(pos: Vector3) -> void:
	if not _source_loaded:
		_load_source()
	if not _source_loaded:
		return

	var started_usec: int = Time.get_ticks_usec()
	var center: Vector2i = chunk_coords_for(pos)
	var wanted: Dictionary = {}
	for cz in range(center.y - view_radius_chunks, center.y + view_radius_chunks + 1):
		for cx in range(center.x - view_radius_chunks, center.x + view_radius_chunks + 1):
			var key: String = _chunk_key(cx, cz)
			wanted[key] = Vector2i(cx, cz)

	for key in _chunks.keys():
		if not wanted.has(key):
			var old_chunk: Node = _chunks[key] as Node
			if old_chunk != null:
				old_chunk.queue_free()
			_chunks.erase(key)
			chunks_removed += 1

	for key in wanted.keys():
		if not _chunks.has(key):
			var coords: Vector2i = wanted[key]
			_chunks[key] = _build_chunk(coords.x, coords.y)
			chunks_built += 1

	_last_center = center
	peak_loaded_chunks = max(peak_loaded_chunks, _chunks.size())
	last_update_usec = Time.get_ticks_usec() - started_usec


func sample_height_global(global_x: float, global_z: float) -> float:
	if not _source_loaded:
		_load_source()
	if not _source_loaded:
		return 0.0
	return _sample_height_global(global_x, global_z)


func _load_source() -> void:
	var meta: Dictionary = _load_meta()
	if meta.is_empty():
		push_error("ChunkLoader: failed to load meta " + meta_path)
		return

	_height_img = RuntimeImageCache.load_image(heightmap_cache_path, heightmap_path)
	if _height_img == null:
		push_error("ChunkLoader: failed to load heightmap " + heightmap_path)
		return

	var world_size: float = float(meta.get("world_size_m", 1024.0))
	_source_size_x_m = float(meta.get("world_size_x_m", world_size))
	_source_size_z_m = float(meta.get("world_size_z_m", world_size))
	_elev_min_m = float(meta.get("elevation_min_m", 0.0))
	_elev_range_m = float(meta.get("elevation_range_m", 1.0))
	_img_w = _height_img.get_width()
	_img_h = _height_img.get_height()
	if source_valid_mask_path != "":
		_source_valid_mask_img = RuntimeImageCache.load_image(source_valid_mask_cache_path, source_valid_mask_path)
		if _source_valid_mask_img == null:
			push_warning("ChunkLoader: failed to load source valid mask " + source_valid_mask_path)
		else:
			_valid_mask_w = _source_valid_mask_img.get_width()
			_valid_mask_h = _source_valid_mask_img.get_height()

	if terrain_material is ShaderMaterial:
		var sm: ShaderMaterial = terrain_material as ShaderMaterial
		sm.set_shader_parameter("elev_min_m", _elev_min_m)
		sm.set_shader_parameter("elev_range_m", _elev_range_m)
		sm.set_shader_parameter("use_source_macro_world_uv", true)
		sm.set_shader_parameter("source_world_size_m", Vector2(_source_size_x_m, _source_size_z_m))
		sm.set_shader_parameter("source_repeat_mode_code", _source_repeat_mode_code())
		sm.set_shader_parameter("use_source_macro_seam_blend", source_repeat_mode == "blend_wrap" and source_repeat_blend_macro_color)
		sm.set_shader_parameter("source_macro_seam_fade", source_repeat_blend_macro_fade)
		sm.set_shader_parameter(
			"source_macro_seam_width_uv",
			Vector2(
				clamp(source_repeat_blend_width_m / max(_source_size_x_m, 0.001), 0.0, 0.49),
				clamp(source_repeat_blend_width_m / max(_source_size_z_m, 0.001), 0.0, 0.49)
			)
		)
		if splat_weights_path != "":
			var splat_tex: Texture2D = _load_runtime_texture(splat_weights_cache_path, splat_weights_path)
			if splat_tex != null:
				sm.set_shader_parameter("splat_weights", splat_tex)

	_source_loaded = true


func _load_runtime_texture(cache_path: String, path: String) -> Texture2D:
	return RuntimeImageCache.load_texture(cache_path, path)


func _load_meta() -> Dictionary:
	return _load_json(meta_path)


func _load_json(path: String) -> Dictionary:
	var f: FileAccess = FileAccess.open(path, FileAccess.READ)
	if f == null:
		return {}
	var txt: String = f.get_as_text()
	f.close()
	var parsed: Variant = JSON.parse_string(txt)
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	return parsed


func _res_path(path: String) -> String:
	if path.begins_with("res://"):
		return path
	if path.begins_with("world3/"):
		return "res://" + path.substr(7)
	return path


func _hash2(x: float, y: float) -> float:
	return fposmod(sin(x * 12.9898 + y * 78.233) * 43758.5453, 1.0)


func _smoothstep(edge0: float, edge1: float, x: float) -> float:
	var t: float = clamp((x - edge0) / max(edge1 - edge0, 0.000001), 0.0, 1.0)
	return t * t * (3.0 - 2.0 * t)


func _build_chunk(cx: int, cz: int) -> MeshInstance3D:
	var mesh_instance: MeshInstance3D = MeshInstance3D.new()
	mesh_instance.name = "Chunk_%d_%d" % [cx, cz]
	mesh_instance.position = Vector3(
		(float(cx) + 0.5) * chunk_size_m,
		0.0,
		(float(cz) + 0.5) * chunk_size_m
	)
	mesh_instance.mesh = _build_chunk_mesh(cx, cz)
	mesh_instance.material_override = _material_for_chunk(cx, cz)
	if build_collision_chunks:
		_add_collision(mesh_instance)
	add_child(mesh_instance)
	return mesh_instance


func _material_for_chunk(cx: int, cz: int) -> Material:
	if not enable_transition_boundaries:
		return terrain_material
	if not _ensure_transition_rule_loaded():
		return terrain_material
	if not terrain_material is ShaderMaterial:
		return terrain_material

	var mat: ShaderMaterial = (terrain_material as ShaderMaterial).duplicate()
	_bind_boundary_side_material(mat, _chunk_is_to_side(cx, cz))
	if not _chunk_intersects_transition(cx, cz):
		mat.set_shader_parameter("use_transition_strip", false)
		mat.set_shader_parameter("use_transition_mask", false)
		return mat

	mat.set_shader_parameter("use_transition_strip", false)
	mat.set_shader_parameter("use_transition_mask", true)
	mat.set_shader_parameter("transition_mask", _build_transition_mask_texture(cx, cz))
	mat.set_shader_parameter("transition_albedo", _transition_albedo)
	mat.set_shader_parameter("transition_rough", _transition_rough)
	mat.set_shader_parameter("transition_ao", _transition_ao)
	mat.set_shader_parameter("transition_strength", transition_strength)
	return mat


func _chunk_is_to_side(cx: int, cz: int) -> bool:
	var center_v: float = (float(cx if transition_boundary_axis == "x" else cz) + 0.5) * chunk_size_m
	return center_v >= transition_boundary_world_m


func _chunk_intersects_transition(cx: int, cz: int) -> bool:
	if not enable_transition_boundaries:
		return false
	var min_v: float = float(cx if transition_boundary_axis == "x" else cz) * chunk_size_m
	var max_v: float = min_v + chunk_size_m
	var half_width: float = transition_width_m * 0.5
	return transition_boundary_world_m >= min_v - half_width and transition_boundary_world_m <= max_v + half_width


func _ensure_transition_rule_loaded() -> bool:
	if _transition_rule_loaded:
		return _transition_rule_ok
	_transition_rule_loaded = true

	var rules_doc: Dictionary = _load_json(transition_rules_path)
	for rule in rules_doc.get("rules", []):
		if typeof(rule) == TYPE_DICTIONARY and str(rule.get("id", "")) == transition_rule_id and bool(rule.get("enabled", false)):
			_transition_rule = rule
			break
	if _transition_rule.is_empty():
		push_warning("ChunkLoader: transition rule not found: " + transition_rule_id)
		return false

	var manifest_path: String = _res_path(str(_transition_rule.get("transition_manifest", "")))
	_transition_manifest = _load_json(manifest_path)
	if _transition_manifest.is_empty():
		push_warning("ChunkLoader: failed to load transition manifest: " + manifest_path)
		return false

	var catalog_path: String = _res_path(str(rules_doc.get("material_catalog", "world3/materials/catalog.json")))
	var catalog_doc: Dictionary = _load_json(catalog_path)
	_transition_from_maps = _load_catalog_texture_set(catalog_doc, str(_transition_rule.get("from_material", "")))
	_transition_to_maps = _load_catalog_texture_set(catalog_doc, str(_transition_rule.get("to_material", "")))
	if _transition_from_maps.is_empty() or _transition_to_maps.is_empty():
		push_warning("ChunkLoader: failed to load transition side materials for rule: " + transition_rule_id)
		return false

	var outputs: Dictionary = _transition_manifest.get("outputs", {})
	_transition_albedo = RuntimeImageCache.load_texture("", _res_path(str(outputs.get("albedo", ""))))
	_transition_rough = RuntimeImageCache.load_texture("", _res_path(str(outputs.get("roughness", ""))))
	_transition_ao = RuntimeImageCache.load_texture("", _res_path(str(outputs.get("ao", ""))))
	_transition_rule_ok = _transition_albedo != null and _transition_rough != null and _transition_ao != null
	if not _transition_rule_ok:
		push_warning("ChunkLoader: failed to load transition textures for rule: " + transition_rule_id)
	return _transition_rule_ok


func _load_catalog_texture_set(catalog_doc: Dictionary, material_id: String) -> Dictionary:
	var material: Dictionary = {}
	for entry in catalog_doc.get("materials", []):
		if typeof(entry) == TYPE_DICTIONARY and str(entry.get("id", "")) == material_id:
			material = entry
			break
	if material.is_empty():
		return {}

	var pbr_maps: Dictionary = material.get("pbr_maps", {})
	var textures: Dictionary = {}
	for channel in ["albedo", "normal", "roughness", "ao"]:
		var path: String = str(pbr_maps.get(channel, ""))
		if path == "" or path == "<null>":
			continue
		var tex: Texture2D = RuntimeImageCache.load_texture("", _res_path(path))
		if tex != null:
			textures[channel] = tex
	if not textures.has("albedo") or not textures.has("normal") or not textures.has("roughness"):
		return {}
	return textures


func _bind_boundary_side_material(mat: ShaderMaterial, use_to_side: bool) -> void:
	var maps: Dictionary = _transition_to_maps if use_to_side else _transition_from_maps
	for slot in ["grass", "dirt", "rock_light", "rock_dark", "snow"]:
		mat.set_shader_parameter(slot + "_albedo", maps.get("albedo"))
		mat.set_shader_parameter(slot + "_normal", maps.get("normal"))
		mat.set_shader_parameter(slot + "_rough", maps.get("roughness"))
		mat.set_shader_parameter(slot + "_ao", maps.get("ao", _get_white_texture()))
		mat.set_shader_parameter(slot + "_detail_albedo", maps.get("albedo"))
		mat.set_shader_parameter(slot + "_detail_normal", maps.get("normal"))
		mat.set_shader_parameter(slot + "_detail_rough", maps.get("roughness"))


func _get_white_texture() -> Texture2D:
	if _white_texture != null:
		return _white_texture
	var img: Image = Image.create(1, 1, false, Image.FORMAT_RGBA8)
	img.set_pixel(0, 0, Color.WHITE)
	_white_texture = ImageTexture.create_from_image(img)
	return _white_texture


func _build_transition_mask_texture(cx: int, cz: int) -> Texture2D:
	var started_usec: int = Time.get_ticks_usec()
	var n: int = clampi(transition_mask_resolution, 16, 1024)
	var img: Image = Image.create(n, n, false, Image.FORMAT_RGBA8)
	var min_x: float = float(cx) * chunk_size_m
	var min_z: float = float(cz) * chunk_size_m
	var width_m: float = max(transition_width_m, 0.001)
	var repeat_m: float = max(transition_repeat_m, 0.001)
	var tuning: Dictionary = _transition_rule.get("tuning", {})
	var noise_strength: float = float(tuning.get("noise_strength", 0.0))

	for y in range(n):
		for x in range(n):
			var fx: float = (float(x) + 0.5) / float(n)
			var fz: float = (float(y) + 0.5) / float(n)
			var global_x: float = min_x + fx * chunk_size_m
			var global_z: float = min_z + fz * chunk_size_m
			var across: float = global_x if transition_boundary_axis == "x" else global_z
			var along: float = global_z if transition_boundary_axis == "x" else global_x
			var noisy_offset: float = (_hash2(global_x * 0.035, global_z * 0.035) - 0.5) * width_m * noise_strength
			var raw_local: float = ((across - transition_boundary_world_m) + noisy_offset) / width_m + 0.5
			var inside: float = 1.0 if raw_local >= 0.0 and raw_local <= 1.0 else 0.0
			var band: float = inside * _smoothstep(0.0, 0.12, raw_local) * (1.0 - _smoothstep(0.88, 1.0, raw_local))
			var transition_u: float = clamp(raw_local, 0.0, 1.0)
			var transition_v: float = fposmod(along / repeat_m, 1.0)
			img.set_pixel(x, y, Color(band, transition_u, transition_v, 1.0))

	var tex: ImageTexture = ImageTexture.create_from_image(img)
	var elapsed: int = Time.get_ticks_usec() - started_usec
	transition_masks_built += 1
	transition_mask_build_usec_total += elapsed
	transition_mask_build_usec_max = maxi(transition_mask_build_usec_max, elapsed)
	return tex


func _add_collision(mesh_instance: MeshInstance3D) -> void:
	var started_usec: int = Time.get_ticks_usec()
	var body: StaticBody3D = StaticBody3D.new()
	body.name = "Collision"
	body.collision_layer = collision_layer
	body.collision_mask = collision_mask
	var shape: CollisionShape3D = CollisionShape3D.new()
	shape.name = "Shape"
	shape.shape = mesh_instance.mesh.create_trimesh_shape()
	body.add_child(shape)
	mesh_instance.add_child(body)
	var elapsed: int = Time.get_ticks_usec() - started_usec
	collision_chunks_built += 1
	collision_build_usec_total += elapsed
	collision_build_usec_max = maxi(collision_build_usec_max, elapsed)


func _build_chunk_mesh(cx: int, cz: int) -> ArrayMesh:
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

	var min_x: float = float(cx) * chunk_size_m
	var min_z: float = float(cz) * chunk_size_m
	var half_size: float = chunk_size_m * 0.5
	var mesh_step: float = chunk_size_m / float(n)

	for z in range(n + 1):
		for x in range(n + 1):
			var i: int = z * (n + 1) + x
			var fx: float = float(x) / float(n)
			var fz: float = float(z) / float(n)
			var global_x: float = min_x + fx * chunk_size_m
			var global_z: float = min_z + fz * chunk_size_m
			var elev: float = _sample_height_global(global_x, global_z)
			verts[i] = Vector3(fx * chunk_size_m - half_size, elev, fz * chunk_size_m - half_size)
			uvs[i] = Vector2(
				_source_fraction(global_x, _source_size_x_m),
				_source_fraction(global_z, _source_size_z_m)
			)
			uv2s[i] = Vector2(fx, fz)
			normals[i] = _sample_normal_global(global_x, global_z, mesh_step)

	indices.resize(n * n * 6)
	var k: int = 0
	for z in range(n):
		for x in range(n):
			if clip_to_source_bounds and not _cell_inside_source_bounds(min_x, min_z, x, z, mesh_step):
				continue
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


func _subdivisions_for_chunk() -> int:
	var n: int = int(round(chunk_size_m / max(chunk_resolution_m, 1.0)))
	return clampi(n, 8, max_subdivisions_per_chunk)


func _cell_inside_source_bounds(min_x: float, min_z: float, x: int, z: int, step_m: float) -> bool:
	return (
		_inside_source_bounds(min_x + float(x) * step_m, min_z + float(z) * step_m)
		and _inside_source_bounds(min_x + float(x + 1) * step_m, min_z + float(z) * step_m)
		and _inside_source_bounds(min_x + float(x) * step_m, min_z + float(z + 1) * step_m)
		and _inside_source_bounds(min_x + float(x + 1) * step_m, min_z + float(z + 1) * step_m)
	)


func _inside_source_bounds(global_x: float, global_z: float) -> bool:
	var half_x: float = _source_size_x_m * 0.5
	var half_z: float = _source_size_z_m * 0.5
	var in_bounds: bool = (
		global_x >= -half_x
		and global_x <= half_x
		and global_z >= -half_z
		and global_z <= half_z
	)
	if not in_bounds:
		return false
	if _source_valid_mask_img == null:
		return true
	return _sample_source_valid_mask(global_x, global_z) >= 0.5


func _sample_source_valid_mask(global_x: float, global_z: float) -> float:
	if _source_valid_mask_img == null or _valid_mask_w < 1 or _valid_mask_h < 1:
		return 1.0
	var fx: float = _clamped_fraction(global_x, _source_size_x_m)
	var fz: float = _clamped_fraction(global_z, _source_size_z_m)
	var px: int = clampi(int(round(fx * float(_valid_mask_w - 1))), 0, _valid_mask_w - 1)
	var pz: int = clampi(int(round(fz * float(_valid_mask_h - 1))), 0, _valid_mask_h - 1)
	return _source_valid_mask_img.get_pixel(px, pz).r


func _sample_normal_global(global_x: float, global_z: float, spacing_m: float) -> Vector3:
	var hl: float = _sample_height_global(global_x - spacing_m, global_z)
	var hr: float = _sample_height_global(global_x + spacing_m, global_z)
	var hd: float = _sample_height_global(global_x, global_z - spacing_m)
	var hu: float = _sample_height_global(global_x, global_z + spacing_m)
	var dhx: float = (hr - hl) / max(spacing_m * 2.0, 0.001)
	var dhz: float = (hu - hd) / max(spacing_m * 2.0, 0.001)
	return Vector3(-dhx, 1.0, -dhz).normalized()


func _sample_height_global(global_x: float, global_z: float) -> float:
	if source_repeat_mode == "blend_wrap":
		return _sample_height_global_blend_wrap(global_x, global_z)
	var fx: float = _source_fraction(global_x, _source_size_x_m)
	var fz: float = _source_fraction(global_z, _source_size_z_m)
	var nrm: float = _sample_height_fraction(fx, fz)
	return _elev_min_m + nrm * _elev_range_m * height_scale


func _sample_height_global_blend_wrap(global_x: float, global_z: float) -> float:
	var fx: float = _wrapped_fraction(global_x, _source_size_x_m)
	var fz: float = _wrapped_fraction(global_z, _source_size_z_m)
	var nrm: float = _sample_height_fraction(fx, fz)
	var wx: float = clamp(source_repeat_blend_width_m / max(_source_size_x_m, 0.001), 0.0, 0.49)
	var wz: float = clamp(source_repeat_blend_width_m / max(_source_size_z_m, 0.001), 0.0, 0.49)
	if wx > 0.0:
		var edge_x: float = max(1.0 - _smoothstep(0.0, wx, fx), _smoothstep(1.0 - wx, 1.0, fx))
		if edge_x > 0.0:
			var alt_x: float = _sample_height_fraction(1.0 - fx, fz)
			nrm = lerp(nrm, (nrm + alt_x) * 0.5, edge_x)
	if wz > 0.0:
		var edge_z: float = max(1.0 - _smoothstep(0.0, wz, fz), _smoothstep(1.0 - wz, 1.0, fz))
		if edge_z > 0.0:
			var alt_z: float = _sample_height_fraction(fx, 1.0 - fz)
			nrm = lerp(nrm, (nrm + alt_z) * 0.5, edge_z)
	return _elev_min_m + nrm * _elev_range_m * height_scale


func _source_fraction(v: float, size_m: float) -> float:
	match source_repeat_mode:
		"wrap":
			return _wrapped_fraction(v, size_m)
		"blend_wrap":
			return _wrapped_fraction(v, size_m)
		"clamp":
			return _clamped_fraction(v, size_m)
		_:
			return _mirrored_fraction(v, size_m)


func _source_repeat_mode_code() -> float:
	match source_repeat_mode:
		"wrap":
			return 1.0
		"blend_wrap":
			return 2.0
		"clamp":
			return 3.0
		_:
			return 0.0


func _wrapped_fraction(v: float, size_m: float) -> float:
	return fposmod(v + size_m * 0.5, size_m) / size_m


func _mirrored_fraction(v: float, size_m: float) -> float:
	var period_m: float = max(size_m * 2.0, 0.001)
	var local_m: float = fposmod(v + size_m * 0.5, period_m)
	if local_m <= size_m:
		return local_m / max(size_m, 0.001)
	return (period_m - local_m) / max(size_m, 0.001)


func _clamped_fraction(v: float, size_m: float) -> float:
	return clamp((v + size_m * 0.5) / max(size_m, 0.001), 0.0, 1.0)


func _sample_height_fraction(fx: float, fz: float) -> float:
	var px: float = clamp(fx, 0.0, 1.0) * float(_img_w - 1)
	var pz: float = clamp(fz, 0.0, 1.0) * float(_img_h - 1)
	var x0: int = clampi(int(floor(px)), 0, _img_w - 1)
	var z0: int = clampi(int(floor(pz)), 0, _img_h - 1)
	var x1: int = clampi(x0 + 1, 0, _img_w - 1)
	var z1: int = clampi(z0 + 1, 0, _img_h - 1)
	var tx: float = px - float(x0)
	var tz: float = pz - float(z0)
	var h00: float = _height_img.get_pixel(x0, z0).r
	var h10: float = _height_img.get_pixel(x1, z0).r
	var h01: float = _height_img.get_pixel(x0, z1).r
	var h11: float = _height_img.get_pixel(x1, z1).r
	var hx0: float = lerp(h00, h10, tx)
	var hx1: float = lerp(h01, h11, tx)
	return lerp(hx0, hx1, tz)


func _chunk_key(cx: int, cz: int) -> String:
	return "%d:%d" % [cx, cz]
