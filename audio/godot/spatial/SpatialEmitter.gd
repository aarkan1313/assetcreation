# SpatialEmitter — abstraction over AudioStreamPlayer3D / ResonanceAudioSource.
#
# When the godot-resonance-audio GDExtension is installed (see
# pipelines/audio/recipes/hrtf_resonance.json for install steps), this helper
# returns a ResonanceAudioSource with HRTF panning. Otherwise it returns a
# plain AudioStreamPlayer3D with inverse-distance attenuation.
#
# Used by BiomeAmbienceController to spawn one-shot wildlife / distant-event
# sweeteners. Beds (bed_drone, bed_air) stay non-spatial.
#
# Public API:
#   SpatialEmitter.create_emitter(stream: AudioStream, listener_xform: Transform3D,
#                                 *, max_distance := 30.0, bus := "Ambience")
#       -> Node3D  (caller adds it to the scene tree, calls play(), free()s on
#                   finished)

extends Node
class_name SpatialEmitter

const RESONANCE_CLASS_NAME := "ResonanceAudioSource"


static func has_resonance() -> bool:
	# ClassDB lookup; works on any Godot 4.5 build whether the extension is
	# loaded or not.
	return ClassDB.class_exists(RESONANCE_CLASS_NAME)


static func create_emitter(stream: AudioStream, position: Vector3,
		max_distance: float = 30.0, bus: StringName = &"Ambience") -> Node3D:
	if has_resonance():
		var src: Node3D = ClassDB.instantiate(RESONANCE_CLASS_NAME)
		# Resonance source nodes expose the same `stream`, `bus`, `position`
		# properties as AudioStreamPlayer3D in the upstream addon. If the
		# property names diverge, replace these with set_meta() lookups.
		src.set("stream", stream)
		src.set("bus", bus)
		src.set("max_distance", max_distance)
		src.set("position", position)
		return src
	# Fallback: plain 3D player
	var p: AudioStreamPlayer3D = AudioStreamPlayer3D.new()
	p.stream = stream
	p.bus = bus
	p.max_distance = max_distance
	p.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
	p.position = position
	return p
