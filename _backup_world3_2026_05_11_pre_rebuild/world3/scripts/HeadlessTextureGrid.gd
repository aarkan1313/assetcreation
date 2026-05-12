extends Node

# Multi-shot capture of the texture viewer.
#
# Three views, each tests a different question:
#   1. far_overhead  — all 6 planes from above. Tests "do tiling artifacts
#                      stand out at distance? Is there visible repetition
#                      across hundreds of tiles per plane?"
#   2. mid_oblique   — one plane filling the frame at oblique angle. Mimics
#                      typical iso/topdown game framing.
#   3. close_walk    — eye-level over one plane. Mimics walk-mode FPV.

@export var output_dir: String = "D:/tmp/world3_screens/textures"
@export var warmup_frames: int = 8


func _ready() -> void:
	for i in range(warmup_frames):
		await get_tree().process_frame

	var dir := DirAccess.open(output_dir)
	if dir == null:
		DirAccess.make_dir_recursive_absolute(output_dir)

	# Find the active camera in the scene (recursive).
	var cam: Camera3D = _find_camera(get_tree().current_scene)
	if cam == null:
		push_error("[capture] no Camera3D in " + str(get_tree().current_scene))
		get_tree().quit(1); return

	# Disable any script on the cam (FlyCam) so we can drive it ourselves.
	cam.set_script(null)

	# Plane grid: cols=3 rows=2, plane=200, gap=30 → grid spans ~690x430m
	# centered on origin (with grid centered at z = -PLANE_SIZE*0.5 due to row-0.5).
	var grid_w: float = 3.0 * 200.0 + 2.0 * 30.0
	var grid_h: float = 2.0 * 200.0 + 1.0 * 30.0
	var grid_center := Vector3(0, 0, -100)  # row 0 at z=-115, row 1 at z=115; center ~0

	# 1. far_overhead — diagonal ortho looking down on the whole grid.
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = max(grid_w, grid_h) * 1.2
	cam.position = grid_center + Vector3(0, 800, 600)
	cam.look_at(grid_center, Vector3.UP)
	for i in range(2):
		await get_tree().process_frame
	await _save("far_overhead.png")

	# 2. mid_oblique — perspective over a single plane (dirt at row=0 col=0).
	#    plane center for col=0 row=0: x = -1*230, z = -0.5*230 = -115
	var plane_center := Vector3(-230, 0, -115)
	cam.projection = Camera3D.PROJECTION_PERSPECTIVE
	cam.fov = 50.0
	cam.position = plane_center + Vector3(0, 220, 220)
	cam.look_at(plane_center, Vector3.UP)
	for i in range(2):
		await get_tree().process_frame
	await _save("mid_oblique_dirt.png")

	# Repeat mid for each plane.
	var names := ["dirt", "grass", "forest_floor", "rock_light", "rock_dark", "snow"]
	for i in range(names.size()):
		var col := i % 3
		var row := i / 3
		var px := (col - 1.0) * 230.0
		var pz := (row - 0.5) * 230.0
		var pc := Vector3(px, 0, pz)
		cam.position = pc + Vector3(0, 220, 220)
		cam.look_at(pc, Vector3.UP)
		for j in range(2):
			await get_tree().process_frame
		await _save("mid_oblique_%s.png" % names[i])

	# 3. close_walk — eye-level over each plane, looking forward.
	for i in range(names.size()):
		var col2 := i % 3
		var row2 := i / 3
		var pcx := (col2 - 1.0) * 230.0
		var pcz := (row2 - 0.5) * 230.0
		# stand 50m in front of plane center (south edge), look at center
		cam.position = Vector3(pcx, 1.7, pcz + 60.0)
		cam.look_at(Vector3(pcx, 0, pcz), Vector3.UP)
		for j in range(2):
			await get_tree().process_frame
		await _save("close_walk_%s.png" % names[i])

	get_tree().quit(0)


func _find_camera(node: Node) -> Camera3D:
	if node is Camera3D:
		return node
	for child in node.get_children():
		var r := _find_camera(child)
		if r != null:
			return r
	return null


func _save(filename: String) -> void:
	var img := get_viewport().get_texture().get_image()
	var path := output_dir.path_join(filename)
	img.save_png(path)
	print("[capture] " + path)
