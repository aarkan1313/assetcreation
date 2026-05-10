# M12 Runtime Parity Proof - 2026-05-10

## Purpose

M12 needs more than camera wrappers. The milestone asks whether the same terrain
decision can be inspected in close play, medium play, iso/tactical, and
topdown/map views without silently swapping to a different pipeline.

This proof brings the accepted M11 four-way corner source stack into a runtime
scene that covers all four bands through one source/material/height/splat
contract.

## Scene

Runtime review scene:

- `world3/scenes/review/source_stack_m12_runtime_fourway_tour.tscn`

The scene instantiates:

- `CharacterBody3D` named `Player`
- `Walker.gd` on the player
- player collision capsule
- `ChunkLoader.gd` streamed terrain chunks
- streamed collision chunks
- one review camera that switches between walk and gallery-style bands

## Shared Contract

Every band uses:

- Material: `res://textures/wgv3/terrain_m11_fourway_corner.tres`
- Heightmap: `res://toporeview/m11_fourway_corner_proof/heightmap.png`
- Meta: `res://toporeview/m11_fourway_corner_proof/meta.json`
- Source valid mask: `res://textures/source_stack/m11_fourway_corner_proof/source_macro_valid_mask.png`
- Source macro albedo: `res://textures/source_stack/m11_fourway_corner_proof/source_macro_albedo.png`
- Source macro mask: `res://textures/source_stack/m11_fourway_corner_proof/source_macro_weight_mask.png`
- Runtime splat weights: `res://textures/source_stack/m11_fourway_corner_proof/layers/splat_weights_rgba.png`

View-mode differences are limited to camera projection, framing, exposure-safe
lighting, and traversal path. Material ownership, source macro guidance, valid
masking, chunk generation, and splat weights do not change between bands.

## Captures

- Close walk: `world3/docs/captures/review/source_stack_m12_runtime_fourway_close.png`
- Medium walk: `world3/docs/captures/review/source_stack_m12_runtime_fourway_medium.png`
- Gallery iso: `world3/docs/captures/review/source_stack_m12_runtime_fourway_iso.png`
- Gallery topdown: `world3/docs/captures/review/source_stack_m12_runtime_fourway_topdown.png`

Capture wrappers:

- `world3/scenes/review/capture_source_stack_m12_runtime_fourway_close.tscn`
- `world3/scenes/review/capture_source_stack_m12_runtime_fourway_medium.tscn`
- `world3/scenes/review/capture_source_stack_m12_runtime_fourway_iso.tscn`
- `world3/scenes/review/capture_source_stack_m12_runtime_fourway_topdown.tscn`

## Visual Review

Structural pass:

- No invalid plateau wall.
- No boxed debug card or old texture-sheet artifact.
- No per-view material swap.
- Four-way material ownership remains visible in all bands.
- Topdown/iso are gallery-style views over the runtime contract, not the legacy
  `RegionGalleryCapture.gd` per-kit material swap path.

Quality caveats:

- This is representative M12 parity evidence, not final production terrain.
- The full bulk region gallery remains a legacy tool until we choose to promote
  it onto the source-stack contract.
- The accepted M11 four-way visual quality carries forward; M12 is testing
  parity and runtime wiring, not authoring a new terrain solve.

## Commands

Import:

```powershell
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --quiet --headless --editor --import
```

Capture:

```powershell
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m12_runtime_fourway_close.tscn'
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m12_runtime_fourway_medium.tscn'
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m12_runtime_fourway_iso.tscn'
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m12_runtime_fourway_topdown.tscn'
```

Audit:

```powershell
python world3/pipeline/audit_m12_view_mode_parity.py
```

## Decision

M12 now has representative runtime parity evidence and passed live user review
on 2026-05-10 as workflow evidence. M12 can close without treating the full bulk
region gallery retrofit as a blocker.

This does not promote the terrain art to production. Production promotion stays
under the M13 candidate manifest and audit gate.
