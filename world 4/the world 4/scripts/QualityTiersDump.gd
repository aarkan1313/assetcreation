extends SceneTree

# Headless tool: resolves every tier via QualityTiers.gd and writes
# the resulting dict to a JSON file. Consumed by the cross-impl test.
#
# Usage:
#   "C:/Godot/Godot_v4.5-stable_win64.exe" --headless \
#     --path "D:/assets/world 4/the world 4" \
#     -s scripts/QualityTiersDump.gd \
#     -- --out "D:/path/to/dump.json"

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var out_path: String = ""
	for i in range(args.size() - 1):
		if args[i] == "--out":
			out_path = args[i + 1]
			break
	if out_path.is_empty():
		push_error("QualityTiersDump: --out <path> required")
		quit(1)
		return

	var tiers := ["low", "medium", "high", "ultra"]
	var dump := {"schema_version": 1, "resolved": {}}
	for t in tiers:
		dump["resolved"][t] = QualityTiers.resolve_tier(t)

	var f := FileAccess.open(out_path, FileAccess.WRITE)
	if f == null:
		push_error("QualityTiersDump: cannot open " + out_path)
		quit(1)
		return
	f.store_string(JSON.stringify(dump, "  "))
	f.close()
	print("[QualityTiersDump] wrote ", tiers.size(), " tiers to ", out_path)
	quit(0)
