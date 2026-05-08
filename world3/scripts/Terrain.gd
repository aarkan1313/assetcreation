extends MeshInstance3D
class_name Terrain

# Builds a subdivided plane mesh from the heightmap PNG at runtime.
# Reads world dimensions from meta.json so the scale matches reality.

@export var heightmap_path: String = "res://heightmap/heightmap.png"
@export var heightmap_cache_path: String = ""
@export var meta_path: String = "res://heightmap/meta.json"
@export var subdivisions: int = 256  # mesh resolution; 256 = 65k verts
@export var height_scale: float = 1.0  # multiplier on real elevation
@export_node_path("StaticBody3D") var collision_target: NodePath
# Set true when an external loader (e.g. RegionLoader) will call
# load_dataset/rebuild after wiring up the right paths. Avoids a wasted
# initial build against the default heightmap_path.
@export var defer_initial_build: bool = false


func _ready() -> void:
	if not defer_initial_build:
		rebuild()


func load_dataset(new_heightmap_path: String, new_meta_path: String) -> void:
	heightmap_path = new_heightmap_path
	meta_path = new_meta_path
	rebuild()


func rebuild() -> void:
	var meta := _load_meta()
	if meta.is_empty():
		push_error("Terrain: failed to load meta.json")
		return
	var img: Image = RuntimeImageCache.load_image(heightmap_cache_path, heightmap_path)
	if img == null:
		push_error("Terrain: failed to load heightmap " + heightmap_path)
		return

	var world_size: float = float(meta.get("world_size_m", 1024.0))
	var world_size_x: float = float(meta.get("world_size_x_m", world_size))
	var world_size_z: float = float(meta.get("world_size_z_m", world_size))
	var elev_min: float = float(meta.get("elevation_min_m", 0.0))
	var elev_range: float = float(meta.get("elevation_range_m", 1.0))

	mesh = _build_mesh(img, world_size_x, world_size_z, elev_min, elev_range)

	# If the scene set a ShaderMaterial that uses elev_min_m / elev_range_m
	# uniforms (e.g. terrain_blend.gdshader), populate them from meta so the
	# blend shader doesn't need per-DEM hardcoded values in the .tres.
	if material_override is ShaderMaterial:
		var sm: ShaderMaterial = material_override
		if sm.shader != null:
			# These calls are no-ops if the uniform doesn't exist in the shader.
			sm.set_shader_parameter("elev_min_m", elev_min)
			sm.set_shader_parameter("elev_range_m", elev_range)

	if collision_target != NodePath(""):
		var body: StaticBody3D = get_node_or_null(collision_target) as StaticBody3D
		if body != null:
			# HeightMapShape3D grid covers (map_width-1) x (map_depth-1) cells
			# centered on the body. Scale X/Z to the terrain footprint and keep Y
			# unscaled so stored elevations remain world meters.
			var collision_subdiv := subdivisions
			var sx_scale := world_size_x / float(collision_subdiv)
			var sz_scale := world_size_z / float(collision_subdiv)
			var hm_shape := HeightMapShape3D.new()
			hm_shape.map_width = collision_subdiv + 1
			hm_shape.map_depth = collision_subdiv + 1
			var heights := PackedFloat32Array()
			heights.resize((collision_subdiv + 1) * (collision_subdiv + 1))
			var step_x: float = float(img.get_width() - 1) / float(collision_subdiv)
			var step_z: float = float(img.get_height() - 1) / float(collision_subdiv)
			for z in range(collision_subdiv + 1):
				for x in range(collision_subdiv + 1):
					var sample_x: int = clampi(int(round(x * step_x)), 0, img.get_width() - 1)
					var sample_z: int = clampi(int(round(z * step_z)), 0, img.get_height() - 1)
					var nrm: float = img.get_pixel(sample_x, sample_z).r
					var elev: float = elev_min + nrm * elev_range * height_scale
					heights[z * (collision_subdiv + 1) + x] = elev
			hm_shape.map_data = heights
			var col := CollisionShape3D.new()
			col.shape = hm_shape
			body.add_child(col)
			body.transform = Transform3D(Basis().scaled(Vector3(sx_scale, 1.0, sz_scale)), Vector3.ZERO)


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


func _build_mesh(img: Image, world_size_x: float, world_size_z: float, elev_min: float, elev_range: float) -> ArrayMesh:
	var n := subdivisions
	var verts := PackedVector3Array()
	var uvs := PackedVector2Array()
	var normals := PackedVector3Array()
	var indices := PackedInt32Array()
	verts.resize((n + 1) * (n + 1))
	uvs.resize((n + 1) * (n + 1))
	normals.resize((n + 1) * (n + 1))

	var img_w := img.get_width()
	var img_h := img.get_height()
	var step_x := float(img_w - 1) / float(n)
	var step_z := float(img_h - 1) / float(n)
	var half_x := world_size_x * 0.5
	var half_z := world_size_z * 0.5

	# Pre-sample heights into a 2D array for normal calculation.
	var hgrid := PackedFloat32Array()
	hgrid.resize((n + 1) * (n + 1))
	for z in range(n + 1):
		for x in range(n + 1):
			var sx := int(round(x * step_x))
			var sz := int(round(z * step_z))
			sx = clampi(sx, 0, img_w - 1)
			sz = clampi(sz, 0, img_h - 1)
			var nrm: float = img.get_pixel(sx, sz).r
			var elev: float = elev_min + nrm * elev_range * height_scale
			hgrid[z * (n + 1) + x] = elev

	for z in range(n + 1):
		for x in range(n + 1):
			var i: int = z * (n + 1) + x
			var fx: float = float(x) / float(n)
			var fz: float = float(z) / float(n)
			var wx: float = fx * world_size_x - half_x
			var wz: float = fz * world_size_z - half_z
			verts[i] = Vector3(wx, hgrid[i], wz)
			uvs[i] = Vector2(fx, fz)

	# Compute normals from finite differences on the world-space height grid.
	var dx: float = world_size_x / float(n)
	var dz: float = world_size_z / float(n)
	for z in range(n + 1):
		for x in range(n + 1):
			var i: int = z * (n + 1) + x
			var xl: int = max(x - 1, 0)
			var xr: int = min(x + 1, n)
			var zd: int = max(z - 1, 0)
			var zu: int = min(z + 1, n)
			var hl: float = hgrid[z * (n + 1) + xl]
			var hr: float = hgrid[z * (n + 1) + xr]
			var hd: float = hgrid[zd * (n + 1) + x]
			var hu: float = hgrid[zu * (n + 1) + x]
			var dhx: float = (hr - hl) / max(float(xr - xl), 1.0) / dx
			var dhz: float = (hu - hd) / max(float(zu - zd), 1.0) / dz
			normals[i] = Vector3(-dhx, 1.0, -dhz).normalized()

	# Triangle indices: two tris per quad.
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

	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return am
