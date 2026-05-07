extends Node

# Capture the iso scene's built-in IsoCam — one screenshot, no mutation.
# The IsoCam is positioned by scene_tscn.py and oriented by IsoCam.gd's
# look_at on _ready.

const OUTPUT_DIR := "D:/tmp/wgv2_screens"


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUTPUT_DIR)
	# Wait several frames so look_at has fired and the renderer has settled.
	for i in range(12):
		await get_tree().process_frame
	var img := get_viewport().get_texture().get_image()
	var path := "%s/iso_view.png" % OUTPUT_DIR
	var err := img.save_png(path)
	if err != OK:
		push_error("[iso_headless] failed to save %s (err=%d)" % [path, err])
	else:
		var c := img.get_pixel(img.get_width() / 2, img.get_height() / 2)
		print("[iso_headless] wrote %s — centre pixel = %s" % [path, c])
	get_tree().quit(0)
