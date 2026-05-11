extends Node3D
class_name M15FeatureScatterOverlay

# M15 production-style scatter proof. It stays deterministic and mask-driven so
# it can evolve into the procedural runtime instead of becoming hand placement.

@export var enabled: bool = true
@export var debug_masks_visible: bool = false
@export var loader_path: NodePath
@export var meta_path: String = ""
@export var policy_path: String = "res://jobs/m15_feature_scatter_policy.json"
@export var shrub_mask_path: String = ""
@export var grass_mask_path: String = ""
@export var rock_mask_path: String = ""
@export var soil_mask_path: String = ""
@export var wash_mask_path: String = ""
@export var no_scatter_mask_path: String = ""
@export var seed: int = 15217
@export var shrub_spacing_m: float = 7.5
@export var grass_spacing_m: float = 7.0
@export var rock_spacing_m: float = 8.0
@export var debris_spacing_m: float = 8.5
@export var lichen_spacing_m: float = 6.5
@export var debug_spacing_m: float = 12.0
@export var max_shrubs: int = 980
@export var max_grass_tufts: int = 1150
@export var max_rocks: int = 780
@export var max_debris: int = 520
@export var max_lichen_decals: int = 760
@export var shrub_visibility_end_m: float = 420.0
@export var grass_visibility_end_m: float = 210.0
@export var rock_visibility_end_m: float = 360.0
@export var debris_visibility_end_m: float = 180.0
@export var lichen_visibility_end_m: float = 145.0

var _loader: Node
var _world_size_x_m: float = 512.0
var _world_size_z_m: float = 512.0
var _shrub_mask: Image
var _grass_mask: Image
var _rock_mask: Image
var _soil_mask: Image
var _wash_mask: Image
var _no_scatter_mask: Image
var _scatter_root: Node3D
var _debug_root: Node3D
var _summary: Dictionary = {}
var _policy: Dictionary = {}


func _ready() -> void:
	_loader = get_node_or_null(loader_path)
	_load_policy()
	_apply_policy()
	_load_meta()
	_load_masks()
	_rebuild()


func set_scatter_visible(value: bool) -> void:
	enabled = value
	if _scatter_root != null:
		_scatter_root.visible = enabled


func set_debug_masks_visible(value: bool) -> void:
	debug_masks_visible = value
	if _debug_root != null:
		_debug_root.visible = debug_masks_visible


func get_scatter_summary() -> Dictionary:
	return _summary.duplicate()


func _load_policy() -> void:
	if policy_path == "":
		return
	var f: FileAccess = FileAccess.open(policy_path, FileAccess.READ)
	if f == null:
		push_warning("M15FeatureScatterOverlay failed to load policy: " + policy_path)
		return
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) == TYPE_DICTIONARY:
		_policy = parsed


func _apply_policy() -> void:
	shrub_spacing_m = _kind_float("shrub", "spacing_m", shrub_spacing_m)
	grass_spacing_m = _kind_float("dry_grass", "spacing_m", grass_spacing_m)
	rock_spacing_m = _kind_float("stone", "spacing_m", rock_spacing_m)
	debris_spacing_m = _kind_float("dry_debris", "spacing_m", debris_spacing_m)
	lichen_spacing_m = _kind_float("lichen_decal", "spacing_m", lichen_spacing_m)
	max_shrubs = _kind_int("shrub", "max_count", max_shrubs)
	max_grass_tufts = _kind_int("dry_grass", "max_count", max_grass_tufts)
	max_rocks = _kind_int("stone", "max_count", max_rocks)
	max_debris = _kind_int("dry_debris", "max_count", max_debris)
	max_lichen_decals = _kind_int("lichen_decal", "max_count", max_lichen_decals)
	shrub_visibility_end_m = _kind_float("shrub", "visibility_end_m", shrub_visibility_end_m)
	grass_visibility_end_m = _kind_float("dry_grass", "visibility_end_m", grass_visibility_end_m)
	rock_visibility_end_m = _kind_float("stone", "visibility_end_m", rock_visibility_end_m)
	debris_visibility_end_m = _kind_float("dry_debris", "visibility_end_m", debris_visibility_end_m)
	lichen_visibility_end_m = _kind_float("lichen_decal", "visibility_end_m", lichen_visibility_end_m)


func _kind_float(kind: String, key: String, fallback: float) -> float:
	var entry: Variant = _policy_entry(kind)
	if typeof(entry) != TYPE_DICTIONARY:
		return fallback
	return float(entry.get(key, fallback))


