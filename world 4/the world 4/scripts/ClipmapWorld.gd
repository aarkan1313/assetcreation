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

# Debug toggle: disable morph zones on every ring. Lets us A/B the
# cliff vs no-cliff comparison without editing the .tres (the .tres
# default would otherwise be overwritten by set_coarse_uniforms()).
@export var debug_disable_morph: bool = false

# Resolved at _ready, never changes during the session.
var _ring_count: int = 0
var _ring_grid_n: int = 0
var _ring_grid_step_base_m: float = 0.0
var _update_interval_s: float = 0.0
var _fmt_inner: String = "RF"
var _fmt_outer: String = "RH"
var _collision_rings: int = 1
var _morph_band_fraction: float = 0.10

# Per-ring morph band width in meters. Index = ring_index.
# Resolved once at _spawn_rings, used by _finalize_ring_upload to
# push uniforms into ring (i-1)'s coarse-side material slot.
var _morph_band_m_per_ring: Array[float] = []

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

# Async heightmap regen. ring_idx → { task_id, payload, superseded, result }.
# _process polls task completion via WorkerThreadPool.is_task_completed.
# Worker reads from _composer + world_seed (both read-only after _ready);
# main thread owns ImageTexture creation + shader uniform updates
# (RenderingServer is main-thread-only in Godot 4.5).
var _ring_tasks: Dictionary = {}


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
	_collision_rings = int(qt["collision_rings"])
	_morph_band_fraction = float(qt["morph_band_fraction"])
	print("[ClipmapWorld] tier=%s rings=%d grid_n=%d step=%.1fm formats=%s/%s collision_rings=%d morph_band=%.2f" % [
		qt.get("_tier", "?"), _ring_count, _ring_grid_n,
		_ring_grid_step_base_m, _fmt_inner, _fmt_outer, _collision_rings,
		_morph_band_fraction])


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
		# Inner rings get HeightMapShape3D collision so the player can
		# walk on them; outer rings are too coarse to matter for player
		# physics and skip collision to save VRAM/CPU. Tier knob:
		# `collision_rings` (1 on low/medium, 2 on high/ultra).
		if i < _collision_rings:
			ring.enable_collision()
	# Precompute each ring's morph band width in meters. The morph
	# happens INSIDE this ring's edge — so it's a fraction of THIS
	# ring's outer half-extent, not of the coarser ring.
	_morph_band_m_per_ring.clear()
	for ring_i in _rings:
		var half_extent: float = (float(ring_i.grid_n) - 1.0) * ring_i.grid_step_m * 0.5
		_morph_band_m_per_ring.append(half_extent * _morph_band_fraction)
	# The outermost ring has no coarser ring to blend toward. Disable
	# its morph blend up front; subsequent _finalize_ring_upload calls
	# won't touch its coarse-side uniforms again.
	var outermost_idx: int = _rings.size() - 1
	if outermost_idx >= 0:
		_rings[outermost_idx].set_coarse_uniforms(
			null, Vector2.ZERO, 1.0, 1, 0.0, false)
	# Force first heightmap eval at world origin (rings will re-snap
	# to camera position on the first _process tick).
	for r in _rings:
		_refresh_ring_heightmap(r, Vector2.ZERO)


func _process(delta: float) -> void:
	_update_clock += delta
	if _update_clock < _update_interval_s:
		return
	_update_clock = 0.0
	# Drain finished worker tasks every tick, regardless of camera state.
	# This keeps the per-frame poll cost tiny.
	_poll_ring_tasks()
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
			_enqueue_ring_refresh(r, snap)
			_last_snap_per_ring[i] = snap


# Synchronous fallback used for the initial heightmap eval at startup
# (before WorkerThreadPool is reliably warm). All later refreshes go
# through _enqueue_ring_refresh.
func _refresh_ring_heightmap(r: ClipmapRing, ring_center: Vector2) -> void:
	var n: int = r.grid_n
	var step: float = r.grid_step_m
	var half_extent: float = (float(n) - 1.0) * step * 0.5
	var origin: Vector2 = ring_center - Vector2(half_extent, half_extent)
	var floats := _compute_heightmap_floats(n, step, ring_center)
	_finalize_ring_upload(r, ring_center, origin, floats, n, step)


# Enqueue an off-thread refresh. Cheap: only constructs the worker
# task + result holder. If a task for this ring is already in flight,
# mark it superseded so its result is discarded when it lands; the new
# task fires immediately.
#
# WorkerThreadPool can't cancel running tasks, hence the superseded
# flag instead of true cancellation. The cost is one wasted worker run.
func _enqueue_ring_refresh(r: ClipmapRing, ring_center: Vector2) -> void:
	var ring_idx: int = r.ring_index
	if _ring_tasks.has(ring_idx):
		_ring_tasks[ring_idx]["superseded"] = true
	var payload: Dictionary = {
		"ring_idx": ring_idx,
		"ring_center": ring_center,
		"grid_n": r.grid_n,
		"grid_step_m": r.grid_step_m,
	}
	var task_id: int = WorkerThreadPool.add_task(
		_worker_compute_heightmap.bind(payload), false, "clipmap_ring_refresh"
	)
	_ring_tasks[ring_idx] = {
		"task_id": task_id,
		"payload": payload,
		"superseded": false,
		"result": null,
	}


