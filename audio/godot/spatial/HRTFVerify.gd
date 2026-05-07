# HRTFVerify.gd — headless smoke for the godot-resonance-audio GDExtension.
#
# Run with:
#   godot --headless --quit-after 1 --script res://audio/godot/spatial/HRTFVerify.gd
#
# Pass: writes "ok" to stdout. Fail: writes "missing" + a diagnostic and
# returns exit 1 (the operator hasn't unzipped the addon).

extends SceneTree


func _initialize() -> void:
	var has := ClassDB.class_exists("ResonanceAudioSource")
	if has:
		print("[HRTFVerify] resonance audio addon: OK (ResonanceAudioSource registered)")
		# Try instantiating to be sure
		var n := ClassDB.instantiate("ResonanceAudioSource")
		if n == null:
			print("[HRTFVerify] WARN: class registered but instantiate() failed")
			quit(1)
		else:
			n.free()
			print("[HRTFVerify] instantiate OK")
			quit(0)
	else:
		print("[HRTFVerify] resonance audio addon: MISSING")
		print("[HRTFVerify] Install per pipelines/audio/recipes/hrtf_resonance.json")
		print("[HRTFVerify] (download release, unzip into res://addons/, restart Godot)")
		quit(1)
