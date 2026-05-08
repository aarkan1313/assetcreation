extends Node3D
class_name ChunkLoader

# Runtime chunk streamer for the M3 size sweep.
#
# Chunks sample one source heightmap as an infinite tiled height field. Mesh
# vertices are local to each chunk, but heights/normals are sampled from global
# XZ so adjacent chunks agree at shared borders. Normals sample one mesh step
# outside the chunk footprint, which avoids the one-sided finite-difference seam
# seen in the Phase F.3 static stitch test.

@export var heightmap_path: String = "res://heightmap/heightmap.png"
@export var meta_path: String = "res://heightmap/meta.json"
@export var terrain_material: Material
@export var chunk_size_m: float = 512.0
@export var view_radius_chunks: int = 1
@export var chunk_resolution_m: float = 8.0
@export var max_subdivisions_per_chunk: int = 160
@export var height_scale: float = 1.0
@export var target_path: NodePath
@export var auto_update: bool = true

var last_update_usec: int = 0
var peak_loaded_chunks: int = 0
var chunks_built: int = 0
var chunks_removed: int = 0

var _chunks: Dictionary = {}
var _height_img: Image
var _img_w: int = 0
var _img_h: int = 0
var _source_size_x_m: float = 1.0
var _source_size_z_m: float = 1.0
var _elev_min_m: float = 0.0
var _elev_range_m: float = 1.0
var _last_center: Vector2i = Vector2i(99999999, 99999999)
var _source_loaded: bool = false


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

	_height_img = Image.load_from_file(heightmap_path)
	if _height_img == null:
		var tex: Texture2D = load(heightmap_path) as Texture2D
		if tex != null:
			_height_img = tex.get_image()
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

	if terrain_material is ShaderMaterial:
		var sm: ShaderMaterial = terrain_material as ShaderMaterial
		sm.set_shader_parameter("elev_min_m", _elev_min_m)
		sm.set_shader_parameter("elev_range_m", _elev_range_m)

	_source_loaded = true


func _load_meta() -> Dictionary:
	var f: FileAccess = FileAccess.open(meta_path, FileAccess.READ)
	if f == null:
		return {}
	var txt: String = f.get_as_text()
	f.close()
	var parsed: Variant = JSON.parse_string(txt)
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	return parsed


func _build_chunk(cx: int, cz: int) -> MeshInstance3D:
	var mesh_instance: MeshInstance3D = MeshInstance3D.new()
	mesh_instance.name = "Chunk_%d_%d" % [cx, cz]
	mesh_instance.position = Vector3(
		(float(cx) + 0.5) * chunk_size_m,
		0.0,
		(float(cz) + 0.5) * chunk_size_m
	)
	mesh_instance.mesh = _build_chunk_mesh(cx, cz)
	mesh_instance.material_override = terrain_material
	add_child(mesh_instance)
	return mesh_instance


func _build_chunk_mesh(cx: int, cz: int) -> ArrayMesh:
	var n: int = _subdivisions_for_chunk()
	var vert_count: int = (n + 1) * (n + 1)
	var verts: PackedVector3Array = PackedVector3Array()
	var uvs: PackedVector2Array = PackedVector2Array()
	var normals: PackedVector3Array = PackedVector3Array()
	var indices: PackedInt32Array = PackedInt32Array()
	verts.resize(vert_count)
	uvs.resize(vert_count)
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
			uvs[i] = Vector2(global_x / _source_size_x_m, global_z / _source_size_z_m)
			normals[i] = _sample_normal_global(global_x, global_z, mesh_step)

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

	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = indices

	var am: ArrayMesh = ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return am


func _subdivisions_for_chunk() -> int:
	var n: int = int(round(chunk_size_m / max(chunk_resolution_m, 1.0)))
	return clampi(n, 8, max_subdivisions_per_chunk)


func _sample_normal_global(global_x: float, global_z: float, spacing_m: float) -> Vector3:
	var hl: float = _sample_height_global(global_x - spacing_m, global_z)
	var hr: float = _sample_height_global(global_x + spacing_m, global_z)
	var hd: float = _sample_height_global(global_x, global_z - spacing_m)
	var hu: float = _sample_height_global(global_x, global_z + spacing_m)
	var dhx: float = (hr - hl) / max(spacing_m * 2.0, 0.001)
	var dhz: float = (hu - hd) / max(spacing_m * 2.0, 0.001)
	return Vector3(-dhx, 1.0, -dhz).normalized()


func _sample_height_global(global_x: float, global_z: float) -> float:
	var fx: float = _wrapped_fraction(global_x, _source_size_x_m)
	var fz: float = _wrapped_fraction(global_z, _source_size_z_m)
	var nrm: float = _sample_height_fraction(fx, fz)
	return _elev_min_m + nrm * _elev_range_m * height_scale


func _wrapped_fraction(v: float, size_m: float) -> float:
	return fposmod(v + size_m * 0.5, size_m) / size_m


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
