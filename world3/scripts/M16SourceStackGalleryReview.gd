extends Control

@export var manifest_path: String = "res://jobs/m16_source_stack_gallery_manifest.json"
@export var title: String = "world3 M16 Source-Stack Gallery Runner"
@export var auto_play: bool = true
@export var seconds_per_band: float = 4.0
@export var background_color: Color = Color(0.07, 0.085, 0.085, 1.0)

var _cards: Array[Dictionary] = []
var _card_index: int = 0
var _band_index: int = 0
var _time: float = 0.0
var _paused: bool = false
var _ui_visible: bool = true
var _texture: ImageTexture
var _image_size: Vector2 = Vector2.ZERO
var _overlay_panel: ColorRect
var _overlay_label: Label
var _thumbnail_panel: ColorRect
var _thumbnail_label: Label


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_load_manifest()
	_setup_overlay()
	_load_current_texture()
	queue_redraw()


func _process(delta: float) -> void:
	if auto_play and not _paused and not _cards.is_empty():
		_time += delta
		if _time >= max(seconds_per_band, 0.1):
			_time = 0.0
			_advance_band(1)
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
		KEY_N:
			_advance_card(1)
		KEY_B:
			_advance_card(-1)
		KEY_V:
			_advance_band(1)
		KEY_R:
			_card_index = 0
			_band_index = 0
			_time = 0.0
			_paused = false
			_load_current_texture()
		KEY_H:
			_ui_visible = not _ui_visible
			if _overlay_panel != null:
				_overlay_panel.visible = _ui_visible
			if _overlay_label != null:
				_overlay_label.visible = _ui_visible
			if _thumbnail_panel != null:
				_thumbnail_panel.visible = _ui_visible
			if _thumbnail_label != null:
				_thumbnail_label.visible = _ui_visible


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), background_color, true)
	if _texture == null or _image_size.x <= 0.0 or _image_size.y <= 0.0:
		return
	var inset: Vector2 = Vector2(34.0, 156.0)
	var bottom_margin: float = 34.0
	var side_margin: float = 300.0 if size.x >= 1300.0 else 34.0
	var view_rect: Rect2 = Rect2(
		Vector2(inset.x, inset.y),
		Vector2(max(size.x - inset.x - side_margin, 100.0), max(size.y - inset.y - bottom_margin, 100.0))
	)
	var scale: float = min(view_rect.size.x / _image_size.x, view_rect.size.y / _image_size.y)
	var draw_size: Vector2 = _image_size * scale
	var origin: Vector2 = view_rect.position + (view_rect.size - draw_size) * 0.5
	draw_texture_rect(_texture, Rect2(origin, draw_size), false)
	draw_rect(Rect2(origin, draw_size), Color(1, 1, 1, 0.18), false, 1.0)


func _load_manifest() -> void:
	var global_path: String = ProjectSettings.globalize_path(manifest_path)
	var f: FileAccess = FileAccess.open(global_path, FileAccess.READ)
	if f == null:
		push_error("M16SourceStackGalleryReview failed to load " + manifest_path)
		return
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("M16SourceStackGalleryReview manifest is not an object")
		return
	for raw in parsed.get("cards", []):
		if typeof(raw) == TYPE_DICTIONARY:
			_cards.append(raw)


func _setup_overlay() -> void:
	_overlay_panel = ColorRect.new()
	_overlay_panel.color = Color(0.02, 0.025, 0.02, 0.72)
	_overlay_panel.position = Vector2(16.0, 14.0)
	_overlay_panel.size = Vector2(1120.0, 126.0)
	add_child(_overlay_panel)

	_overlay_label = Label.new()
	_overlay_label.position = Vector2(30.0, 24.0)
	_overlay_label.size = Vector2(1080.0, 108.0)
	_overlay_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_overlay_label.add_theme_font_size_override("font_size", 18)
	_overlay_label.add_theme_color_override("font_color", Color.WHITE)
	_overlay_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.92))
	_overlay_label.add_theme_constant_override("outline_size", 6)
	add_child(_overlay_label)

	_thumbnail_panel = ColorRect.new()
	_thumbnail_panel.color = Color(0.02, 0.025, 0.02, 0.68)
	_thumbnail_panel.position = Vector2(0.0, 0.0)
	_thumbnail_panel.size = Vector2(260.0, 420.0)
	add_child(_thumbnail_panel)

	_thumbnail_label = Label.new()
	_thumbnail_label.position = Vector2(0.0, 0.0)
	_thumbnail_label.size = Vector2(232.0, 392.0)
	_thumbnail_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_thumbnail_label.add_theme_font_size_override("font_size", 14)
	_thumbnail_label.add_theme_color_override("font_color", Color(0.88, 0.92, 0.86))
	_thumbnail_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.92))
	_thumbnail_label.add_theme_constant_override("outline_size", 4)
	add_child(_thumbnail_label)
	_update_side_panel_layout()
	_update_overlay()


