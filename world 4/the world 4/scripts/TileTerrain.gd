extends Node3D
class_name TileTerrain

# W4 scale demo — one tile of a multi-tile world.
#
# Refactor of AnchorTerrain.gd that handles a SINGLE 256m tile out of a
# larger grid. Each instance loads its own per-tile heightmap and builds
# its mesh translated to the tile's world origin so adjacent tiles meet
# seamlessly in world space.
#
# UV continuity across tiles: the v2 terrain shader computes UVs from
# world_pos.xz (not from mesh UV0). So as long as each tile's mesh is
# positioned correctly in world space via translate(), textures tile
# continuously across tile boundaries automatically. No per-tile UV math
# adjustment needed.
#
# Each tile is built with cast_shadow=OFF (terrain-self-shadow artifact
# fix from the anchor build) and tangents generated via SurfaceTool (PBR
# normal-map fix). Same as AnchorTerrain.

@export var tile_dir: String = ""              # "res://worlds/scale_demo/tiles/tile_0_0/"
@export var shared_material_path: String = ""  # "res://worlds/scale_demo/material.tres"
# v2 path: ScaleWorld pre-builds a per-tile material (with arrays + splat
# + per-slot indices uniforms) and hands it in directly. If set, this
# wins over shared_material_path.
@export var shared_material: Material = null
@export var resolution_m: float = 1.0          # 1m per quad
# Tangents are only required when the shader samples a normal map. The
# unshaded scale_v1 shader doesn't, so skipping `SurfaceTool.generate_tangents()`
# saves ~120ms per tile build. Anchor's lit v2 shader DOES use a normal
# map, so AnchorTerrain.gd (which has its own copy of the build code)
# still generates tangents; this knob only affects TileTerrain.
@export var generate_tangents: bool = false
# Finite-difference stencil width (in mesh vertices) used for normal
# calculation. 1 = adjacent-vertex centered difference (sharpest, noisiest).
# 4 = sample ±4 vertices = ±4m on a 1m mesh (smoother shading, mild
# blurring of micro-relief). Necessary at high-relief crops where
# adjacent-pixel slopes swing dramatically.
@export var normal_stencil: int = 8
# Build the mesh on a WorkerThreadPool task instead of blocking _ready.
# The ~77ms math (vertex/normal pass) runs off the main thread; only the
# final ArrayMesh.add_surface_from_arrays + scene-graph attach is back
# on the main thread (~4ms + ~3ms ≈ 7ms). Player sees no stutter.
@export var async_build: bool = true

# Shared world heightmap reference, set by ScaleWorld before _ready.
# When present, all height sampling goes through this (in world
# coordinates) instead of the per-tile heightmap. This is what makes
# finite-difference normals at tile edges read into the neighbor tile's
# data — eliminates white seam artifacts at tile boundaries.
var world_height_data: PackedFloat32Array
var world_height_w: int = 0
var world_height_h: int = 0
var world_size_m: float = 0.0

var _heightmap_img: Image
# Flattened heightmap as 0..1 floats indexed [z * w + x]. We decode the
# image once at load time; reading from a PackedFloat32Array is roughly
# 30x faster than calling Image.get_pixel() per sample, which matters
# because building one 256m tile at 1m density does ~1.3M lookups.
var _heightmap_data: PackedFloat32Array
var _tile_x: int = 0
var _tile_z: int = 0
var _tile_size_m: float = 256.0
var _heightmap_w: int = 0
var _heightmap_h: int = 0
# World-shared elev range (same across all tiles in the world).
var _elev_min_m: float = 0.0
var _elev_range_m: float = 1.0
# World-space origin of this tile's (0,0) corner.
var _world_origin_x_m: float = 0.0
var _world_origin_z_m: float = 0.0

var _mesh_instance: MeshInstance3D

# Async build state. When `async_build = true`, _ready submits a task to
# WorkerThreadPool and the worker writes its outputs into _async_result.
# _process polls _async_task_id until WorkerThreadPool.is_task_completed,
# then runs the (cheap) main-thread finalize: build ArrayMesh, attach.
var _async_task_id: int = -1
var _async_result: Dictionary = {}
var _async_start_ms: int = 0


