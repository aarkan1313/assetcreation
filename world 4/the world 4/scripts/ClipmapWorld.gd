class_name ClipmapWorld
extends Node3D

# Scene-root runtime for clipmap-based worlds (scale_v2 onward). Owns:
#  - the clipmap rings (N nested square donut meshes, camera-snapped)
#  - the KernelComposer (per-biome procedural height + biome weights)
#  - the per-ring displacement-texture stack (one heightmap per ring)
#
# Reads sizing knobs from QualityTiers.get_current() — `ring_count`,
# `ring_grid_n`, `ring_grid_step_base_m`, `update_interval_s`,
# `heightmap_format_inner` / `_outer`. The first two inner rings get
# the inner format; the rest get the outer format.
#
# Stage 3.3 evaluates heightmaps SYNCHRONOUSLY on the main thread.
# Stage 3.4 moves the eval to WorkerThreadPool with double-buffer.

@export var bundle_dir: String = "res://worlds/scale_v2/"
@export var world_v3_material_path: String = "res://worlds/scale_v2/material_world_v3.tres"
@export var camera_path: NodePath
@export var world_seed: int = 42

# Optional overrides for testing a non-tier config in isolation.
# Empty / zero = use the tier value.
@export var override_ring_count: int = 0
@export var override_ring_grid_n: int = 0
@export var override_ring_grid_step_base_m: float = 0.0
@export var override_update_interval_s: float = 0.0

# Resolved at _ready, never changes during the session.
var _ring_count: int = 0
var _ring_grid_n: int = 0
var _ring_grid_step_base_m: float = 0.0
var _update_interval_s: float = 0.0
var _fmt_inner: String = "RF"
var _fmt_outer: String = "RH"

# How many of the innermost rings get the inner heightmap format.
# Outer rings (further from camera) get the cheaper format.
const _INNER_FORMAT_RING_COUNT := 2

var _rings: Array[ClipmapRing] = []
var _camera: Camera3D = null
var _update_clock: float = 0.0
var _composer: KernelComposer = null
var _catalog: Dictionary = {}
var _base_material: ShaderMaterial = null
var _last_snap_per_ring: Array[Vector2] = []


func _ready() -> void:
	_resolve_config()
	_load_catalog_and_composer()
	_load_base_material()
	_spawn_rings()


func _resolve_config() -> void:
	var qt: Dictionary = QualityTiers.get_current()
	_ring_count = override_ring_count if override_ring_count > 0 else int(qt["ring_count"])
	_ring_grid_n = override_ring_grid_n if override_ring_grid_n > 0 else int(qt["ring_grid_n"])
	_ring_grid_step_base_m = override_ring_grid_step_base_m if override_ring_grid_step_base_m > 0.0 else float(qt["ring_grid_step_base_m"])
	_update_interval_s = override_update_interval_s if override_update_interval_s > 0.0 else float(qt["update_interval_s"])
	_fmt_inner = String(qt["heightmap_format_inner"])
	_fmt_outer = String(qt["heightmap_format_outer"])
	print("[ClipmapWorld] tier=%s rings=%d grid_n=%d step=%.1fm formats=%s/%s" % [
		qt.get("_tier", "?"), _ring_count, _ring_grid_n,
		_ring_grid_step_base_m, _fmt_inner, _fmt_outer])


func _load_catalog_and_composer() -> void:
	var cat_path: String = bundle_dir + "biome_catalog.json"
	var file := FileAccess.open(cat_path, FileAccess.READ)
	if file == null:
		push_error("ClipmapWorld: missing catalog at " + cat_path)
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	file.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("ClipmapWorld: catalog is not a dict")
		return
	_catalog = parsed
	var registry: Dictionary = {"noise_stack": NoiseStackKernel.new()}
	_composer = KernelComposer.new(_catalog, registry)


func _load_base_material() -> void:
	if world_v3_material_path.is_empty():
		push_error("ClipmapWorld: world_v3_material_path empty")
		return
	var res := load(world_v3_material_path)
	if not (res is ShaderMaterial):
		push_error("ClipmapWorld: world_v3_material is not ShaderMaterial")
		return
	_base_material = res


func _spawn_rings() -> void:
	for i in range(_ring_count):
		var ring := ClipmapRing.new()
		ring.name = "Ring_%d" % i
		ring.ring_index = i
		ring.grid_n = _ring_grid_n
		ring.grid_step_m = _ring_grid_step_base_m * pow(2.0, float(i))
		ring.skirt_depth_m = 10.0
		ring.outermost = (i == _ring_count - 1)
		# inner_grid_n: round DOWN to even so this ring's hole is
		# slightly smaller than the inner ring's outer extent → guaranteed
		# overlap, no gap. See Stage 2 fix.
		if i == 0:
			ring.inner_grid_n = 0
		else:
			ring.inner_grid_n = ((_ring_grid_n - 1) / 2) & ~1
		add_child(ring)
		_rings.append(ring)
		_last_snap_per_ring.append(Vector2(NAN, NAN))
		if _base_material != null:
			var per: ShaderMaterial = _base_material.duplicate(false)
			per.set_shader_parameter("ring_index", i)
			ring.set_shared_material(per)
	# Force first heightmap eval at world origin (rings will re-snap
	# to camera position on the first _process tick).
	for r in _rings:
		_refresh_ring_heightmap(r, Vector2.ZERO)


