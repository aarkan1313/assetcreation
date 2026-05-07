extends CharacterBody3D

# Walker with fly toggle.
#   WASD            move
#   Space           jump (walk) / up (fly)
#   Ctrl            down (fly)
#   Shift           run / fast fly
#   F               toggle fly mode
#   Esc             release mouse
@export var walk_speed: float = 30.0
@export var fly_speed: float = 200.0
@export var run_mult: float = 4.0
@export var jump_speed: float = 60.0
@export var gravity: float = 200.0
@export var look_sensitivity: float = 0.0025
@export var fly_mode: bool = true  # start in fly so falling-through is impossible
@export var fall_recover_y: float = -1000.0  # if we ever fall past this, teleport up

@onready var _cam: Camera3D = $Camera3D
var _yaw: float = 0.0
var _pitch: float = 0.0
var _spawn_y: float = 0.0


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	# Tilt the camera down a bit so the initial view sees the terrain
	# (matters for headless captures; mouse-look overrides this in play).
	_pitch = -0.5
	_cam.rotation.x = _pitch
	_spawn_y = global_position.y


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_yaw -= event.relative.x * look_sensitivity
		_pitch = clamp(_pitch - event.relative.y * look_sensitivity, -1.4, 1.4)
		rotation.y = _yaw
		_cam.rotation.x = _pitch
	elif event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_ESCAPE:
				Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
			KEY_F:
				fly_mode = not fly_mode
				velocity = Vector3.ZERO
				print("[walker] fly_mode=", fly_mode)


func _physics_process(delta: float) -> void:
	# Recovery: if we fall through somehow, teleport above spawn.
	if global_position.y < fall_recover_y:
		global_position = Vector3(global_position.x, _spawn_y, global_position.z)
		velocity = Vector3.ZERO
		return

	var input2d := Vector2.ZERO
	if Input.is_action_pressed("move_forward"): input2d.y -= 1
	if Input.is_action_pressed("move_back"): input2d.y += 1
	if Input.is_action_pressed("move_left"): input2d.x -= 1
	if Input.is_action_pressed("move_right"): input2d.x += 1
	input2d = input2d.normalized()
	var fast: bool = Input.is_key_pressed(KEY_SHIFT)

	var speed: float
	var move_basis: Basis
	var fwd: Vector3
	var right: Vector3

	if fly_mode:
		speed = fly_speed * (run_mult if fast else 1.0)
		# Camera-relative movement so look direction drives flight.
		move_basis = _cam.global_transform.basis
		fwd = -move_basis.z
		right = move_basis.x
		var dir: Vector3 = fwd * -input2d.y + right * input2d.x
		var vy: float = 0.0
		if Input.is_action_pressed("move_jump"): vy += 1.0
		if Input.is_key_pressed(KEY_CTRL): vy -= 1.0
		var has_input: bool = dir.length() > 0 or vy != 0.0
		velocity = (dir + Vector3.UP * vy).normalized() * speed if has_input else Vector3.ZERO
		move_and_slide()
		return

	# Walk mode.
	speed = walk_speed * (run_mult if fast else 1.0)
	move_basis = global_transform.basis
	fwd = -move_basis.z
	right = move_basis.x
	fwd.y = 0; right.y = 0
	fwd = fwd.normalized(); right = right.normalized()
	var horiz: Vector3 = (fwd * -input2d.y + right * input2d.x) * speed
	velocity.x = horiz.x
	velocity.z = horiz.z
	if is_on_floor():
		if Input.is_action_just_pressed("move_jump"):
			velocity.y = jump_speed
	else:
		velocity.y -= gravity * delta
	move_and_slide()
