# Player controller (CharacterBody3D + fly toggle) — design

Status: approved 2026-05-12, ready to plan.

## Why

Right now every W4 scene uses `AnchorCameraRig` (`Node3D`) as the
camera root, with WASD doing `global_position += direction * speed`.
There is no gravity, no collision body, no concept of "the floor."
The user can fly through terrain — which is fine for debug
inspection, but blocks any test of "does the world feel walkable."

Stage 3.5 added `HeightMapShape3D` collision proxies under each
inner ring, but nothing currently collides with them. This spec
introduces a `CharacterBody3D` mode on the existing camera rig +
a hotkey to toggle between **walk-physics** (gravity, capsule
collision, ground-locked) and **fly** (current behavior, no
collision).

## Scope

In:
- Convert `AnchorCameraRig` from `Node3D` to `CharacterBody3D`.
- Add a `CollisionShape3D` child with a `CapsuleShape3D` (height
  1.8m, radius 0.4m).
- Add `_physics_process` doing `move_and_slide()` in walk mode;
  walk mode applies gravity + horizontal motion from WASD.
- Add a `G` hotkey to toggle gravity/fly. (`F` and `Esc` keep
  mouse-capture toggle — both currently bound there.)
- Default mode: **fly** (current behavior, no regression for
  anchor + scale_demo HUD walkthroughs).
- HUD line update to reflect current mode.

Out:
- Jumping (later if we want it).
- Sprint while flying (already works in fly via shift; walk mode
  inherits the same shift handling).
- Crouching, sliding, swimming.
- AI / NPC bodies (separate concern).
- Replacing the iso/topdown cameras with bodies — those are
  spectator cams, no collision needed.

## Architecture

### Single node type change

`AnchorCameraRig` becomes `CharacterBody3D` instead of `Node3D`.
This is a one-line `extends` change. The class name stays the same
so every scene file that references it continues to work without
edit (the .tscn does `script = ExtResource("rig_script")` — Godot
allows a script to set a different parent type than the .tscn's
declared type, with a warning. To avoid the warning, we update each
.tscn that uses the rig to declare `type="CharacterBody3D"`).

### The `_mode` state machine extends

Current modes (from `AnchorCameraRig.CameraMode`): `WALK`, `ISO`,
`TOPDOWN`.

New addition: `WALK` gets a sub-flag `_fly_enabled: bool`. When
true, walk camera moves as it does today (free-cam, no physics).
When false, the rig does `move_and_slide()` with gravity.

ISO and TOPDOWN remain pure-spectator (no body collision). They're
already orthographic + WASD-pan in their own logic — unaffected
by physics.

### Collision shape

Child of the rig:
```
AnchorCameraRig (CharacterBody3D)
├── WalkCamera (Camera3D, existing)
├── IsoCamera (Camera3D, existing)
├── TopdownCamera (Camera3D, existing)
├── PlayerCollision (CollisionShape3D)
│   └── shape = CapsuleShape3D(height=1.8, radius=0.4)
└── HUD (CanvasLayer, existing)
```

`CapsuleShape3D` height 1.8m (typical adult), radius 0.4m. The
capsule's bottom sphere sits at the rig's `global_position`; eye
height is `walk_eye_height` (existing export, default 4.0m → bump
to 1.6m which is human eye-level, see "Open questions" below).

The capsule is on collision layer 1 / mask 1 by default; the
`StaticBody3D` Stage 3.5 added on each ring uses default layer/mask
1 / 1 as well, so they collide.

### Walk mode physics

```gdscript
func _physics_process(delta: float) -> void:
    if _current_mode != CameraMode.WALK or _fly_enabled:
        return
    # Gravity.
    if not is_on_floor():
        velocity.y -= gravity_m_s2 * delta
    else:
        velocity.y = 0.0
    # Horizontal motion from WASD (existing input handling).
    var horiz: Vector3 = _walk_input_direction()
    velocity.x = horiz.x * walk_speed
    velocity.z = horiz.z * walk_speed
    move_and_slide()
```

