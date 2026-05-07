# AmbienceDensityAutoload — singleton that the BiomeAmbienceController polls
# for per-zone density overrides.
#
# Add this as an Autoload (Project > Project Settings > Globals) so it's
# registered as `AmbienceDensity` from anywhere in the game:
#
#   AmbienceDensity.set_zone("library_courtyard", 0.5)   # quieter zone
#   AmbienceDensity.set_zone("battle_arena", 2.0)        # more wildlife
#
# Gameplay code that knows the player's current zone (Area3D.body_entered,
# trigger volumes, save-data zone tag) calls `set_active_zone(zone_id)` and
# the BiomeAmbienceController picks up the multiplier on next reschedule.
#
# Schema for `audio/godot/ambience/zone_overrides.json` (loaded at _ready):
#
#   {
#     "default_multiplier": 1.0,
#     "zones": {
#       "library_courtyard": {"density": 0.5, "biome_hint": "grassland"},
#       "battle_arena":      {"density": 2.0, "biome_hint": null},
#       "deep_cave":         {"density": 0.3, "biome_hint": "ice_cavern"}
#     }
#   }
#
# This file is the *contract*. Gameplay teams populate it. The audio side
# treats it as read-only.

extends Node
# class_name AmbienceDensity   # keep commented out; Autoload provides the name

const ZONE_OVERRIDES_PATH := "res://audio/godot/ambience/zone_overrides.json"

signal zone_changed(zone_id: String, density: float, biome_hint: String)

var _zones: Dictionary = {}
var _default_multiplier: float = 1.0
var _active_zone: String = ""
var _active_density: float = 1.0
var _active_biome_hint: String = ""

# Optional weak ref to the active BiomeAmbienceController. The controller can
# call `register_controller(self)` in its _ready(), and we'll push density
# updates instead of having the controller poll.
var _controller: Node = null


func _ready() -> void:
	_load_zone_overrides()


func _load_zone_overrides() -> void:
	if not FileAccess.file_exists(ZONE_OVERRIDES_PATH):
		# No overrides file is fine; density stays at 1.0 default.
		return
	var f := FileAccess.open(ZONE_OVERRIDES_PATH, FileAccess.READ)
	if f == null:
		push_warning("AmbienceDensity: cannot read %s" % ZONE_OVERRIDES_PATH)
		return
	var text := f.get_as_text()
	var parsed = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		push_warning("AmbienceDensity: zone_overrides.json is not a JSON object")
		return
	_default_multiplier = float(parsed.get("default_multiplier", 1.0))
	_active_density = _default_multiplier
	_zones = parsed.get("zones", {}) if typeof(parsed.get("zones")) == TYPE_DICTIONARY else {}


func register_controller(c: Node) -> void:
	_controller = c
	# Push current density immediately
	if _controller and _controller.has_method("set_density_multiplier"):
		_controller.call("set_density_multiplier", _active_density)
	elif _controller and "density_multiplier" in _controller:
		_controller.set("density_multiplier", _active_density)


func set_active_zone(zone_id: String) -> void:
	if zone_id == _active_zone:
		return
	_active_zone = zone_id
	var zone_data: Dictionary = _zones.get(zone_id, {})
	_active_density = float(zone_data.get("density", _default_multiplier))
	_active_biome_hint = String(zone_data.get("biome_hint", ""))
	_push_to_controller()
	zone_changed.emit(_active_zone, _active_density, _active_biome_hint)


func set_zone(zone_id: String, density: float,
		biome_hint: String = "") -> void:
	"""Programmatic override (e.g. quest scripts)."""
	_zones[zone_id] = {"density": density, "biome_hint": biome_hint}
	if zone_id == _active_zone:
		_active_density = density
		_active_biome_hint = biome_hint
		_push_to_controller()
		zone_changed.emit(zone_id, density, biome_hint)


func _push_to_controller() -> void:
	if _controller == null:
		return
	if _controller.has_method("set_density_multiplier"):
		_controller.call("set_density_multiplier", _active_density)
	elif "density_multiplier" in _controller:
		_controller.set("density_multiplier", _active_density)
	if _active_biome_hint != "" and _controller.has_method("set_biome"):
		_controller.call("set_biome", _active_biome_hint)


func get_active_density() -> float:
	return _active_density


func get_active_zone() -> String:
	return _active_zone


func get_zones() -> Dictionary:
	return _zones.duplicate()