func _ready() -> void:
	var t0: int = Time.get_ticks_msec()
	if not _load_tile():
		push_error("TileTerrain: failed to load tile from " + tile_dir)
		return
	var t_load: int = Time.get_ticks_msec()

	if async_build:
		# Hand the math off to a worker thread; _process picks up when done.
		set_process(true)
		_async_start_ms = Time.get_ticks_msec()
		_async_task_id = WorkerThreadPool.add_task(_build_arrays_threaded)
		print("[TileTerrain %d_%d] load=%dms  async build queued (task %d)" % [
			_tile_x, _tile_z, t_load - t0, _async_task_id
		])
		return

	# Synchronous path — same as before.
	_mesh_instance = MeshInstance3D.new()
	_mesh_instance.name = "TileMesh_%d_%d" % [_tile_x, _tile_z]
	_mesh_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_mesh_instance.mesh = _build_mesh()
	var t_build: int = Time.get_ticks_msec()
	_apply_material()
	add_child(_mesh_instance)
	var t_done: int = Time.get_ticks_msec()
	print("[TileTerrain %d_%d] load=%dms build=%dms attach=%dms total=%dms" % [
		_tile_x, _tile_z, t_load - t0, t_build - t_load, t_done - t_build, t_done - t0
	])


func _process(_delta: float) -> void:
	# Only relevant when async_build = true and we have a pending task.
	if _async_task_id < 0:
		return
	if not WorkerThreadPool.is_task_completed(_async_task_id):
		return
	# Wait for completion (cheap because is_task_completed already passed).
	WorkerThreadPool.wait_for_task_completion(_async_task_id)
	_async_task_id = -1
	_finalize_async_build()
	set_process(false)


# Cleanup: if we're freed while a task is still pending, block on it
# before exiting. WorkerThreadPool tasks read our member vars and we
# can't have a freed instance underneath them.
func _exit_tree() -> void:
	if _async_task_id >= 0:
		WorkerThreadPool.wait_for_task_completion(_async_task_id)
		_async_task_id = -1


func _load_tile() -> bool:
	var meta_path: String = tile_dir + "meta.json"
	var heightmap_path: String = tile_dir + "heightmap.png"

	var f: FileAccess = FileAccess.open(meta_path, FileAccess.READ)
	if f == null:
		push_error("TileTerrain: cannot open " + meta_path)
		return false
	var meta_text: String = f.get_as_text()
	f.close()
	var meta: Variant = JSON.parse_string(meta_text)
	if not meta is Dictionary:
		push_error("TileTerrain: meta.json is not a dictionary")
		return false
	_tile_x = int(meta.get("tile_x", 0))
	_tile_z = int(meta.get("tile_z", 0))
	_tile_size_m = float(meta.get("tile_size_m", 256.0))
	_elev_min_m = float(meta.get("elevation_min_m", 0.0))
	_elev_range_m = float(meta.get("elevation_range_m", 1.0))
	_world_origin_x_m = float(meta.get("world_origin_x_m", 0.0))
	_world_origin_z_m = float(meta.get("world_origin_z_m", 0.0))

	_heightmap_img = Image.load_from_file(ProjectSettings.globalize_path(heightmap_path))
	if _heightmap_img == null:
		push_error("TileTerrain: cannot load heightmap " + heightmap_path)
		return false
	_heightmap_w = _heightmap_img.get_width()
	_heightmap_h = _heightmap_img.get_height()
	# Decode once into a flat PackedFloat32Array. Image.convert to FORMAT_RF
	# gives 32-bit float per pixel which we copy into a typed array. After
	# this point _heightmap_img is unused.
	_heightmap_img.convert(Image.FORMAT_RF)
	var raw: PackedByteArray = _heightmap_img.get_data()
	var n: int = _heightmap_w * _heightmap_h
	_heightmap_data.resize(n)
	var rb: PackedFloat32Array = raw.to_float32_array()
	if rb.size() != n:
		push_error("TileTerrain: heightmap decode size mismatch %d vs %d" % [rb.size(), n])
		return false
	for i in range(n):
		_heightmap_data[i] = rb[i]
	return true


