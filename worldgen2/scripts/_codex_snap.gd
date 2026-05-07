extends Node3D

@export var out_path: String = "res://_codex_snap.png"
@export var wait_frames: int = 30

func _ready() -> void:
	for i in range(wait_frames):
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	if img == null:
		print("[snap] image is null (likely headless without window)")
		get_tree().quit()
		return
	var global_out := ProjectSettings.globalize_path(out_path)
	var rc := img.save_png(global_out)
	print("[snap] wrote ", global_out, " rc=", rc, " size=", img.get_size())
	get_tree().quit()
