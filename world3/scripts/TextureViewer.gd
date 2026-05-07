extends Node3D

# Lays out the wgv3 textures as flat ground planes for at-scale tiling review.
# Each plane is 200x200 m. With uv1_scale=0.1 (one tile per 10m), that's
# 20x20=400 tile repeats per plane. Camera flies through; you fly close to
# inspect a tile or far to see if patterns repeat across the field.

@export var use_hex_for_rock_dark: bool = false
@export var use_hex_for_all: bool = false
@export var use_hex_detail_for_rock_dark: bool = false
@export var use_hex_detail_v2_for_rock_dark: bool = false  # detail variant tex

const PLANES := [
	{"name": "dirt",         "mat": "res://textures/wgv3/dirt/material.tres"},
	{"name": "grass",        "mat": "res://textures/wgv3/grass/material.tres"},
	{"name": "forest_floor", "mat": "res://textures/wgv3/forest_floor/material.tres"},
	{"name": "rock_light",   "mat": "res://textures/wgv3/rock_light/material.tres"},
	{"name": "rock_dark",    "mat": "res://textures/wgv3/rock_dark/material.tres"},
	{"name": "snow",         "mat": "res://textures/wgv3/snow/material.tres"},
]

const PLANE_SIZE: float = 200.0
const PLANE_GAP: float = 30.0
const COLS: int = 3


func _ready() -> void:
	for i in range(PLANES.size()):
		var info := PLANES[i] as Dictionary
		var col := i % COLS
		var row := i / COLS
		var x := (col - (COLS - 1) * 0.5) * (PLANE_SIZE + PLANE_GAP)
		var z := (row - 0.5) * (PLANE_SIZE + PLANE_GAP)

		var mesh_instance := MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2(PLANE_SIZE, PLANE_SIZE)
		pm.subdivide_width = 8
		pm.subdivide_depth = 8
		mesh_instance.mesh = pm
		mesh_instance.position = Vector3(x, 0, z)

		var mat_path: String = info["mat"]
		if use_hex_detail_v2_for_rock_dark and info["name"] == "rock_dark":
			mat_path = "res://textures/wgv3/rock_dark/material_hex_detail_v2.tres"
		elif use_hex_detail_for_rock_dark and info["name"] == "rock_dark":
			mat_path = "res://textures/wgv3/rock_dark/material_hex_detail.tres"
		elif use_hex_for_all:
			mat_path = "res://textures/wgv3/" + str(info["name"]) + "/material_hex.tres"
		elif use_hex_for_rock_dark and info["name"] == "rock_dark":
			mat_path = "res://textures/wgv3/rock_dark/material_hex.tres"
		var mat: Material = load(mat_path)
		if mat != null:
			mesh_instance.material_override = mat
		mesh_instance.name = info["name"]
		add_child(mesh_instance)

		# A floating label per plane.
		var label := Label3D.new()
		label.text = info["name"]
		label.font_size = 96
		label.outline_size = 12
		label.modulate = Color.WHITE
		label.outline_modulate = Color(0, 0, 0, 1)
		label.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
		label.position = Vector3(x, 8, z)
		label.no_depth_test = true
		add_child(label)
