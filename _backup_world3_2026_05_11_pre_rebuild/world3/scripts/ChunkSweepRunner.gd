extends Node
class_name ChunkSweepRunner

@export var loader_path: NodePath
@export var target_path: NodePath
@export var camera_path: NodePath
@export var output_dir: String = "res://docs/captures/phase_f/chunk_sweep"
@export var chunk_sizes_m: PackedInt32Array = PackedInt32Array([256, 512, 1024])
@export var chunk_resolution_m: float = 8.0
@export var warmup_frames: int = 12
@export var frames_per_size: int = 96

var _results: Array = []


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var loader: Variant = get_node_or_null(loader_path)
	var target: Node3D = get_node_or_null(target_path) as Node3D
	var camera: Camera3D = get_node_or_null(camera_path) as Camera3D
	if loader == null or target == null or camera == null:
		push_error("ChunkSweepRunner: loader, target, or camera path is invalid")
		get_tree().quit(1)
		return

	var abs_dir: String = ProjectSettings.globalize_path(output_dir)
	var err: int = DirAccess.make_dir_recursive_absolute(abs_dir)
	if err != OK:
		push_error("ChunkSweepRunner: failed to create " + abs_dir)
		get_tree().quit(1)
		return

	for size in chunk_sizes_m:
		var result: Dictionary = await _run_one_size(loader, target, camera, int(size), abs_dir)
		_results.append(result)

	var json_path: String = abs_dir.path_join("chunk_sweep_metrics.json")
	var f: FileAccess = FileAccess.open(json_path, FileAccess.WRITE)
	if f == null:
		push_error("ChunkSweepRunner: failed to write " + json_path)
		get_tree().quit(1)
		return
	f.store_string(JSON.stringify({
		"height_source": loader.heightmap_path,
		"chunk_resolution_m": chunk_resolution_m,
		"view_radius_chunks": loader.view_radius_chunks,
		"results": _results,
	}, "\t"))
	f.close()
	print("[chunk_sweep] wrote " + json_path)
	get_tree().quit(0)


func _run_one_size(loader: Variant, target: Node3D, camera: Camera3D, size_m: int, abs_dir: String) -> Dictionary:
	loader.configure_for_sweep(float(size_m), chunk_resolution_m)
	target.global_position = Vector3(-float(size_m) * 0.75, 0.0, 0.0)
	loader.update_for_position(target.global_position)
	await _wait_frames(warmup_frames)

	var frame_ms: Array = []
	var load_ms: Array = []
	var peak_video_mem_bytes: float = 0.0
	var peak_chunks: int = loader.get_loaded_chunk_count()

	for i in range(frames_per_size):
		var denom: float = max(float(frames_per_size - 1), 1.0)
		var t: float = float(i) / denom
		var x: float = lerp(-float(size_m) * 1.25, float(size_m) * 1.75, t)
		var z: float = sin(t * TAU) * float(size_m) * 0.25
		target.global_position = Vector3(x, 0.0, z)

		var frame_started: int = Time.get_ticks_usec()
		loader.update_for_position(target.global_position)
		load_ms.append(float(loader.last_update_usec) / 1000.0)
		await get_tree().process_frame
		frame_ms.append(float(Time.get_ticks_usec() - frame_started) / 1000.0)

		peak_chunks = max(peak_chunks, loader.get_loaded_chunk_count())
		peak_video_mem_bytes = max(
			peak_video_mem_bytes,
			float(Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED))
		)

	await _capture_seam(loader, target, camera, size_m, abs_dir)

	return {
		"chunk_size_m": size_m,
		"subdivisions_per_chunk": int(round(float(size_m) / chunk_resolution_m)),
		"steady_loaded_chunks": loader.get_loaded_chunk_count(),
		"peak_loaded_chunks": peak_chunks,
		"chunks_built": loader.chunks_built,
		"chunks_removed": loader.chunks_removed,
		"frame_ms_mean": _mean(frame_ms),
		"frame_ms_p95": _percentile(frame_ms, 0.95),
		"frame_ms_p99": _percentile(frame_ms, 0.99),
		"load_ms_worst": _max_value(load_ms),
		"load_ms_p95": _percentile(load_ms, 0.95),
		"peak_video_mem_mb": peak_video_mem_bytes / (1024.0 * 1024.0),
		"seam_capture": "chunk_%dm_seam.png" % size_m,
	}


func _capture_seam(loader: Variant, target: Node3D, camera: Camera3D, size_m: int, abs_dir: String) -> void:
	var seam_x: float = 0.0
	var seam_z: float = 0.0
	var seam_y: float = loader.sample_height_global(seam_x, seam_z)
	target.global_position = Vector3(seam_x, 0.0, seam_z)
	loader.update_for_position(target.global_position)

	var cam_dist: float = max(float(size_m) * 1.45, 650.0)
	camera.global_position = Vector3(float(size_m) * 0.35, seam_y + cam_dist, -float(size_m) * 1.10)
	camera.look_at(Vector3(seam_x, seam_y, seam_z), Vector3.UP)
	await _wait_frames(8)

	var img: Image = get_viewport().get_texture().get_image()
	var png_path: String = abs_dir.path_join("chunk_%dm_seam.png" % size_m)
	img.save_png(png_path)
	print("[chunk_sweep] wrote " + png_path)


func _wait_frames(count: int) -> void:
	for _i in range(count):
		await get_tree().process_frame


func _mean(values: Array) -> float:
	if values.is_empty():
		return 0.0
	var total: float = 0.0
	for v in values:
		total += float(v)
	return total / float(values.size())


func _percentile(values: Array, p: float) -> float:
	if values.is_empty():
		return 0.0
	var sorted: Array = values.duplicate()
	sorted.sort()
	var idx: int = clampi(int(ceil(float(sorted.size()) * p)) - 1, 0, sorted.size() - 1)
	return float(sorted[idx])


func _max_value(values: Array) -> float:
	if values.is_empty():
		return 0.0
	var m: float = float(values[0])
	for v in values:
		m = max(m, float(v))
	return m
