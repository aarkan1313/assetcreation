# AudioCueBus - runtime VFX-audio sync.
#
# Per `research/C2_vfx_3d_volumetric.md` §4: audio-reactive VFX is a runtime
# concern, not a bake-time one. FFT-bake never survives variable playback
# (time scaling, hit-stop, replay). Instead, the VFX bake records named cue
# timestamps in `BakeManifest.extras.audio_cues` (a list of {t, name}), and
# this autoload watches AnimatedSprite2D / AnimatedSprite3D frame_changed
# signals to fire `cue_hit(name, effect_id)` events when the cue frame plays.
#
# Cue list format (from `manifest.json`):
#
#   "extras": {
#     "audio_cues": [
#       { "t": 0.05, "name": "impact" },
#       { "t": 0.20, "name": "burst" },
#       { "t": 0.55, "name": "settle" }
#     ]
#   }
#
# Cue `t` is in seconds from animation start; we convert to a frame index
# using `manifest.fps`.
#
# Set up as autoload at `res://vfx/runtime/AudioCueBus.gd` so the bus is
# available everywhere as `AudioCueBus.cue_hit.connect(...)`.
#
# Usage:
#
#   AudioCueBus.register(animated_sprite_2d, "fireball_projectile",
#         load("res://vfx/spell/fireball_projectile/manifest.json"))
#   AudioCueBus.cue_hit.connect(_on_cue_hit)
#
#   func _on_cue_hit(cue_name: String, effect_id: String) -> void:
#       if cue_name == "impact":
#           camera.add_trauma(0.4)
#           sfx.play("res://audio/impact.wav")

class_name AudioCueBus
extends Node


## Emitted when a registered AnimatedSprite reaches a cue's frame threshold.
signal cue_hit(cue_name: String, effect_id: String)

# Active subscriptions: { sprite_node_id -> { effect_id, fps, cues, last_frame } }
var _subs: Dictionary = {}


## Register an AnimatedSprite{2D,3D} for cue tracking. `manifest_path` is the
## VFX manifest.json on disk (or you can pass `cues_dict` directly).
func register(sprite: Node, effect_id: String,
		manifest_path: String = "", cues_override: Array = []) -> void:
	if sprite == null:
		return
	var fps: float = 24.0
	var cues: Array = []
	if cues_override.size() > 0:
		cues = cues_override
	elif manifest_path != "":
		var f := FileAccess.open(manifest_path, FileAccess.READ)
		if f != null:
			var data := JSON.parse_string(f.get_as_text())
			if data is Dictionary:
				fps = float(data.get("fps", 24.0))
				var extras: Variant = data.get("extras", {})
				if extras is Dictionary:
					var ac: Variant = extras.get("audio_cues", [])
					if ac is Array:
						cues = ac
	if cues.size() == 0:
		return  # nothing to subscribe to

	var key: int = sprite.get_instance_id()
	_subs[key] = {
		"effect_id": effect_id,
		"fps": fps,
		"cues": cues,
		"last_frame": -1,
		"sprite": sprite,
	}

	# Connect the frame_changed signal of either AnimatedSprite2D or
	# AnimatedSprite3D. Both expose `frame_changed` and `frame` property.
	if sprite.has_signal("frame_changed"):
		var cb: Callable = Callable(self, "_on_frame_changed").bind(key)
		if not sprite.frame_changed.is_connected(cb):
			sprite.frame_changed.connect(cb)
	# Free on tree-exit so we don't leak.
	if sprite.has_signal("tree_exited"):
		sprite.tree_exited.connect(Callable(self, "unregister").bind(sprite))


## Stop tracking a sprite. Safe to call multiple times.
func unregister(sprite: Node) -> void:
	if sprite == null:
		return
	var key: int = sprite.get_instance_id()
	_subs.erase(key)


func _on_frame_changed(key: int) -> void:
	if not _subs.has(key):
		return
	var sub: Dictionary = _subs[key]
	var sprite: Node = sub["sprite"]
	if sprite == null or not is_instance_valid(sprite):
		_subs.erase(key)
		return
	var frame_idx: int = int(sprite.get("frame"))
	var last: int = int(sub["last_frame"])
	if frame_idx == last:
		return
	# Fire any cues whose threshold frame falls in (last, frame_idx].
	var fps: float = float(sub["fps"])
	var effect_id: String = sub["effect_id"]
	var cues: Array = sub["cues"]
	for cue in cues:
		if not (cue is Dictionary):
			continue
		var t: float = float(cue.get("t", 0.0))
		var threshold: int = int(round(t * fps))
		var cue_name: String = String(cue.get("name", ""))
		if cue_name == "":
			continue
		if last < threshold and frame_idx >= threshold:
			cue_hit.emit(cue_name, effect_id)
	sub["last_frame"] = frame_idx


## Manually fire a cue. Useful for in-engine testing or for cues bound to
## non-sprite events (timed buffs, ability-cast moments).
func fire_manual(cue_name: String, effect_id: String) -> void:
	cue_hit.emit(cue_name, effect_id)


## Diagnostic: how many sprites are currently registered.
func subscription_count() -> int:
	return _subs.size()
