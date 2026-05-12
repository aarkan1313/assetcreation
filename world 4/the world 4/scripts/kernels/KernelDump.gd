extends SceneTree

# Headless tool: runs NoiseStackKernel at a fixed grid + fixed params,
# writes results to a JSON file consumed by Python cross-impl test.
#
# Usage:
#   "C:/Godot/Godot_v4.5-stable_win64.exe" --headless \
#     --path "D:/assets/world 4/the world 4" \
#     -s scripts/kernels/KernelDump.gd \
#     -- --out "D:/path/to/cross_impl_dump.json"

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var out_path: String = ""
	for i in range(args.size() - 1):
		if args[i] == "--out":
			out_path = args[i + 1]
			break
	if out_path.is_empty():
		push_error("KernelDump: --out <path> required")
		quit(1)
		return

	var kernel := NoiseStackKernel.new()
	var params := {
		"elevation_base_m": 500.0,
		"elevation_amplitude_m": 200.0,
		"octaves": 4,
		"lacunarity": 2.0,
		"persistence": 0.5,
		"base_frequency_per_m": 1.0 / 256.0,
		"seed_offset": 0,
	}
	var world_seed := 42
	var samples := []
	var n := 32
	var extent_m := 1024.0
	for i in range(n):
		var z: float = (float(i) / float(n - 1) - 0.5) * extent_m
		var row := []
		for j in range(n):
			var x: float = (float(j) / float(n - 1) - 0.5) * extent_m
			var h: float = kernel.height(x, z, world_seed, params)
			row.append({"x": x, "z": z, "h": h})
		samples.append(row)

	var dump := {
		"schema_version": 1,
		"kernel": "noise_stack",
		"world_seed": world_seed,
		"params": params,
		"grid_n": n,
		"extent_m": extent_m,
		"samples": samples,
	}
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	if f == null:
		push_error("KernelDump: cannot open " + out_path)
		quit(1)
		return
	f.store_string(JSON.stringify(dump, "  "))
	f.close()
	print("[KernelDump] wrote ", samples.size() * n, " samples to ", out_path)
	quit(0)
