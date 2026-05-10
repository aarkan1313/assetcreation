extends Control

@export var source_image_path: String = "res://docs/captures/review/source_stack_m12_runtime_fourway_iso_clean.png"
@export var title: String = "world3 M16 Cached Iso Impostor Seed"
@export var contract_note: String = "Baked from M12 runtime parity: same source/material/height/splat contract"
@export var auto_play: bool = true
@export var background_color: Color = Color(0.08, 0.095, 0.10, 1.0)

var _texture: ImageTexture
var _image_size: Vector2 = Vector2.ZERO
var _time: float = 0.0
var _paused: bool = false
var _ui_visible: bool = true
var _overlay_panel: ColorRect
var _overlay_label: Label


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_load_source_texture()
	_setup_overlay()
	queue_redraw()


func _process(delta: float) -> void:
	if auto_play and not _paused:
		_time += delta
	queue_redraw()
	_update_overlay()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		queue_redraw()


func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	match event.keycode:
		KEY_SPACE:
			_paused = not _paused
		KEY_R:
			_time = 0.0
			_paused = false
		KEY_H:
			_ui_visible = not _ui_visible
			if _overlay_panel != null:
				_overlay_panel.visible = _ui_visible
			if _overlay_label != null:
				_overlay_label.visible = _ui_visible


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), background_color, true)
	if _texture == null or _image_size.x <= 0.0 or _image_size.y <= 0.0:
		return

	var view_size: Vector2 = size
	var base_scale: float = max(view_size.x / _image_size.x, view_size.y / _image_size.y)
	var cycle: float = fposmod(_time / 11.0, 1.0)
	var eased: float = _smoothstep(cycle)
	var zoom: float = lerp(1.02, 1.18, eased)
	var pan_phase: float = sin(_time * 0.38)
	var pan := Vector2(pan_phase * view_size.x * 0.035, cos(_time * 0.31) * view_size.y * 0.025)
	var draw_size: Vector2 = _image_size * base_scale * zoom
	var origin: Vector2 = (view_size - draw_size) * 0.5 + pan
	draw_texture_rect(_texture, Rect2(origin, draw_size), false)


func _load_source_texture() -> void:
	var global_path: String = ProjectSettings.globalize_path(source_image_path)
	var img: Image = Image.load_from_file(global_path)
	if img == null:
		push_error("M16IsoImpostorCardReview failed to load " + source_image_path)
		return
	_image_size = Vector2(img.get_width(), img.get_height())
	_texture = ImageTexture.create_from_image(img)


func _setup_overlay() -> void:
	_overlay_panel = ColorRect.new()
	_overlay_panel.color = Color(0.02, 0.025, 0.02, 0.68)
	_overlay_panel.position = Vector2(14.0, 14.0)
	_overlay_panel.size = Vector2(1010.0, 126.0)
	add_child(_overlay_panel)

	_overlay_label = Label.new()
	_overlay_label.position = Vector2(28.0, 24.0)
	_overlay_label.size = Vector2(970.0, 108.0)
	_overlay_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_overlay_label.add_theme_font_size_override("font_size", 18)
	_overlay_label.add_theme_color_override("font_color", Color.WHITE)
	_overlay_label.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 0.9))
	_overlay_label.add_theme_constant_override("outline_size", 6)
	add_child(_overlay_label)
	_update_overlay()


func _update_overlay() -> void:
	if _overlay_label == null:
		return
	var mode: String = "paused" if _paused else "2D cached playback"
	_overlay_label.text = (
		"%s\n%s\nMode: %s | no live terrain mesh/ChunkLoader in this scene | Space pause | R reset | H UI"
	) % [title, contract_note, mode]


func _smoothstep(t: float) -> float:
	var x: float = clampf(t, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)
