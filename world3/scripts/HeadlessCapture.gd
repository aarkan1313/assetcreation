extends Node

# Renders a few frames so terrain has built and lighting has settled, then
# saves a screenshot and quits.
@export var output_path: String = "user://capture.png"
@export var warmup_frames: int = 6


func _ready() -> void:
	for i in range(warmup_frames):
		await get_tree().process_frame
	var img := get_viewport().get_texture().get_image()
	# Resolve user:// to an absolute path or keep res:// untouched.
	if output_path.begins_with("user://") or output_path.begins_with("res://"):
		img.save_png(output_path)
	else:
		# Allow absolute Windows paths like D:/tmp/foo.png
		img.save_png(output_path)
	print("[capture] wrote " + output_path)
	get_tree().quit(0)
