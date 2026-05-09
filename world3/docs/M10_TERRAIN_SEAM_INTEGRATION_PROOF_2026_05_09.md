# M10 Terrain Seam Integration Proof

Date: 2026-05-09

## Purpose

This is the first production-facing seam proof after the same-source repeat
correction. It does not wrap a finite crop. It takes two overlapping
real-source Gloss Mountain terrain bundles and emits one runtime bundle with a
solved integration band.

## Inputs

- Source macro: `world3/textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png`
- Source macro valid mask: `world3/textures/source_stack/gloss_scrub_source_stack/source_macro_valid_mask.png`
- Source height: `world3/toporeview/gloss_mountain_textured_master/heightmap.png`
- Source meta: `world3/toporeview/gloss_mountain_textured_master/meta.json`
- Left crop: `240,520,416,1024` in source-macro pixels.
- Right crop: `592,520,416,1024` in source-macro pixels.
- Overlap/integration band: `64 px`, about `33.6 m`.

The two crops overlap in the original source. That is intentional for the first
rung: the proof validates the integration-band artifact, runtime sampling,
mesh clipping, and visual review path before moving to unlike or non-overlap
sources.

## Outputs

- Generator: `world3/pipeline/build_terrain_seam_integration_proof.py`
- Runtime macro: `world3/textures/source_stack/gloss_scrub_seam_integration_proof/source_macro_albedo.png`
- Runtime valid mask: `world3/textures/source_stack/gloss_scrub_seam_integration_proof/source_macro_valid_mask.png`
- Seam mask: `world3/textures/source_stack/gloss_scrub_seam_integration_proof/seam_integration_mask.png`
- Manifest: `world3/textures/source_stack/gloss_scrub_seam_integration_proof/manifest.json`
- Runtime height: `world3/toporeview/gloss_mountain_seam_integration_proof/heightmap.png`
- Runtime meta: `world3/toporeview/gloss_mountain_seam_integration_proof/meta.json`
- Metrics: `world3/docs/captures/review/terrain_seam_integration_gloss_metrics.json`

Review scene:

- `world3/scenes/review/source_stack_seam_integration_tour.tscn`

Smoke captures:

- `world3/docs/captures/review/source_stack_seam_integration_tour_smoke.png`
- `world3/docs/captures/review/source_stack_seam_integration_tour_iso_smoke.png`
- `world3/docs/captures/review/source_stack_seam_integration_tour_3d_smoke.png`

## Metrics

Height overlap before solve:

- mean: `0.011 m`
- p95: `0.029 m`
- max: `0.283 m`

Height overlap after solve:

- mean: `0.007 m`
- p95: `0.024 m`
- max: `0.277 m`

Macro overlap delta:

- mean: `0.000`
- p95: `0.000`
- max: `0.000`

Valid coverage:

- left: `1.000`
- right: `0.9999`
- band: `1.000`
- output: `0.9999`

## Runtime Fix Found

The 3D verification exposed a `ChunkLoader.gd` edge case: source-footprint
clipping can legitimately produce empty chunks outside the valid terrain
footprint. `ChunkLoader.gd` now returns an empty mesh for zero-triangle chunks
and skips collision creation for empty meshes instead of submitting an invalid
surface to Godot.

## Visual Read

Pass for first-rung seam integration:

- no height wall;
- no ghost strip;
- no orthophoto box;
- no fake fallback plateau inside the valid footprint;
- topdown, iso, and close 3D all render the integrated band as continuous
  terrain.

Remaining caveats:

- finite-source footprint edges remain visible by design when clipping exposes
  missing data;
- the source macro still contains baked shadows, shrub/tree blobs, and
  orthophoto lighting variation;
- this is overlap-based same-source proof, not unlike-biome or non-overlap
  synthesis yet.

## Next Step

M10 should now move to the second rung:

1. run this same generator structure on two nearby non-overlap crops from the
   same source and measure how much height/profile correction is needed;
2. then run a real-to-real pair from different but compatible catalog sources;
3. only after those pass, promote to real-to-procedural and unlike-biome
   cross-source blending.
