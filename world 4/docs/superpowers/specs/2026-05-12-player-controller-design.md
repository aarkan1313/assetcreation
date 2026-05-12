# Player controller (modular test-harness component) — design

Status: approved 2026-05-12 (revised: modular, no rig changes), ready to plan.

## Why

Right now every W4 scene uses `AnchorCameraRig` (`Node3D`) as the
camera root, with WASD doing `global_position += direction * speed`.
There is no gravity, no collision body, no concept of "the floor."
The user can fly through terrain — fine for debug, but blocks any
test of "does the world feel walkable."

Stage 3.5 added `HeightMapShape3D` collision proxies under each
inner clipmap ring. Nothing currently collides with them. This spec
introduces an **isolated test-harness component** that adds walk-
physics WITHOUT modifying `AnchorCameraRig` or any shared scene.

## Scope

In:
- New file `the world 4/scripts/test_harness/PlayerBody.gd` — a
  self-contained `CharacterBody3D` with capsule collider, its own
  WalkCamera child, gravity, WASD physics, and a `G` hotkey to
  toggle between its own physics camera and a fly camera elsewhere
  in the scene.
- New test scene `the world 4/scenes/test_harness/clipmap_walk_test.tscn`
  that instances ClipmapWorld + AnchorCameraRig + PlayerBody and
  starts in fly-cam mode. `G` toggles to walk-physics.
- A small landing-test headless capture scene.

Out:
- ANY change to `AnchorCameraRig.gd`. Untouched. Its public API and
  behavior stay exactly as-is.
- ANY change to `anchor.tscn`, `scale_demo.tscn`, `clipmap_debug.tscn`,
  or any `capture_*.tscn`. Untouched. They never spawn a PlayerBody
  → never see any difference. Regression captures bit-identical
  by construction.
- Jumping (later).
- AI / NPC bodies (separate concern).
- Replacing the iso/topdown cameras with bodies.

## Why "modular sidecar" instead of converting the rig

The user explicitly said: "make sure this is modular, we aren't
affecting the main gen code with this, its a one off for our
testing purposes."

The shared `AnchorCameraRig` is used by 7+ scenes including the
regression-locked anchor and scale_demo. Bolting walk-physics into
the rig itself would inject test-harness state into every scene.
Even with a default-off flag, the type change (`Node3D` →
`CharacterBody3D`) propagates risk: physics order-of-operations,
collision layer assumptions, default Y velocity from gravity-while-
idle, etc.

A separate `PlayerBody` component sits alongside the rig and is
only present where opted in. **Zero edits to the shared rig means
zero risk to existing scenes.**

## Architecture

### Scene composition (opt-in)

```
ClipmapWalkTest (Node3D)
├── World (ClipmapWorld)
├── CameraRig (AnchorCameraRig — UNTOUCHED)
│   ├── WalkCamera (Camera3D)
│   ├── IsoCamera (Camera3D)
│   └── TopdownCamera (Camera3D)
├── Sun (DirectionalLight3D)
└── PlayerBody (CharacterBody3D — NEW)
    ├── PlayerCollision (CollisionShape3D + CapsuleShape3D)
    └── PlayerCamera (Camera3D)
```

Anchor + scale_demo + the existing clipmap captures spawn NO
PlayerBody. They run identically to today.

The walk-test scene spawns ALL of: World + AnchorCameraRig + PlayerBody.
Both cameras exist simultaneously. One is `current`. The toggle
flips which.

### Camera switching

`Camera3D.current` controls which camera the viewport uses. Only one
camera should be `current = true` at a time per viewport.

- Scene starts with `AnchorCameraRig.WalkCamera.current = true`
  (free-cam fly mode, current behavior).
- `G` keypress: PlayerBody flips `current` on both cameras.
  Sets `PlayerCamera.current = true` and tells the rig to set
  its WalkCamera current = false.
- `G` again: flip back.

The PlayerBody doesn't reach into the rig's internals — it just
toggles `current` on the two cameras (which Godot manages via
the viewport's camera stack).

### PlayerBody behavior

- `CharacterBody3D` with `CapsuleShape3D` (height 1.8m, radius 0.4m).
- `_physics_process` applies gravity, reads WASD relative to
  `PlayerCamera`'s yaw, calls `move_and_slide()`.
- `_input` handles `G` toggle + mouse-look for `PlayerCamera`.
- `_input` handles mouse capture (Esc/F) just for PlayerCamera —
  same UX as the rig's existing mouse capture, but isolated.
- When inactive (rig's camera is current), PlayerBody's
  `_physics_process` early-returns. Body stays where it is.
- When activated, PlayerBody warps to the rig's WalkCamera position
  so the transition feels seamless (no teleport across the map).

### Collision

Capsule on layer 1 / mask 1. The Stage 3.5 `HeightMapShape3D`
proxies use defaults (1/1) → they collide by default.

### Eye height

`PlayerCamera.position = Vector3(0, 1.6, 0)` relative to body.
1.6m human eye-level. Capsule height 1.8m means the camera is just
below the capsule's top sphere — close enough.

### Test scene

`the world 4/scenes/test_harness/clipmap_walk_test.tscn`:
- Instances ClipmapWorld (scale_v2)
- Instances AnchorCameraRig (defaults to WalkCamera current)
- Instances PlayerBody (with PlayerCamera not current)
- Includes a DirectionalLight3D for shading

User opens this scene, F6, press G to enter walk-physics. Press G
again to return to fly.

## What changes outside the test harness

Nothing. Zero edits to shared scripts, shared shaders, shared
scenes, materials, configs.

## Validation

- **Anchor + scale_demo regression**: by construction. No files
  touched. Hash check is optional but should be bit-identical.
- **Clipmap A/B captures**: same. Untouched.
- **New `capture_clipmap_walk_test.tscn`**: spawns the test scene
  + forces PlayerBody active via a small init script + warmup 120
  frames. Capture should show the player landed on terrain.
- **Editor verification**: user opens `clipmap_walk_test.tscn`, F6,
  presses G, walks. Reports what they see.
- **No new pytest**: physics is editor-verified.

## Quality tier knob

None. This is a test harness, not a shipping system. Hardcoded
1.8m × 0.4m capsule, 9.81 m/s² gravity, default Godot physics.

## Open questions resolved

- **Rig untouched**: yes, mandatory per user.
- **Two cameras**: yes, one per role. Toggle via `Camera3D.current`.
- **PlayerBody warps to rig position on activation**: yes, for UX
  continuity.
- **PlayerBody can warp away from rig position on deactivation**:
  no — when G goes back to fly, rig's camera takes over wherever
  the rig currently is. PlayerBody stays where it was so the next G
  press resumes from there.
- **Mouse-look on PlayerBody**: own copy of the rig's mouse-look
  code. Don't import the rig's. Modular = independent.

## Implementation order

1. New file `scripts/test_harness/PlayerBody.gd` with:
   - extends CharacterBody3D
   - CapsuleShape3D + PlayerCamera children built in `_ready`
   - `_physics_process` walk-physics
   - `_input` for G toggle + mouse-look
   - public `activate()` / `deactivate()` methods that flip
     `current` between PlayerCamera and a reference to the rig's
     WalkCamera (set via export NodePath)
2. New folder `scenes/test_harness/` + scene `clipmap_walk_test.tscn`
   that instances World + AnchorCameraRig + PlayerBody + Sun.
3. New capture scene `capture_clipmap_walk_test.tscn` that wraps
   the test scene + a forced-activation hook + HeadlessCapture.
4. Editor verification command for user.
5. Build-note + STATE refresh — flag this as "test harness, not
   shipping," call out the modularity choice.
