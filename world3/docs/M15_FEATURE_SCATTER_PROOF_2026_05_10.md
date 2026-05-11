# M15 Feature Scatter/Decal Proof - 2026-05-10

## Status

M15 is started and the workflow path is proven. This is not final scatter art.
The pass demonstrates deterministic, mask-driven placement and gameplay-band
visibility over the accepted M10 source-stack ecotone.

## Files

- Runtime overlay: `world3/scripts/M15FeatureScatterOverlay.gd`
- Scatter policy: `world3/jobs/m15_feature_scatter_policy.json`
- Tour scene: `world3/scenes/review/source_stack_m15_feature_scatter_tour.tscn`
- Captures:
  - `world3/docs/captures/review/source_stack_m15_feature_scatter_topdown.png`
  - `world3/docs/captures/review/source_stack_m15_feature_scatter_iso.png`
  - `world3/docs/captures/review/source_stack_m15_feature_scatter_medium.png`
  - `world3/docs/captures/review/source_stack_m15_feature_scatter_close.png`
- Review sheet:
  `world3/docs/captures/review/source_stack_m15_feature_scatter_sheet.png`

## Inputs

- M10 ecotone source stack:
  `world3/textures/source_stack/gloss_grassland_ecotone_layer_proof/`
- Masks:
  - `shrub_carryover_mask.png`
  - `dry_grass_density_mask.png`
  - `rock_cluster_mask.png`
  - `soil_exposure_mask.png`
  - `wash_line_mask.png`
  - `no_scatter_mask.png`

## What Changed

- `World3AutoReviewTour.gd` now supports `scatter_overlay_mode = "m15_production"`.
- `M15FeatureScatterOverlay.gd` reads
  `world3/jobs/m15_feature_scatter_policy.json` for spacing/count/visibility
  policy so the hardcoded prototype can graduate to authored assets without
  changing the mask contract.
- The M15 overlay generates shrubs, dry grass, rocks, dry debris, and lichen/
  decal candidates from the masks.
- Topdown hides scatter by default to preserve the map read.
- Iso can keep scatter visible through visibility ranges.
- Medium/close views expose the feature layer so flat organic textures no longer
  need to carry all visible plant/debris identity.

## Visual Read

Pass:

- Placement is visibly mask-driven.
- Topdown remains clean enough for map/strategic reading.
- Iso/medium/close show the intended feature-layer path.
- The overlay is deterministic and can be regenerated without hand placement.

Limitations:

- Shrubs, grass, stones, debris, and decals are procedural review primitives.
- The close view still reads as prototype scatter, not authored AAA vegetation.
- M15 should next replace primitive meshes/materials with real authored library
  assets while keeping the same mask and LOD contract.

## Verification

Godot capture command used normal Godot with explicit `--scene`; do not use the
older headless scene path for final viewport captures.

```powershell
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --headless --editor --import

$godot = 'C:/Godot/Godot_v4.5-stable_win64.exe'
$scenes = @(
  'res://scenes/review/capture_source_stack_m15_feature_scatter_topdown.tscn',
  'res://scenes/review/capture_source_stack_m15_feature_scatter_iso.tscn',
  'res://scenes/review/capture_source_stack_m15_feature_scatter_medium.tscn',
  'res://scenes/review/capture_source_stack_m15_feature_scatter_close.tscn'
)
foreach ($scene in $scenes) {
  $args = @('--path', 'D:/assets/world3', '--single-window', '--disable-crash-handler', '--scene', $scene)
  $p = Start-Process -FilePath $godot -ArgumentList $args -WindowStyle Hidden -Wait -PassThru
  if ($p.ExitCode -ne 0) { throw "Godot capture failed: $scene" }
}
```

All four capture scenes exited `0`.

## Next

1. Build a small authored scatter asset library for shrubs, grass clumps, stones,
   dry sticks, leaf/debris clusters, and decal cards.
2. Swap M15 primitive mesh factories to consume the authored asset library while
   preserving `m15_feature_scatter_policy.json`.
3. Repeat the same capture sheet and compare prototype primitives versus authored
   assets.
4. Port the same scatter overlay to the M11 junction/four-way proof once the M10
   ecotone version passes visual review.
