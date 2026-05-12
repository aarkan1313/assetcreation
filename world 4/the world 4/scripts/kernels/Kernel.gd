class_name Kernel
extends RefCounted

# Abstract kernel interface. Subclasses must set `kind` and implement
# `height` + `biome_weight`. GDScript doesn't enforce abstractness;
# subclasses just override these.

var kind: String = ""


func height(_world_x: float, _world_z: float, _world_seed: int,
			_params: Dictionary) -> float:
	push_error("Kernel.height not implemented")
	return 0.0


func biome_weight(_biome_name: String, _world_x: float, _world_z: float,
				  _world_seed: int, _params: Dictionary) -> float:
	push_error("Kernel.biome_weight not implemented")
	return 0.0
