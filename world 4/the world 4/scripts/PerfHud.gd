extends CanvasLayer
class_name PerfHud

# W4 perf HUD — small text overlay showing FPS, frame time, draw calls,
# vertex count, and visible mesh count. Drop into any scene; needs no
# configuration. Designed to be cheap to leave on while iterating.
#
# Stats sources:
# - FPS / frame ms: Engine.get_frames_per_second() + Performance singleton
# - Verts / draw calls: Performance.get_monitor(...)
# - Tile count: read from the first ScaleWorld in the tree if present

@export var update_interval_s: float = 0.25
@export var enabled: bool = true

var _label: Label
var _clock: float = 0.0
var _peak_frame_ms: float = 0.0
var _peak_clock: float = 0.0
const PEAK_WINDOW_S: float = 1.5


func _ready() -> void:
	layer = 100  # render above gameplay HUD
	_label = Label.new()
	# Anchor top-right so we don't fight the gameplay HUD in the top-left.
	# GROW_DIRECTION_BEGIN lets the label extend leftward from the right edge
	# as text gets wider (multi-line, large numbers).
	_label.anchor_left = 1.0
	_label.anchor_right = 1.0
	_label.anchor_top = 0.0
	_label.anchor_bottom = 0.0
	_label.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_label.offset_left = -360
	_label.offset_right = -20
	_label.offset_top = 20
	_label.offset_bottom = 120
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_label.add_theme_font_size_override("font_size", 16)
	_label.add_theme_color_override("font_color", Color(0.9, 1.0, 0.9, 1))
	_label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	_label.add_theme_constant_override("shadow_offset_x", 1)
	_label.add_theme_constant_override("shadow_offset_y", 1)
	add_child(_label)
	_refresh()


func _process(delta: float) -> void:
	if not enabled:
		return
	# Track peak frame time over a rolling window — useful for catching
	# the per-tile-build stutters that are easy to miss in an average.
	var frame_ms: float = delta * 1000.0
	if frame_ms > _peak_frame_ms:
		_peak_frame_ms = frame_ms
	_peak_clock += delta
	if _peak_clock >= PEAK_WINDOW_S:
		_peak_clock = 0.0
		_peak_frame_ms = frame_ms

	_clock += delta
	if _clock < update_interval_s:
		return
	_clock = 0.0
	_refresh()


func _refresh() -> void:
	var fps: float = Engine.get_frames_per_second()
	var frame_ms: float = 1000.0 / max(fps, 1.0)
	var verts: int = int(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME))
	var draws: int = int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
	var obj_count: int = int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))

	# Find a ScaleWorld in the tree (optional)
	var tile_info: String = ""
	var sw: Node = get_tree().get_root().find_child("World", true, false)
	if sw != null and sw.has_method("get_world_size"):
		var tile_count: int = sw.get_node_or_null(".").get_child_count() if sw != null else 0
		# Count only MeshInstance3D descendants — children of ScaleWorld
		# are Tile_X_Z node3d wrappers; the actual mesh is one deeper.
		tile_info = "\nTiles: %d" % _count_tile_meshes(sw)

	_label.text = "FPS: %.0f (%.1fms)  peak: %.1fms\nTris: %s  Draws: %d  Nodes: %d%s" % [
		fps, frame_ms, _peak_frame_ms,
		_humanize(verts), draws, obj_count, tile_info
	]


func _count_tile_meshes(root: Node) -> int:
	var n: int = 0
	for child in root.get_children():
		if child.name.begins_with("Tile_"):
			n += 1
	return n


func _humanize(n: int) -> String:
	if n >= 1_000_000:
		return "%.1fM" % (n / 1_000_000.0)
	if n >= 1_000:
		return "%.1fk" % (n / 1_000.0)
	return str(n)
