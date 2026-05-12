extends Node
class_name AutoWalker

# Auto-walker / micro-profiler for scale_demo perf testing.
#
# Drives the walk camera along a fixed back-and-forth path that crosses
# tile boundaries repeatedly. Samples FPS / peak frame ms / tile count
# at fixed intervals and prints a summary to stdout when the path
# finishes (or when its time budget runs out, headless-safe).
#
# Use:
# - Add as a child of a scale_demo-style scene (or use the capture_scale_walk_auto.tscn)
# - Set `enabled = true` (default) and run the scene
# - Walks along a straight line at walk_speed, reversing every leg_distance_m
# - Prints periodic stats + a final summary, then quits the engine in
#   headless mode (autodetected)
#
# Why: lets us measure the boundary-cross hitch numerically without
# needing the user to eyeball the editor every iteration.

@export var enabled: bool = true
# Distance to walk in each direction before reversing. 600m = ~2-3 tile
# boundary crosses each leg at 256m tiles.
@export var leg_distance_m: float = 600.0
@export var walk_speed: float = 12.0
# How many legs to do before stopping. 4 = forward-back-forward-back.
@export var leg_count: int = 4
# Period between stat samples. 0.1s = 10 samples/s, dense enough to
# catch one-frame spikes during the leg.
@export var sample_interval_s: float = 0.1
# Force a specific camera mode at startup. "auto" = leave as-is.
@export_enum("auto", "walk", "iso", "topdown") var force_camera_mode: String = "walk"
# Quit the engine when done (headless). In editor mode, just print and stop.
@export var quit_on_finish: bool = true


var _camera: Camera3D
var _rig: Node
var _start_pos: Vector3 = Vector3.ZERO
var _direction: int = 1
var _leg_progress_m: float = 0.0
var _legs_done: int = 0
var _finished: bool = false
var _start_time: int = 0

# Stat accumulators
var _sample_clock: float = 0.0
var _samples: Array = []  # each: {t, fps, peak_ms, frame_ms, tiles, verts}
var _frame_ms_max_window: float = 0.0
var _frame_ms_window_clock: float = 0.0
const PEAK_WINDOW_S: float = 0.5

# Hitch detection
const HITCH_THRESHOLD_MS: float = 33.0  # anything > ~30fps single-frame
var _hitch_count: int = 0
var _hitch_ms_total: float = 0.0


func _ready() -> void:
	if not enabled:
		return
	_start_time = Time.get_ticks_msec()
	_rig = get_tree().get_root().find_child("CameraRig", true, false)
	if _rig != null and force_camera_mode != "auto" and _rig.has_method("_set_mode"):
		var mode_int: int = 0
		match force_camera_mode:
			"walk":    mode_int = 0
			"iso":     mode_int = 1
			"topdown": mode_int = 2
		_rig.call_deferred("_set_mode", mode_int)


func _process(delta: float) -> void:
	if not enabled or _finished:
		return
	# Resolve walk camera lazily — the rig builds cameras in its own _ready.
	if _camera == null:
		_camera = get_viewport().get_camera_3d()
		if _camera == null:
			return
		_start_pos = _camera.global_position

	# Track peak frame ms over a rolling window.
	var frame_ms: float = delta * 1000.0
	if frame_ms > _frame_ms_max_window:
		_frame_ms_max_window = frame_ms
	_frame_ms_window_clock += delta
	if _frame_ms_window_clock >= PEAK_WINDOW_S:
		_frame_ms_window_clock = 0.0
		_frame_ms_max_window = frame_ms

	# Hitch detection — count frames > threshold
	if frame_ms > HITCH_THRESHOLD_MS:
		_hitch_count += 1
		_hitch_ms_total += frame_ms

	# Drive the camera along the path.
	var step: float = walk_speed * delta * float(_direction)
	_camera.global_position.x += step
	_leg_progress_m += abs(step)
	if _leg_progress_m >= leg_distance_m:
		_direction *= -1
		_leg_progress_m = 0.0
		_legs_done += 1
		print("[AutoWalker] leg %d done, reversing" % _legs_done)
		if _legs_done >= leg_count:
			_finish()
			return

	# Sample stats periodically.
	_sample_clock += delta
	if _sample_clock >= sample_interval_s:
		_sample_clock = 0.0
		_record_sample(frame_ms)


func _record_sample(frame_ms: float) -> void:
	var t: float = float(Time.get_ticks_msec() - _start_time) / 1000.0
	var fps: float = Engine.get_frames_per_second()
	var tris: int = int(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME))
	var draws: int = int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
	# Tile count = children of the World node named Tile_*
	var tile_count: int = 0
	var sw: Node = get_tree().get_root().find_child("World", true, false)
	if sw != null:
		for child in sw.get_children():
			if child.name.begins_with("Tile_"):
				tile_count += 1
	_samples.append({
		"t": t,
		"fps": fps,
		"frame_ms": frame_ms,
		"peak_ms": _frame_ms_max_window,
		"tris": tris,
		"draws": draws,
		"tiles": tile_count,
	})


func _finish() -> void:
	_finished = true
	print()
	print("============================================================")
	print("[AutoWalker] FINISHED — %d legs × %.0fm at %.1fm/s" % [_legs_done, leg_distance_m, walk_speed])
	print("============================================================")
	_print_summary()
	if quit_on_finish:
		get_tree().quit(0)


func _print_summary() -> void:
	if _samples.is_empty():
		print("  no samples recorded")
		return
	# Skip the first ~1s of samples — initial scene-load freeze pollutes
	# the steady-state numbers.
	var warmup_seconds: float = 1.5
	var stable: Array = []
	for s in _samples:
		if s.t > warmup_seconds:
			stable.append(s)
	if stable.is_empty():
		stable = _samples

	var fps_total: float = 0.0
	var fps_min: float = INF
	var ms_total: float = 0.0
	var ms_max: float = 0.0
	var tiles_total: int = 0
	var tris_total: int = 0
	for s in stable:
		fps_total += s.fps
		fps_min = min(fps_min, s.fps)
		ms_total += s.frame_ms
		ms_max = max(ms_max, s.peak_ms)
		tiles_total += s.tiles
		tris_total += s.tris
	var n: int = stable.size()
	print("  samples (post-warmup): %d  (warmup discarded: %d)" % [n, _samples.size() - n])
	print("  FPS avg: %.1f   min: %.1f" % [fps_total / n, fps_min])
	print("  frame ms avg: %.2f   peak (rolling 0.5s window): %.2f" % [ms_total / n, ms_max])
	print("  tiles avg: %.1f   tris avg: %s" % [float(tiles_total) / n, _humanize(tris_total / n)])
	print("  hitches > %.0fms: %d (total %.0fms over %.1fs)" % [
		HITCH_THRESHOLD_MS, _hitch_count, _hitch_ms_total,
		float(Time.get_ticks_msec() - _start_time) / 1000.0
	])


func _humanize(n: int) -> String:
	if n >= 1_000_000:
		return "%.1fM" % (n / 1_000_000.0)
	if n >= 1_000:
		return "%.1fk" % (n / 1_000.0)
	return str(n)
