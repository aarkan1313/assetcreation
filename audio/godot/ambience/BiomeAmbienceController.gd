class_name BiomeAmbienceController
extends Node

# Runtime controller for biome-aware ambience.
#
# Usage:
#   var c := preload("res://audio/ambience/BiomeAmbienceController.tscn").instantiate()
#   add_child(c)
#   c.set_biome("ice_cavern")
#
# What it does:
#   - Two AudioStreamPlayer for bed_drone + bed_air (always-on loops, Ambience bus)
#   - Two Timer-driven Poisson schedulers for wildlife + distant sweeteners
#   - 4-second crossfade between current and target biome on set_biome()
#   - Per-biome reverb tuning on the AmbienceReverb bus (room_size/damp/wet/predelay)
#
# Per-zone density override:
#   c.density_multiplier = 2.0    # double the wildlife/distant rate
#
# Requirements:
#   res://audio/ambience/biome_ambience_registry.tres   (output of ambience_pack.py)
#   Bus "Ambience" + "AmbienceReverb" loaded (or import bus_layout_ambience_overlay.tres)

const REGISTRY_PATH := "res://audio/ambience/biome_ambience_registry.tres"
const CROSSFADE_S := 4.0
const AMBIENCE_BUS := "Ambience"
const AMBIENCE_REVERB_BUS := "AmbienceReverb"
const SWEETENER_RADIUS_M := 12.0     # Poisson emitters spawned within this radius

@export var density_multiplier: float = 1.0

var registry: BiomeAmbienceRegistry
var current_biome: String = ""
var current_preset: BiomeAmbiencePreset = null

@onready var bed_drone_player: AudioStreamPlayer = $BedDrone
@onready var bed_air_player: AudioStreamPlayer = $BedAir
@onready var wildlife_timer: Timer = $WildlifeTimer
@onready var distant_timer: Timer = $DistantTimer

func _ready() -> void:
    if ResourceLoader.exists(REGISTRY_PATH):
        registry = load(REGISTRY_PATH) as BiomeAmbienceRegistry
    bed_drone_player.bus = AMBIENCE_BUS
    bed_air_player.bus = AMBIENCE_BUS
    wildlife_timer.timeout.connect(_on_wildlife_tick)
    distant_timer.timeout.connect(_on_distant_tick)
    _schedule_wildlife()
    _schedule_distant()

func set_biome(biome_id: String) -> void:
    if biome_id == current_biome:
        return
    if registry == null or not registry.presets.has(biome_id):
        push_warning("BiomeAmbienceController: unknown biome %s" % biome_id)
        return
    var target: BiomeAmbiencePreset = registry.presets[biome_id]
    _crossfade_to(target)
    current_biome = biome_id
    current_preset = target
    _apply_reverb(target)
    _schedule_wildlife()
    _schedule_distant()

func _crossfade_to(target: BiomeAmbiencePreset) -> void:
    var tween := create_tween().set_parallel(true)
    # fade out current beds
    if bed_drone_player.playing:
        tween.tween_property(bed_drone_player, "volume_db", -80.0, CROSSFADE_S)
    if bed_air_player.playing:
        tween.tween_property(bed_air_player, "volume_db", -80.0, CROSSFADE_S)
    await tween.finished
    # swap streams + restart at -80 dB then fade in
    bed_drone_player.stream = target.bed_drone
    bed_air_player.stream = target.bed_air
    bed_drone_player.volume_db = -80.0
    bed_air_player.volume_db = -80.0
    bed_drone_player.play()
    bed_air_player.play()
    var fade_in := create_tween().set_parallel(true)
    fade_in.tween_property(bed_drone_player, "volume_db", 0.0, CROSSFADE_S)
    fade_in.tween_property(bed_air_player, "volume_db", 0.0, CROSSFADE_S)

func _apply_reverb(p: BiomeAmbiencePreset) -> void:
    var idx := AudioServer.get_bus_index(AMBIENCE_REVERB_BUS)
    if idx == -1:
        push_warning("BiomeAmbienceController: AmbienceReverb bus not found.")
        return
    var fx := AudioServer.get_bus_effect(idx, 0)
    if fx is AudioEffectReverb:
        fx.room_size = p.reverb_room_size
        fx.damping = p.reverb_damp
        fx.wet = p.reverb_wet
        fx.predelay_msec = p.reverb_predelay_ms

func _schedule_wildlife() -> void:
    if current_preset == null:
        wildlife_timer.stop()
        return
    var lam := current_preset.wildlife_lambda * max(density_multiplier, 0.0)
    if lam <= 0.0:
        wildlife_timer.stop()
        return
    # Poisson inter-arrival = -ln(U)/lambda
    var u := randf()
    if u <= 0.0:
        u = 0.0001
    wildlife_timer.start(-log(u) / lam)

func _schedule_distant() -> void:
    if current_preset == null:
        distant_timer.stop()
        return
    var lam := current_preset.distant_lambda * max(density_multiplier, 0.0)
    if lam <= 0.0:
        distant_timer.stop()
        return
    var u := randf()
    if u <= 0.0:
        u = 0.0001
    distant_timer.start(-log(u) / lam)

func _on_wildlife_tick() -> void:
    _spawn_one_shot(current_preset.wildlife_randomizer)
    _schedule_wildlife()

func _on_distant_tick() -> void:
    _spawn_one_shot(current_preset.distant_randomizer)
    _schedule_distant()

func _spawn_one_shot(stream: AudioStream) -> void:
    if stream == null:
        return
    var p := AudioStreamPlayer3D.new()
    p.stream = stream
    p.bus = AMBIENCE_BUS
    p.unit_size = 4.0
    p.max_distance = 80.0
    p.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
    add_child(p)
    var ang := randf() * TAU
    var r := randf_range(SWEETENER_RADIUS_M * 0.3, SWEETENER_RADIUS_M)
    p.position = Vector3(r * cos(ang), 0.0, r * sin(ang))
    p.finished.connect(p.queue_free)
    p.play()
