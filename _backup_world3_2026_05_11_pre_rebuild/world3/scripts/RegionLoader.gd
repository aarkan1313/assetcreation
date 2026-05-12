extends Node3D
class_name RegionLoader

# Drives a Terrain node to load a specific region's heightmap+meta from
# the world3/opentopo/processed/heightmaps/ tree. Reads regions.json for
# the catalog. Per-scene script — one instance per region you want to
# render.
#
# Two ways to specify the region:
#   1. region_id + dataset (preferred): looks up regions.json
#   2. heightmap_path + meta_path (escape hatch): direct file paths

@export var region_id: String = ""
@export var dataset: String = ""  # empty = use preferred_dataset
@export var heightmap_path_override: String = ""
@export var meta_path_override: String = ""
@export_node_path("Terrain") var terrain_node: NodePath

const REGIONS_JSON := "res://jobs/regions.json"


func _ready() -> void:
	var terrain: Terrain = get_node_or_null(terrain_node) as Terrain
	if terrain == null:
		push_error("RegionLoader: terrain_node not set or not a Terrain")
		return

	var hp: String
	var mp: String
	if heightmap_path_override != "":
		hp = heightmap_path_override
		mp = meta_path_override if meta_path_override != "" else _meta_for(hp)
	else:
		var bundle := _resolve_bundle(region_id, dataset)
		if bundle == null:
			push_error("RegionLoader: could not resolve region=" + region_id +
					   " dataset=" + dataset)
			return
		hp = bundle["heightmap_path"]
		mp = bundle["meta_path"]

	terrain.load_dataset(hp, mp)


func _resolve_bundle(rid: String, ds: String) -> Variant:
	var f := FileAccess.open(REGIONS_JSON, FileAccess.READ)
	if f == null:
		push_error("RegionLoader: regions.json not found at " + REGIONS_JSON)
		return null
	var parsed = JSON.parse_string(f.get_as_text())
	f.close()
	if typeof(parsed) != TYPE_ARRAY:
		return null
	for region in parsed:
		if region.get("id", "") != rid:
			continue
		var pick_ds: String = ds if ds != "" else region.get("preferred_dataset", "")
		for b in region.get("bundles", []):
			if b.get("dataset", "") == pick_ds:
				return b
	return null


func _meta_for(heightmap_path: String) -> String:
	# heightmap.png lives next to meta.json in the bundle.
	if heightmap_path.ends_with(".png"):
		var i := heightmap_path.rfind("/")
		if i >= 0:
			return heightmap_path.substr(0, i) + "/meta.json"
	return ""
