class_name PlayerBody
extends CharacterBody3D

# Test-harness walk-physics body. Sits BESIDE AnchorCameraRig in
# test scenes — does not modify the rig itself. Two cameras exist
# in the scene at once: the rig's WalkCamera (fly-cam) and this
# body's PlayerCamera (physics-cam). The `G` hotkey toggles which
# camera is `current` on the viewport, swapping between fly and
# walk-physics seamlessly.
#
# Modular by design: anchor, scale_demo, and the existing clipmap
# capture scenes never spawn a PlayerBody, so they're entirely
# unaffected. Only opt-in test scenes include this node.
#
# This is a TEST HARNESS, not a shipping player controller. Final
# gameplay player will be a separate, game-specific implementation.

@export var rig_walk_camera_path: NodePath
@export var walk_speed: float = 6.0
@export var sprint_multiplier: float = 2.5
@export var mouse_sensitivity: float = 0.003
@export var eye_height: float = 1.6
# Initial upward velocity on jump. With 9.81 gravity, jump_speed=5.5
# clears ~1.5m vertical (v² / 2g). Tune to taste.
@export var jump_speed: float = 5.5

const GRAVITY_M_S2 := 9.81
const CAPSULE_HEIGHT := 1.8
const CAPSULE_RADIUS := 0.4

var _player_camera: Camera3D
var _player_collision: CollisionShape3D
var _rig_walk_camera: Camera3D = null
var _active: bool = false
var _mouse_captured: bool = false
var _yaw: float = 0.0
var _pitch: float = 0.0
var _hud_label: Label = null


func _ready() -> void:
	_build_collision()
	_build_camera()
	_build_hud()
	# Cache the rig's walk camera so toggling cheap (no get_node per frame).
	if rig_walk_camera_path != NodePath(""):
		var n := get_node_or_null(rig_walk_camera_path)
		if n is Camera3D:
			_rig_walk_camera = n
	# Start inactive — rig's camera is current, fly mode is default.
	_player_camera.current = false


func _build_collision() -> void:
	_player_collision = CollisionShape3D.new()
	_player_collision.name = "PlayerCollision"
	var capsule := CapsuleShape3D.new()
	capsule.height = CAPSULE_HEIGHT
	capsule.radius = CAPSULE_RADIUS
	_player_collision.shape = capsule
	# Capsule center at half-height so the capsule's bottom sphere
	# sits at the body's origin (= floor).
	_player_collision.position = Vector3(0, CAPSULE_HEIGHT * 0.5, 0)
	add_child(_player_collision)


func _build_camera() -> void:
	_player_camera = Camera3D.new()
	_player_camera.name = "PlayerCamera"
	_player_camera.fov = 70.0
	_player_camera.near = 0.1
	_player_camera.far = 4000.0
	_player_camera.position = Vector3(0, eye_height, 0)
	add_child(_player_camera)


func _build_hud() -> void:
	# Minimal HUD so the user can see the toggle state. Anchored to
	# top-left, doesn't conflict with the rig's HUD layout (which is
	# also top-left but on its own CanvasLayer — both stack).
	var canvas := CanvasLayer.new()
	canvas.name = "PlayerHUD"
	canvas.layer = 100  # above rig's HUD
	add_child(canvas)
	_hud_label = Label.new()
	_hud_label.text = "[G] toggle walk-physics  •  [Space] jump  (currently: fly)"
	_hud_label.position = Vector2(20, 160)
	_hud_label.add_theme_color_override("font_color", Color(1.0, 1.0, 0.6))
	canvas.add_child(_hud_label)


