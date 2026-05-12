extends Node3D
class_name AnchorCameraRig

# W4 anchor demo — 3-camera rig.
# Three cameras looking at the same world at the same scale. Hotkey 1/2/3
# switches between them. 3D walk camera has WASD + mouse-look.

@export var terrain_path: NodePath
@export var world_center_offset: Vector3 = Vector3.ZERO  # if terrain isn't at origin
@export var walk_speed: float = 30.0
@export var walk_eye_height: float = 4.0
@export var mouse_sensitivity: float = 0.003

# Camera modes
enum CameraMode { WALK, ISO, TOPDOWN }
var _current_mode: CameraMode = CameraMode.WALK

var _camera_walk: Camera3D
var _camera_iso: Camera3D
var _camera_topdown: Camera3D
var _walk_yaw: float = 0.0
var _walk_pitch: float = -0.1
var _mouse_captured: bool = false
var _world_size: Vector2 = Vector2(256.0, 256.0)
var _elev_range: Vector2 = Vector2(0.0, 256.0)
var _hud: Label


func _ready() -> void:
	# Duck-typed: works with AnchorTerrain (single mesh) or ScaleWorld
	# (multi-tile root). Both expose get_world_size() + get_elev_range().
	var terrain: Node = get_node_or_null(terrain_path)
	if terrain != null and terrain.has_method("get_world_size") and terrain.has_method("get_elev_range"):
		_world_size = terrain.call("get_world_size")
		_elev_range = terrain.call("get_elev_range")

	_setup_cameras()
	_setup_hud()
	_set_mode(CameraMode.WALK)


func _setup_cameras() -> void:
	# Walk camera — eye-level standing on the terrain surface at a chosen
	# scenic point. We sample the terrain height under the spawn point so
	# the camera starts ON the ground, not floating in the sky.
	_camera_walk = Camera3D.new()
	_camera_walk.name = "WalkCamera"
	_camera_walk.fov = 70.0
	_camera_walk.near = 0.1
	_camera_walk.far = 2000.0
	add_child(_camera_walk)
	# Spawn at a mid-slope point and look at world center. Position so we
	# can actually see terrain in front of us — pulled back from origin,
	# at mid-elevation, then look_at world center.
	var spawn_y: float = _elev_range.x + (_elev_range.y - _elev_range.x) * 0.55 + walk_eye_height
	_camera_walk.global_position = Vector3(-80.0, spawn_y, -80.0)
	_camera_walk.look_at(
		Vector3(0, (_elev_range.x + _elev_range.y) * 0.4, 0),
		Vector3.UP
	)
	# Capture the resulting rotation for mouse-look continuity
	_walk_yaw = _camera_walk.rotation.y
	_walk_pitch = _camera_walk.rotation.x

	# Iso camera — classic 30° iso angle, framed so the lit side of the
	# slope faces the camera. The sun comes from upper-X-and-Y (light dir
	# ~ +X/-Y/-Z), so positive-X slopes are lit. Iso camera is at
	# +X / +Y / +Z corner looking toward origin and the lit slopes.
	_camera_iso = Camera3D.new()
	_camera_iso.name = "IsoCamera"
	_camera_iso.fov = 38.0
	_camera_iso.near = 0.1
	_camera_iso.far = 4000.0
	add_child(_camera_iso)
	var iso_dist: float = max(_world_size.x, _world_size.y) * 1.0
	_camera_iso.global_position = Vector3(
		iso_dist * 0.7,
		_elev_range.y + iso_dist * 0.55,
		iso_dist * 0.7
	)
	_camera_iso.look_at(
		Vector3(0, (_elev_range.x + _elev_range.y) * 0.5, 0),
		Vector3.UP
	)

	# Topdown camera — straight down, orthographic
	_camera_topdown = Camera3D.new()
	_camera_topdown.name = "TopdownCamera"
	_camera_topdown.projection = Camera3D.PROJECTION_ORTHOGONAL
	_camera_topdown.size = max(_world_size.x, _world_size.y) * 1.05
	_camera_topdown.near = 0.1
	_camera_topdown.far = 2000.0
	add_child(_camera_topdown)
	_camera_topdown.global_position = Vector3(0.0, _elev_range.y + 200.0, 0.0)
	_camera_topdown.look_at(Vector3(0, _elev_range.x, 0), Vector3(0, 0, -1))