func _kind_int(kind: String, key: String, fallback: int) -> int:
	var entry: Variant = _policy_entry(kind)
	if typeof(entry) != TYPE_DICTIONARY:
		return fallback
	return int(entry.get(key, fallback))


func _policy_entry(kind: String) -> Variant:
	var kinds: Variant = _policy.get("kinds", {})
	if typeof(kinds) != TYPE_DICTIONARY:
		return {}
	return kinds.get(kind, {})


func _load_meta() -> void:
	if meta_path == "":
		return
	var f: FileAccess = FileAccess.open(meta_path, FileAccess.READ)
	if f == null:
		return
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	var meta: Dictionary = parsed
	var world_size: float = float(meta.get("world_size_m", 512.0))
	_world_size_x_m = float(meta.get("world_size_x_m", world_size))
	_world_size_z_m = float(meta.get("world_size_z_m", world_size))


func _load_masks() -> void:
	_shrub_mask = _load_image(shrub_mask_path)
	_grass_mask = _load_image(grass_mask_path)
	_rock_mask = _load_image(rock_mask_path)
	_soil_mask = _load_image(soil_mask_path)
	_wash_mask = _load_image(wash_mask_path)
	_no_scatter_mask = _load_image(no_scatter_mask_path)


func _load_image(path: String) -> Image:
	if path == "":
		return null
	return RuntimeImageCache.load_image("", path)


