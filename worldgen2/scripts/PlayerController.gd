extends CharacterBody3D

@export var move_speed_m_s: float = 12.0
@export var sprint_multiplier: float = 4.0
@export var jump_velocity_m_s: float = 8.0
@export var mouse_sensitivity: float = 0.0025
@export var gravity_m_s2: float = 24.0
@export var snap_to_ground_on_ready: bool = true
@export var ground_snap_max_drop_m: float = 5000.0

var _yaw := 0.0
var _pitch := 0.0


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if snap_to_ground_on_ready:
		_snap_to_ground()


func _snap_to_ground() -> void:
	# Cast a ray straight down to find the terrain Y at the player's XZ.
	# Avoids the "fell through the world" edge case if collision is missing.
	var space := get_world_3d().direct_space_state
	var from := global_position + Vector3.UP * 1.0
	var to := from + Vector3.DOWN * ground_snap_max_drop_m
	var query := PhysicsRayQueryParameters3D.create(from, to)
	query.exclude = [self]
	var result := space.intersect_ray(query)
	if result.has("position"):
		global_position = result.position + Vector3.UP * 1.5
		print("[PlayerController] snapped to ground at y=", global_position.y)
	else:
		push_warning("PlayerController: ground snap missed (no collision below)")


func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_yaw -= event.relative.x * mouse_sensitivity
		_pitch = clamp(_pitch - event.relative.y * mouse_sensitivity, -1.4, 1.4)
		rotation.y = _yaw
		var cam := get_node_or_null("CharacterCam")
		if cam:
			cam.rotation.x = _pitch
	if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if event is InputEventMouseButton and event.pressed:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _physics_process(delta: float) -> void:
	var input_v := Vector3.ZERO
	if Input.is_key_pressed(KEY_W): input_v.z -= 1.0
	if Input.is_key_pressed(KEY_S): input_v.z += 1.0
	if Input.is_key_pressed(KEY_A): input_v.x -= 1.0
	if Input.is_key_pressed(KEY_D): input_v.x += 1.0
	input_v = input_v.normalized()

	var speed := move_speed_m_s
	if Input.is_key_pressed(KEY_SHIFT):
		speed *= sprint_multiplier

	var basis_xz := Basis(Vector3.UP, _yaw)
	var move_world := basis_xz * input_v * speed
	velocity.x = move_world.x
	velocity.z = move_world.z

	if not is_on_floor():
		velocity.y -= gravity_m_s2 * delta
	elif Input.is_key_pressed(KEY_SPACE):
		velocity.y = jump_velocity_m_s

	move_and_slide()
