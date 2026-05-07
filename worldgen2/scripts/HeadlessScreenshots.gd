extends Node

# Headless screenshot harness. Loaded as a SceneTree autoload-style script:
# replaces the FlyCam, parks a Camera3D at predetermined viewpoints, waits a
# few frames for the renderer to settle, saves PNGs to D:/tmp/wgv2_screens/,
# then quits.

const OUTPUT_DIR := "D:/tmp/wgv2_screens"

# Camera viewpoints. Position + look_at target, both in world coords.
# Picked to span: high overview, mid-air looking at ridge, low ground-level.
var VIEWS := [
	{
		"name": "overview_high",
		"pos": Vector3(0.0, 200.0, -400.0),
		"look_at": Vector3(0.0, 30.0, 0.0),
	},
	{
		"name": "overview_close",
		"pos": Vector3(0.0, 120.0, -250.0),
		"look_at": Vector3(0.0, 30.0, 0.0),
	},
	{
		"name": "ridge_side",
		"pos": Vector3(220.0, 80.0, 0.0),
		"look_at": Vector3(0.0, 30.0, 0.0),
	},
	{
		"name": "low_ground",
		"pos": Vector3(-100.0, 8.0, -100.0),
		"look_at": Vector3(80.0, 30.0, 80.0),
	},
	{
		"name": "topdown",
		"pos": Vector3(0.0, 400.0, 0.0),
		"look_at": Vector3(0.0, 0.0, 0.001),  # avoid degenerate look_at
	},
]


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUTPUT_DIR)
	print("[headless] starting screenshot run")
	# Wait one frame for the loaded scene to initialize
	await get_tree().process_frame
	# headless_capture.tscn instances the world scene as a child named "World".
	# When run directly on death_valley_character.tscn, current_scene IS the
	# world, so handle both.
	var root := get_tree().current_scene
	if root == null:
		push_error("[headless] no current_scene — bailing")
		get_tree().quit(1)
		return
	var scene: Node = root.get_node_or_null("World")
	if scene == null:
		scene = root  # running directly on the world scene

	# Replace FlyCam (if present) with a fresh Camera3D we control.
	var flycam := scene.get_node_or_null("FlyCam")
	if flycam:
		flycam.queue_free()
		await get_tree().process_frame

	var cam := Camera3D.new()
	cam.fov = 60.0
	cam.near = 1.0
	cam.far = 200000.0
	cam.current = true
	scene.add_child(cam)
	await get_tree().process_frame  # let cam settle in tree before look_at

	# Confirm scene state: terrain present, sun present, etc.
	var terrain := scene.get_node_or_null("Terrain")
	var sun := scene.get_node_or_null("Sun")
	print("[headless] scene=%s terrain=%s sun=%s cam.current=%s" % [
		scene.name, terrain != null, sun != null, cam.current])

	for view in VIEWS:
		cam.global_position = view["pos"]
		cam.look_at(view["look_at"], Vector3.UP)
		print("[headless] view=%s cam.global_pos=%s look=%s" % [
			view["name"], cam.global_position, view["look_at"]])
		# Wait several frames so the renderer fully settles before snapping.
		for i in range(8):
			await get_tree().process_frame
		var img := get_viewport().get_texture().get_image()
		var path := "%s/%s.png" % [OUTPUT_DIR, view["name"]]
		var err := img.save_png(path)
		if err != OK:
			push_error("[headless] failed to save %s (err=%d)" % [path, err])
		else:
			# Sample the centre pixel to see what color the renderer produced.
			var c := img.get_pixel(img.get_width() / 2, img.get_height() / 2)
			print("[headless] wrote %s — centre pixel = %s" % [path, c])

	print("[headless] done — quitting")
	get_tree().quit(0)
