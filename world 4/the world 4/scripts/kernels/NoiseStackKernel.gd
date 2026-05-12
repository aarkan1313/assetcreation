class_name NoiseStackKernel
extends Kernel

# Multi-octave fBm over gradient noise. MUST agree numerically with
# pipeline/kernels/noise_stack.py — the hash function, gradient
# computation, fade curve, and accumulation order are all pinned to
# match. The cross-impl test (tests/test_kernel_cross_impl.py +
# scripts/kernels/KernelDump.gd) verifies max delta < epsilon.

const REQUIRED_PARAMS := [
	"elevation_base_m", "elevation_amplitude_m",
	"octaves", "lacunarity", "persistence",
	"base_frequency_per_m", "seed_offset",
]


func _init() -> void:
	kind = "noise_stack"


# 32-bit unsigned hash. Mirrors Python _hash2 exactly. GDScript ints
# are 64-bit; Python's `& 0xFFFFFFFF` keeps them 32-bit, so we mask
# the same way after each step.
static func _hash2(ix: int, iz: int, world_seed: int) -> int:
	var h: int = (world_seed * 374761393) & 0xFFFFFFFF
	h = (h + ix * 668265263) & 0xFFFFFFFF
	h = (h + iz * 2147483647) & 0xFFFFFFFF
	h = h ^ (h >> 13)
	h = (h * 1274126177) & 0xFFFFFFFF
	h = h ^ (h >> 16)
	return h


static func _gradient(ix: int, iz: int, world_seed: int) -> Vector2:
	var h: int = _hash2(ix, iz, world_seed)
	var angle: float = (float(h) / float(0xFFFFFFFF)) * TAU
	return Vector2(cos(angle), sin(angle))


static func _fade(t: float) -> float:
	return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


static func _gradient_noise_2d(x: float, z: float, world_seed: int) -> float:
	var ix: int = int(floor(x))
	var iz: int = int(floor(z))
	var fx: float = x - float(ix)
	var fz: float = z - float(iz)

	var g00 := _gradient(ix,     iz,     world_seed)
	var g10 := _gradient(ix + 1, iz,     world_seed)
	var g01 := _gradient(ix,     iz + 1, world_seed)
	var g11 := _gradient(ix + 1, iz + 1, world_seed)

	var d00 := Vector2(fx,       fz)
	var d10 := Vector2(fx - 1.0, fz)
	var d01 := Vector2(fx,       fz - 1.0)
	var d11 := Vector2(fx - 1.0, fz - 1.0)

	var n00: float = g00.dot(d00)
	var n10: float = g10.dot(d10)
	var n01: float = g01.dot(d01)
	var n11: float = g11.dot(d11)

	var u: float = _fade(fx)
	var v: float = _fade(fz)
	var nx0: float = n00 * (1.0 - u) + n10 * u
	var nx1: float = n01 * (1.0 - u) + n11 * u
	return nx0 * (1.0 - v) + nx1 * v


func height(world_x: float, world_z: float, world_seed: int,
			params: Dictionary) -> float:
	for p in REQUIRED_PARAMS:
		if not params.has(p):
			push_error("NoiseStackKernel missing param: " + p)
			return 0.0
	var s: int = int(world_seed) + int(params["seed_offset"])
	var octaves: int = int(params["octaves"])
	var lacunarity: float = float(params["lacunarity"])
	var persistence: float = float(params["persistence"])
	var base_freq: float = float(params["base_frequency_per_m"])
	var base_m: float = float(params["elevation_base_m"])
	var amp_m: float = float(params["elevation_amplitude_m"])

	var total: float = 0.0
	var amp: float = 1.0
	var freq: float = base_freq
	var norm: float = 0.0
	for _i in range(octaves):
		total += _gradient_noise_2d(world_x * freq, world_z * freq, s) * amp
		norm += amp
		amp *= persistence
		freq *= lacunarity
	if norm > 0.0:
		total /= norm
	return base_m + total * amp_m


func biome_weight(_biome_name: String, _world_x: float, _world_z: float,
				  _world_seed: int, _params: Dictionary) -> float:
	return 1.0