`walk_input_direction` is extracted from the existing free-cam WASD
code — same axis mapping (forward/strafe relative to camera yaw),
just returns a direction without applying it.

### Fly mode

Walk camera in fly mode does what AnchorCameraRig does today:
direct `global_position` translation per `_process`. No physics. No
gravity. No `move_and_slide()`.

`_physics_process` early-returns when `_fly_enabled` is true.

### Toggle

`G` keypress toggles `_fly_enabled`. HUD updates: walk-mode label
becomes `WALK (3D physics)` vs `WALK (3D fly)`.

When toggling from fly → physics: the rig's `velocity` resets to
zero. If the rig is currently below ground, the next
`_physics_process` will pop it up to floor via `move_and_slide`'s
collision resolution. Acceptable.

When toggling physics → fly: just stop applying gravity. The rig
is already where it is; fly-WASD takes over.

### Hotkey discoverability

HUD update: append `[G] fly toggle` to the existing
`WASD + mouse to move • Shift = sprint • Esc/F = mouse` line.

## What changes in existing scenes

`anchor.tscn`, `scale_demo.tscn`, `scale_v2.tscn` (via
`clipmap_debug.tscn`): the `CameraRig` node's declared type
changes from `Node3D` to `CharacterBody3D`. Without that change,
Godot logs a warning at load. The change is one word in the .tscn.

The rig's behavior with anchor / scale_demo is identical (default
mode is fly = current behavior), so anchor + scale_demo regression
captures should be bit-identical. Verify with re-capture.

## Quality tier knob

Add `player_walk_speed_m_s` to the JSON tier config? **No** — this
isn't a perf knob. It's a gameplay knob and lives as an `@export
var walk_speed` on the rig (already exists today). Leave the tier
system alone.

## Validation

- Anchor + scale_demo headless re-captures should be bit-identical
  (defaults to fly mode, current behavior).
- New `capture_scale_v2_walk_physics.tscn` capture: a scene that
  spawns the player above the terrain, lets gravity pull it down,
  captures after 60 warmup frames. Confirms landing on the heightmap.
- Editor verification: open clipmap_debug.tscn, F6, press G to
  enter walk-physics, confirm: gravity pulls you down, WASD walks,
  you stop at slopes that are too steep (capsule max slope ≈
  45° by default).
- No new pytest — physics behavior is editor-verified.

## Open questions resolved

- **One mode toggle or three?** One — fly toggle. ISO and TOPDOWN
  are spectator cams, no physics. Inside walk mode, fly/physics
  toggle.
- **Eye height**: current `walk_eye_height = 4.0m` was set for the
  256m anchor. For 4km scale_v2 + future games it should be ~1.6m
  (human eye level). Bump default; anchor + scale_demo can override
  per-scene if needed for their existing framing.
- **Capsule size**: 1.8m × 0.4m radius. Industry standard.
- **Gravity**: 9.81 m/s² as a constant, not a tier knob.
- **Collision layer/mask**: defaults (1/1). Future enemies/NPCs
  can claim layers 2-N.

## Implementation order

1. Add `extends CharacterBody3D` to AnchorCameraRig.gd.
2. Update each .tscn referencing the rig (`anchor`, `scale_demo`,
   `clipmap_debug`) to declare `type="CharacterBody3D"`.
3. Spawn `CollisionShape3D` + `CapsuleShape3D` in `_setup_cameras`.
4. Extract `_walk_input_direction()` from existing WASD code.
5. Add `_fly_enabled: bool = true` (default fly to preserve
   current behavior).
6. Add `_physics_process(delta)` walk-physics path.
7. Add `G` hotkey toggle + HUD update.
8. Re-capture anchor + scale_demo headless; confirm bit-identical.
9. Build `capture_scale_v2_walk_physics.tscn`; capture landing test.
10. Editor verification — user toggles G, walks around, reports.
11. Build-note + STATE refresh.
