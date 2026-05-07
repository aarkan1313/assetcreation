# vfx/ drop-in for Godot 4.5
Copy the *contents* of this folder (vfx/catalog/) into res://vfx/.

Each effect lives at:
  res://vfx/<kind>/<id>/effect.json     (authored)
  res://vfx/<kind>/<id>/manifest.json   (baked metadata)
  res://vfx/<kind>/<id>/frames/*.png    (baked frames)
  res://vfx/<kind>/<id>/flipbook.png    (baked atlas)
  res://vfx/<kind>/<id>/godot/<id>.tscn (Godot scene; what you instance)
  res://vfx/<kind>/<id>/godot/sprite_frames.tres  (the SpriteFrames resource)
  res://vfx/<kind>/<id>/godot/<id>_billboard.tscn (3D billboard variant, if export_target=3d_billboard)
  res://vfx/<kind>/<id>/godot/<id>_decal.tscn     (decal variant)
  res://vfx/<kind>/<id>/godot/<id>_trail.tscn     (mesh trail variant)
  res://vfx/<kind>/<id>/godot/<id>_fog.tscn       (fog volume variant)

Runtime helpers (autoload one):
  res://vfx/runtime/AudioCueBus.gd  - register as autoload AudioCueBus
  res://vfx/runtime/MeshTrail3D.gd  - class for mesh-trail nodes

Usage:
  var effect = preload('res://vfx/spell/fireball_projectile/godot/fireball_projectile.tscn').instantiate()
  add_child(effect)
