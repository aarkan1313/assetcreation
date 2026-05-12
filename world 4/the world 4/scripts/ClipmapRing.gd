class_name ClipmapRing
extends Node3D

# One clipmap ring: a square donut mesh that translates with the camera
# at integer multiples of its grid step. Loaded with a heightmap texture
# the vertex shader displaces by.
#
# Geometry parameters (set by ClipmapWorld at instantiation):
#   ring_index:   0..N-1 (0 = innermost, finest)
#   grid_n:       vertices per side (typically 256)
#   grid_step_m:  meters between adjacent grid verts (2, 4, 8, 16...)
#   inner_grid_n: vertices skipped in the center (= next finer ring's grid_n)
#                  0 for the innermost ring (no hole)
#
# Per-frame: the ring's global_position is snapped to (cam_x, 0, cam_z)
# rounded to the nearest multiple of grid_step_m. This keeps vertex
# positions aligned with the world grid as the camera moves.

@export var ring_index: int = 0
@export var grid_n: int = 256
@export var grid_step_m: float = 2.0
@export var inner_grid_n: int = 0
# Skirt depth (meters below surface). See spec
# "Ring boundary stitching (REQUIRED)" — skirt verts hide the
# heightmap-discontinuity crack between adjacent rings.
@export var skirt_depth_m: float = 10.0
# If true, this is the outermost ring; we add an outer-edge skirt
# too to hide the "world rim" behind the bound.
@export var outermost: bool = false

var _mesh_instance: MeshInstance3D
var _mesh: ArrayMesh


func _ready() -> void:
	_mesh = _build_donut_mesh(grid_n, grid_step_m, inner_grid_n,
							  skirt_depth_m, outermost)
	_mesh_instance = MeshInstance3D.new()
	_mesh_instance.mesh = _mesh
	_mesh_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_mesh_instance)


func set_shared_material(mat: Material) -> void:
	if _mesh_instance != null:
		_mesh_instance.material_override = mat


func snap_to_camera(cam_world_xz: Vector2) -> void:
	var snap: float = grid_step_m
	var sx: float = roundf(cam_world_xz.x / snap) * snap
	var sz: float = roundf(cam_world_xz.y / snap) * snap
	global_position = Vector3(sx, 0.0, sz)


func get_world_rect_m() -> Rect2:
	var half: float = (float(grid_n) - 1.0) * grid_step_m * 0.5
	var origin: Vector2 = Vector2(global_position.x - half,
								  global_position.z - half)
	return Rect2(origin, Vector2(half * 2.0, half * 2.0))


# Build the donut mesh. Mirrors pipeline/build_clipmap_mesh_debug.py.
func _build_donut_mesh(p_grid_n: int, p_grid_step_m: float,
					   p_inner_grid_n: int,
					   p_skirt_depth_m: float = 10.0,
					   p_outermost: bool = false) -> ArrayMesh:
	if p_inner_grid_n > 0 and p_inner_grid_n % 2 != 0:
		push_error("inner_grid_n must be even")
	if p_inner_grid_n >= p_grid_n:
		push_error("inner_grid_n must be < grid_n")
	var half_extent: float = (float(p_grid_n) - 1.0) * p_grid_step_m * 0.5
	var inner_half: float = float(p_inner_grid_n) * p_grid_step_m * 0.5

	var indices: Array = []
	for i in range(p_grid_n):
		var row: Array[int] = []
		for j in range(p_grid_n):
			row.append(-1)
		indices.append(row)
	var positions := PackedVector3Array()
	for i in range(p_grid_n):
		for j in range(p_grid_n):
			var x: float = -half_extent + float(j) * p_grid_step_m
			var z: float = -half_extent + float(i) * p_grid_step_m
			if p_inner_grid_n > 0:
				if abs(x) < inner_half - 1e-3 and abs(z) < inner_half - 1e-3:
					continue
			indices[i][j] = positions.size()
			positions.append(Vector3(x, 0.0, z))

	var idx_buf := PackedInt32Array()
	for i in range(p_grid_n - 1):
		for j in range(p_grid_n - 1):
			var v00: int = indices[i][j]
			var v10: int = indices[i][j + 1]
			var v01: int = indices[i + 1][j]
			var v11: int = indices[i + 1][j + 1]
			if v00 == -1 or v10 == -1 or v01 == -1 or v11 == -1:
				continue
			idx_buf.append(v00); idx_buf.append(v10); idx_buf.append(v11)
			idx_buf.append(v00); idx_buf.append(v11); idx_buf.append(v01)

	if p_inner_grid_n > 0:
		_add_skirt_strip(positions, indices, idx_buf, p_grid_n,
						 true, p_skirt_depth_m)
	if p_outermost:
		_add_skirt_strip(positions, indices, idx_buf, p_grid_n,
						 false, p_skirt_depth_m)

	# Normals — flat upward; the vertex shader displaces per-vertex
	# and derives surface normals from heightmap finite-differences.
	# So mesh normals are placeholders.
	var normals := PackedVector3Array()
	for _i in range(positions.size()):
		normals.append(Vector3(0, 1, 0))

	# UVs — vertex.xz in mesh-local meters; the shader divides by
	# ring_extent_m to get the ring's [0..1] UV.
	var uvs := PackedVector2Array()
	for v in positions:
		uvs.append(Vector2(v.x, v.z))

	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = positions
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_INDEX] = idx_buf

	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh


