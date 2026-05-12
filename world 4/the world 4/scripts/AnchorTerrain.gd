extends Node3D
class_name AnchorTerrain

# W4 anchor demo — terrain mesh builder.
# Loads the anchor bundle (heightmap + meta + material) and builds ONE mesh
# covering the entire 256m world. No streaming, no chunking — anchor scope.
#
# The mesh:
# - World vertices laid out in a regular grid in world XZ
# - Y elevation sampled from heightmap.png (16-bit) and decoded via meta.json's
#   elev_min_m + elev_range_m
# - Normals computed per-vertex from height gradient
# - UV0 = world-relative source UV (0..1 across the bundle) — the shader uses
#   this for source_macro_albedo and splat_weights sampling
# - UV2 = local mesh UV (unused by current shader but kept for future use)

@export var bundle_dir: String = "res://worlds/anchor/"
@export var resolution_m: float = 1.0  # 1m per mesh quad → 256x256 quads for a 256m world

var _heightmap_img: Image
var _heightmap_w: int = 0
var _heightmap_h: int = 0
var _world_size_x_m: float = 256.0
var _world_size_z_m: float = 256.0
var _elev_min_m: float = 0.0
var _elev_range_m: float = 1.0

var _mesh_instance: MeshInstance3D


func _ready() -> void:
	if not _load_bundle():
		push_error("AnchorTerrain: failed to load bundle from " + bundle_dir)
		return
	_mesh_instance = MeshInstance3D.new()
	_mesh_instance.name = "TerrainMesh"
	# Disable self-cast shadows on the terrain mesh. With cast_shadow ON
	# (the default), every dip and crevice in the heightmap casts a shadow
	# onto its neighbor mesh cells. At Godot's full editor shadow quality
	# that reads as black speckles all over the terrain — visible in live
	# editor but mostly washed out in low-res headless captures (which is
	# why my captures kept looking fine while the user's live view kept
	# showing the spots). Disabling means the terrain only receives the
	# sun's directional shadow on a large scale, not its own per-pixel
	# crevice self-shadows.
	_mesh_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_mesh_instance.mesh = _build_mesh()
	_apply_material()
	add_child(_mesh_instance)
	print("[AnchorTerrain] loaded bundle: %s, %dx%d mesh, elev %.1f..%.1fm" % [
		bundle_dir, _heightmap_w, _heightmap_h, _elev_min_m, _elev_min_m + _elev_range_m
	])


func _load_bundle() -> bool:
	var meta_path: String = bundle_dir + "meta.json"
	var heightmap_path: String = bundle_dir + "heightmap.png"

	# Load meta
	var f: FileAccess = FileAccess.open(meta_path, FileAccess.READ)
	if f == null:
		push_error("AnchorTerrain: cannot open " + meta_path)
		return false
	var meta_text: String = f.get_as_text()
	f.close()
	var meta: Variant = JSON.parse_string(meta_text)
	if not meta is Dictionary:
		push_error("AnchorTerrain: meta.json is not a dictionary")
		return false
	_world_size_x_m = float(meta.get("world_size_x_m", 256.0))
	_world_size_z_m = float(meta.get("world_size_z_m", 256.0))
	_elev_min_m = float(meta.get("elevation_min_m", 0.0))
	_elev_range_m = float(meta.get("elevation_range_m", 1.0))

	# Load heightmap as Image (CPU sampling for vertex Y)
	_heightmap_img = Image.load_from_file(ProjectSettings.globalize_path(heightmap_path))
	if _heightmap_img == null:
		push_error("AnchorTerrain: cannot load heightmap " + heightmap_path)
		return false
	_heightmap_w = _heightmap_img.get_width()
	_heightmap_h = _heightmap_img.get_height()
	return true


func _sample_height(world_x: float, world_z: float) -> float:
	# world_x and world_z are in 0..world_size_*_m
	var fx: float = clamp(world_x / _world_size_x_m, 0.0, 1.0)
	var fz: float = clamp(world_z / _world_size_z_m, 0.0, 1.0)
	var px: int = clampi(int(round(fx * float(_heightmap_w - 1))), 0, _heightmap_w - 1)
	var pz: int = clampi(int(round(fz * float(_heightmap_h - 1))), 0, _heightmap_h - 1)
	var c: Color = _heightmap_img.get_pixel(px, pz)
	return _elev_min_m + c.r * _elev_range_m


