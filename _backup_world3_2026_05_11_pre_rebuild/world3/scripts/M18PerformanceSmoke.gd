extends Node

@export var output_path: String = "res://docs/captures/review/m18_guided_neighbor_performance_smoke.json"
@export var warmup_frames: int = 120
@export var sample_frames: int = 360
@export var viewport_size: Vector2i = Vector2i(1600, 1000)

var _frame_index: int = 0
var _last_ticks_usec: int = 0
var _samples_ms: Array[float] = []


func _ready() -> void:
	if viewport_size.x > 0 and viewport_size.y > 0:
		get_window().size = viewport_size
	_last_ticks_usec = Time.get_ticks_usec()


func _process(_delta: float) -> void:
	var now: int = Time.get_ticks_usec()
	var frame_ms: float = float(now - _last_ticks_usec) / 1000.0
	_last_ticks_usec = now
	_frame_index += 1
	if _frame_index > warmup_frames:
		_samples_ms.append(frame_ms)
	if _samples_ms.size() >= sample_frames:
		_write_report()
		get_tree().quit(0)


func _write_report() -> void:
	var sorted := _samples_ms.duplicate()
	sorted.sort()
	var sum_ms: float = 0.0
	for value in _samples_ms:
		sum_ms += value
	var avg_ms: float = sum_ms / max(float(_samples_ms.size()), 1.0)
	var p95_ms: float = _percentile(sorted, 0.95)
	var p99_ms: float = _percentile(sorted, 0.99)
	var max_ms: float = sorted[sorted.size() - 1] if not sorted.is_empty() else 0.0
	var report := {
		"version": 1,
		"id": "m18_guided_neighbor_performance_smoke",
		"scene": "res://scenes/review/source_stack_m18_guided_neighbor_tour.tscn",
		"warmup_frames": warmup_frames,
		"sample_frames": _samples_ms.size(),
		"viewport_size": [viewport_size.x, viewport_size.y],
		"frame_ms": {
			"average": avg_ms,
			"p95": p95_ms,
			"p99": p99_ms,
			"max": max_ms
		},
		"fps_estimate": {
			"average": 1000.0 / max(avg_ms, 0.001),
			"p95_frame_time": 1000.0 / max(p95_ms, 0.001)
		},
		"status": "smoke_metric_only_not_optimization_pass"
	}
	var f := FileAccess.open(output_path, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(report, "  ") + "\n")
		f.close()
	print("[m18-performance] wrote " + output_path)


func _percentile(sorted: Array[float], t: float) -> float:
	if sorted.is_empty():
		return 0.0
	var idx := int(round(clampf(t, 0.0, 1.0) * float(sorted.size() - 1)))
	return sorted[clampi(idx, 0, sorted.size() - 1)]