# Sample height at LOCAL tile coordinates (0..tile_size_m), returns world Y.
# Bilinear sampling between 4 neighboring heightmap pixels.
# If a world heightmap is provided, samples from THAT in world coordinates
# so finite-difference reads at tile boundaries naturally cross into the
# neighbor's data without clamping.
func _sample_height(local_x: float, local_z: float) -> float:
	if world_height_data.size() > 0 and world_size_m > 0.0:
		# World-coordinate sample. local 0..tile_size maps to world
		# origin..(origin+tile_size). The world heightmap covers
		# -world_size_m/2 .. +world_size_m/2 → 0 .. world_height_w-1 px.
		var world_x: float = _world_origin_x_m + local_x
		var world_z: float = _world_origin_z_m + local_z
		var fx: float = clamp((world_x + world_size_m * 0.5) / world_size_m, 0.0, 1.0) * float(world_height_w - 1)
		var fz: float = clamp((world_z + world_size_m * 0.5) / world_size_m, 0.0, 1.0) * float(world_height_h - 1)
		var px0: int = clampi(int(floor(fx)), 0, world_height_w - 1)
		var pz0: int = clampi(int(floor(fz)), 0, world_height_h - 1)
		var px1: int = clampi(px0 + 1, 0, world_height_w - 1)
		var pz1: int = clampi(pz0 + 1, 0, world_height_h - 1)
		var tx: float = fx - float(px0)
		var tz: float = fz - float(pz0)
		var w: int = world_height_w
		var h00: float = world_height_data[pz0 * w + px0]
		var h10: float = world_height_data[pz0 * w + px1]
		var h01: float = world_height_data[pz1 * w + px0]
		var h11: float = world_height_data[pz1 * w + px1]
		var h0: float = h00 * (1.0 - tx) + h10 * tx
		var h1: float = h01 * (1.0 - tx) + h11 * tx
		var h: float = h0 * (1.0 - tz) + h1 * tz
		return _elev_min_m + h * _elev_range_m
	# Fallback: per-tile sample (used if ScaleWorld didn't provide a world
	# heightmap — e.g. legacy tests).
	var fx2: float = clamp(local_x / _tile_size_m, 0.0, 1.0) * float(_heightmap_w - 1)
	var fz2: float = clamp(local_z / _tile_size_m, 0.0, 1.0) * float(_heightmap_h - 1)
	var px0_l: int = clampi(int(floor(fx2)), 0, _heightmap_w - 1)
	var pz0_l: int = clampi(int(floor(fz2)), 0, _heightmap_h - 1)
	var px1_l: int = clampi(px0_l + 1, 0, _heightmap_w - 1)
	var pz1_l: int = clampi(pz0_l + 1, 0, _heightmap_h - 1)
	var tx_l: float = fx2 - float(px0_l)
	var tz_l: float = fz2 - float(pz0_l)
	var w_l: int = _heightmap_w
	var h00_l: float = _heightmap_data[pz0_l * w_l + px0_l]
	var h10_l: float = _heightmap_data[pz0_l * w_l + px1_l]
	var h01_l: float = _heightmap_data[pz1_l * w_l + px0_l]
	var h11_l: float = _heightmap_data[pz1_l * w_l + px1_l]
	var h0_l: float = h00_l * (1.0 - tx_l) + h10_l * tx_l
	var h1_l: float = h01_l * (1.0 - tx_l) + h11_l * tx_l
	var h_local: float = h0_l * (1.0 - tz_l) + h1_l * tz_l
	return _elev_min_m + h_local * _elev_range_m


func _sample_normal(local_x: float, local_z: float, step: float) -> Vector3:
	var hl: float = _sample_height(local_x - step, local_z)
	var hr: float = _sample_height(local_x + step, local_z)
	var hd: float = _sample_height(local_x, local_z - step)
	var hu: float = _sample_height(local_x, local_z + step)
	var dhx: float = (hr - hl) / max(step * 2.0, 0.001)
	var dhz: float = (hu - hd) / max(step * 2.0, 0.001)
	return Vector3(-dhx, 1.0, -dhz).normalized()