func _rebuild() -> void:
	_scatter_root = Node3D.new()
	_scatter_root.name = "M15FeatureScatter"
	_scatter_root.visible = enabled
	add_child(_scatter_root)

	_debug_root = Node3D.new()
	_debug_root.name = "M15FeatureMaskDebug"
	_debug_root.visible = debug_masks_visible
	add_child(_debug_root)

	var shrubs: Array[Transform3D] = _build_instances(
		"shrub", shrub_spacing_m, max_shrubs, 0.88, Vector2(0.95, 2.70), Vector2(0.48, 1.15), seed + 11
	)
	var grass: Array[Transform3D] = _build_instances(
		"grass", grass_spacing_m, max_grass_tufts, 0.58, Vector2(0.55, 1.35), Vector2(0.22, 0.58), seed + 23
	)
	var rocks: Array[Transform3D] = _build_instances(
		"rock", rock_spacing_m, max_rocks, 0.92, Vector2(0.62, 1.95), Vector2(0.18, 0.64), seed + 37
	)
	var debris: Array[Transform3D] = _build_instances(
		"debris", debris_spacing_m, max_debris, 0.62, Vector2(0.45, 1.30), Vector2(0.06, 0.18), seed + 53
	)
	var lichen: Array[Transform3D] = _build_instances(
		"lichen", lichen_spacing_m, max_lichen_decals, 0.62, Vector2(0.42, 1.25), Vector2(0.018, 0.035), seed + 71
	)

	_add_multimesh(_scatter_root, "shrub_canopy_olive", _make_shrub_mesh(0.50, 0.48), _make_material(Color(0.18, 0.24, 0.12), 0.98), shrubs, shrub_visibility_end_m)
	_add_multimesh(_scatter_root, "shrub_canopy_sage", _make_shrub_mesh(0.46, 0.42), _make_material(Color(0.24, 0.30, 0.15), 0.98), _child_transforms(shrubs, Vector3(-0.17, 0.04, 0.06), Vector3(0.78, 0.68, 0.86), 0.42), shrub_visibility_end_m)
	_add_multimesh(_scatter_root, "shrub_canopy_shadow", _make_shrub_mesh(0.44, 0.36), _make_material(Color(0.12, 0.17, 0.08), 0.98), _child_transforms(shrubs, Vector3(0.18, -0.02, -0.08), Vector3(0.66, 0.58, 0.74), -0.35), shrub_visibility_end_m)
	_add_multimesh(_scatter_root, "shrub_woody_cores", _make_trunk_mesh(), _make_material(Color(0.22, 0.16, 0.10), 1.0), _child_transforms(shrubs, Vector3(0.0, -0.38, 0.0), Vector3(0.16, 0.50, 0.16), 0.0), 260.0)

	_add_multimesh(_scatter_root, "dry_grass_blades_a", _make_blade_mesh(), _make_material(Color(0.60, 0.55, 0.31), 0.98), _child_transforms(grass, Vector3(0.0, 0.0, 0.0), Vector3(0.12, 1.00, 0.38), 0.0), grass_visibility_end_m)
	_add_multimesh(_scatter_root, "dry_grass_blades_b", _make_blade_mesh(), _make_material(Color(0.44, 0.46, 0.23), 0.98), _child_transforms(grass, Vector3(0.08, -0.01, -0.03), Vector3(0.10, 0.86, 0.34), PI * 0.5), grass_visibility_end_m)
	_add_multimesh(_scatter_root, "dry_grass_seed_heads", _make_seed_head_mesh(), _make_material(Color(0.76, 0.70, 0.44), 0.98), _child_transforms(grass, Vector3(0.0, 0.23, 0.0), Vector3(0.22, 0.20, 0.22), 0.2), 145.0)

	_add_multimesh(_scatter_root, "rock_slabs_warm", _make_rock_mesh(), _make_material(Color(0.43, 0.37, 0.29), 1.0), rocks, rock_visibility_end_m)
	_add_multimesh(_scatter_root, "rock_caps_light", _make_rock_mesh(), _make_material(Color(0.56, 0.52, 0.42), 1.0), _child_transforms(rocks, Vector3(0.07, 0.08, -0.04), Vector3(0.64, 0.34, 0.74), 0.31), rock_visibility_end_m)

	_add_multimesh(_scatter_root, "dry_debris_twigs_a", _make_debris_mesh(), _make_material(Color(0.28, 0.20, 0.12), 1.0), _child_transforms(debris, Vector3(0.0, 0.01, 0.0), Vector3(1.0, 1.0, 1.0), 0.0), debris_visibility_end_m)
	_add_multimesh(_scatter_root, "dry_debris_twigs_b", _make_debris_mesh(), _make_material(Color(0.38, 0.30, 0.18), 1.0), _child_transforms(debris, Vector3(0.12, 0.02, 0.08), Vector3(0.62, 0.92, 0.62), PI * 0.42), debris_visibility_end_m)

	_add_multimesh(_scatter_root, "lichen_decal_pale", _make_lichen_mesh(), _make_material(Color(0.62, 0.69, 0.61), 1.0), lichen, lichen_visibility_end_m)
	_add_multimesh(_scatter_root, "lichen_decal_shadow", _make_lichen_mesh(), _make_material(Color(0.33, 0.41, 0.34), 1.0), _child_transforms(lichen, Vector3(0.13, 0.006, -0.08), Vector3(0.56, 0.82, 0.44), 0.7), lichen_visibility_end_m)

	_build_debug_overlay()
	_summary = {
		"policy_id": str(_policy.get("id", "inline_defaults")),
		"shrubs": shrubs.size(),
		"grass_tufts": grass.size(),
		"rocks": rocks.size(),
		"debris": debris.size(),
		"lichen_decals": lichen.size(),
		"debug_tiles": _debug_root.get_child_count()
	}


func _child_transforms(source: Array[Transform3D], local_offset: Vector3, local_scale: Vector3, local_yaw: float) -> Array[Transform3D]:
	var out: Array[Transform3D] = []
	var local_basis := Basis(Vector3.UP, local_yaw).scaled(local_scale)
	var child := Transform3D(local_basis, local_offset)
	for transform in source:
		out.append(transform * child)
	return out


