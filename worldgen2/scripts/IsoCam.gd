extends Camera3D

# Look-at target in world coordinates. Set in the scene file (or via inspector).
@export var target: Vector3 = Vector3.ZERO


func _ready() -> void:
	# Defer one frame so the global_position is finalised before look_at.
	await get_tree().process_frame
	look_at(target, Vector3.UP)