func _build_mesh() -> ArrayMesh:
	# Each tile is its own 256m x 256m mesh. The local mesh coordinate space
	# runs from 0..tile_size_m on X and Z, and we translate the whole mesh by
	# (world_origin_x, 0, world_origin_z) so it lands in the right world spot.
	# This way the vertex positions in world space are continuous across tile
	# boundaries (tile_0_0 ends at world_x=-256, tile_1_0 starts at
	# world_x=-256), so the world-XZ UVs the shader computes are continuous
	# too.
	var nx: int = int(round(_tile_size_m / resolution_m))
	var nz: int = int(round(_tile_size_m / resolution_m))
	var vert_count: int = (nx + 1) * (nz + 1)

	var verts: PackedVector3Array = PackedVector3Array()
	var uvs: PackedVector2Array = PackedVector2Array()
	var normals: PackedVector3Array = PackedVector3Array()
	var indices: PackedInt32Array = PackedInt32Array()
	verts.resize(vert_count)
	uvs.resize(vert_count)
	normals.resize(vert_count)

	var step_m: float = resolution_m

	var t_p1: int = Time.get_ticks_msec()
	# Pass 1: compute all vertex heights including a `normal_stencil`-wide
	# border that extends past each edge of the tile. The wide border is
	# what lets pass 2 read normal-stencil neighbors directly from the
	# cache instead of calling _sample_height again per-vertex (~5x
	# speedup on the hot loop).
	#
	# Cache layout: (nx + 1 + 2*pad) × (nz + 1 + 2*pad) where pad >=
	# normal_stencil. Indices run x_ext = 0..nx+2*pad and z_ext likewise,
	# where x_ext = pad..nx+pad corresponds to mesh vertices 0..nx.
	# (When a world heightmap is present, _sample_height seamlessly reads
	# the next tile's data for off-tile coordinates.)
	var pad: int = max(1, normal_stencil)
	var ext_stride: int = nx + 1 + 2 * pad
	var ext_count: int = ext_stride * (nz + 1 + 2 * pad)
	var heights_ext: PackedFloat32Array = PackedFloat32Array()
	heights_ext.resize(ext_count)
	for z_ext in range(nz + 1 + 2 * pad):
		for x_ext in range(nx + 1 + 2 * pad):
			var local_x: float = float(x_ext - pad) * step_m  # -pad*step .. tile_size+pad*step
			var local_z: float = float(z_ext - pad) * step_m
			heights_ext[z_ext * ext_stride + x_ext] = _sample_height(local_x, local_z)
	var t_p2: int = Time.get_ticks_msec()

	# Pass 2: build vertex/uv/normal arrays. Cache index for mesh vertex
	# (x, z) is (x + pad, z + pad). Normal neighbors at ±normal_stencil
	# are guaranteed to land inside the cache by construction.
	var stencil: int = normal_stencil
	var inv_2span: float = 1.0 / max(float(stencil) * 2.0, 0.001)
	for z in range(nz + 1):
		for x in range(nx + 1):
			var i: int = z * (nx + 1) + x
			var x_ext: int = x + pad
			var z_ext: int = z + pad
			var cache_row: int = z_ext * ext_stride
			var elev: float = heights_ext[cache_row + x_ext]
			verts[i] = Vector3(
				_world_origin_x_m + float(x) * step_m,
				elev,
				_world_origin_z_m + float(z) * step_m,
			)
			# UV0 = local 0..1 (shader ignores; placeholder for parity)
			uvs[i] = Vector2(float(x) / float(nx), float(z) / float(nz))
			# Centered-difference normals read directly from the cached
			# height grid — no _sample_height calls in the hot loop.
			var hl: float = heights_ext[cache_row + x_ext - stencil]
			var hr: float = heights_ext[cache_row + x_ext + stencil]
			var hd: float = heights_ext[(z_ext - stencil) * ext_stride + x_ext]
			var hu: float = heights_ext[(z_ext + stencil) * ext_stride + x_ext]
			var dhx: float = (hr - hl) * inv_2span
			var dhz: float = (hu - hd) * inv_2span
			normals[i] = Vector3(-dhx, 1.0, -dhz).normalized()
	var t_p3: int = Time.get_ticks_msec()

	indices.resize(nx * nz * 6)
	var k: int = 0
	for z in range(nz):
		for x in range(nx):
			var i00: int = z * (nx + 1) + x
			var i10: int = i00 + 1
			var i01: int = i00 + (nx + 1)
			var i11: int = i01 + 1
			indices[k] = i00; k += 1
			indices[k] = i11; k += 1
			indices[k] = i01; k += 1
			indices[k] = i00; k += 1
			indices[k] = i10; k += 1
			indices[k] = i11; k += 1

	var t_p4: int = Time.get_ticks_msec()

	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = indices

	var am: ArrayMesh = ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var t_p5: int = Time.get_ticks_msec()

	# Tangent generation is the single biggest cost when enabled (~120ms
	# per tile on 66K verts). For unshaded shaders that don't sample
	# normal maps it's pure waste — skip it.
	if generate_tangents:
		var st: SurfaceTool = SurfaceTool.new()
		st.create_from(am, 0)
		st.generate_tangents()
		var am_with_tangents: ArrayMesh = ArrayMesh.new()
		st.commit(am_with_tangents)
		am = am_with_tangents
	var t_p6: int = Time.get_ticks_msec()

	print("  [tile %d_%d build]  p1=%dms verts/normals=%dms idx=%dms attach=%dms tangents=%dms" % [
		_tile_x, _tile_z,
		t_p2 - t_p1,  # height cache (pass 1)
		t_p3 - t_p2,  # vertex+normal pass (pass 2)
		t_p4 - t_p3,  # index pass
		t_p5 - t_p4,  # ArrayMesh.add_surface_from_arrays
		t_p6 - t_p5   # SurfaceTool tangent generation (0 if skipped)
	])
	return am


