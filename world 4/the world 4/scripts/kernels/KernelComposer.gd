class_name KernelComposer
extends RefCounted

# Combines per-biome kernels at world level. Mirrors
# pipeline/kernel_composer.py.

const BIOME_SEED_STRIDE: int = 1000
const DEFAULT_BIOME_TEMPERATURE: float = 0.5


class BiomeBinding:
	var biome_name: String
	var kernel: Kernel
	var params: Dictionary
	var biome_index: int

	func _init(p_name: String, p_kernel: Kernel, p_params: Dictionary,
			   p_index: int) -> void:
		biome_name = p_name
		kernel = p_kernel
		params = p_params
		biome_index = p_index


var _biomes: Array[BiomeBinding] = []
var _biome_scale_m: float = 1024.0
var _temperature: float = DEFAULT_BIOME_TEMPERATURE


# kernel_registry is a Dictionary: kind_string -> Kernel instance.
# Caller builds this dictionary (typically holding one NoiseStackKernel).
func _init(catalog: Dictionary, kernel_registry: Dictionary,
		   biome_temperature: float = DEFAULT_BIOME_TEMPERATURE) -> void:
	_biome_scale_m = float(catalog.get("biome_scale_m", 1024.0))
	_temperature = biome_temperature
	var biomes_arr: Array = catalog["biomes"]
	for i in range(biomes_arr.size()):
		var b: Dictionary = biomes_arr[i]
		if not b.has("generator"):
			push_error("biome %s: missing generator block" % b["name"])
			continue
		var gen: Dictionary = b["generator"]
		var kind: String = gen.get("kernel", "")
		if not kernel_registry.has(kind):
			push_error("biome %s: unknown kernel %s" % [b["name"], kind])
			continue
		var k: Kernel = kernel_registry[kind]
		var params: Dictionary = gen.get("params", {})
		_biomes.append(BiomeBinding.new(b["name"], k, params, i))


func biome_names() -> Array[String]:
	var names: Array[String] = []
	for b in _biomes:
		names.append(b.biome_name)
	return names


func _biome_scalar(biome_index: int, world_x: float, world_z: float,
				   world_seed: int) -> float:
	var s: int = world_seed + biome_index * BIOME_SEED_STRIDE
	var u: float = world_x / _biome_scale_m
	var v: float = world_z / _biome_scale_m
	return NoiseStackKernel._gradient_noise_2d(u, v, s)


func sample_biome_weights(world_x: float, world_z: float,
						  world_seed: int) -> Dictionary:
	var scalars: Array[float] = []
	for b in _biomes:
		scalars.append(_biome_scalar(b.biome_index, world_x, world_z, world_seed))
	var mx: float = scalars[0]
	for s in scalars:
		if s > mx:
			mx = s
	var t: float = max(_temperature, 1e-6)
	var exps: Array[float] = []
	var total: float = 0.0
	for s in scalars:
		var e: float = exp((s - mx) / t)
		exps.append(e)
		total += e
	var result: Dictionary = {}
	for i in range(_biomes.size()):
		result[_biomes[i].biome_name] = exps[i] / total
	return result


func sample_height(world_x: float, world_z: float, world_seed: int) -> float:
	var weights: Dictionary = sample_biome_weights(world_x, world_z, world_seed)
	var h: float = 0.0
	for b in _biomes:
		var w: float = weights[b.biome_name]
		if w < 1e-6:
			continue
		h += w * b.kernel.height(world_x, world_z, world_seed, b.params)
	return h