func _process(delta: float) -> void:
	_update_clock += delta
	if _update_clock < _update_interval_s:
		return
	_update_clock = 0.0
	if _camera == null and camera_path != NodePath(""):
		var node := get_node_or_null(camera_path)
		if node is Camera3D:
			_camera = node
	if _camera == null or _composer == null:
		return
	var cam_xz: Vector2 = Vector2(_camera.global_position.x,
								  _camera.global_position.z)
	for i in range(_rings.size()):
		var r: ClipmapRing = _rings[i]
		r.snap_to_camera(cam_xz)
		var snap: Vector2 = Vector2(r.global_position.x, r.global_position.z)
		if snap != _last_snap_per_ring[i]:
			_refresh_ring_heightmap(r, snap)
			_last_snap_per_ring[i] = snap


# Sample the composer on this ring's grid and write the heightmap to
# the ring's displacement texture (bulk path: PackedByteArray →
# Image.create_from_data → ImageTexture).
#
# Stage 3.4 will move the inner loop to WorkerThreadPool. The bulk
# byte-buffer build is already correct for that path — only the
# scheduling changes.
func _refresh_ring_heightmap(r: ClipmapRing, ring_center: Vector2) -> void:
	var n: int = r.grid_n
	var step: float = r.grid_step_m
	var half_extent: float = (float(n) - 1.0) * step * 0.5
	var origin: Vector2 = ring_center - Vector2(half_extent, half_extent)
	var extent: float = (float(n) - 1.0) * step

	var fmt_string: String = _fmt_inner if r.ring_index < _INNER_FORMAT_RING_COUNT else _fmt_outer
	var fmt: int = _image_format_from_string(fmt_string)

	# Sample composer onto a float buffer. Bulk PackedFloat32Array
	# → bytes is much faster than per-pixel set_pixel() in GDScript.
	var floats := PackedFloat32Array()
	floats.resize(n * n)
	var idx: int = 0
	for i in range(n):
		var z: float = origin.y + float(i) * step
		for j in range(n):
			var x: float = origin.x + float(j) * step
			floats[idx] = float(_composer.sample_height(x, z, world_seed))
			idx += 1

	var img: Image
	if fmt == Image.FORMAT_RF:
		img = Image.create_from_data(n, n, false, fmt, floats.to_byte_array())
	else:
		# FORMAT_RH: half-float. Pack manually — Godot has no float32→
		# float16 helper exposed to GDScript, so we go via float32 and
		# let create_from_data refuse the wrong byte count below if
		# something's off. Workaround: write FORMAT_RF and rely on
		# Godot's renderer to upload as the texture's storage format
		# (it does — sampler reads .r as float either way).
		# For now, store as RF on outer rings too; the tier knob's job
		# is documenting intent. Real VRAM savings on outer rings
		# require either a GDScript float16 helper or moving to a
		# native script. Track as a Phase-2 follow-up.
		img = Image.create_from_data(n, n, false, Image.FORMAT_RF, floats.to_byte_array())

	var tex: ImageTexture = ImageTexture.create_from_image(img)
	r.set_displacement_texture(tex)
	r.set_ring_uniforms(origin, extent, n, r.ring_index)


# AnchorCameraRig duck-types both ScaleWorld and ClipmapWorld via these
# two methods. Returning sensible values lets the rig spawn the walk
# camera above the actual terrain instead of below it.
func get_world_size() -> Vector2:
	# Reported as the outermost ring's extent. The "world" is unbounded
	# in practice (camera-relative), but the rig uses this to size the
	# iso/topdown framing.
	if _rings.is_empty():
		return Vector2(1024.0, 1024.0)
	var outer: ClipmapRing = _rings[-1]
	var ext: float = (float(outer.grid_n) - 1.0) * outer.grid_step_m
	return Vector2(ext, ext)


func get_elev_range() -> Vector2:
	# Pulled from the catalog's biome generators — min(base - amp) to
	# max(base + amp) across all biomes. Safe overestimate; the camera
	# rig uses it to pick a "mid-elevation" spawn height.
	if _catalog.is_empty() or not _catalog.has("biomes"):
		return Vector2(0.0, 1000.0)
	var lo: float = INF
	var hi: float = -INF
	for b in _catalog["biomes"]:
		var gen: Dictionary = b.get("generator", {})
		var params: Dictionary = gen.get("params", {})
		var base: float = float(params.get("elevation_base_m", 500.0))
		var amp: float = float(params.get("elevation_amplitude_m", 200.0))
		lo = min(lo, base - amp)
		hi = max(hi, base + amp)
	if lo == INF:
		lo = 0.0
		hi = 1000.0
	return Vector2(lo, hi)


static func _image_format_from_string(s: String) -> int:
	if s == "RF":
		return Image.FORMAT_RF
	if s == "RH":
		return Image.FORMAT_RH
	push_error("ClipmapWorld: unknown heightmap format " + s)
	return Image.FORMAT_RF