# Worker-thread entry point. Computes the geometry arrays from heightmap
# data and stores them in `_async_result`. Does NOT touch the scene tree
# (forbidden from non-main threads). Reads only data set up before the
# task was queued: _heightmap_data, world_height_data, _tile_size_m,
# _heightmap_w/h, world_height_w/h, world_size_m, _world_origin_x/z_m,
# _elev_min/range_m, resolution_m, normal_stencil. All of these are set
# in _load_tile before the task is queued and never mutated by the main
# thread afterwards.
func _build_arrays_threaded() -> void:
	var nx: int = int(round(_tile_size_m / resolution_m))
	var nz: int = int(round(_tile_size_m / resolution_m))
	var vert_count: int = (nx + 1) * (nz + 1)
	var step_m: float = resolution_m

	var verts: PackedVector3Array = PackedVector3Array()
	var uvs: PackedVector2Array = PackedVector2Array()
	var normals: PackedVector3Array = PackedVector3Array()
	var indices: PackedInt32Array = PackedInt32Array()
	verts.resize(vert_count)
	uvs.resize(vert_count)
	normals.resize(vert_count)

	# Pass 1: wide-bordered height cache (identical to sync version).
	var pad: int = max(1, normal_stencil)
	var ext_stride: int = nx + 1 + 2 * pad
	var ext_count: int = ext_stride * (nz + 1 + 2 * pad)
	var heights_ext: PackedFloat32Array = PackedFloat32Array()
	heights_ext.resize(ext_count)
	for z_ext in range(nz + 1 + 2 * pad):
		for x_ext in range(nx + 1 + 2 * pad):
			var local_x: float = float(x_ext - pad) * step_m
			var local_z: float = float(z_ext - pad) * step_m
			heights_ext[z_ext * ext_stride + x_ext] = _sample_height(local_x, local_z)

	# Pass 2: vertex/uv/normal arrays.
	var stencil: int = normal_stencil
	var inv_2span: float = 1.0 / max(float(stencil) * 2.0, 0.001)
	for z in range(nz + 1):
		for x in range(nx + 1):
			var i: int = z * (nx + 1) + x
			var x_ext: int = x + pad
			var z_ext: int = z + pad
			var cache_row: int = z_ext * ext_stride
			var elev: float = heights_ext[cache_row + x_ext]
			verts[i] = Vector3(
				_world_origin_x_m + float(x) * step_m,
				elev,
				_world_origin_z_m + float(z) * step_m,
			)
			uvs[i] = Vector2(float(x) / float(nx), float(z) / float(nz))
			var hl: float = heights_ext[cache_row + x_ext - stencil]
			var hr: float = heights_ext[cache_row + x_ext + stencil]
			var hd: float = heights_ext[(z_ext - stencil) * ext_stride + x_ext]
			var hu: float = heights_ext[(z_ext + stencil) * ext_stride + x_ext]
			var dhx: float = (hr - hl) * inv_2span
			var dhz: float = (hu - hd) * inv_2span
			normals[i] = Vector3(-dhx, 1.0, -dhz).normalized()

	indices.resize(nx * nz * 6)
	var k: int = 0
	for z in range(nz):
		for x in range(nx):
			var i00: int = z * (nx + 1) + x
			var i10: int = i00 + 1
			var i01: int = i00 + (nx + 1)
			var i11: int = i01 + 1
			indices[k] = i00; k += 1
			indices[k] = i11; k += 1
			indices[k] = i01; k += 1
			indices[k] = i00; k += 1
			indices[k] = i10; k += 1
			indices[k] = i11; k += 1

	_async_result = {
		"verts": verts,
		"uvs": uvs,
		"normals": normals,
		"indices": indices,
	}


