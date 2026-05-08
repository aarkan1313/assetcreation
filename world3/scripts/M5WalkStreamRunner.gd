extends SceneTree


func _arg_value(name: String, default_value: String) -> String:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i in range(args.size()):
		if args[i] == name and i + 1 < args.size():
			return args[i + 1]
	return default_value


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var scene_path: String = _arg_value("--scene", "res://scenes/walk.tscn")
	var out_path: String = _arg_value("--out", "res://docs/captures/m5/walk_stream_after_crossing.png")
	var metrics_path: String = _arg_value("--metrics", "res://docs/captures/m5/walk_stream_smoke_metrics.json")
	var frames: int = maxi(2, int(_arg_value("--frames", "360")))
	var width: int = int(_arg_value("--width", "1920"))
	var height: int = int(_arg_value("--height", "1080"))

	var root_view: Window = get_root()
	root_view.size = Vector2i(width, height)

	var scene_res: Resource = load(scene_path)
	if scene_res == null:
		push_error("[m5] could not load scene: " + scene_path)
		quit(2)
		return

	var scene: Node = scene_res.instantiate()
	root_view.add_child(scene)

	for i in range(30):
		await process_frame
		await RenderingServer.frame_post_draw

	var player: Node3D = scene.get_node_or_null("Player") as Node3D
	var loader: Node = scene.get_node_or_null("ChunkLoader")
	if player == null or loader == null:
		push_error("[m5] walk scene is missing Player or ChunkLoader")
		quit(3)
		return

	if loader.has_method("reset_metrics"):
		loader.call("reset_metrics")

	var start_z: float = player.global_position.z
	var end_z: float = start_z + 900.0
	var x: float = player.global_position.x
	var clearance_m: float = 135.0
	var start_y: float = float(loader.call("sample_height_global", x, start_z)) + clearance_m
	var end_y: float = start_y
	var worst_update_usec: int = 0
	var samples: Array = []

	for frame in range(frames):
		var t: float = float(frame) / float(frames - 1)
		var z: float = lerp(start_z, end_z, t)
		var terrain_y: float = float(loader.call("sample_height_global", x, z))
		var player_y: float = terrain_y + clearance_m
		player.global_position = Vector3(x, player_y, z)
		player.rotation.y = PI
		end_y = player_y

		if loader.has_method("update_for_position"):
			loader.call("update_for_position", player.global_position)
		worst_update_usec = maxi(worst_update_usec, int(loader.get("last_update_usec")))

		if frame % 60 == 0 or frame == frames - 1:
			var coords: Vector2i = loader.call("chunk_coords_for", player.global_position)
			samples.append({
				"frame": frame,
				"z": z,
				"chunk": [coords.x, coords.y],
				"loaded_chunks": int(loader.call("get_loaded_chunk_count")),
				"last_update_ms": float(loader.get("last_update_usec")) / 1000.0
			})

		await process_frame
		await RenderingServer.frame_post_draw

	var img: Image = root_view.get_texture().get_image()
	if img == null:
		push_error("[m5] image is null")
		quit(4)
		return

	var global_out: String = ProjectSettings.globalize_path(out_path)
	var rc: int = img.save_png(global_out)

	var metrics := {
		"scene": scene_path,
		"capture": out_path,
		"frames": frames,
		"chunk_size_m": float(loader.get("chunk_size_m")),
		"chunk_resolution_m": float(loader.get("chunk_resolution_m")),
		"view_radius_chunks": int(loader.get("view_radius_chunks")),
		"start_position": [x, start_y, start_z],
		"end_position": [x, end_y, end_z],
		"distance_z_m": end_z - start_z,
		"peak_loaded_chunks": int(loader.get("peak_loaded_chunks")),
		"chunks_built": int(loader.get("chunks_built")),
		"chunks_removed": int(loader.get("chunks_removed")),
		"worst_update_ms": float(worst_update_usec) / 1000.0,
		"samples": samples
	}

	var global_metrics: String = ProjectSettings.globalize_path(metrics_path)
	var f: FileAccess = FileAccess.open(global_metrics, FileAccess.WRITE)
	if f == null:
		push_error("[m5] could not write metrics: " + global_metrics)
		quit(5)
		return
	f.store_string(JSON.stringify(metrics, "\t"))
	f.close()

	print("[m5] wrote ", global_out, " rc=", rc, " metrics=", global_metrics)
	quit(0 if rc == OK else 6)
