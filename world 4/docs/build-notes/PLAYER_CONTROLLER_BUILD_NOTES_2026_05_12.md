# Player controller (test harness) — build notes

> Test-harness `PlayerBody` (CharacterBody3D) lets us walk on the
> clipmap terrain with gravity + capsule collision. Sits BESIDE
> AnchorCameraRig instead of replacing it — anchor, scale_demo,
> and the regression captures are unaffected by construction.
> Shipped 2026-05-12 on `main`. Commits `2123779`…`08ce785`.

## What shipped

| Task | Component | Commit |
|---|---|---|
| 1 | `scripts/test_harness/PlayerBody.gd` (CharacterBody3D + capsule + PlayerCamera + G toggle + own HUD) | `2123779` |
| 2 | `scenes/test_harness/clipmap_walk_test.tscn` (opt-in test scene with rig + body) | `d73880a` |
| 3 | `scenes/test_harness/capture_clipmap_walk_test.tscn` + `scripts/test_harness/ForceWalkPhysics.gd` (landing-test capture) | `08ce785` |
| 4 | This build-note + STATE refresh | (this commit) |

## Why "sidecar" instead of converting the rig

Initial spec proposed converting AnchorCameraRig itself to
CharacterBody3D. User pushed back: "make sure this is modular, we
aren't affecting the main gen code with this, its a one off for our
testing purposes." Revised approach: PlayerBody is a separate node
type that sits alongside the rig in opt-in test scenes. Rig is
untouched. Anchor + scale_demo + every existing clipmap capture
scene are bit-identical to before by construction.

## Architecture

```
ClipmapWalkTest (Node3D)
├── World (ClipmapWorld)
├── CameraRig (AnchorCameraRig — UNTOUCHED)
│   ├── WalkCamera (Camera3D, current = true at start)
│   ├── IsoCamera
│   └── TopdownCamera
├── Sun (DirectionalLight3D)
└── PlayerBody (CharacterBody3D — NEW)
    ├── PlayerCollision (CapsuleShape3D 1.8m × 0.4m)
    └── PlayerCamera (Camera3D, current = false at start)
```

Two cameras exist simultaneously. `G` swaps which is `current`:

- Start: rig.WalkCamera current → fly mode (rig drives via `_process`)
- Press G: PlayerBody.PlayerCamera current → walk-physics
  (PlayerBody drives via `_physics_process`, applies gravity,
  `move_and_slide()` against the Stage 3.5 HeightMapShape3D
  collision proxies)
- Press G: back to fly

The `activate()` call on PlayerBody warps the body to the rig's
WalkCamera position so the transition is seamless.

## Landing test validates collision works

`captures/axis1_walk_physics_landing_2026_05_12.png` — capsule
spawned at y=1500m, gravity pulled it down to terrain elevation
(~700-1000m for alpine/desert blend), capsule rests on the
HeightMapShape3D inner-ring collision proxies. No fall-through.

## Plan deviations

**One** during execution: my first capture scene embedded the
"force walk-physics on capture" helper as an inline GDScript
sub_resource inside the .tscn. The triple-quoted string escapes
broke .tscn parsing. Fixed by extracting the helper to a normal .gd
file (`ForceWalkPhysics.gd`) and referencing it via ExtResource.
Worth a memory entry — see lessons.

## Lessons + new pitfalls

**Don't embed GDScript with `\\\"` escape chains inside .tscn**
`sub_resource type="GDScript"` blocks. The escapes get processed
twice (once by Python's shell, once by Godot's .tscn parser) and
multi-line scripts with strings end up corrupted. Extract helpers
to separate .gd files and reference via ExtResource.

Not a PITFALLS-worthy entry on its own (specific to one capture
workflow), but documented here for future test-scene authors.

## What's still missing

- **Jumping**: not implemented. Easy follow-up
  (`velocity.y += jump_force` on Space when `is_on_floor()`).
- **Mid-air control**: capsule has full directional control in air
  (fly-game feel). Tunable later by lerping toward input vector.
- **Crouching / sliding / swimming**: out of scope.
- **AI / NPC bodies**: separate game-specific concern.
- **Final shipping player controller**: this is a test harness.
  Real player will be a separate, game-specific implementation
  built on the same `HeightMapShape3D` collision infrastructure.

## What's next

User opens `scenes/test_harness/clipmap_walk_test.tscn` in editor,
F6, presses G, walks. Confirms physics feels right. If yes,
unblocks Stage 4.2 (biome culler) verification — biome blending
can now be evaluated from a realistic walking POV instead of a
fly-cam.
