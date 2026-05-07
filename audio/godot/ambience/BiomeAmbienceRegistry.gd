@tool
class_name BiomeAmbienceRegistry
extends Resource

# Lookup table biome_id -> BiomeAmbiencePreset. Used by
# BiomeAmbienceController.set_biome(biome_id).

@export var presets: Dictionary = {}
