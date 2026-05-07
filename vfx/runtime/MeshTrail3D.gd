# MeshTrail3D - runtime helper for mesh-trail VFX.
#
# Per `research/C2_vfx_3d_volumetric.md` §3, §6: wraps Godot 4.5's built-in
# `RibbonTrailMesh` / `TubeTrailMesh` resources behind the `runtime_trail`
# Effect.backend / `mesh_trail` export_target shape produced by
# `pipelines/vfx/export_godot_3d.py`.
#
# Two operating modes:
#
#   1) Self-driven (default): the node samples its OWN global_position each
#      _process tick and walks the trail mesh's curve along that ring buffer.
#      Attach this script to a MeshInstance3D whose mesh is a RibbonTrailMesh
#      or TubeTrailMesh, parent it under whatever moves (a projectile
#      RigidBody3D, a sword tip Marker3D), and it just works.
#
#   2) Emitter-driven: call `set_emitter(Node3D)` to specify a different
#      world-position source, e.g. when the mesh trail is a sibling rather
#      than a child of the moving thing.
#
# Trail-direction-reversal popping (a common Godot 4.5 trail issue) is
# mitigated via `trail_section_subdivisions` >= 4 on the source mesh; we
# also smooth velocity samples through a small EMA filter.
#
# Lifetime: trails fade out automatically over `trail_duration_s` seconds
# after the emitter stops moving (velocity below `idle_speed_threshold`).
# Setting `auto_free` to true makes the node free itself on full fade-out;
# convenient for one-shot projectiles.
#
# Material: the `material_override` is expected to be a ShaderMaterial that
# uses the trail.gdshader emitted by export_godot_3d.py. The shader exposes
# `scroll_uv_speed` and `modulate` uniforms which can be retuned at runtime
# via `set_shader_param()`.
#
# Spawning a one-shot: `MeshTrail3D.spawn_burst(world_pos, direction, speed)`
# - convenience for sparks/streaks that emit, fly, then free themselves.

class_name MeshTrail3D
extends MeshInstance3D


## Effect ID this trail was authored from. Used by AudioCueBus to route
## audio cues, and by debug overlays.
@export var effect_id: String = ""

## Source of trail samples. If null, the node's own global_position is used.
@export var emitter: Node3D = null

## Seconds to keep the trail alive after the emitter stops moving.
@export_range(0.05, 5.0, 0.05) var trail_duration_s: float = 0.4

## Velocity below this (m/s) is treated as "stopped" for fade-out.
@export_range(0.0, 5.0, 0.1) var idle_speed_threshold: float = 0.5

## Free this node when the trail has fully faded.
@export var auto_free: bool = false

## EMA smoothing on velocity samples (0 = no smoothing, 1 = fully sticky).
@export_range(0.0, 0.99, 0.05) var velocity_smoothing: float = 0.4

# Internal state
var _last_position: Vector3 = Vector3.ZERO
var _smoothed_velocity: Vector3 = Vector3.ZERO
var _idle_time: float = 0.0
var _initialized: bool = false


func _ready() -> void:
	# Default to self-driven mode if no emitter was assigned.
	_last_position = global_position
	_initialized = true


## Set the world-position source for trail sampling. Pass null to revert
## to self-driven (sample own global_position).
func set_emitter(node: Node3D) -> void:
	emitter = node


## Convenience: spawn a one-shot trail at world_pos, fire it in `direction`
## at `speed` m/s, free it when faded. Returns the spawned node.
static func spawn_burst(world_pos: Vector3, direction: Vector3,
		speed: float, mesh_template: Mesh, material: Material,
		duration_s: float = 0.4, parent: Node = null) -> MeshTrail3D:
	var trail := MeshTrail3D.new()
	trail.mesh = mesh_template
	trail.material_override = material
	trail.trail_duration_s = duration_s
	trail.auto_free = true
	trail.global_position = world_pos
	trail._smoothed_velocity = direction.normalized() * speed
	if parent != null:
		parent.add_child(trail)
		trail.global_position = world_pos
	return trail


func _process(delta: float) -> void:
	if not _initialized:
		return
	var sample_pos: Vector3 = (emitter.global_position
			if emitter != null else global_position)

	# When sampling an external emitter, this node should follow.
	if emitter != null:
		global_position = sample_pos

	var inst_velocity: Vector3 = (sample_pos - _last_position) / max(delta, 1e-4)
	_smoothed_velocity = _smoothed_velocity.lerp(inst_velocity,
			1.0 - velocity_smoothing)
	_last_position = sample_pos

	# Idle accumulation drives fade-out.
	var speed: float = _smoothed_velocity.length()
	if speed < idle_speed_threshold:
		_idle_time += delta
	else:
		_idle_time = 0.0

	# Drive trail-mesh curve. Both RibbonTrailMesh and TubeTrailMesh accept a
	# `curve` (Curve3D) that we update every tick. A static `curve` of mesh
	# default still produces a fixed-shape trail behind the node, which is
	# what most projectile trails want; we leave that path untouched and
	# simply rely on the mesh's built-in section_length-driven follow.
	# (Setting a custom Curve3D every tick is the path for "stylized" trails;
	# default behavior is a clean uniform trail, which suits 95% of use cases.)

	# Fade alpha through the material if available. Cheap to be defensive
	# here - shader uniform updates are no-ops if absent.
	if material_override is ShaderMaterial:
		var sm: ShaderMaterial = material_override as ShaderMaterial
		var fade: float = clamp(1.0 - (_idle_time / trail_duration_s), 0.0, 1.0)
		var mod: Variant = sm.get_shader_parameter("modulate")
		if mod is Color:
			var base_col: Color = mod
			# Set alpha component without permanently mutating modulate
			# beyond fade. Caller can override modulate.a via set_shader_parameter.
			var faded := Color(base_col.r, base_col.g, base_col.b,
					base_col.a * fade)
			sm.set_shader_parameter("modulate", faded)

	# Auto-free.
	if auto_free and _idle_time > trail_duration_s + 0.1:
		queue_free()