func _update_side_panel_layout() -> void:
	if _thumbnail_panel == null or _thumbnail_label == null:
		return
	var panel_w: float = 268.0
	var panel_h: float = min(max(size.y - 188.0, 300.0), 560.0)
	var x: float = max(size.x - panel_w - 22.0, 22.0)
	var y: float = 156.0
	_thumbnail_panel.position = Vector2(x, y)
	_thumbnail_panel.size = Vector2(panel_w, panel_h)
	_thumbnail_label.position = Vector2(x + 14.0, y + 14.0)
	_thumbnail_label.size = Vector2(panel_w - 28.0, panel_h - 28.0)


func _update_overlay() -> void:
	_update_side_panel_layout()
	if _cards.is_empty():
		if _overlay_label != null:
			_overlay_label.text = title + "\nNo cards loaded."
		return
	var card := _current_card()
	var band := _current_band()
	var mode := "paused" if _paused else "auto"
	var full := _has_full_bands(card)
	var full_text := "full topdown/iso/medium/close" if full else "sidecar / partial"
	var captures: Dictionary = card.get("captures", {})
	var path_text: String = str(captures.get(band, "missing"))
	if _overlay_label != null:
		_overlay_label.text = (
			"%s\n%d/%d %s | band %s | %s | %s\n%s\nKeys: Space pause | N/B card | V band | R reset | H UI"
		) % [
			title,
			_card_index + 1,
			_cards.size(),
			str(card.get("title", card.get("id", ""))),
			band,
			full_text,
			mode,
			path_text,
		]
	if _thumbnail_label != null:
		var lines: Array[String] = []
		for i in range(_cards.size()):
			var c: Dictionary = _cards[i]
			var marker := ">" if i == _card_index else " "
			var state := "FULL" if _has_full_bands(c) else "SIDE"
			lines.append("%s %d. %s\n   %s" % [marker, i + 1, str(c.get("title", c.get("id", ""))), state])
		_thumbnail_label.text = "\n".join(lines)


func _current_card() -> Dictionary:
	if _cards.is_empty():
		return {}
	return _cards[clampi(_card_index, 0, _cards.size() - 1)]


func _current_band() -> String:
	var bands := _available_bands(_current_card())
	if bands.is_empty():
		return ""
	return bands[clampi(_band_index, 0, bands.size() - 1)]


func _available_bands(card: Dictionary) -> Array[String]:
	var captures: Dictionary = card.get("captures", {})
	var out: Array[String] = []
	for band in ["topdown", "iso", "medium", "close"]:
		if captures.has(band):
			out.append(band)
	return out


func _has_full_bands(card: Dictionary) -> bool:
	var captures: Dictionary = card.get("captures", {})
	for band in ["topdown", "iso", "medium", "close"]:
		if not captures.has(band):
			return false
	return true


func _advance_card(dir: int) -> void:
	if _cards.is_empty():
		return
	_card_index = posmod(_card_index + dir, _cards.size())
	_band_index = 0
	_time = 0.0
	_load_current_texture()


func _advance_band(dir: int) -> void:
	var bands := _available_bands(_current_card())
	if bands.is_empty():
		return
	var next_band := _band_index + dir
	if next_band >= bands.size():
		_advance_card(1)
		return
	if next_band < 0:
		_advance_card(-1)
		return
	_band_index = next_band
	_time = 0.0
	_load_current_texture()


func _load_current_texture() -> void:
	_texture = null
	_image_size = Vector2.ZERO
	if _cards.is_empty():
		return
	var card := _current_card()
	var band := _current_band()
	var captures: Dictionary = card.get("captures", {})
	var repo_path: String = str(captures.get(band, ""))
	var res_path := _repo_to_res_path(repo_path)
	var global_path := ProjectSettings.globalize_path(res_path)
	var img: Image = Image.load_from_file(global_path)
	if img == null:
		push_warning("M16SourceStackGalleryReview failed to load " + repo_path)
		return
	_image_size = Vector2(img.get_width(), img.get_height())
	_texture = ImageTexture.create_from_image(img)


func _repo_to_res_path(path: String) -> String:
	if path.begins_with("res://"):
		return path
	if path.begins_with("world3/"):
		return "res://" + path.substr("world3/".length())
	return path
