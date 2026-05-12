extends Node3D
class_name AnchorWater

# W4 anchor demo — water plane.
# A flat plane at threshold elevation. Sized to just the actual water area
# (computed from the heightmap), with a generous border for the alpha-fade
# edges of the water shader. NOT the whole world — that produced an ugly
# black rectangle extending behind the terrain in iso views.

@export var threshold_elev_offset_m: float = 25.0
@export var terrain_path: NodePath
# Extra meters past the water region to add to the plane (so the edges
# can fade and we don't see plane edges through the terrain)
@export var border_m: float = 20.0


var _mesh_instance: MeshInstance3D


func _ready() -> void:
	var terrain = get_node_or_null(terrain_path) as AnchorTerrain
	if terrain == null:
		push_error("AnchorWater: terrain_path doesn't resolve to AnchorTerrain")
		return
	var world_size: Vector2 = terrain.get_world_size()
	var elev_range: Vector2 = terrain.get_elev_range()
	var water_y: float = elev_range.x + threshold_elev_offset_m

	# Compute actual water bounds by scanning the heightmap. AnchorTerrain
	# exposes the heightmap image; scan it for below-threshold pixels and
	# size the plane to that region only (+ border).
	var bounds = _compute_water_bounds(terrain, water_y)
	if bounds == null:
		# No water — skip the plane entirely
		print("[AnchorWater] no terrain below threshold y=%.1fm, skipping water plane" % water_y)
		return

	var min_x: float = bounds[0]
	var min_z: float = bounds[1]
	var max_x: float = bounds[2]
	var max_z: float = bounds[3]
	# Expand by border
	min_x -= border_m; min_z -= border_m
	max_x += border_m; max_z += border_m
	# Clamp to world
	min_x = max(min_x, -world_size.x * 0.5)
	min_z = max(min_z, -world_size.y * 0.5)
	max_x = min(max_x, world_size.x * 0.5)
	max_z = min(max_z, world_size.y * 0.5)
	var plane_w: float = max_x - min_x
	var plane_h: float = max_z - min_z
	var plane_cx: float = (min_x + max_x) * 0.5
	var plane_cz: float = (min_z + max_z) * 0.5

	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(plane_w, plane_h)
	plane.subdivide_width = 8
	plane.subdivide_depth = 8

	_mesh_instance = MeshInstance3D.new()
	_mesh_instance.name = "WaterPlane"
	_mesh_instance.mesh = plane
	_mesh_instance.position = Vector3(plane_cx, water_y, plane_cz)
	_mesh_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	var shader: Shader = load("res://shaders/water_anchor.gdshader") as Shader
	if shader == null:
		push_error("AnchorWater: cannot load water_anchor.gdshader")
		return
	var mat: ShaderMaterial = ShaderMaterial.new()
	mat.shader = shader
	_mesh_instance.material_override = mat
	_mesh_instance.sorting_offset = 0.5
	add_child(_mesh_instance)
	print("[AnchorWater] plane at y=%.1fm, %sx%sm centered at (%.1f, %.1f)" % [
		water_y, plane_w, plane_h, plane_cx, plane_cz
	])


# Scan the terrain's heightmap for below-threshold pixels, return the
# world-space bounding box. Returns null if there's no water.
func _compute_water_bounds(terrain: AnchorTerrain, threshold_y: float):
	# AnchorTerrain caches the heightmap image internally; we can't reach
	# it directly without adding a public accessor. Re-load the file here
	# — cheap, runs once.
	var img: Image = Image.load_from_file(ProjectSettings.globalize_path(terrain.bundle_dir + "heightmap.png"))
	if img == null:
		return null
	var w: int = img.get_width()
	var h: int = img.get_height()
	var world_size: Vector2 = terrain.get_world_size()
	var elev_range: Vector2 = terrain.get_elev_range()
	var elev_min: float = elev_range.x
	var elev_full: float = elev_range.y - elev_range.x
	if elev_full <= 0.0:
		return null

	# Threshold as 0..1 normalized
	var t_norm: float = (threshold_y - elev_min) / elev_full
	var found: bool = false
	var bb_min_x: float = INF
	var bb_min_z: float = INF
	var bb_max_x: float = -INF
	var bb_max_z: float = -INF
	for z in range(h):
		for x in range(w):
			if img.get_pixel(x, z).r < t_norm:
				# World position of this pixel — note terrain mesh is centered on (0,0)
				var world_x: float = (float(x) / float(w - 1) - 0.5) * world_size.x
				var world_z: float = (float(z) / float(h - 1) - 0.5) * world_size.y
				bb_min_x = min(bb_min_x, world_x)
				bb_min_z = min(bb_min_z, world_z)
				bb_max_x = max(bb_max_x, world_x)
				bb_max_z = max(bb_max_z, world_z)
				found = true
	if not found:
		return null
	return [bb_min_x, bb_min_z, bb_max_x, bb_max_z]
