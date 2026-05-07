@tool
class_name BiomeAmbiencePreset
extends Resource

# Per-biome ambience preset. Loaded by BiomeAmbienceController.
# Authored by pipelines/audio/ambience_pack.py — do not hand-edit.

@export var biome_id: String = ""
@export var bed_drone: AudioStream
@export var bed_air: AudioStream
@export var wildlife_randomizer: AudioStream  # AudioStreamRandomizer
@export var distant_randomizer: AudioStream   # AudioStreamRandomizer

# Reverb (applied to AmbienceReverb bus on biome enter)
@export_range(0.0, 1.0, 0.01) var reverb_room_size: float = 0.5
@export_range(0.0, 1.0, 0.01) var reverb_damp: float = 0.5
@export_range(0.0, 1.0, 0.01) var reverb_wet: float = 0.2
@export_range(0.0, 500.0, 1.0) var reverb_predelay_ms: float = 30.0

# Poisson scheduling (mean events/second for sweetener layers)
@export_range(0.0, 1.0, 0.001) var wildlife_lambda: float = 0.05
@export_range(0.0, 1.0, 0.001) var distant_lambda: float = 0.01
