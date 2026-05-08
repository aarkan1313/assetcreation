extends Node

# Iterates a list of regions, loads each into the active Terrain, and
# captures iso + topdown views. Output goes to a per-region subfolder
# under D:/tmp/world3_screens/regions/.
#
# Reads the region list from world3/jobs/regions.json.

@export var output_dir: String = "D:/tmp/world3_screens/regions"
@export var warmup_frames_per_view: int = 8
@export var iso_size_pad: float = 1.15
@export var only_regions: PackedStringArray = []  # empty = all regions

const REGIONS_JSON := "res://jobs/regions.json"


func _ready() -> void:
	# Wait for everything to settle.
	await get_tree().process_frame

	var terrain: Terrain = _find_terrain()
	if terrain == null:
		push_error("[gallery] no Terrain in scene")
		get_tree().quit(1); return

	var iso_cam: Camera3D = _find_iso_cam()
	if iso_cam == null:
		push_error("[gallery] no IsoCam in scene")
		get_tree().quit(1); return

	# Strip the IsoCam's own auto-frame script so we can drive it.
	iso_cam.set_script(null)
	iso_cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	iso_cam.near = 1.0
	iso_cam.far = 200000.0

	var regions := _load_regions()
	if regions.is_empty():
		push_error("[gallery] no regions to render")
		get_tree().quit(1); return

	DirAccess.make_dir_recursive_absolute(output_dir)

	for region in regions:
		var rid: String = region.get("id", "")
		var ds: String = region.get("preferred_dataset", "")
		var bundle = _bundle_of(region, ds)
		if bundle == null:
			continue

		# Phase E: derive per-mode material paths from `biome_kit_material`.
		# Expected form: res://textures/wgv3/terrain_blend_<kit>.tres
		# Per-mode variants:           ..._<kit>_<mode>.tres   (mode in iso/topdown)
		# If the per-mode variant is missing, fall back to the base kit material.
		var kit_mat_path: String = region.get("biome_kit_material", "")
		var iso_mat_path: String = _per_mode_path(kit_mat_path, "iso")
		var topdown_mat_path: String = _per_mode_path(kit_mat_path, "topdown")

		print("[gallery] %s / %s (kit=%s)" % [rid, ds, region.get("biome_kit", "?")])
		# Read meta upfront so per-mode swaps can re-push elev_min/range to
		# the new ShaderMaterial (Terrain.rebuild only pushes to whatever was
		# bound at load time).
		var meta := _read_meta(bundle["meta_path"])
		var elev_min: float = float(meta.get("elevation_min_m", 0.0))
		var elev_range: float = float(meta.get("elevation_range_m", 1.0))

		terrain.load_dataset(bundle["heightmap_path"], bundle["meta_path"])
		# Wait a couple frames for the rebuild to settle.
		for i in range(warmup_frames_per_view):
			await get_tree().process_frame

		var aabb: AABB = terrain.get_aabb()
		var center: Vector3 = aabb.position + aabb.size * 0.5
		var diag := aabb.size.length()

		var region_dir: String = output_dir.path_join(rid)
		DirAccess.make_dir_recursive_absolute(region_dir)

		# Iso view: bind iso-tuned material, frame, capture.
		_bind_material(terrain, iso_mat_path, kit_mat_path, elev_min, elev_range)
		_frame_iso(iso_cam, aabb, center, diag)
		for i in range(warmup_frames_per_view):
			await get_tree().process_frame
		await _save(region_dir.path_join("iso.png"))

		# Topdown view: swap to topdown-tuned material, reframe, capture.
		_bind_material(terrain, topdown_mat_path, kit_mat_path, elev_min, elev_range)
		_frame_topdown(iso_cam, aabb, center)
		for i in range(warmup_frames_per_view):
			await get_tree().process_frame
		await _save(region_dir.path_join("topdown.png"))

	print("[gallery] done. wrote %d regions" % regions.size())
	get_tree().quit(0)