# Main-thread finalize: build the ArrayMesh from the worker's arrays,
# (optionally) generate tangents, attach to the scene tree. Cheap part
# of the build (~7ms typical).
func _finalize_async_build() -> void:
	var t0: int = Time.get_ticks_msec()
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = _async_result.get("verts", PackedVector3Array())
	arrays[Mesh.ARRAY_TEX_UV] = _async_result.get("uvs", PackedVector2Array())
	arrays[Mesh.ARRAY_NORMAL] = _async_result.get("normals", PackedVector3Array())
	arrays[Mesh.ARRAY_INDEX] = _async_result.get("indices", PackedInt32Array())

	var am: ArrayMesh = ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	if generate_tangents:
		var st: SurfaceTool = SurfaceTool.new()
		st.create_from(am, 0)
		st.generate_tangents()
		var am_with_tangents: ArrayMesh = ArrayMesh.new()
		st.commit(am_with_tangents)
		am = am_with_tangents

	_mesh_instance = MeshInstance3D.new()
	_mesh_instance.name = "TileMesh_%d_%d" % [_tile_x, _tile_z]
	_mesh_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_mesh_instance.mesh = am
	_apply_material()
	add_child(_mesh_instance)

	# Free the arrays — they're no longer needed after upload.
	_async_result.clear()
	var t_done: int = Time.get_ticks_msec()
	print("[TileTerrain %d_%d] async finalize=%dms  (total wall-clock=%dms)" % [
		_tile_x, _tile_z, t_done - t0, t_done - _async_start_ms
	])


func _apply_material() -> void:
	# v2 path takes priority when ScaleWorld pre-built a material instance.
	if shared_material != null:
		_mesh_instance.material_override = shared_material
		return
	if shared_material_path.is_empty():
		push_error("TileTerrain: shared_material_path empty")
		return
	var mat: Resource = load(shared_material_path)
	if mat == null:
		push_error("TileTerrain: cannot load material " + shared_material_path)
		return
	# All tiles share one material instance — Godot's MaterialOverride
	# accepts the same resource on multiple meshes.
	_mesh_instance.material_override = mat as Material


# Public hot-swap entry point used by ScaleWorld.set_view_mode.
# Accepts an already-loaded material resource so the caller can amortize
# the load across many tiles. Safe to call before the mesh is finalized
# — falls through silently and the next _apply_material picks it up.
func set_shared_material(mat: Material) -> void:
	if _mesh_instance != null:
		_mesh_instance.material_override = mat


# Public accessors for ScaleWorld / camera rig / water plane.
func get_tile_coord() -> Vector2i:
	return Vector2i(_tile_x, _tile_z)

func get_world_origin() -> Vector2:
	return Vector2(_world_origin_x_m, _world_origin_z_m)

func get_tile_size() -> float:
	return _tile_size_m

func get_elev_range() -> Vector2:
	return Vector2(_elev_min_m, _elev_min_m + _elev_range_m)