func _build_instances(
	kind: String,
	spacing_m: float,
	max_count: int,
	accept_scale: float,
	width_range: Vector2,
	height_range: Vector2,
	rng_seed: int
) -> Array[Transform3D]:
	var rng := RandomNumberGenerator.new()
	rng.seed = rng_seed
	var transforms: Array[Transform3D] = []
	var half_x: float = _world_size_x_m * 0.5
	var half_z: float = _world_size_z_m * 0.5
	var cells_x: int = max(1, int(floor(_world_size_x_m / max(spacing_m, 0.1))))
	var cells_z: int = max(1, int(floor(_world_size_z_m / max(spacing_m, 0.1))))
	for gz in range(cells_z):
		for gx in range(cells_x):
			if transforms.size() >= max_count:
				return transforms
			var x: float = -half_x + (float(gx) + rng.randf_range(0.12, 0.88)) * spacing_m
			var z: float = -half_z + (float(gz) + rng.randf_range(0.12, 0.88)) * spacing_m
			if x < -half_x or x > half_x or z < -half_z or z > half_z:
				continue
			var density: float = _density_for(kind, x, z)
			if rng.randf() > density * accept_scale:
				continue
			var h: float = rng.randf_range(height_range.x, height_range.y)
			var w: float = rng.randf_range(width_range.x, width_range.y)
			var y: float = _height_at(x, z) + h * 0.48 + 0.04
			if kind == "grass":
				y = _height_at(x, z) + h * 0.32 + 0.03
			elif kind == "rock":
				y = _height_at(x, z) + h * 0.34 + 0.035
			elif kind == "debris" or kind == "lichen":
				y = _height_at(x, z) + 0.055
			var basis := Basis(Vector3.UP, rng.randf_range(0.0, TAU))
			if kind == "debris":
				basis = basis.scaled(Vector3(w * 1.6, max(h, 0.05), w * 0.16))
			elif kind == "lichen":
				basis = basis.scaled(Vector3(w, max(h, 0.018), w * rng.randf_range(0.55, 1.25)))
			elif kind == "grass":
				basis = basis.scaled(Vector3(w, h, w * rng.randf_range(0.65, 1.25)))
			elif kind == "rock":
				basis = basis.scaled(Vector3(w, h, w * rng.randf_range(0.58, 1.35)))
			else:
				basis = basis.scaled(Vector3(w, h, w * rng.randf_range(0.72, 1.18)))
			transforms.append(Transform3D(basis, Vector3(x, y, z)))
	return transforms


func _density_for(kind: String, x: float, z: float) -> float:
	var no_scatter: float = _sample_mask(_no_scatter_mask, x, z)
	var soil: float = _sample_mask(_soil_mask, x, z)
	var wash: float = _sample_mask(_wash_mask, x, z)
	var shrub: float = _sample_mask(_shrub_mask, x, z)
	var grass: float = _sample_mask(_grass_mask, x, z)
	var rock: float = _sample_mask(_rock_mask, x, z)
	if kind == "shrub":
		return clamp(shrub * (1.0 - no_scatter * 0.82) + wash * 0.06, 0.0, 1.0)
	if kind == "grass":
		return clamp(grass * (0.82 - no_scatter * 0.55) + shrub * 0.12 + soil * 0.08, 0.0, 1.0)
	if kind == "rock":
		return clamp(rock * (1.05 - no_scatter * 0.20) + soil * 0.20 + wash * 0.08, 0.0, 1.0)
	if kind == "debris":
		return clamp(wash * 0.55 + soil * 0.24 + shrub * 0.12 - no_scatter * 0.36, 0.0, 1.0)
	if kind == "lichen":
		return clamp(rock * 0.54 + soil * 0.22 + grass * 0.06 - wash * 0.12 - no_scatter * 0.30, 0.0, 1.0)
	return 0.0


func _build_debug_overlay() -> void:
	var soil_tiles: Array[Transform3D] = _build_debug_tiles("soil", seed + 101)
	var green_tiles: Array[Transform3D] = _build_debug_tiles("green", seed + 103)
	var wash_tiles: Array[Transform3D] = _build_debug_tiles("wash", seed + 107)
	_add_multimesh(_debug_root, "soil_rock_debug", _make_debug_tile_mesh(), _make_debug_material(Color(0.88, 0.28, 0.12, 0.35)), soil_tiles, 0.0)
	_add_multimesh(_debug_root, "green_scatter_debug", _make_debug_tile_mesh(), _make_debug_material(Color(0.12, 0.82, 0.20, 0.32)), green_tiles, 0.0)
	_add_multimesh(_debug_root, "wash_debug", _make_debug_tile_mesh(), _make_debug_material(Color(0.18, 0.46, 1.0, 0.32)), wash_tiles, 0.0)


