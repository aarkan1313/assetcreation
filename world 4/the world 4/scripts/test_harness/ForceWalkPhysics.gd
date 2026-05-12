extends Node

# Headless-capture helper for the walk-physics landing test.
# Activates the sibling PlayerBody after a few frames so the rig's
# deferred camera-mode-set has settled. Spawns the body 100m above
# the expected terrain peak so gravity has time to land it before
# the capture fires.

@export var player_body_path: NodePath = NodePath("../PlayerBody")
@export var spawn_height_m: float = 1500.0
@export var activate_after_frames: int = 5

var _frames: int = 0
var _activated: bool = false


func _process(_delta: float) -> void:
	if _activated:
		return
	_frames += 1
	if _frames < activate_after_frames:
		return
	var body := get_node_or_null(player_body_path) as PlayerBody
	if body == null:
		push_error("ForceWalkPhysics: PlayerBody not found at " + str(player_body_path))
		_activated = true
		return
	body.global_position = Vector3(0, spawn_height_m, 0)
	body.activate()
	_activated = true