func _setup_hud() -> void:
	# Simple text overlay showing current mode + hotkeys
	var canvas: CanvasLayer = CanvasLayer.new()
	canvas.name = "HUD"
	add_child(canvas)
	_hud = Label.new()
	_hud.position = Vector2(20, 20)
	_hud.add_theme_font_size_override("font_size", 18)
	_hud.add_theme_color_override("font_color", Color(1, 1, 1, 1))
	_hud.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.7))
	_hud.add_theme_constant_override("shadow_offset_x", 1)
	_hud.add_theme_constant_override("shadow_offset_y", 1)
	canvas.add_child(_hud)
	_refresh_hud()


func _refresh_hud() -> void:
	if _hud == null:
		return
	var mode_name: String
	var hint: String
	match _current_mode:
		CameraMode.WALK:
			mode_name = "WALK (3D)"
			hint = "WASD + mouse to move  •  Shift = sprint  •  Esc/F = mouse"
		CameraMode.ISO:
			mode_name = "ISO (2.5D)"
			hint = "WASD to pan  •  Shift = sprint"
		CameraMode.TOPDOWN:
			mode_name = "TOPDOWN (2D)"
			hint = "WASD to pan  •  Shift = sprint  •  Scroll = zoom"
	_hud.text = "W4 scale demo\nMode: %s\n[1] Walk  [2] Iso  [3] Topdown\n%s" % [mode_name, hint]


func _set_mode(mode: int) -> void:
	_current_mode = mode
	_camera_walk.current = (mode == CameraMode.WALK)
	_camera_iso.current = (mode == CameraMode.ISO)
	_camera_topdown.current = (mode == CameraMode.TOPDOWN)
	_refresh_hud()
	if mode == CameraMode.WALK:
		_capture_mouse(true)
	else:
		_capture_mouse(false)
	# Notify the world (if any) so it can swap to a per-view material.
	# Duck-typed: works with ScaleWorld + AnchorTerrain alike (anchor
	# ignores it since it has no per-view materials configured).
	var terrain: Node = get_node_or_null(terrain_path)
	if terrain != null and terrain.has_method("set_view_mode"):
		var mode_name: String = "walk"
		match mode:
			CameraMode.WALK: mode_name = "walk"
			CameraMode.ISO: mode_name = "iso"
			CameraMode.TOPDOWN: mode_name = "topdown"
		terrain.call("set_view_mode", mode_name)


func _capture_mouse(capture: bool) -> void:
	if capture:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		_mouse_captured = true
	else:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		_mouse_captured = false


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_1: _set_mode(CameraMode.WALK)
			KEY_2: _set_mode(CameraMode.ISO)
			KEY_3: _set_mode(CameraMode.TOPDOWN)
			KEY_ESCAPE: _capture_mouse(false)
			KEY_F:
				# Re-capture mouse (useful after escape)
				if _current_mode == CameraMode.WALK:
					_capture_mouse(true)
	if _current_mode == CameraMode.WALK and event is InputEventMouseMotion and _mouse_captured:
		var mm: InputEventMouseMotion = event
		_walk_yaw -= mm.relative.x * mouse_sensitivity
		_walk_pitch -= mm.relative.y * mouse_sensitivity
		_walk_pitch = clamp(_walk_pitch, -PI / 2 + 0.01, PI / 2 - 0.01)
		_camera_walk.rotation = Vector3(_walk_pitch, _walk_yaw, 0.0)
	# Topdown scroll-wheel zoom — adjust orthographic `size`. Smaller =
	# closer in, larger = further out. Clamp so we don't invert or zoom
	# to absurd extremes.
	if _current_mode == CameraMode.TOPDOWN and event is InputEventMouseButton:
		var mb: InputEventMouseButton = event
		if mb.pressed:
			var min_size: float = 64.0   # zoomed in: ~64m field
			var max_size: float = max(_world_size.x, _world_size.y) * 2.0
			var factor: float = 1.0
			if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
				factor = 0.85  # zoom in
			elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				factor = 1.18  # zoom out (inverse of 0.85 for symmetric scrolls)
			if factor != 1.0:
				_camera_topdown.size = clamp(_camera_topdown.size * factor, min_size, max_size)


