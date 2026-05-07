# Attach to the Decal node from `arcane_aura_decal.tscn` to enable
# animated UV playback. For static decals (logos, blood splats),
# the .tscn alone (frame 0) is enough.
extends Decal
class_name VFXDecalFlipbook_arcane_aura

const SHADER_MATERIAL := preload("res://vfx/ambient/arcane_aura/godot/decal_material.tres")

func _ready() -> void:
    var quad := MeshInstance3D.new()
    var qm := QuadMesh.new()
    qm.size = Vector2(3.0, 3.0)
    quad.mesh = qm
    quad.material_override = SHADER_MATERIAL
    quad.position.y = -size.y * 0.5 + 0.01
    quad.rotation_degrees.x = -90.0
    add_child(quad)
