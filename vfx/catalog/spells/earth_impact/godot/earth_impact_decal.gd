# Attach to the Decal node from `earth_impact_decal.tscn` to enable
# animated UV playback. For static decals (logos, blood splats),
# the .tscn alone (frame 0) is enough.
extends Decal
class_name VFXDecalFlipbook_earth_impact

const SHADER_MATERIAL := preload("res://vfx/destruction/earth_impact/godot/decal_material.tres")

func _ready() -> void:
    var quad := MeshInstance3D.new()
    var qm := QuadMesh.new()
    qm.size = Vector2(1.8, 1.8)
    quad.mesh = qm
    quad.material_override = SHADER_MATERIAL
    quad.position.y = -size.y * 0.5 + 0.01
    quad.rotation_degrees.x = -90.0
    add_child(quad)
