# vfx/runtime — Godot 4.5 helpers for VFX v2

Drop these scripts into `res://vfx/runtime/` of any Godot 4.5 project that
consumes the VFX catalogue. Two files matter:

- `MeshTrail3D.gd` — `class_name MeshTrail3D extends MeshInstance3D`. Drives a
  `RibbonTrailMesh` / `TubeTrailMesh` from a moving emitter. Used by the
  `mesh_trail` export target produced by `pipelines/vfx/export_godot_3d.py`.
- `AudioCueBus.gd` — `class_name AudioCueBus extends Node`. Autoload that
  watches `AnimatedSprite2D.frame_changed` and emits `cue_hit(name, effect_id)`
  when a cue's frame plays. Cue list comes from `manifest.extras.audio_cues`.

## Install

1. Copy the entire `vfx/` folder to your project's `res://vfx/`.
2. Add `AudioCueBus.gd` as an autoload via the Godot editor:
   - Project Settings → Autoload → add `res://vfx/runtime/AudioCueBus.gd`
     with name `AudioCueBus`. Singleton ON.

## Wire-up examples

### Mesh trail attached to a projectile

```gdscript
# Anywhere a fireball is spawned:
var fireball = preload("res://Fireball.tscn").instantiate()
get_tree().current_scene.add_child(fireball)
var trail = preload("res://vfx/spell/fireball_projectile_mesh_trail/fireball_projectile_trail.tscn").instantiate()
fireball.add_child(trail)
trail.set_emitter(fireball)
```

### Audio cue from a baked flipbook

```gdscript
# Spawn a baked AnimatedSprite2D effect:
var sf = load("res://vfx/spell/fireball_projectile/sprite_frames.tres")
var sprite := AnimatedSprite2D.new()
sprite.sprite_frames = sf
sprite.play("fireball_projectile")
add_child(sprite)

# Tell the bus to track it:
AudioCueBus.register(sprite, "fireball_projectile",
    "res://vfx/spell/fireball_projectile/manifest.json")

# React to cues elsewhere:
AudioCueBus.cue_hit.connect(func(name, eid):
    if name == "impact":
        $Camera2D.shake(0.4)
        AudioStreamPlayer.new().play()
)
```

### Volumetric fog per biome

```gdscript
# A scene that uses a baked biome fog volume:
var fog = preload("res://vfx/ambient/lava_field_haze_fog_volume/lava_field_haze_fog.tscn").instantiate()
fog.position = biome_zone_center
fog.size = Vector3(biome_aabb.x, fog_height_m, biome_aabb.z)
add_child(fog)
# Make sure WorldEnvironment.environment.volumetric_fog_enabled = true.
```

## Notes

- The `MeshTrail3D` script is also a static convenience: `MeshTrail3D.spawn_burst(...)` for one-shot trails.
- `AudioCueBus` is intentionally not a hard dependency. If the autoload is
  missing, the VFX scenes still play — they just don't fire cue events.
- Both scripts are pure Godot 4.5 GDScript; no external addons required.