# Worker thread entry. Pure: reads _composer + world_seed only, both
# of which are unchanged after _ready. The result is stored in the
# task entry; main thread picks it up on next _poll_ring_tasks tick.
func _worker_compute_heightmap(payload: Dictionary) -> void:
	var n: int = int(payload["grid_n"])
	var step: float = float(payload["grid_step_m"])
	var ring_center: Vector2 = payload["ring_center"]
	var heights: PackedFloat32Array = _compute_heightmap_floats(n, step, ring_center)
	var ring_idx: int = int(payload["ring_idx"])
	if _ring_tasks.has(ring_idx):
		_ring_tasks[ring_idx]["result"] = heights


# Pure-function helper. Same math as the sync path; reused by both
# _refresh_ring_heightmap and _worker_compute_heightmap so the two
# paths can't drift.
func _compute_heightmap_floats(n: int, step: float,
							   ring_center: Vector2) -> PackedFloat32Array:
	var half_extent: float = (float(n) - 1.0) * step * 0.5
	var origin: Vector2 = ring_center - Vector2(half_extent, half_extent)
	var floats := PackedFloat32Array()
	floats.resize(n * n)
	# Defense-in-depth: workers may still be in flight when the scene
	# tears down and frees _composer. _exit_tree drains pending tasks,
	# but if a worker is mid-loop when shutdown begins this guard
	# returns a zero-filled buffer instead of crashing.
	if _composer == null:
		return floats
	var idx: int = 0
	for i in range(n):
		var z: float = origin.y + float(i) * step
		for j in range(n):
			var x: float = origin.x + float(j) * step
			floats[idx] = float(_composer.sample_height(x, z, world_seed))
			idx += 1
	return floats


# Drain in-flight worker tasks before the scene frees _composer.
# Without this, shutdown causes a flurry of "null instance" errors
# from workers that started before quit() and haven't run yet.
func _exit_tree() -> void:
	for ring_idx_v in _ring_tasks.keys():
		var task: Dictionary = _ring_tasks[ring_idx_v]
		var task_id: int = int(task["task_id"])
		WorkerThreadPool.wait_for_task_completion(task_id)
	_ring_tasks.clear()


# Drains finished worker tasks. For each completed non-superseded task,
# uploads the resulting heightmap to the GPU on the main thread.
func _poll_ring_tasks() -> void:
	var done: Array[int] = []
	for ring_idx_v in _ring_tasks.keys():
		var ring_idx: int = int(ring_idx_v)
		var task: Dictionary = _ring_tasks[ring_idx]
		var task_id: int = int(task["task_id"])
		if not WorkerThreadPool.is_task_completed(task_id):
			continue
		WorkerThreadPool.wait_for_task_completion(task_id)
		done.append(ring_idx)
		if bool(task.get("superseded", false)):
			continue
		var result = task.get("result")
		if result == null:
			continue
		var heights: PackedFloat32Array = result
		var payload: Dictionary = task["payload"]
		var n: int = int(payload["grid_n"])
		var step: float = float(payload["grid_step_m"])
		var ring_center: Vector2 = payload["ring_center"]
		var half_extent: float = (float(n) - 1.0) * step * 0.5
		var origin: Vector2 = ring_center - Vector2(half_extent, half_extent)
		var r: ClipmapRing = _rings[ring_idx]
		_finalize_ring_upload(r, ring_center, origin, heights, n, step)
	for ring_idx in done:
		_ring_tasks.erase(ring_idx)


# Main thread only. Owns GPU upload + per-ring shader uniforms.
# Bulk PackedByteArray → Image.create_from_data → ImageTexture is
# much faster than per-pixel set_pixel (which is what GDScript per-vert
# code paths default to).
func _finalize_ring_upload(r: ClipmapRing, ring_center: Vector2,
						   origin: Vector2, heights: PackedFloat32Array,
						   n: int, step: float) -> void:
	var extent: float = (float(n) - 1.0) * step
	# Heightmap format intent: tier knob is honored when GDScript gets a
	# float32→float16 helper. Until then, both inner and outer rings
	# store FORMAT_RF; the sampler reads .r as float either way so the
	# shader is correct. Tracked as a follow-up.
	var img := Image.create_from_data(n, n, false, Image.FORMAT_RF,
									  heights.to_byte_array())
	var tex: ImageTexture = ImageTexture.create_from_image(img)
	r.set_displacement_texture(tex)
	r.set_ring_uniforms(origin, extent, n, r.ring_index)
	# Update collision proxy if this ring has one. No-op if not.
	r.update_collision_heightmap(heights, n)
	# Position the ring's StaticBody3D (parent of CollisionShape3D)
	# at the ring's snap position so collision coordinates match the
	# rendered geometry. ClipmapRing's global_position is already at
	# ring_center, so the child collision sits there automatically.
	# Morph plumbing: this ring's freshly-uploaded texture is the
	# COARSE input for ring (ring_index - 1). Push it. (If ring_index
	# is 0, no inner ring exists; skip.)
	if r.ring_index > 0:
		var inner: ClipmapRing = _rings[r.ring_index - 1]
		var inner_band_m: float = _morph_band_m_per_ring[r.ring_index - 1]
		inner.set_coarse_uniforms(
			tex, origin, extent, n, inner_band_m, not debug_disable_morph)


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


