# Source-Stack Valid-Area Policy

Date: 2026-05-08

## Purpose

Source-stack runtime review now treats OpenTopo macro color as a valid-coverage
input, not a full-rectangle texture. This closes the first source-stack TODO
from the visual remediation pass: do not judge terrain through wrapped, filled,
or invalid source pixels.

The policy is still workflow validation, not production asset promotion. It
exists so M4/M5/M7 rerenders can compare generated detail materials against a
source-faithful macro terrain read.

## Implementation

- `pipeline/build_source_stack_runtime_review.py` discovers source validity in
  this order:
  - `layers/texture_coverage_mask.png`
  - `layers/source_valid_mask.png`
  - inverted `layers/render_fill_mask.png`
- The builder writes a downsampled runtime mask beside each source macro:
  `textures/source_stack/<id>/source_macro_valid_mask.png`.
- The builder edge-bleeds valid macro color into invalid pixels before saving
  `source_macro_albedo.png`. This prevents bilinear edge bleed from sampling
  black/fill pixels near validity boundaries.
- `shaders/terrain_splat_unified.gdshader` now has opt-in
  `source_macro_valid_mask` support. Where the mask is invalid, the shader
  falls back to the procedural/tileable terrain blend instead of forcing source
  macro color.
- Source UV sampling is clamped just inside texture bounds for source macro
  reads.

For the Gloss Mountain source stack, the runtime mask coverage is about
`0.8449` at `1180 x 2048`.

## Regenerated Assets

The following source-stack review materials were regenerated with the valid
mask contract:

- `gloss_scrub_source_stack`
- `gloss_grass_repair_source_stack`
- `gloss_grassland_repair_source_stack`
- `gloss_grassland_current_source_stack`
- `gloss_grassland_current_detail_stress`
- `gloss_grassland_comfy_v3_source_stack`
- `gloss_grassland_comfy_v3_detail_stress`

Each manifest now records:

- `source_macro_valid_mask`
- `runtime_source_macro_valid_mask`
- `source_macro_valid_coverage`
- `source_macro_invalid_coverage`
- `source_macro_runtime_size_px`
- `source_macro_edge_bleed_px`

## Visual Result

Rerendered captures:

- `docs/captures/visual_remediation/source_stack_runtime_grassland_current_close.png`
- `docs/captures/visual_remediation/source_stack_runtime_grassland_current_mid.png`
- `docs/captures/visual_remediation/source_stack_runtime_grassland_current_topdown.png`
- `docs/captures/visual_remediation/source_stack_runtime_grassland_comfy_v3_close.png`
- `docs/captures/visual_remediation/source_stack_runtime_grassland_comfy_v3_mid.png`
- `docs/captures/visual_remediation/source_stack_runtime_grassland_comfy_v3_topdown.png`
- `docs/captures/visual_remediation/source_stack_runtime_grassland_current_detail_stress_close.png`
- `docs/captures/visual_remediation/source_stack_runtime_grassland_comfy_v3_detail_stress_close.png`

Contact sheets:

- `docs/captures/visual_remediation/grassland_comfy_v3_terrain_context_contact_sheet.png`
- `docs/captures/visual_remediation/grassland_comfy_v3_detail_stress_contact_sheet.png`

Read:

- Normal source-stack close/mid/topdown now read as real source terrain with
  low-strength detail, not debug material assignment.
- The current `grassland_grass` material still fails the detail-stress view by
  pushing straw/tuft noise across the terrain.
- `m8_grassland_grass_calm_v3` remains the better sidecar candidate under the
  same stress, but it is still a little pale/hazy and is not canonically
  promoted.
- The remaining blue/background footprint in mid/topdown captures is a review
  framing/finite-footprint issue, not a source-macro invalid-pixel failure.

## Rebuild

```powershell
python world3/pipeline/build_source_stack_runtime_review.py --detail-material grassland_grass --id gloss_grassland_current_source_stack
python world3/pipeline/build_source_stack_runtime_review.py --detail-material grassland_grass --id gloss_grassland_current_detail_stress --source-macro-strength 0.72 --normal-strength 0.0 --detail-albedo-strength 0.22 --detail-normal-strength 0.0 --detail-rough-strength 0.03
python world3/pipeline/build_source_stack_runtime_review.py --detail-material m8_grassland_grass_calm_v3 --id gloss_grassland_comfy_v3_source_stack --extra-catalog world3/materials/catalog_comfy_candidates.json
python world3/pipeline/build_source_stack_runtime_review.py --detail-material m8_grassland_grass_calm_v3 --id gloss_grassland_comfy_v3_detail_stress --source-macro-strength 0.72 --normal-strength 0.0 --detail-albedo-strength 0.22 --detail-normal-strength 0.0 --detail-rough-strength 0.03 --extra-catalog world3/materials/catalog_comfy_candidates.json
```

Run Godot import after regenerating PNGs, then recapture the relevant scenes
through `scripts/CaptureSceneOnce.gd`.