func _sample_normal(world_x: float, world_z: float, step: float) -> Vector3:
	var hl: float = _sample_height(world_x - step, world_z)
	var hr: float = _sample_height(world_x + step, world_z)
	var hd: float = _sample_height(world_x, world_z - step)
	var hu: float = _sample_height(world_x, world_z + step)
	var dhx: float = (hr - hl) / max(step * 2.0, 0.001)
	var dhz: float = (hu - hd) / max(step * 2.0, 0.001)
	return Vector3(-dhx, 1.0, -dhz).normalized()


func _build_mesh() -> ArrayMesh:
	var nx: int = int(round(_world_size_x_m / resolution_m))
	var nz: int = int(round(_world_size_z_m / resolution_m))
	var vert_count: int = (nx + 1) * (nz + 1)

	var verts: PackedVector3Array = PackedVector3Array()
	var uvs: PackedVector2Array = PackedVector2Array()
	var uv2s: PackedVector2Array = PackedVector2Array()
	var normals: PackedVector3Array = PackedVector3Array()
	var indices: PackedInt32Array = PackedInt32Array()
	verts.resize(vert_count)
	uvs.resize(vert_count)
	uv2s.resize(vert_count)
	normals.resize(vert_count)

	var step_m: float = resolution_m
	for z in range(nz + 1):
		for x in range(nx + 1):
			var i: int = z * (nx + 1) + x
			var world_x: float = float(x) * step_m
			var world_z: float = float(z) * step_m
			var elev: float = _sample_height(world_x, world_z)
			# Center the mesh on (0, 0) by subtracting half world size
			verts[i] = Vector3(
				world_x - _world_size_x_m * 0.5,
				elev,
				world_z - _world_size_z_m * 0.5,
			)
			# UV0 = world-relative source UV (the shader uses this for macro
			# and splat sampling — both are 1:1 with the bundle)
			uvs[i] = Vector2(world_x / _world_size_x_m, world_z / _world_size_z_m)
			# UV2 = local mesh UV (unused but kept)
			uv2s[i] = Vector2(float(x) / float(nx), float(z) / float(nz))
			normals[i] = _sample_normal(world_x, world_z, step_m)

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

	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_TEX_UV2] = uv2s
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_INDEX] = indices

	# CRITICAL: Godot 4 PBR requires tangents on every vertex to render
	# normal maps correctly. Without ARRAY_TANGENT, the normal-map sampling
	# path produces wild artifacts that look like black hexagons/squares/
	# stripes overlaid on otherwise-fine texture — exactly the bug we hit.
	# `add_surface_from_arrays` does NOT auto-generate tangents. We have to
	# either compute them or use SurfaceTool, which handles the math.
	var am: ArrayMesh = ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)

	# Now regenerate the surface through SurfaceTool to add proper tangents
	var st: SurfaceTool = SurfaceTool.new()
	st.create_from(am, 0)
	st.generate_tangents()
	var am_with_tangents: ArrayMesh = ArrayMesh.new()
	st.commit(am_with_tangents)
	return am_with_tangents


func _apply_material() -> void:
	var mat_path: String = bundle_dir + "material.tres"
	var mat: Resource = load(mat_path)
	if mat == null:
		push_error("AnchorTerrain: cannot load material " + mat_path)
		return
	# W3 lesson: the macro binding survives duplicate() better when we
	# explicitly re-bind it via RuntimeImageCache. For anchor we have only
	# one terrain instance so we don't need duplicate() at all — bind the
	# loaded material directly.
	_mesh_instance.material_override = mat as Material


# Public accessors for water plane to know world bounds + elev range
func get_world_size() -> Vector2:
	return Vector2(_world_size_x_m, _world_size_z_m)


func get_elev_range() -> Vector2:
	return Vector2(_elev_min_m, _elev_min_m + _elev_range_m)
