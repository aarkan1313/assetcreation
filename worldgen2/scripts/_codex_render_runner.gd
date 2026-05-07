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
	var scene_path: String = _arg_value("--scene", "")
	var out_path: String = _arg_value("--out", "res://_codex_snap.png")
	var wait_frames: int = maxi(1, int(_arg_value("--wait-frames", "60")))
	var width: int = int(_arg_value("--width", "2560"))
	var height: int = int(_arg_value("--height", "1600"))

	var root_view: Window = get_root()
	root_view.size = Vector2i(width, height)

	var scene_res: Resource = load(scene_path)
	if scene_res == null:
		push_error("[snap] could not load scene: " + scene_path)
		quit(2)
		return

	var scene: Node = scene_res.instantiate()
	root_view.add_child(scene)

	for i in range(wait_frames):
		await process_frame
		await RenderingServer.frame_post_draw

	var img: Image = root_view.get_texture().get_image()
	if img == null:
		push_error("[snap] image is null")
		quit(3)
		return

	var global_out: String = ProjectSettings.globalize_path(out_path)
	var rc: int = img.save_png(global_out)
	print("[snap] wrote ", global_out, " rc=", rc, " size=", img.get_size())
	quit(0 if rc == OK else 4)