func activate() -> void:
	# Warp to the rig camera's current position so the transition
	# feels seamless — no teleport across the map.
	if _rig_walk_camera != null:
		var p: Vector3 = _rig_walk_camera.global_position
		# Body origin is at the player's feet; spawn so feet are
		# below where the rig camera was floating.
		global_position = Vector3(p.x, p.y - eye_height, p.z)
		# Inherit yaw from the rig camera's facing direction.
		_yaw = _rig_walk_camera.global_rotation.y
		_pitch = clamp(_rig_walk_camera.global_rotation.x, -1.4, 1.4)
	_active = true
	velocity = Vector3.ZERO
	_player_camera.current = true
	if _rig_walk_camera != null:
		_rig_walk_camera.current = false
	# Capture the mouse automatically so the user can look around
	# immediately. Esc/F still toggles it for menu access.
	_set_mouse_captured(true)
	_update_hud()
	_apply_look()


func deactivate() -> void:
	_active = false
	if _rig_walk_camera != null:
		_rig_walk_camera.current = true
	_player_camera.current = false
	# Release the mouse so the user can interact with the editor UI
	# (or whatever surrounds the viewport in fly mode). The rig may
	# re-capture if its own walk mode is active.
	_set_mouse_captured(false)
	_update_hud()


func _update_hud() -> void:
	if _hud_label == null:
		return
	_hud_label.text = "[G] toggle walk-physics  •  [Space] jump  (currently: %s)" % (
		"PHYSICS" if _active else "fly"
	)


func _input(event: InputEvent) -> void:
	# G toggles fly ↔ walk-physics regardless of mouse capture state.
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_G:
			if _active:
				deactivate()
			else:
				activate()
			return
		if _active:
			if event.keycode == KEY_ESCAPE or event.keycode == KEY_F:
				_set_mouse_captured(not _mouse_captured)
				return
	# Click anywhere in the viewport while active re-captures the
	# mouse (standard FPS pattern: Esc releases, click re-grabs).
	if _active and not _mouse_captured \
			and event is InputEventMouseButton and event.pressed:
		_set_mouse_captured(true)
		return
	# Mouse-look only when this body's camera is active AND mouse is
	# captured.
	if _active and _mouse_captured and event is InputEventMouseMotion:
		_yaw -= event.relative.x * mouse_sensitivity
		_pitch -= event.relative.y * mouse_sensitivity
		_pitch = clamp(_pitch, -1.4, 1.4)
		_apply_look()


func _set_mouse_captured(b: bool) -> void:
	_mouse_captured = b
	if b:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	else:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _apply_look() -> void:
	# Yaw rotates the body itself (so move-forward is camera-forward).
	# Pitch rotates only the camera.
	rotation.y = _yaw
	_player_camera.rotation.x = _pitch
	_player_camera.rotation.y = 0.0
	_player_camera.rotation.z = 0.0


func _physics_process(delta: float) -> void:
	if not _active:
		return
	var grounded := is_on_floor()
	if grounded:
		velocity.y = 0.0
		# Jump (Space): set initial upward velocity. Gravity does the
		# rest. Only fires when grounded — no double-jump.
		if Input.is_key_pressed(KEY_SPACE):
			velocity.y = jump_speed
	else:
		velocity.y -= GRAVITY_M_S2 * delta
	var dir := _walk_input_direction()
	var speed := walk_speed
	if Input.is_key_pressed(KEY_SHIFT):
		speed *= sprint_multiplier
	velocity.x = dir.x * speed
	velocity.z = dir.z * speed
	move_and_slide()


func _walk_input_direction() -> Vector3:
	var dir := Vector3.ZERO
	var fwd := -global_transform.basis.z
	var right := global_transform.basis.x
	fwd.y = 0.0
	right.y = 0.0
	if fwd.length() > 1e-4:
		fwd = fwd.normalized()
	if right.length() > 1e-4:
		right = right.normalized()
	if Input.is_key_pressed(KEY_W): dir += fwd
	if Input.is_key_pressed(KEY_S): dir -= fwd
	if Input.is_key_pressed(KEY_A): dir -= right
	if Input.is_key_pressed(KEY_D): dir += right
	if dir.length() > 0.001:
		dir = dir.normalized()
	return dir