# Append skirt verts (duplicates of perimeter verts at y=-skirt_depth)
# and the strip triangles into the in-progress packed arrays.
#
# inner_edge=true: walks the inner-hole perimeter (boundary verts
#   whose axial neighbor is in the hole). Triangle winding produces
#   outward-facing normals (visible from above the surface).
# inner_edge=false: walks the outer-mesh-edge perimeter (i==0 or
#   i==grid_n-1 or j==0 or j==grid_n-1). Triangle winding produces
#   outward-facing normals (visible from outside the world).
func _add_skirt_strip(positions: PackedVector3Array, indices: Array,
					  idx_buf: PackedInt32Array, p_grid_n: int,
					  inner_edge: bool, skirt_depth: float) -> void:
	var perimeter: Array[Vector2i] = []
	for i in range(p_grid_n):
		for j in range(p_grid_n):
			if indices[i][j] == -1:
				continue
			var is_boundary: bool = false
			if inner_edge:
				for offsets in [Vector2i(-1, 0), Vector2i(1, 0),
								 Vector2i(0, -1), Vector2i(0, 1)]:
					var ni: int = i + offsets.y
					var nj: int = j + offsets.x
					if ni >= 0 and ni < p_grid_n and nj >= 0 and nj < p_grid_n:
						if indices[ni][nj] == -1:
							is_boundary = true
							break
			else:
				if i == 0 or i == p_grid_n - 1 or j == 0 or j == p_grid_n - 1:
					is_boundary = true
			if not is_boundary:
				continue
			var surf_idx: int = indices[i][j]
			var surf_pos: Vector3 = positions[surf_idx]
			var skirt_idx: int = positions.size()
			positions.append(Vector3(surf_pos.x, -skirt_depth, surf_pos.z))
			perimeter.append(Vector2i(surf_idx, skirt_idx))
	perimeter.sort_custom(func(a: Vector2i, b: Vector2i) -> bool:
		var pa: Vector3 = positions[a.x]
		var pb: Vector3 = positions[b.x]
		return atan2(pa.z, pa.x) < atan2(pb.z, pb.x)
	)
	for k in range(perimeter.size()):
		var sa: int = perimeter[k].x
		var da: int = perimeter[k].y
		var nxt: int = (k + 1) % perimeter.size()
		var sb: int = perimeter[nxt].x
		var db: int = perimeter[nxt].y
		if inner_edge:
			idx_buf.append(sa); idx_buf.append(sb); idx_buf.append(db)
			idx_buf.append(sa); idx_buf.append(db); idx_buf.append(da)
		else:
			idx_buf.append(sa); idx_buf.append(db); idx_buf.append(sb)
			idx_buf.append(sa); idx_buf.append(da); idx_buf.append(db)