func _frame_iso(cam: Camera3D, aabb: AABB, center: Vector3, diag: float) -> void:
	var dir := Vector3(1, 1, 1).normalized()
	cam.transform.origin = center + dir * diag * 1.5
	cam.look_at(center, Vector3.UP)
	# Project corners into camera-local to size the ortho frustum tightly.
	var basis_inv := cam.transform.basis.inverse()
	var min_u := INF; var max_u := -INF
	var min_v := INF; var max_v := -INF
	for c in [
		aabb.position,
		aabb.position + Vector3(aabb.size.x, 0, 0),
		aabb.position + Vector3(0, aabb.size.y, 0),
		aabb.position + Vector3(0, 0, aabb.size.z),
		aabb.position + Vector3(aabb.size.x, aabb.size.y, 0),
		aabb.position + Vector3(aabb.size.x, 0, aabb.size.z),
		aabb.position + Vector3(0, aabb.size.y, aabb.size.z),
		aabb.position + aabb.size,
	]:
		var local: Vector3 = basis_inv * (c - cam.transform.origin)
		min_u = min(min_u, local.x); max_u = max(max_u, local.x)
		min_v = min(min_v, local.y); max_v = max(max_v, local.y)
	var height_extent: float = (max_v - min_v) * iso_size_pad
	var width_extent: float = (max_u - min_u) * iso_size_pad
	var aspect := 16.0 / 9.0
	cam.size = max(height_extent, width_extent / aspect)


func _frame_topdown(cam: Camera3D, aabb: AABB, center: Vector3) -> void:
	cam.transform.origin = Vector3(center.x, aabb.position.y + aabb.size.y + 5000.0, center.z)
	cam.look_at(center, Vector3.FORWARD)
	var aspect := 16.0 / 9.0
	cam.size = max(aabb.size.z * iso_size_pad, aabb.size.x * iso_size_pad / aspect)


func _save(path: String) -> void:
	var img := get_viewport().get_texture().get_image()
	img.save_png(path)
	print("[gallery]   " + path)


func _find_terrain() -> Terrain:
	return _walk(get_tree().current_scene, "Terrain") as Terrain


func _find_iso_cam() -> Camera3D:
	# Find any Camera3D — there should only be one in the scene.
	return _walk(get_tree().current_scene, "Camera3D") as Camera3D


func _walk(node: Node, type_name: String) -> Node:
	if node.get_class() == type_name or (node.get_script() != null and
			str(node.get_script().get_global_name()) == type_name):
		return node
	for c in node.get_children():
		var r := _walk(c, type_name)
		if r != null:
			return r
	return null


func _load_regions() -> Array:
	var f := FileAccess.open(REGIONS_JSON, FileAccess.READ)
	if f == null:
		return []
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_ARRAY:
		return []
	var out: Array = []
	for r in parsed:
		if only_regions.size() > 0 and not (r.get("id", "") in only_regions):
			continue
		out.append(r)
	return out


func _bundle_of(region: Dictionary, dataset: String) -> Variant:
	for b in region.get("bundles", []):
		if b.get("dataset", "") == dataset:
			return b
	return null


func _per_mode_path(base: String, mode: String) -> String:
	# Convert .../terrain_blend_<kit>.tres -> .../terrain_blend_<kit>_<mode>.tres
	if not base.ends_with(".tres"):
		return ""
	return base.substr(0, base.length() - 5) + "_" + mode + ".tres"


func _bind_material(terrain: MeshInstance3D, primary: String, fallback: String,
		elev_min: float, elev_range: float) -> void:
	for path in [primary, fallback]:
		if path == "":
			continue
		var mat: Material = load(path) as Material
		if mat != null:
			terrain.material_override = mat
			# Re-push elev params (Terrain.rebuild only pushed to the prior material).
			if mat is ShaderMaterial:
				var sm: ShaderMaterial = mat
				sm.set_shader_parameter("elev_min_m", elev_min)
				sm.set_shader_parameter("elev_range_m", elev_range)
			return
	push_warning("[gallery] no material loaded; primary=%s fallback=%s" % [primary, fallback])


func _read_meta(meta_path: String) -> Dictionary:
	var f := FileAccess.open(meta_path, FileAccess.READ)
	if f == null:
		return {}
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}
