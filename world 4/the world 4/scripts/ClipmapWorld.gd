class_name ClipmapWorld
extends Node3D

# Scene-root runtime for the scale_v2 world. v1 of this script does
# only the clipmap geometry setup; heightmap-from-kernel-composer and
# clipmap splat come in Stages 3+4.

@export var ring_count: int = 4
@export var ring_grid_n: int = 256
@export var ring_grid_step_base_m: float = 2.0
@export var debug_material_path: String = ""
@export var camera_path: NodePath
@export var update_interval_s: float = 0.05

var _rings: Array[ClipmapRing] = []
var _camera: Camera3D = null
var _update_clock: float = 0.0


func _ready() -> void:
	# Camera lookup is lazy in _process — the AnchorCameraRig sibling
	# creates its WalkCamera in its own _ready, which may run after ours.
	var debug_mat: Material = null
	if not debug_material_path.is_empty():
		var res := load(debug_material_path)
		if res is Material:
			debug_mat = res
	# Each ring's inner_grid_n = next-finer ring's grid_n (so it has
	# a hole where the finer ring renders). Innermost ring has no hole.
	for i in range(ring_count):
		var ring := ClipmapRing.new()
		ring.name = "Ring_%d" % i
		ring.ring_index = i
		ring.grid_n = ring_grid_n
		ring.grid_step_m = ring_grid_step_base_m * pow(2.0, float(i))
		ring.skirt_depth_m = 10.0
		ring.outermost = (i == ring_count - 1)
		# Inner hole matches the next-finer ring's outer extent in
		# grid units of THIS ring. Inner ring's outer = (grid_n-1) * step_inner.
		# Expressed in this ring's step = (grid_n - 1) * step_inner / step_this
		#                                = (grid_n - 1) / 2 (since step_inner = step_this / 2).
		if i == 0:
			ring.inner_grid_n = 0
		else:
			# Round DOWN to even so the hole is slightly smaller than the
			# inner ring's outer extent — guaranteeing overlap, not a gap.
			# (grid_n - 1) / 2 in integer division floors automatically;
			# then round down to even by masking off the low bit.
			ring.inner_grid_n = ((ring_grid_n - 1) / 2) & ~1
		add_child(ring)
		_rings.append(ring)
		if debug_mat != null:
			ring.set_shared_material(_per_ring_material(debug_mat, i))


func _process(delta: float) -> void:
	_update_clock += delta
	if _update_clock < update_interval_s:
		return
	_update_clock = 0.0
	if _camera == null and camera_path != NodePath(""):
		var node := get_node_or_null(camera_path)
		if node is Camera3D:
			_camera = node
	if _camera == null:
		return
	var cam_xz: Vector2 = Vector2(_camera.global_position.x,
								  _camera.global_position.z)
	for r in _rings:
		r.snap_to_camera(cam_xz)


# Make a per-ring material instance with `ring_index` set, sharing the
# rest of the shader params with the global debug material.
func _per_ring_material(base_mat: Material, idx: int) -> Material:
	if not (base_mat is ShaderMaterial):
		return base_mat
	var inst: ShaderMaterial = (base_mat as ShaderMaterial).duplicate(false)
	inst.set_shader_parameter("ring_index", idx)
	return inst