func _build_debug_tiles(kind: String, rng_seed: int) -> Array[Transform3D]:
	var rng := RandomNumberGenerator.new()
	rng.seed = rng_seed
	var transforms: Array[Transform3D] = []
	var half_x: float = _world_size_x_m * 0.5
	var half_z: float = _world_size_z_m * 0.5
	var cells_x: int = max(1, int(floor(_world_size_x_m / max(debug_spacing_m, 0.1))))
	var cells_z: int = max(1, int(floor(_world_size_z_m / max(debug_spacing_m, 0.1))))
	for gz in range(cells_z):
		for gx in range(cells_x):
			var x: float = -half_x + (float(gx) + 0.5) * debug_spacing_m
			var z: float = -half_z + (float(gz) + 0.5) * debug_spacing_m
			var value: float = 0.0
			if kind == "soil":
				value = max(_sample_mask(_soil_mask, x, z), _sample_mask(_rock_mask, x, z))
			elif kind == "green":
				value = max(_sample_mask(_shrub_mask, x, z), _sample_mask(_grass_mask, x, z) * 0.72)
			else:
				value = max(_sample_mask(_wash_mask, x, z), _sample_mask(_no_scatter_mask, x, z) * 0.45)
			if value < 0.42 or rng.randf() > value:
				continue
			var y: float = _height_at(x, z) + 0.09
			var basis := Basis().scaled(Vector3(debug_spacing_m * 0.70, 0.035, debug_spacing_m * 0.70))
			transforms.append(Transform3D(basis, Vector3(x, y, z)))
	return transforms


func _add_multimesh(
	parent: Node3D,
	node_name: String,
	mesh: Mesh,
	material: Material,
	transforms: Array[Transform3D],
	visibility_end_m: float
) -> void:
	if transforms.is_empty():
		return
	var multimesh := MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.mesh = mesh
	multimesh.instance_count = transforms.size()
	for i in range(transforms.size()):
		multimesh.set_instance_transform(i, transforms[i])
	var inst := MultiMeshInstance3D.new()
	inst.name = node_name
	inst.multimesh = multimesh
	inst.material_override = material
	inst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	if visibility_end_m > 0.0:
		inst.visibility_range_end = visibility_end_m
		inst.visibility_range_end_margin = min(visibility_end_m * 0.22, 120.0)
	parent.add_child(inst)


func _make_shrub_mesh(radius: float, height: float) -> Mesh:
	var mesh := SphereMesh.new()
	mesh.radius = radius
	mesh.height = height
	mesh.radial_segments = 7
	mesh.rings = 4
	return mesh


func _make_rock_mesh() -> Mesh:
	var mesh := BoxMesh.new()
	mesh.size = Vector3(1.0, 0.52, 0.82)
	return mesh


func _make_blade_mesh() -> Mesh:
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.22, 1.0, 0.055)
	return mesh


func _make_seed_head_mesh() -> Mesh:
	var mesh := SphereMesh.new()
	mesh.radius = 0.5
	mesh.height = 0.36
	mesh.radial_segments = 5
	mesh.rings = 2
	return mesh


func _make_trunk_mesh() -> Mesh:
	var mesh := CylinderMesh.new()
	mesh.top_radius = 0.18
	mesh.bottom_radius = 0.26
	mesh.height = 1.0
	mesh.radial_segments = 5
	mesh.rings = 1
	return mesh


func _make_debris_mesh() -> Mesh:
	var mesh := BoxMesh.new()
	mesh.size = Vector3(1.0, 0.13, 0.13)
	return mesh


func _make_lichen_mesh() -> Mesh:
	var mesh := CylinderMesh.new()
	mesh.top_radius = 0.5
	mesh.bottom_radius = 0.5
	mesh.height = 1.0
	mesh.radial_segments = 9
	mesh.rings = 1
	return mesh


func _make_debug_tile_mesh() -> Mesh:
	var mesh := BoxMesh.new()
	mesh.size = Vector3(1.0, 1.0, 1.0)
	return mesh


func _make_material(color: Color, roughness: float) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = roughness
	mat.specular_mode = BaseMaterial3D.SPECULAR_DISABLED
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	return mat


func _make_debug_material(color: Color) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	return mat


func _height_at(x: float, z: float) -> float:
	if _loader != null and _loader.has_method("sample_height_global"):
		return float(_loader.call("sample_height_global", x, z))
	return 0.0


func _sample_mask(img: Image, x: float, z: float) -> float:
	if img == null:
		return 0.0
	var w: int = img.get_width()
	var h: int = img.get_height()
	if w <= 0 or h <= 0:
		return 0.0
	var fx: float = clamp((x + _world_size_x_m * 0.5) / max(_world_size_x_m, 0.001), 0.0, 1.0)
	var fz: float = clamp((z + _world_size_z_m * 0.5) / max(_world_size_z_m, 0.001), 0.0, 1.0)
	var px: int = clampi(int(round(fx * float(w - 1))), 0, w - 1)
	var pz: int = clampi(int(round(fz * float(h - 1))), 0, h - 1)
	return img.get_pixel(px, pz).r