func _process(delta: float) -> void:
	match _current_mode:
		CameraMode.WALK: _process_walk(delta)
		CameraMode.ISO: _process_iso(delta)
		CameraMode.TOPDOWN: _process_topdown(delta)


# Iso pan: WASD moves the camera + its look_at target together in world
# XZ. No rotation, no zoom yet. Sprint via Shift.
func _process_iso(delta: float) -> void:
	var pan := _wasd_xz()
	if pan.length() < 0.01:
		return
	pan = pan.normalized()
	var speed: float = walk_speed * 4.0  # iso surveys faster than walk
	if Input.is_key_pressed(KEY_SHIFT):
		speed *= 3.0
	var step: Vector3 = Vector3(pan.x, 0.0, pan.y) * speed * delta
	_camera_iso.global_position += step


# Topdown pan + zoom: WASD moves camera in world XZ. Scroll wheel
# zooms the orthographic `size`. Always looks straight down.
func _process_topdown(delta: float) -> void:
	var pan := _wasd_xz()
	if pan.length() >= 0.01:
		pan = pan.normalized()
		var speed: float = walk_speed * 8.0  # topdown surveys fastest
		if Input.is_key_pressed(KEY_SHIFT):
			speed *= 3.0
		var step: Vector3 = Vector3(pan.x, 0.0, pan.y) * speed * delta
		_camera_topdown.global_position += step


# Returns a Vector2 of WASD input in screen-relative XZ axes.
# +x = right (D), -x = left (A), +y = down/forward (S), -y = up/back (W).
# For an iso camera looking at +X+Z, this means W reduces Z (moves away
# from origin along Z) and so on — feels natural enough at iso angle.
func _wasd_xz() -> Vector2:
	var v := Vector2.ZERO
	if Input.is_key_pressed(KEY_W): v.y -= 1.0
	if Input.is_key_pressed(KEY_S): v.y += 1.0
	if Input.is_key_pressed(KEY_A): v.x -= 1.0
	if Input.is_key_pressed(KEY_D): v.x += 1.0
	return v


func _process_walk(delta: float) -> void:
	# WASD + Q/E vertical movement, applied in camera-local space
	var move := Vector3.ZERO
	if Input.is_key_pressed(KEY_W): move.z -= 1.0
	if Input.is_key_pressed(KEY_S): move.z += 1.0
	if Input.is_key_pressed(KEY_A): move.x -= 1.0
	if Input.is_key_pressed(KEY_D): move.x += 1.0
	if Input.is_key_pressed(KEY_Q): move.y -= 1.0
	if Input.is_key_pressed(KEY_E): move.y += 1.0
	if move.length() < 0.01:
		return
	move = move.normalized()
	# Transform to world space using camera rotation
	var basis := _camera_walk.global_transform.basis
	var speed: float = walk_speed
	if Input.is_key_pressed(KEY_SHIFT):
		speed *= 4.0  # sprint
	var world_move: Vector3 = (basis.x * move.x + basis.y * move.y + basis.z * move.z) * speed * delta
	_camera_walk.global_position += world_move
