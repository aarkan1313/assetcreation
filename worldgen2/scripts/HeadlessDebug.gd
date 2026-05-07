extends Node

# Cycle through shader debug_mode values, capturing one overview screenshot per mode.
# Each frame visualises a different aspect of the rendering pipeline so we can
# identify which stage is producing the wrong output.

const OUTPUT_DIR := "D:/tmp/wgv2_screens"
const DEBUG_MODES := {
	0: "normal",
	1: "splat_rgb",
	2: "splat_wsum",
	3: "albedo_0_only",
	4: "world_xz",
}


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUTPUT_DIR)
	await get_tree().process_frame
	var root := get_tree().current_scene
	var scene: Node = root.get_node_or_null("World")
	if scene == null:
		scene = root

	# Remove FlyCam, add controlled camera.
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
	# Must be added to tree before look_at works.
	cam.global_position = Vector3(0.0, 4500.0, -25000.0)
	cam.look_at(Vector3(0.0, 1000.0, 5000.0), Vector3.UP)

	# Find the terrain MeshInstance3D + grab its material so we can poke debug_mode.
	var terrain := scene.get_node_or_null("Terrain") as MeshInstance3D
	if terrain == null:
		push_error("[debug] no Terrain node found")
		get_tree().quit(1)
		return
	# PlaneMesh has the material attached directly.
	var mat := terrain.mesh.surface_get_material(0) as ShaderMaterial
	if mat == null:
		push_error("[debug] terrain mesh has no ShaderMaterial on surface 0")
		get_tree().quit(1)
		return

	for mode in DEBUG_MODES:
		mat.set_shader_parameter("debug_mode", mode)
		# Wait several frames so the renderer fully settles before snapping.
		for i in range(8):
			await get_tree().process_frame
		var img := get_viewport().get_texture().get_image()
		var path := "%s/debug_%d_%s.png" % [OUTPUT_DIR, mode, DEBUG_MODES[mode]]
		var err := img.save_png(path)
		if err != OK:
			push_error("[debug] failed to save %s (err=%d)" % [path, err])
		else:
			print("[debug] wrote %s" % path)

	print("[debug] done")
	get_tree().quit(0)
