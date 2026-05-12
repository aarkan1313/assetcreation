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
	var out_path: String = _arg_value("--out", "")
	var frames: int = maxi(1, int(_arg_value("--frames", "45")))
	var width: int = int(_arg_value("--width", "1920"))
	var height: int = int(_arg_value("--height", "1080"))
	if scene_path == "" or out_path == "":
		push_error("CaptureSceneOnce requires --scene and --out")
		quit(2)
		return

	var root_view: Window = get_root()
	root_view.size = Vector2i(width, height)
	var scene_res: Resource = load(scene_path)
	if scene_res == null:
		push_error("CaptureSceneOnce could not load scene: " + scene_path)
		quit(3)
		return
	var scene: Node = scene_res.instantiate()
	root_view.add_child(scene)

	for _i in range(frames):
		await process_frame
		await RenderingServer.frame_post_draw

	var img: Image = root_view.get_texture().get_image()
	if img == null:
		push_error("CaptureSceneOnce image is null")
		quit(4)
		return

	var global_out: String = ProjectSettings.globalize_path(out_path)
	DirAccess.make_dir_recursive_absolute(global_out.get_base_dir())
	var rc: int = img.save_png(global_out)
	print("CaptureSceneOnce wrote ", global_out, " rc=", rc)
	quit(0 if rc == OK else 5)
