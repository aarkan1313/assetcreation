class_name QualityTiers
extends RefCounted

# Quality-tier resolver (GDScript side).
#
# Loads config/quality_tiers.json, returns a typed Dictionary for any
# named tier, caches the resolved tier for the session.
#
# Consumers call get_current() and read named keys. They MUST NOT
# branch on the tier string — that's what keeps Phase-2 overrides
# a one-file change here.
#
# Reads the active tier from ProjectSettings("world/quality_tier"),
# defaulting to the JSON's `default_tier` if unset.

const CONFIG_PATH := "res://config/quality_tiers.json"
const PROJECT_SETTING_KEY := "world/quality_tier"

# Keys that must be integer-typed after JSON parse. Godot's JSON.parse_string
# returns all numbers as float, so `range(cfg["ring_count"])` blows up
# unless we coerce. List drives _coerce_int_keys below.
const _INT_KEYS := [
	"ring_count",
	"ring_grid_n",
	"collision_rings",
	"splat_texture_array_size",
]

static var _cached_resolved: Dictionary = {}


# Public API ----------------------------------------------------------

static func get_current() -> Dictionary:
	if _cached_resolved.is_empty():
		_cached_resolved = _resolve(_current_tier_name())
	return _cached_resolved.duplicate(true)


static func resolve_tier(tier: String) -> Dictionary:
	# Resolve a specific named tier. Does NOT cache or affect get_current().
	return _resolve(tier)


static func clear_cache() -> void:
	# Force re-read on next get_current(). Test-only.
	_cached_resolved = {}


# Internals -----------------------------------------------------------

static func _load_config() -> Dictionary:
	var f := FileAccess.open(CONFIG_PATH, FileAccess.READ)
	if f == null:
		push_error("QualityTiers: cannot open " + CONFIG_PATH)
		return {}
	var text := f.get_as_text()
	f.close()
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("QualityTiers: config malformed (not a dict)")
		return {}
	return parsed


static func _current_tier_name() -> String:
	var cfg := _load_config()
	var default_tier: String = cfg.get("default_tier", "high")
	var from_project: Variant = ProjectSettings.get_setting(
		PROJECT_SETTING_KEY, "")
	if typeof(from_project) == TYPE_STRING and not (from_project as String).is_empty():
		return from_project
	return default_tier


static func _resolve(tier: String) -> Dictionary:
	var cfg := _load_config()
	var tiers: Dictionary = cfg.get("tiers", {})
	if not tiers.has(tier):
		var fallback: String = cfg.get("default_tier", "high")
		push_error("QualityTiers: unknown tier %s, falling back to %s" % [tier, fallback])
		if not tiers.has(fallback):
			return {}
		tier = fallback
	var out: Dictionary = (tiers[tier] as Dictionary).duplicate(true)
	_coerce_int_keys(out)
	out["_tier"] = tier
	return out


static func _coerce_int_keys(d: Dictionary) -> void:
	for k in _INT_KEYS:
		if d.has(k):
			d[k] = int(d[k])
