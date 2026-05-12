extends Camera3D

# Free-fly debug camera. WASD + space/ctrl. Mouse look while RMB held.
@export var move_speed: float = 200.0
@export var fast_mult: float = 4.0
@export var look_sensitivity: float = 0.003

var _yaw: float = 0.0
var _pitch: float = -0.4
var _looking: bool = false


func _ready() -> void:
	_yaw = rotation.y
	_pitch = rotation.x


func sync_from_transform() -> void:
	_yaw = rotation.y
	_pitch = rotation.x


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT:
		_looking = event.pressed
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if _looking else Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseMotion and _looking:
		_yaw -= event.relative.x * look_sensitivity
		_pitch = clamp(_pitch - event.relative.y * look_sensitivity, -1.5, 1.5)
		rotation = Vector3(_pitch, _yaw, 0)


func _process(delta: float) -> void:
	var input := Vector3.ZERO
	if Input.is_action_pressed("move_forward"): input.z -= 1
	if Input.is_action_pressed("move_back"): input.z += 1
	if Input.is_action_pressed("move_left"): input.x -= 1
	if Input.is_action_pressed("move_right"): input.x += 1
	if Input.is_action_pressed("move_jump"): input.y += 1
	if Input.is_key_pressed(KEY_CTRL): input.y -= 1
	var speed := move_speed
	if Input.is_key_pressed(KEY_SHIFT): speed *= fast_mult
	var dir := (transform.basis * input).normalized() if input.length() > 0 else Vector3.ZERO
	position += dir * speed * delta
